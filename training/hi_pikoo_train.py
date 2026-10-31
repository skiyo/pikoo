#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Finite from-scratch Hi Pikoo comparison. Requires explicitly admitted data.

Never admits TTS by prompt/transcript alone, opens a sealed test, downloads a
model, uploads recordings, changes a device, or retries a failed experiment.
"""
import argparse
import csv
import hashlib
from importlib.metadata import version
import json
import os
import sys
import subprocess
import shutil
import wave
from pathlib import Path
import numpy as np
from hi_pikoo_contract import validate_contract
from hi_pikoo_review import normalized
from hi_pikoo_timing import timing, view
from hi_pikoo_contrast import family
from hi_pikoo_model import FRAMES, SEEDS, build, stream, select_policy, sequence_loss, selection_proxy


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read_audio(p):
    with wave.open(str(p)) as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2 or w.getframerate() not in (16000, 24000):
            raise ValueError('Expected original 16/24kHz mono PCM16')
        rate = w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float32)
    if rate != 16000:
        from generate_google import resample
        pcm = resample(pcm, rate).astype(np.float32)
    return pcm


def admit(rows, root, protected):
    """Fail closed before loading any corpus; tests/household stay inaccessible."""
    speakers, hashes = {}, {}
    selected = []
    for row in rows:
        if row.get('evaluation_only') or row.get('frozen_holdout') or row.get('family_inputs_used') or row.get('reference_audio_used'):
            raise ValueError('Protected recording metadata in training manifest')
        if row['split'] == 'test':
            raise ValueError('Sealed TEST must not be present in a training invocation')
        if row['split'] not in ('train', 'validation'):
            raise ValueError('Unknown split')
        if not row.get('admitted_to_training') or row.get('content_review') != 'passed' or row.get('pronunciation_review') != 'passed':
            raise ValueError('Content and independent pronunciation admission required')
        if row.get('source') not in {'OpenAI-Realtime-synthetic', 'Qwen3-TTS-hi-piku-synthetic-local'} or not row.get('synthetic') or row.get('real_child'):
            raise ValueError('New original fictional corpus required')
        if row.get('perceived_style') not in {'adult', 'childlike'} or row.get('perceived_style_review') != 'passed':
            raise ValueError('Requested voice age cannot stand in for perceived-style review')
        if row.get('synthetic_style') != row['perceived_style']:
            raise ValueError('Training cohort must use reviewed perceived style')
        if row.get('parent_sha256') or row.get('ancestry_parents'):
            raise ValueError('New source manifest must contain originals only')
        speaker, sha = row['speaker'], row['sha256']
        if sha in protected:
            raise ValueError('Protected waveform hash')
        if speakers.setdefault(speaker, row['split']) != row['split'] or hashes.setdefault(sha, row['split']) != row['split']:
            raise ValueError('Speaker/recording leakage')
        p = (root/row['path']).resolve()
        if not p.is_relative_to(root.resolve()) or digest(p) != sha:
            raise ValueError('Source waveform path/hash mismatch')
        selected.append((row, p))
    for split in ('train', 'validation'):
        if {r['label'] for r, _ in selected if r['split'] == split} != {0, 1}:
            raise ValueError('Both classes required in complete TRAIN and DEV')
        negatives = {normalized(r['text']) for r, _ in selected if r['split'] == split and not r['label']}
        if not negatives & {'pikoo', 'piko'} or 'hi' not in negatives or not negatives & {'hitikoo', 'hitiko'}:
            raise ValueError('Name-alone, Hi-alone and T-confusable negatives required in both TRAIN and DEV')
    return selected


def background_rows(manifest, protected):
    rows = json.loads(manifest.read_text())
    seen, speakers, result = set(), {}, []
    for row in sorted(rows, key=lambda x: x['sha256']):
        if row.get('source') not in ('ChildMandarin', 'PolyAI-MInDS14-zh-CN'):
            continue
        if row['split'] != 'train' or row['label'] != 0 or row.get('evaluation_only') or row.get('frozen_holdout'):
            raise ValueError('Background must be original authorized TRAIN negatives')
        if row['source'] == 'ChildMandarin' and not row.get('original_full_utterance'):
            raise ValueError('Do not align cropped child audio with original transcripts')
        if row.get('parent_sha256') or row['sha256'] in protected:
            raise ValueError('Protected/derived background audio')
        if row['sha256'] in seen:
            continue
        speaker = row.get('speaker', row.get('group', 'unknown'))
        # Bounded stratified background pool, no huge negative majority.
        if speakers.get(speaker, 0) >= (4 if row['source'] == 'ChildMandarin' else 200):
            continue
        p = (manifest.parent/row['path']).resolve()
        if digest(p) != row['sha256']:
            raise ValueError('Background waveform hash mismatch')
        result.append((row, p))
        seen.add(row['sha256'])
        speakers[speaker] = speakers.get(speaker, 0)+1
    return result


def features_and_times(pcm):
    from pymicro_features import MicroFrontend
    frontend, specs, times = MicroFrontend(), [], []
    pcm = np.asarray(np.clip(pcm, -32768, 32767), '<i2')
    for start in range(0, len(pcm)-159, 160):
        result = frontend.process_samples(pcm[start:start+160].tobytes())
        if result.features:
            specs.append(result.features)
            times.append((start+160)/16)
    return np.asarray(specs, np.float32), np.asarray(times, np.float32)


def speech_endpoint(pcm):
    """Conservative synthetic-audio endpoint, independent of labels/model scores.

    Retain the entire waveform. Exclude only measured quiet tail from the
    event clock: 20ms RMS, about 26dB below peak or five PCM units, plus 40ms guard.
    This is not a phoneme aligner and is not used to repair truncated speech.
    """
    return timing(pcm)['endpoint_sample']


def example(pcm, row, rng, augment=False, background_pcm=None):
    x = pcm.copy()
    source_timing = None
    if row.get('synthetic'):
        x, source_timing = view(x)
        endpoint = source_timing['endpoint_sample']-source_timing['view_start_sample']
    else:
        endpoint = speech_endpoint(x) if row['label'] else len(x)
    if row['label'] and len(x) > 56000:
        raise ValueError('Positive waveform too long; review instead of trimming')
    if len(x) > 64000:
        if row['label']:
            raise ValueError('Cannot crop a positive')
        start = int(rng.integers(0, len(x)-64000+1)) if augment else 0
        x = x[start:start+64000]
    if augment:
        factor = float(rng.uniform(.9, 1.1))
        x = np.interp(np.arange(0, len(x), factor), np.arange(len(x)), x)
        endpoint = min(len(x), endpoint/factor)
        from acoustic_augment import augment as room
        x = room(x, rng)
        # Slowdown can expand a four-second ordinary negative past the six-
        # second feature envelope once lead/tail are added. Bound negatives
        # after augmentation too; complete positive utterances stay untouched.
        if not row['label'] and len(x) > 64000:
            start = int(rng.integers(0, len(x)-64000+1))
            x = x[start:start+64000]
    lead = int(rng.uniform(.3, 1.0)*16000)
    tail = int(rng.uniform(.6, 1.0)*16000)
    completion = (lead+endpoint)/16
    audio = np.pad(x, (lead, tail))
    if augment:
        audio += rng.normal(0, rng.uniform(1, 30), len(audio))
        if background_pcm is not None and lead:
            # Ordinary authorized TRAIN speech warms frontend/model state.
            # Apply to both labels; never splice words into a positive phrase.
            bg = np.resize(np.asarray(background_pcm, np.float32), lead)
            scale = max(30., float(np.sqrt(np.mean(x*x)))) / max(1., float(np.sqrt(np.mean(bg*bg))))
            audio[:lead] += bg*scale*float(rng.uniform(.15, .8))
    spec, times = features_and_times(audio)
    if len(spec) > FRAMES:
        raise ValueError('Complete utterance does not fit; never silently crop targets')
    n = len(spec)//3
    batch = np.zeros((FRAMES, 40), np.float32)
    batch[:n*3] = spec[:n*3]
    times = times[2:n*3:3]
    labels, weights = np.zeros(FRAMES//3, np.float32), np.zeros(FRAMES//3, np.float32)
    weights[:n] = 1
    # Hard TRAIN/DEV negatives must not disappear in the many ordinary public
    # negatives. This fixed category weight does not inspect model failures or
    # family audio; the whole ordinary/public background remains weight one.
    if not row['label'] and row.get('synthetic'):
        weights[:n] *= 4
    if row['label']:
        labels[:n] = ((times >= completion) & (times <= completion+300)).astype(np.float32)
        # Unknown phonetic endpoint near waveform end: ignore, do not label prefix positive.
        weights[:n][(times >= completion-120) & (times < completion)] = 0
        weights[:n][(times > completion+300) & (times < completion+600)] = 0
        weights[labels > 0] *= 12
    return batch, labels, weights, {'label': row['label'],
        'cohort': row.get('synthetic_style', 'ordinary')+':'+row.get('accent', 'public')+':'+row.get('pronunciation_variant', 'ordinary'),
        'perceived_gender': row.get('perceived_gender', 'unverified'),
        'completion_ms': completion, 'times_ms': times.tolist(),
        'endpoint_method': 'synthetic-RMS20ms-peakMinus26dB-plus40ms-guard',
        'valid_steps': n, 'sha256': row['sha256'], 'source_timing': source_timing,
        'contrast_class': family(row)}


def prepare(selected, background):
    sets = {s: [[], [], [], []] for s in ('train', 'validation')}
    warm_pool = [read_audio(p) for _, p in background[::max(1, len(background)//32)][:32]]
    # New voice/age/accent groups stay balanced; public negatives are bounded.
    for row, p in selected+background:
        repeats = (12 if row['label'] else 6) if row['split'] == 'train' and row.get('synthetic') else 1
        pcm = read_audio(p)
        for repeat in range(repeats):
            # Adding TRAIN sources must not move existing DEV utterances or
            # alter their padding. Each original/descendant owns a stable RNG.
            seed_key = f'20261031/{row["split"]}/{row["sha256"]}/{repeat}'.encode()
            rng = np.random.default_rng(int.from_bytes(hashlib.sha256(seed_key).digest()[:8], 'little'))
            augmented = row['split'] == 'train' and repeat > 0
            warm = warm_pool[int(rng.integers(len(warm_pool)))] if augmented and warm_pool and rng.random() < .5 else None
            values = example(pcm, row, rng, augment=augmented, background_pcm=warm)
            for target, value in zip(sets[row['split']], values):
                target.append(value)
    return {s: (np.asarray(v[0]), np.asarray(v[1]), np.asarray(v[2]), v[3]) for s, v in sets.items()}


def replay(interpreter, features):
    from streaming_runtime import quantize
    interpreter.allocate_tensors()
    inp, out = interpreter.get_input_details()[0], interpreter.get_output_details()[0]
    scale, zero = inp['quantization']
    oscale, ozero = out['quantization']
    result = []
    for start in range(0, FRAMES, 3):
        interpreter.set_tensor(inp['index'], quantize(features[None, start:start+3], scale, zero))
        interpreter.invoke()
        result.append((float(interpreter.get_tensor(out['index']).flat[0])-ozero)*oscale)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ('manifest', 'background-manifest', 'protected-hashes', 'upstream', 'output'):
        p.add_argument('--'+flag, type=Path, required=True)
    p.add_argument('--target-contract', type=Path, required=True)
    p.add_argument('--channels', type=int, choices=(24, 48, 96), default=24)
    p.add_argument('--batch-normalization', action='store_true')
    p.add_argument('--objective', choices=('binary', 'phrase-contrast'), default='binary')
    p.add_argument('--encoder-init', type=Path)
    p.add_argument('--encoder-report', type=Path)
    p.add_argument('--finetune-encoder', action='store_true')
    p.add_argument('--learning-rate', type=float, default=.0005)
    p.add_argument('--resume-export', action='store_true',
        help='Reuse saved weights after an export failure; verifies exact prepared arrays and input hashes')
    a = p.parse_args()
    os.umask(0o077)
    if bool(a.encoder_init) != bool(a.encoder_report) or not .0001 <= a.learning_rate <= .001:
        raise ValueError('Bounded learning rate and paired acoustic encoder provenance required')
    encoder_proof = None
    if a.encoder_init:
        encoder_proof = json.loads(a.encoder_report.read_text())
        if (a.channels != encoder_proof.get('channels') or not a.batch_normalization or
            encoder_proof.get('encoder_sha256') != digest(a.encoder_init) or
            encoder_proof.get('household_used') is not False or
            encoder_proof.get('official_validation_or_test_used') is not False or
            encoder_proof.get('source_weights') is not None or
            encoder_proof.get('wake_background_sha256') != digest(a.background_manifest) or
            encoder_proof.get('encoder_hook') != 'ordered_context.input' or
            not 0 <= encoder_proof.get('phone_error_rate', 100) <= .8):
            raise ValueError('Fresh public-speech encoder provenance/phone quality gate failed')
    upstream_commit = subprocess.check_output(['git', '-C', str(a.upstream), 'rev-parse', 'HEAD'], text=True).strip()
    if upstream_commit != '4665173cd35f1cff9a61e06fc427f124766c488e' or subprocess.check_output(
            ['git', '-C', str(a.upstream), 'status', '--porcelain'], text=True).strip():
        raise ValueError('The pinned clean microWakeWord checkout is required')
    runtime = {name: version(name) for name in ('tensorflow', 'numpy', 'pymicro-features')}
    if runtime != {'tensorflow': '2.18.1', 'numpy': '2.0.2', 'pymicro-features': '2.0.2'}:
        raise ValueError('Use the pinned training/requirements.txt runtime')
    protected = set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values())
    contract = validate_contract(json.loads(a.target_contract.read_text()))
    manifest = json.loads(a.manifest.read_text())
    if any(r.get('target_contract') != contract['target'] for r in manifest):
        raise ValueError('Manifest labels do not belong to this target revision')
    selected = admit(manifest, a.manifest.parent, protected)
    background = background_rows(a.background_manifest, protected)
    # Guards complete before creating features or importing a model checkpoint.
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(4)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    if a.resume_export:
        previous = json.loads((a.output/'provenance.json').read_text())
        if previous['model_source_sha256'] != digest(Path(__file__).with_name('hi_pikoo_model.py')):
            raise ValueError('Resume requires the original model definition; restore its saved source snapshot')
        if previous.get('channels', 24) != a.channels or previous.get('batch_normalization', False) != a.batch_normalization:
            raise ValueError('Resume architecture differs from saved weights')
        if previous.get('objective', 'binary') != a.objective:
            raise ValueError('Resume objective differs from saved weights')
        if a.objective == 'phrase-contrast' and previous.get('contrast_source_sha256') != digest(Path(__file__).with_name('hi_pikoo_contrast.py')):
            raise ValueError('Restore the original phrase-contrast source before resuming')
        for field, file in [('manifest_sha256', a.manifest),
                            ('background_manifest_sha256', a.background_manifest),
                            ('protected_sha256', a.protected_hashes),
                            ('target_contract_sha256', a.target_contract)]:
            if previous[field] != digest(file):
                raise ValueError('Resume inputs differ from the trained experiment')
    else:
        a.output.mkdir(parents=True, exist_ok=False)
        (a.output/'target-contract.json').write_bytes(a.target_contract.read_bytes())
        snapshot = a.output/'source-snapshot'
        snapshot.mkdir()
        for name in ('hi_pikoo_train.py', 'hi_pikoo_model.py', 'hi_pikoo_contract.py',
                     'hi_pikoo_review.py', 'hi_pikoo_timing.py', 'hi_pikoo_contrast.py', 'streaming_runtime.py', 'acoustic_augment.py',
                     'generate_google.py', 'sequence_export_check.py', 'check_esp32_model.py', 'requirements.txt'):
            shutil.copyfile(Path(__file__).with_name(name), snapshot/name)
    sets = prepare(selected, background)
    x, y, w, info = sets['train']
    vx, vy, vw, vi = sets['validation']
    event_balance = None
    if a.objective == 'phrase-contrast':
        from hi_pikoo_contrast import targets, balance
        y, w = targets(info)
        w, event_balance = balance(y, w)
        vy, vw = targets(vi)
        for c, factor in enumerate(event_balance['event_factors'], 1):
            vw[vy == c] *= 12*factor
    arrays = dict(train_x=x, train_y=y, train_w=w, dev_x=vx, dev_y=vy, dev_w=vw,
                  train_binary_labels=np.asarray([m['label'] for m in info], np.int8))
    if a.resume_export:
        with np.load(a.output/'features.npz') as saved:
            if any(not np.array_equal(value, saved[key]) for key, value in arrays.items()):
                raise ValueError('Resume feature/label/mask arrays differ')
    else:
        np.savez_compressed(a.output/'features.npz', **arrays)
    provenance = {'manifest_sha256': digest(a.manifest),
        'background_manifest_sha256': digest(a.background_manifest),
        'protected_sha256': digest(a.protected_hashes),
        'model_source_sha256': digest(a.output/'source-snapshot/hi_pikoo_model.py') if not a.resume_export
            else digest(Path(__file__).with_name('hi_pikoo_model.py')),
        'data_source_sha256': digest(a.output/'source-snapshot/hi_pikoo_train.py') if not a.resume_export
            else digest(__file__), 'target': contract['target'],
        'placement_rng': 'sha256-per-original-split-repeat-v1',
        'upstream_commit': upstream_commit, 'runtime': runtime,
        'checkpoint_metric': 'float-DEV-qualified-first-then-balanced-event-Brier-v1',
        'early_stopping': {'start_from_epoch': 10, 'patience': 8, 'max_epochs': 30},
        'train_synthetic_repeats': {'positive': 12, 'negative': 6},
        'channels': a.channels, 'batch_normalization': a.batch_normalization,
        'objective': a.objective, 'contrast_event_balance': event_balance,
        'encoder_initialization_sha256': digest(a.encoder_init) if a.encoder_init else None,
        'encoder_report_sha256': digest(a.encoder_report) if a.encoder_report else None,
        'encoder_finetuned': a.finetune_encoder, 'learning_rate': a.learning_rate,
        'contrast_source_sha256': digest(a.output/'source-snapshot/hi_pikoo_contrast.py') if not a.resume_export else digest(Path(__file__).with_name('hi_pikoo_contrast.py')),
        'target_contract_sha256': digest(a.target_contract),
        'source_weights': None, 'household_used': False, 'sealed_test_opened': False,
        'public_background_selected': len(background)}
    if not a.resume_export:
        (a.output/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    else:
        (a.output/'export-resume.json').write_text(json.dumps({'new_source': provenance,
            'same_features_labels_and_masks': True, 'saved_weights_reused': True}, indent=2)+'\n')
    reports = []
    class DevelopmentQuality(tf.keras.callbacks.Callback):
        def __init__(self, folder):
            super().__init__()
            self.folder, self.epochs = folder, []

        def on_epoch_end(self, epoch, logs=None):
            probabilities = np.asarray(self.model(vx, training=False))
            if a.objective == 'phrase-contrast':
                probabilities = probabilities[:, :, 1]
            cases = [{**meta, 'probabilities': prob[:meta['valid_steps']].tolist()}
                for prob, meta in zip(probabilities, vi)]
            result = select_policy(cases)
            proxy = selection_proxy(cases, result)
            quality = proxy['score']
            if logs is not None:
                logs['val_detection_quality'] = quality
            self.epochs.append({'epoch': epoch+1, 'float_dev_quality': quality,
                'selection_proxy': proxy,
                'scope': 'DEV checkpoint selection only; not INT8 or sealed TEST', 'development': result})
            (self.folder/'dev-epochs.json').write_text(json.dumps(self.epochs, indent=2)+'\n')

    for steps in (72, 20):
        for seed in SEEDS:
            folder = a.output/f'context-{steps}-seed-{seed}'
            folder.mkdir(exist_ok=a.resume_export)
            if a.resume_export and (folder/'report.json').exists():
                report = json.loads((folder/'report.json').read_text())
                if digest(folder/'hi_pikoo.tflite') != report['static']['sha256']:
                    raise ValueError('Completed candidate changed')
                reports.append(report)
                continue
            if a.objective == 'phrase-contrast':
                from hi_pikoo_contrast import build as contrast_build
                model = contrast_build(a.upstream, steps, seed, a.channels, a.batch_normalization)
                loss = tf.keras.losses.SparseCategoricalCrossentropy(reduction='none')
            else:
                model = build(a.upstream, steps, seed, a.channels, a.batch_normalization)
                loss = sequence_loss
            if a.encoder_init:
                acoustic = tf.keras.Model(model.input, model.get_layer('ordered_context').input)
                acoustic.load_weights(a.encoder_init)
                for layer in acoustic.layers:
                    layer.trainable = bool(a.finetune_encoder and not isinstance(layer, tf.keras.layers.BatchNormalization))
            # Return per-step loss so temporal sample weights are actually applied.
            model.compile(optimizer=tf.keras.optimizers.Adam(a.learning_rate), loss=loss)
            callbacks = [DevelopmentQuality(folder),
                tf.keras.callbacks.ModelCheckpoint(str(folder/'checkpoint.weights.h5'),
                    monitor='val_detection_quality', mode='max', save_best_only=True, save_weights_only=True),
                tf.keras.callbacks.EarlyStopping(monitor='val_detection_quality', mode='max',
                    patience=8, start_from_epoch=10, restore_best_weights=False),
                tf.keras.callbacks.CSVLogger(str(folder/'epochs.csv'))]
            if a.resume_export and (folder/'checkpoint.weights.h5').exists():
                model.load_weights(folder/'checkpoint.weights.h5')
                epochs = len(list(csv.DictReader((folder/'epochs.csv').open())))
                print(json.dumps({'status': 'reusing-saved-weights', 'candidate': folder.name}))
            else:
                history = model.fit(x, y, sample_weight=w, validation_data=(vx, vy, vw),
                    epochs=30, batch_size=16, callbacks=callbacks, verbose=2)
                epochs = len(history.history['loss'])
                model.load_weights(folder/'checkpoint.weights.h5')
            if a.objective == 'phrase-contrast':
                from hi_pikoo_contrast import wake_view
                scalar = wake_view(model)
            else:
                scalar = model
            deploy = stream(scalar)
            archive = tf.keras.export.ExportArchive()
            archive.track(deploy)
            archive.add_endpoint(name='serve', fn=deploy.call,
                input_signature=[tf.TensorSpec(deploy.input.shape, tf.float32)])
            archive.write_out(str(folder/'saved'), verbose=False)
            from sequence_export_check import check
            parity = check(scalar, folder/'saved', x, [i['label'] for i in info])
            if parity['status'] != 'passed-trained-sequence-export-parity':
                raise ValueError('Trained sequence/stream differs')
            converter = tf.lite.TFLiteConverter.from_saved_model(str(folder/'saved'))
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            converter._experimental_variable_quantization = True
            converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
            converter.inference_input_type, converter.inference_output_type = tf.int8, tf.uint8
            # Balanced TRAIN originals only; DEV/TEST never calibrate quantization.
            indexes = [j for label in (0, 1) for j in [k for k, v in enumerate(info) if v['label'] == label][:40]]
            converter.representative_dataset = lambda: ([x[j:j+1, i:i+3]]
                for j in indexes for i in range(0, info[j]['valid_steps']*3, 3))
            target = folder/'hi_pikoo.tflite'
            target.write_bytes(converter.convert())
            from check_esp32_model import check as static_check
            static = static_check(target, Path(__file__).parents[1]/'firmware/main/wake_model.cpp', 524288)
            from streaming_runtime import interpreter
            cases = []
            for data, meta in zip(vx, vi):
                probability = replay(interpreter(target), data)[:meta['valid_steps']]
                cases.append({**meta, 'probabilities': probability})
            policy = select_policy(cases)
            report = {'context_steps': steps, 'seed': seed, 'epochs': epochs,
                'channels': a.channels, 'batch_normalization': a.batch_normalization,
                'objective': a.objective,
                'encoder_initialization_sha256': digest(a.encoder_init) if a.encoder_init else None,
                'parameters': model.count_params(), 'static': static, 'sequence_parity': parity,
                'development': policy, 'sealed_test_scored': False,
                'device_or_household_accepted': False, 'release_eligible': False}
            (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n')
            (folder/'dev-cases.json').write_text(json.dumps(cases)+'\n')
            reports.append(report)
            (a.output/'comparison.json').write_text(json.dumps(reports, indent=2)+'\n')
            tf.keras.backend.clear_session()
    print(json.dumps({'status': 'comparison-complete-not-deployed', 'candidates': len(reports)}))


if __name__ == '__main__':
    main()
