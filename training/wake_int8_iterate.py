#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Select wake checkpoints by full native-Micro INT8 DEV, never float accuracy.

Fixed 3-score/.90 policy. Family and consumed TEST stay protected. Preparation
is cached once with input hashes. No downloads, paid requests, or board writes.
First completely qualified checkpoint is frozen; TEST is a separate action.
"""
import argparse
import ast
from collections import defaultdict
import fcntl
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

import numpy as np
from hi_pikoo_model import build, stream, sequence_loss, event_scores, policy_metrics
from hi_pikoo_train import example, features_and_times
from streaming_runtime import interpreter, quantize
from wake_negative_finetune import DEPLOYED_MODEL, windows, recall_preserved
from wake_playback_negatives import load_rows, read_pcm, sha


PROFILES = [
    {'name': 'refresh24', 'channels': 24, 'head': 32, 'initialization': 'baseline',
     'learning_rate': .0001, 'max_epochs': 12, 'seeds': [43, 42]},
    {'name': 'fresh48', 'channels': 48, 'head': 64, 'initialization': 'fresh',
     'learning_rate': .0005, 'max_epochs': 30, 'seeds': [42, 43]},
]
BALANCED_PROFILES = [
    {'name': 'balanced48-long', 'channels': 48, 'head': 64, 'context_steps': 72, 'initialization': 'fresh',
     'learning_rate': .0005, 'max_epochs': 30, 'seeds': [42, 43]},
    {'name': 'balanced48-short', 'channels': 48, 'head': 64, 'context_steps': 20, 'initialization': 'fresh',
     'learning_rate': .0005, 'max_epochs': 30, 'seeds': [42, 43]},
]


def write_json(path, value):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    temporary.replace(path)


def qualification(old, negative_false_clips, baseline):
    """Retain the old >=90% goal, not only the weaker installed baseline."""
    required = {g: max(v['hits'], math.ceil(v['targets']*.9))
                for g, v in baseline['groups'].items()}
    missing = sum(max(0, n-old['groups'][g]['hits']) for g, n in required.items())
    preserved = recall_preserved(baseline, old)
    passed = bool(old['passed'] and preserved and negative_false_clips == 0)
    # A silent classifier loses all positive requirements. This score only
    # ranks failed DEV checkpoints; hard qualification above is unchanged.
    score = -(missing+2*old['false_wakes']+2*old['early_wakes']+
              negative_false_clips)
    return {'qualified': passed, 'old_DEV_preserved': preserved,
            'intermediate_negative_gate_at_most_one': negative_false_clips <= 1,
            'required_group_hits': required, 'positive_shortfall': missing,
            'selection_score': float(1000+score if passed else score)}


def prepare(a):
    hashes = {name: sha(path) for name, path in [
        ('original_features', a.baseline/'features.npz'),
        ('original_provenance', a.baseline/'provenance.json'),
        ('negative_manifest', a.manifest), ('protected_registry', a.protected),
        ('preparation_code', Path(__file__))]}
    target = a.output/'prepared'
    if target.exists():
        saved = json.loads((target/'provenance.json').read_text())
        if saved['input_sha256'] != hashes:
            raise ValueError('Cached data inputs changed; use a new experiment directory')
        for name, digest in saved['prepared_sha256'].items():
            if sha(target/name) != digest:
                raise ValueError('Prepared array changed')
        return target
    rows = load_rows(a.manifest, a.protected)
    protected = set(json.loads(a.protected.read_text())['audio_sha256'].values())
    original_proof = json.loads((a.baseline/'provenance.json').read_text())
    if original_proof.get('household_used') is not False or original_proof.get('sealed_test_opened') is not False:
        raise ValueError('Original audited TRAIN/DEV provenance required')
    old_cases = json.loads((a.baseline/'context-20-seed-43/dev-cases.json').read_text())
    if any(c['sha256'] in protected for c in old_cases):
        raise ValueError('Protected old DEV')
    with np.load(a.baseline/'features.npz') as cache:
        x, y, w, vx = [cache[k] for k in ('train_x', 'train_y', 'train_w', 'dev_x')]
    groups = ['legacy-positive' if value else 'legacy-negative' for value in y.max(axis=1)>0]
    extras, negative_info, negative_features = [], [], {}
    for number, row in enumerate(rows):
        pcm = read_pcm(a.manifest.parent/row['path'])
        continuous, _ = features_and_times(np.pad(pcm, (16000, 16000)))
        if row['split'] == 'validation':
            key = f'case_{len(negative_info)}'
            negative_features[key] = continuous[:len(continuous)//3*3]
            negative_info.append({k: row[k] for k in ('sha256', 'source', 'category')})
            continue
        for offset, piece in windows(pcm):
            rng = np.random.default_rng(int(hashlib.sha256(
                f"{row['sha256']}:{offset}".encode()).hexdigest()[:8], 16))
            data, labels, weight, _ = example(piece, row, rng, augment=True)
            extras.append((data, labels, weight*4))
            groups.append(row['source'])
        for _, chunk in windows(continuous, length=600, stride=300):
            n = len(chunk)//3
            data = np.zeros((600, 40), np.float32)
            data[:n*3] = chunk[:n*3]
            weight = np.zeros(200, np.float32)
            weight[:n] = 4
            extras.append((data, np.zeros(200, np.float32), weight))
            groups.append(row['source'])
        if number % 250 == 0:
            print(json.dumps({'stage': 'prepare', 'source_records': number}), flush=True)
    target.mkdir()
    for name, values in [('train_x.npy', np.concatenate([x, np.asarray([e[0] for e in extras])])),
                         ('train_y.npy', np.concatenate([y, np.asarray([e[1] for e in extras])])),
                         ('train_w.npy', np.concatenate([w, np.asarray([e[2] for e in extras])])),
                         ('old_dev_x.npy', vx)]:
        np.save(target/name, values)
    (target/'train-groups.json').write_text(json.dumps(groups)+'\n')
    (target/'old-dev-cases.json').write_text(json.dumps(old_cases)+'\n')
    (target/'negative-dev-info.json').write_text(json.dumps(negative_info)+'\n')
    np.savez_compressed(target/'negative-dev-features.npz', **negative_features)
    files = [p for p in target.iterdir() if p.is_file()]
    write_json(target/'provenance.json', {'input_sha256': hashes,
        'prepared_sha256': {p.name: sha(p) for p in files},
        'train_examples': len(groups), 'old_DEV_cases': len(old_cases),
        'negative_DEV_cases': len(negative_info), 'household_used': False,
        'TEST_opened': False, 'calibration_split': 'TRAIN only'})
    return target


def reuse_prepared(a):
    """Reuse verified arrays after training-only code changes, without recaching."""
    target = a.reuse_prepared.resolve()
    saved = json.loads((target/'provenance.json').read_text())
    for name, path in [('original_features', a.baseline/'features.npz'),
                       ('original_provenance', a.baseline/'provenance.json'),
                       ('negative_manifest', a.manifest), ('protected_registry', a.protected)]:
        if saved['input_sha256'][name] != sha(path):
            raise ValueError('Prepared data inputs differ')
    source = target.parent/'source'
    original_code = (source/Path(__file__).name).read_text()
    if sha(source/Path(__file__).name) != saved['input_sha256']['preparation_code']:
        raise ValueError('Original preparation source changed')
    def body(text):
        function = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == 'prepare')
        return ast.get_source_segment(text, function)
    if body(original_code) != body(Path(__file__).read_text()):
        raise ValueError('Preparation semantics changed; old arrays cannot be reused')
    for name in ('hi_pikoo_model.py', 'hi_pikoo_train.py', 'wake_negative_finetune.py',
                 'wake_playback_negatives.py', 'streaming_runtime.py'):
        if sha(source/name) != sha(Path(__file__).with_name(name)):
            raise ValueError('Preparation dependency changed')
    for name, digest in saved['prepared_sha256'].items():
        if sha(target/name) != digest:
            raise ValueError('Prepared array changed')
    if saved['household_used'] is not False or saved['TEST_opened'] is not False:
        raise ValueError('Protected data in reused cache')
    return target


def balance_train_weights(labels, weights, negative_to_positive=3.):
    """Compute event balancing strictly from TRAIN; DEV cannot set the factor."""
    positive = labels > .5
    positive_mass = float(np.asarray(weights)[positive].sum())
    negative_mass = float(np.asarray(weights)[~positive].sum())
    if positive_mass <= 0 or negative_mass <= 0:
        raise ValueError('Both TRAIN event classes must have positive weight mass')
    factor = negative_mass/(negative_to_positive*positive_mass)
    if not 1 <= factor <= 8:
        raise ValueError('Unexpected TRAIN balance; do not silently amplify targets')
    balanced = np.array(weights, copy=True)
    balanced[positive] *= factor
    return balanced, {'positive_mass_before': positive_mass, 'negative_mass': negative_mass,
        'positive_factor': factor, 'negative_to_positive_mass_target': negative_to_positive,
        'scope': 'TRAIN temporal loss weights only; no threshold or DEV calibration change'}


def balance_positive_cohorts(labels, weights, metadata):
    """Equalize TRAIN positive-event cohorts; do not read DEV performance."""
    if len(metadata) > len(labels):
        raise ValueError('TRAIN metadata length mismatch')
    if any(bool(labels[i].max() > .5) != bool(row['label']) for i, row in enumerate(metadata)):
        raise ValueError('TRAIN labels do not match reconstructed source ordering')
    if np.any(labels[len(metadata):] > .5):
        raise ValueError('Unmapped positive TRAIN example')
    indexes = defaultdict(list)
    for i, row in enumerate(metadata):
        if row['label']:
            indexes[row['cohort']].append(i)
    if len(indexes) != 6:
        raise ValueError('All six declared positive TRAIN cohorts required')
    masses = {group: sum(float(weights[i][labels[i] > .5].sum()) for i in part)
              for group, part in indexes.items()}
    mean = sum(masses.values())/len(masses)
    balanced = np.array(weights, copy=True)
    factors = {}
    for group, part in indexes.items():
        factor = mean/masses[group]
        if not .25 <= factor <= 8:
            raise ValueError('Unexpected TRAIN cohort imbalance')
        factors[group] = factor
        for i in part:
            balanced[i, labels[i] > .5] *= factor
    return balanced, {'cohort_event_mass_before': masses, 'factors': factors,
        'scope': 'TRAIN original source metadata and event mass only; no DEV weighting'}


def load_profiles(path):
    profiles = json.loads(path.read_text())
    if not isinstance(profiles, list) or not 1 <= len(profiles) <= 6:
        raise ValueError('A bounded profile list is required')
    for profile in profiles:
        if (not re.fullmatch('[a-z0-9_-]+', profile['name']) or
            profile['channels'] not in (24, 48, 96) or profile['head'] not in (32, 64) or
            profile.get('context_steps', 20) not in (20, 72) or
            profile.get('auxiliary_phrase_weight', 0) not in (0, .2, .5) or
            profile.get('weight_decay', 0) not in (0, .01) or
            ('encoder_frozen' in profile and
             (type(profile['encoder_frozen']) is not bool or profile['initialization'] != 'phone-encoder')) or
            profile['initialization'] not in ('fresh', 'baseline', 'checkpoint', 'phone-encoder') or
            not .00001 <= profile['learning_rate'] <= .001 or
            not 1 <= profile['max_epochs'] <= 30 or sorted(profile['seeds']) != [42, 43]):
            raise ValueError('Profile outside declared architecture/training bounds')
    if len({p['name'] for p in profiles}) != len(profiles):
        raise ValueError('Duplicate profile name')
    for profile in profiles:
        if profile.get('required_secondary_negative_dev'):
            from wake_secondary_dev import load
            load(profile['required_secondary_negative_dev'])
    return profiles


def optimizer_spec(profile, clipnorm=False):
    decay = profile.get('weight_decay', 0)
    if decay not in (0, .01):
        raise ValueError('Only the declared zero/.01 weight-decay comparison is eligible')
    options = {'learning_rate': profile['learning_rate']}
    if clipnorm:
        options['global_clipnorm'] = 1.
    if decay:
        options['weight_decay'] = decay
    return ('AdamW' if decay else 'Adam'), options


def set_encoder_trainability(encoder, batch_norm_type, frozen=False):
    """Freeze the shared public-speech encoder without freezing the wake head."""
    for layer in encoder.layers:
        if frozen or isinstance(layer, batch_norm_type):
            layer.trainable = False
    return {'encoder_frozen': bool(frozen),
            'encoder_layers': len(encoder.layers),
            'encoder_trainable_layers': sum(bool(layer.trainable) for layer in encoder.layers)}


class NativeEvaluator:
    def __init__(self, micro):
        self.micro = micro.resolve()

    def configure(self, model):
        self.model = model.resolve()
        engine = interpreter(model)
        engine.allocate_tensors()
        inp, out = engine.get_input_details()[0], engine.get_output_details()[0]
        if list(inp['shape']) != [1, 3, 40] or inp['dtype'] != np.int8 or out['dtype'] != np.uint8 or int(np.prod(out['shape'])) != 1:
            raise ValueError('Streaming ABI mismatch')
        self.input_quant, self.output_quant = inp['quantization'], out['quantization']

    def run(self, data, temporary):
        n = len(data)//3
        fixture, trace = temporary/'input.int8', temporary/'output.uint8'
        fixture.write_bytes(quantize(data[:n*3], *self.input_quant).tobytes())
        result = subprocess.run([str(self.micro), str(self.model), str(fixture),
            '--trace-output', str(trace)], check=True, capture_output=True, text=True)
        proof = json.loads(result.stdout.strip().splitlines()[-1])
        raw = np.frombuffer(trace.read_bytes(), np.uint8).reshape(3, n)
        if not np.array_equal(raw, np.tile(raw[0], (3, 1))):
            raise ValueError('Native reset replay differs')
        scale, zero = self.output_quant
        return (raw[0].astype(float)-zero)*scale, proof['host_arena_used_bytes']


def export_and_evaluate(model, folder, representative, evaluator, vx, old_info, new_features, baseline,
                        content_review=None, tempo_data=None):
    import tensorflow as tf
    begin = time.monotonic()
    deploy = stream(model)
    archive = tf.keras.export.ExportArchive()
    archive.track(deploy)
    archive.add_endpoint(name='serve', fn=deploy.call,
                        input_signature=[tf.TensorSpec(deploy.input.shape, tf.float32)])
    archive.write_out(str(folder/'saved'), verbose=False)
    converter = tf.lite.TFLiteConverter.from_saved_model(str(folder/'saved'))
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter._experimental_variable_quantization = True
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type, converter.inference_output_type = tf.int8, tf.uint8
    converter.representative_dataset = lambda: ([data[None, i:i+3]]
        for data in representative for i in range(0, len(data)-2, 3))
    binary = folder/'hi_pikoo.tflite'
    binary.write_bytes(converter.convert())
    from check_esp32_model import check
    static = check(binary, Path(__file__).parents[1]/'firmware/main/wake_model.cpp', 524288)
    evaluator.configure(binary)
    cases, negatives, arena = [], [], 0
    with tempfile.TemporaryDirectory(dir=folder) as temporary:
        temporary = Path(temporary)
        for data, meta in zip(vx, old_info):
            probabilities, used = evaluator.run(data[:meta['valid_steps']*3], temporary)
            cases.append({**meta, 'probabilities': probabilities.tolist()})
            arena = max(arena, used)
        for features in new_features:
            probabilities, used = evaluator.run(features, temporary)
            scores = event_scores(probabilities, 3)
            negatives.append({'activated': bool(np.any(scores >= np.float32(.9))),
                              'peak': float(max(scores, default=0))})
            arena = max(arena, used)
    old = policy_metrics(cases, 3, .9)
    false = sum(n['activated'] for n in negatives)
    quality = qualification(old, false, baseline)
    reviewed = None
    if content_review is not None:
        from wake_dev_content_review import reviewed_cohorts
        reviewed = policy_metrics(reviewed_cohorts(cases, content_review), 3, .9)
        reviewed_baseline = policy_metrics(reviewed_cohorts(old_info, content_review), 3, .9)
        reviewed_quality = qualification(reviewed, false, reviewed_baseline)
        quality['qualified'] = quality['qualified'] and reviewed_quality['qualified']
        quality['selection_score'] = min(quality['selection_score'], reviewed_quality['selection_score'])
        quality['positive_shortfall'] = max(quality['positive_shortfall'], reviewed_quality['positive_shortfall'])
        quality['reviewed_DEV_required_group_hits'] = reviewed_quality['required_group_hits']
    positive_confidence = []
    for case in cases:
        if case['label']:
            times = np.asarray(case['times_ms'])
            scores = event_scores(case['probabilities'], 3)
            valid = scores[(times >= case['completion_ms']-120) & (times <= case['completion_ms']+800)]
            positive_confidence.append(float(max(valid, default=0)))
    # Tie-break with actual INT8 confidence, never a replacement for hard gates.
    tie_break = .001*(float(np.mean(positive_confidence))-
                     float(np.mean([n['peak']**2 for n in negatives])))
    quality['selection_score'] += tie_break
    quality['INT8_confidence_tie_break'] = tie_break
    tempo = None
    if tempo_data is not None:
        from wake_tempo import evaluate, apply_gate
        with tempfile.TemporaryDirectory(dir=folder) as temporary:
            tempo = evaluate(evaluator, tempo_data, Path(temporary), folder, content_review)
        quality = apply_gate(quality, tempo)
    report = {'old_DEV': old, 'new_negative_DEV_false_clips': false,
        'new_negative_DEV_cases': len(negatives), **quality,
        'static': static, 'host_arena_bytes': arena,
        'native_reset_replays': 3, 'micro_sha256': sha(evaluator.micro),
        'backend': 'pinned native TFLite Micro', 'threshold': .9, 'rolling': 3,
        'elapsed_seconds': time.monotonic()-begin,
        'household_used': False, 'TEST_opened': False, 'device_accepted': False}
    if reviewed is not None:
        report['reviewed_DEV'] = reviewed
        report['reviewed_DEV_gate_passed'] = reviewed_quality['qualified']
    if tempo is not None:
        report['tempo_DEV'] = tempo
    write_json(folder/'evaluation.json', report)
    (folder/'old-dev-cases.json').write_text(json.dumps(cases)+'\n')
    write_json(folder/'negative-dev-scores.json', negatives)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'manifest', 'protected', 'upstream', 'micro', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--reuse-prepared', type=Path)
    parser.add_argument('--balanced', action='store_true')
    parser.add_argument('--cohort-meta', type=Path)
    parser.add_argument('--profiles', type=Path)
    parser.add_argument('--phrase-events', type=Path,
                        help='Exact original TRAIN array replay metadata for an auxiliary-only phrase head')
    parser.add_argument('--train-admission', type=Path,
                        help='Complete independent TRAIN content audit; quarantine uncertain originals and descendants')
    parser.add_argument('--phrase-boundaries', action='store_true',
                        help='Fixed 4x TRAIN loss on incomplete target prefixes and competitor endings')
    parser.add_argument('--extra-train-manifest', type=Path)
    parser.add_argument('--extra-train-review', type=Path)
    parser.add_argument('--base-admitted-manifest', type=Path)
    parser.add_argument('--dev-content-review', type=Path,
                        help='Independent human-heard vowels add a second gate without replacing historical DEV')
    parser.add_argument('--tempo-config', type=Path,
                        help='Bounded pitch-preserving faster TRAIN augmentation and separate reused-DEV gate')
    parser.add_argument('--reuse-tempo', type=Path, help='Verified tempo preparation cache only')
    parser.add_argument('--preserve-dev-cases', type=Path, help='Current-candidate native DEV trace preservation floor')
    parser.add_argument('--preserve-dev-evaluation', type=Path)
    a = parser.parse_args()
    os.umask(0o077)
    a.output.mkdir(parents=True, exist_ok=True)
    lock = (a.output/'job.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if (a.output/'frozen.json').exists():
        raise ValueError('Candidate frozen; no further selection or training in this run')
    revision = subprocess.check_output(['git', '-C', str(a.upstream), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != '4665173cd35f1cff9a61e06fc427f124766c488e' or subprocess.check_output(
            ['git', '-C', str(a.upstream), 'status', '--porcelain'], text=True).strip():
        raise ValueError('Pinned clean upstream required')
    runtime = {name: version(name) for name in ('tensorflow', 'numpy', 'pymicro-features')}
    if runtime != {'tensorflow': '2.18.1', 'numpy': '2.0.2', 'pymicro-features': '2.0.2'}:
        raise ValueError('Pinned runtime required')
    if sha(a.baseline/'context-20-seed-43/hi_pikoo.tflite') != DEPLOYED_MODEL:
        raise ValueError('Baseline model differs')
    write_json(a.output/'status.json', {'stage': 'preparing', 'pid': os.getpid(), 'goal_completed': False})
    prepared = reuse_prepared(a) if a.reuse_prepared else prepare(a)
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(4)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    x, y, w, vx = [np.load(prepared/name, mmap_mode='r') for name in
                   ('train_x.npy', 'train_y.npy', 'train_w.npy', 'old_dev_x.npy')]
    metadata = json.loads(a.cohort_meta.read_text()) if a.cohort_meta else None
    original_metadata = metadata
    keep, admission_summary = None, None
    if a.train_admission:
        if metadata is None:
            raise ValueError('TRAIN admission needs verified original source metadata')
        from wake_train_admission import retained_indices
        admission = json.loads(a.train_admission.read_text())
        if admission['original_manifest_sha256'] != json.loads((a.baseline/'provenance.json').read_text())['manifest_sha256']:
            raise ValueError('TRAIN admission belongs to another original corpus')
        keep, metadata, admission_summary = retained_indices(admission, metadata, len(x))
        x, y, w = x[keep], y[keep], w[keep]
    profiles = load_profiles(a.profiles) if a.profiles else BALANCED_PROFILES if a.balanced else PROFILES
    needs_auxiliary = any(p.get('auxiliary_phrase_weight', 0) for p in profiles)
    events = None
    if needs_auxiliary or a.phrase_boundaries or a.extra_train_manifest or a.tempo_config:
        if not a.phrase_events:
            raise ValueError('Verified TRAIN phrase events required for phrase supervision')
        events = json.loads(a.phrase_events.read_text())
        if (events['proof']['original_features_sha256'] != sha(a.baseline/'features.npz') or
                events['proof']['protected_sha256'] != sha(a.protected)):
            raise ValueError('Auxiliary metadata belongs to a different original TRAIN cache')
        if keep is not None:
            from wake_train_admission import subset_phrase_events
            events = subset_phrase_events(events, original_metadata, keep)
    groups = json.loads((prepared/'train-groups.json').read_text())
    if keep is not None:
        groups = [groups[i] for i in keep]
    extra_summary = None
    if a.extra_train_manifest:
        if not a.extra_train_review or not a.base_admitted_manifest or metadata is None:
            raise ValueError('Extra TRAIN needs its independent review and original admitted source metadata')
        from wake_extra_train import append
        original_manifest_sha = json.loads((a.baseline/'provenance.json').read_text())['manifest_sha256']
        x, y, w, metadata, events, groups, extra_summary = append(x, y, w, metadata, events, groups,
            a.extra_train_manifest, a.extra_train_review, a.base_admitted_manifest,
            original_manifest_sha, a.protected, a.output)
    tempo_summary, tempo_data = None, None
    if a.tempo_config:
        if metadata is None or events is None or not a.base_admitted_manifest or not a.train_admission:
            raise ValueError('Tempo experiment needs complete admitted TRAIN lineage and events')
        if len(metadata) != len(x) or len(events['records']) != len(x):
            raise ValueError('Complete TRAIN metadata required before tempo augmentation')
        from wake_tempo import prepare as prepare_tempo
        x, y, w, metadata, events, groups, tempo_summary, tempo_data = prepare_tempo(
            x, y, w, metadata, events, groups, a.base_admitted_manifest,
            a.extra_train_manifest, a.protected, a.tempo_config, a.output, reuse=a.reuse_tempo)
    boundary_summary = None
    if a.phrase_boundaries:
        from wake_phrase_boundaries import emphasize
        w, boundary_summary = emphasize(events, y, w)
    balance, cohort_balance = None, None
    if a.cohort_meta:
        w, cohort_balance = balance_positive_cohorts(y, w, metadata)
    if a.balanced:
        w, balance = balance_train_weights(y, w)
    auxiliary = None
    auxiliary_summary = None
    if needs_auxiliary:
        from wake_phrase_auxiliary import training_targets
        ay, aw, auxiliary_summary = training_targets(events, y, w)
        auxiliary = ay, aw
    old_info = json.loads((prepared/'old-dev-cases.json').read_text())
    preservation = None
    if a.preserve_dev_cases:
        if not a.preserve_dev_evaluation or not a.tempo_config:
            raise ValueError('Preservation floor requires declared tempo donor proof')
        from wake_tempo import preservation_cases
        donor_proof = json.loads(a.preserve_dev_evaluation.read_text())
        config = json.loads(a.tempo_config.read_text())
        if donor_proof['static']['sha256'] != config['baseline_model_sha256']:
            raise ValueError('Preservation proof belongs to another model')
        old_info = preservation_cases(old_info, json.loads(a.preserve_dev_cases.read_text()), donor_proof)
        preservation = {'cases_sha256': sha(a.preserve_dev_cases), 'evaluation_sha256': sha(a.preserve_dev_evaluation),
            'baseline_model_sha256': config['baseline_model_sha256']}
        shutil.copyfile(a.preserve_dev_cases, a.output/'preservation-dev-cases.json')
        shutil.copyfile(a.preserve_dev_evaluation, a.output/'preservation-dev-evaluation.json')
    content_review = json.loads(a.dev_content_review.read_text()) if a.dev_content_review else None
    if content_review is not None:
        from wake_dev_content_review import reviewed_cohorts
        if content_review['original_manifest_sha256'] != json.loads((a.baseline/'provenance.json').read_text())['manifest_sha256']:
            raise ValueError('DEV content review belongs to another original corpus')
        reviewed_cohorts(old_info, content_review)
    baseline = policy_metrics(old_info, 3, .9)
    with np.load(prepared/'negative-dev-features.npz') as data:
        negative_features = [data[f'case_{i}'] for i in range(len(data.files))]
    indices = defaultdict(list)
    for i, group in enumerate(groups):
        indices[group].append(i)
    selected = []
    if a.cohort_meta:
        positive_cohorts = defaultdict(list)
        for index, row in enumerate(metadata):
            if row['label']:
                positive_cohorts[row['cohort']].append(index)
        for part in positive_cohorts.values():
            selected.extend(part[i] for i in np.linspace(0, len(part)-1, min(8, len(part))).astype(int))
    for group, count in [('legacy-positive', 40), ('legacy-negative', 20),
                         ('ChildMandarin', 12), ('LibriSpeech-train.100', 16), ('ESC-50', 12)]:
        if a.cohort_meta and group == 'legacy-positive':
            continue
        part = indices[group]
        selected.extend(part[i] for i in np.linspace(0, len(part)-1, min(count, len(part))).astype(int))
    representative = [x[i, :(int(np.flatnonzero(w[i] > 0)[-1])+1)*3].copy() for i in selected]
    write_json(a.output/'plan.json', {'profiles': profiles, 'runtime': runtime,
        'TRAIN_event_balance': balance,
        'TRAIN_positive_cohort_balance': cohort_balance,
        'TRAIN_auxiliary_phrase': auxiliary_summary,
        'TRAIN_phrase_boundaries': boundary_summary,
        'TRAIN_extra_sources': extra_summary,
        'pitch_preserving_tempo': tempo_summary,
        'current_candidate_DEV_preservation': preservation,
        'TRAIN_effective_examples': len(x),
        'TRAIN_content_admission': admission_summary,
        'TRAIN_admission_sha256': sha(a.train_admission) if a.train_admission else None,
        'retained_original_TRAIN_indices': keep.tolist() if keep is not None else None,
        'TRAIN_phrase_events_sha256': sha(a.phrase_events) if a.phrase_events else None,
        'TRAIN_cohort_metadata_sha256': sha(a.cohort_meta) if a.cohort_meta else None,
        'optimizer_global_clipnorm': 1. if a.cohort_meta else None,
        'formal_negative_DEV_requirement': 0,
        'prepared_provenance_sha256': sha(prepared/'provenance.json'),
        'representative_TRAIN_indices': selected, 'calibration_uses_DEV': False,
        'selection_rule': 'first full native INT8 qualification, then freeze; no TEST model choice',
        'household_used': False, 'threshold': .9, 'rolling': 3,
        'DEV_content_review_sha256': sha(a.dev_content_review) if a.dev_content_review else None})
    snapshot = a.output/'source'
    names = ('wake_int8_iterate.py', 'hi_pikoo_model.py', 'hi_pikoo_train.py',
             'wake_negative_finetune.py', 'wake_playback_negatives.py', 'streaming_runtime.py',
             'wake_phrase_auxiliary.py', 'wake_train_events.py', 'hi_pikoo_contrast.py',
             'hi_pikoo_timing.py', 'acoustic_augment.py', 'wake_train_admission.py',
             'wake_phrase_boundaries.py', 'wake_extra_train.py', 'wake_catalog_train.py',
             'hi_pikoo_review.py', 'wake_dev_content_review.py', 'wake_train_human_review.py', 'wake_tempo.py',
             'wake_secondary_dev.py')
    if snapshot.exists() and any((snapshot/name).exists() and
            sha(snapshot/name) != sha(Path(__file__).with_name(name)) for name in names):
        snapshot = a.output/f'source-continuation-{sha(Path(__file__))[:16]}'
    snapshot.mkdir(exist_ok=True)
    for name in names:
        if not (snapshot/name).exists():
            shutil.copyfile(Path(__file__).with_name(name), snapshot/name)
    evaluator = NativeEvaluator(a.micro)
    if a.tempo_config:
        from wake_tempo import evaluate as evaluate_tempo
        config = json.loads(a.tempo_config.read_text())
        donor = Path(config['baseline_model'])
        if sha(donor) != config['baseline_model_sha256']:
            raise ValueError('Tempo comparison baseline changed')
        baseline_folder = a.output/'tempo-baseline'
        baseline_folder.mkdir(exist_ok=False)
        evaluator.configure(donor)
        with tempfile.TemporaryDirectory(dir=baseline_folder) as temporary:
            tempo_baseline = evaluate_tempo(evaluator, tempo_data, Path(temporary), baseline_folder, content_review)
        write_json(baseline_folder/'evaluation.json', tempo_baseline)
    all_results = []
    for profile in profiles:
        for seed in profile['seeds']:
            folder = a.output/f"{profile['name']}-seed-{seed}"
            if (folder/'completed.json').exists():
                all_results.append(json.loads((folder/'completed.json').read_text())['best'])
                continue
            folder.mkdir(exist_ok=False)
            model = build(a.upstream, profile.get('context_steps', 20), seed,
                          profile['channels'], profile.get('batch_normalization', False), head_units=profile['head'])
            if profile['initialization'] == 'baseline':
                model.load_weights(a.baseline/'context-20-seed-43/checkpoint.weights.h5')
            elif profile['initialization'] == 'checkpoint':
                initial = Path(profile['checkpoint'])
                proof = json.loads((initial.parent/'evaluation.json').read_text())
                if proof['household_used'] is not False or proof['TEST_opened'] is not False:
                    raise ValueError('Protected donor checkpoint')
                model.load_weights(initial)
                write_json(folder/'initialization.json', {'kind': 'continued-known-TRAIN-DEV-checkpoint',
                    'checkpoint_sha256': sha(initial), 'donor_evaluation_sha256': sha(initial.parent/'evaluation.json')})
            elif profile['initialization'] == 'phone-encoder':
                initial, report = Path(profile['encoder']), Path(profile['encoder_report'])
                proof = json.loads(report.read_text())
                if (proof.get('status') != 'phone-pretraining-complete-not-wake-acceptance' or
                    proof.get('channels') != profile['channels'] or not profile.get('batch_normalization') or
                    proof.get('encoder_sha256') != sha(initial) or proof.get('household_used') is not False or
                    proof.get('official_validation_or_test_used') is not False or proof.get('source_weights') is not None or
                    proof.get('encoder_hook') != 'ordered_context.input' or proof.get('phone_error_rate', 1) > .8):
                    raise ValueError('Phonetic encoder provenance/quality does not match')
                encoder = tf.keras.Model(model.input, model.get_layer('ordered_context').input)
                encoder.load_weights(initial)
                trainability = set_encoder_trainability(encoder, tf.keras.layers.BatchNormalization,
                                                       frozen=profile.get('encoder_frozen', False))
                write_json(folder/'initialization.json', {'kind': 'public-TRAIN-only-phonetic-encoder',
                    'encoder_sha256': sha(initial), 'report_sha256': sha(report),
                    'source_phone_error_rate': proof['phone_error_rate'], **trainability})
            optimizer_name, optimizer_options = optimizer_spec(profile, clipnorm=bool(a.cohort_meta))
            optimizer = getattr(tf.keras.optimizers, optimizer_name)(**optimizer_options)
            if profile.get('auxiliary_phrase_weight', 0):
                from wake_phrase_auxiliary import attach
                training_model = attach(model)
                training_model.compile(optimizer=optimizer,
                    loss={'wake': sequence_loss, 'phrase': tf.keras.losses.SparseCategoricalCrossentropy()},
                    loss_weights={'wake': 1., 'phrase': profile['auxiliary_phrase_weight']})
                fit_labels = {'wake': y, 'phrase': auxiliary[0]}
                fit_weights = {'wake': w, 'phrase': auxiliary[1]}
            else:
                training_model = model
                model.compile(optimizer=optimizer, loss=sequence_loss)
                fit_labels, fit_weights = y, w
            history, best = [], [None]

            class NativeQuality(tf.keras.callbacks.Callback):
                def on_epoch_end(self, epoch, logs=None):
                    checkpoint = folder/f'epoch-{epoch+1:02}'
                    checkpoint.mkdir()
                    model.save_weights(checkpoint/'checkpoint.weights.h5')
                    result = export_and_evaluate(model, checkpoint, representative,
                        evaluator, vx, old_info, negative_features, baseline, content_review=content_review,
                        tempo_data=tempo_data)
                    result.update(epoch=epoch+1, profile=profile['name'], seed=seed)
                    history.append(result)
                    logs['val_native_quality'] = result['selection_score']
                    if best[0] is None or result['selection_score'] > best[0]['selection_score']:
                        best[0] = result
                    write_json(folder/'epochs.json', history)
                    write_json(a.output/'status.json', {'stage': 'INT8-evaluated', 'pid': os.getpid(),
                        'profile': profile['name'], 'seed': seed, 'epoch': epoch+1,
                        'negative_DEV_false_clips': result['new_negative_DEV_false_clips'],
                        'positive_shortfall': result['positive_shortfall'],
                        'qualified': result['qualified'], 'goal_completed': False})
                    print(json.dumps({'profile': profile['name'], 'seed': seed, 'epoch': epoch+1,
                        'new_false': result['new_negative_DEV_false_clips'],
                        'positive_shortfall': result['positive_shortfall'],
                        'old_false': result['old_DEV']['false_wakes'],
                        'early': result['old_DEV']['early_wakes'], 'qualified': result['qualified']}), flush=True)
                    if result['qualified']:
                        write_json(a.output/'frozen.json', {'checkpoint': str(checkpoint.relative_to(a.output)),
                            'model_sha256': sha(checkpoint/'hi_pikoo.tflite'), 'policy': {'rolling': 3, 'threshold': .9},
                            'secondary_DEV_pending': bool(profile.get('required_secondary_negative_dev')),
                            'evaluation': result, 'TEST_opened': False, 'device_accepted': False,
                            'goal_completed': False})
                        self.model.stop_training = True

            training_model.fit(x, fit_labels, sample_weight=fit_weights,
                epochs=profile['max_epochs'], batch_size=16,
                callbacks=[NativeQuality(), tf.keras.callbacks.EarlyStopping(
                    monitor='val_native_quality', mode='max', patience=6, start_from_epoch=12),
                    tf.keras.callbacks.CSVLogger(str(folder/'training.csv'))], verbose=2)
            write_json(folder/'completed.json', {'profile': profile, 'seed': seed, 'best': best[0],
                                                'epochs': len(history), 'device_changed': False})
            all_results.append(best[0])
            write_json(a.output/'comparison.json', all_results)
            tf.keras.backend.clear_session()
            if (a.output/'frozen.json').exists():
                stage = ('candidate-numerically-frozen-awaiting-secondary-DEV' if
                         profile.get('required_secondary_negative_dev') else 'candidate-frozen-awaiting-independent-TEST')
                write_json(a.output/'status.json', {'stage': stage,
                    'goal_completed': False, 'device_changed': False})
                return
    write_json(a.output/'status.json', {'stage': 'finite-INT8-comparison-completed-no-qualification',
        'goal_completed': False, 'device_changed': False})


if __name__ == '__main__':
    main()
