# SPDX-License-Identifier: Apache-2.0
"""Bounded pitch-preserving TRAIN augmentation and a separate tempo DEV gate.

No downloads, synthesis requests, household input, TEST access or device writes.
Derived DEV is still reused development data, never an independent test.
"""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stretch(pcm, factor, ffmpeg):
    if not np.isfinite(factor) or not 1 < factor <= 1.5:
        raise ValueError('Predeclared faster tempo in (1, 1.5] required')
    samples = np.asarray(pcm)
    if samples.ndim != 1 or not len(samples) or not np.isfinite(samples).all():
        raise ValueError('Finite nonempty mono PCM required')
    raw = np.asarray(np.clip(samples, -32768, 32767), '<i2').tobytes()
    result = subprocess.run([str(ffmpeg), '-v', 'error', '-f', 's16le', '-ar', '16000',
        '-ac', '1', '-i', 'pipe:0', '-af', f'atempo={factor}', '-f', 's16le', 'pipe:1'],
        input=raw, capture_output=True, check=True, timeout=30)
    x = np.frombuffer(result.stdout, '<i2').astype(np.float32)
    # Do not silently accept dropped output or an unexpectedly different rate.
    if not len(x) or abs(len(x)-len(samples)/factor) > 1600:
        raise ValueError('Unexpected tempo output duration')
    return x


def source_rows(original, extra, retained, protected):
    """Validate source/split lineage before reading any audio payload."""
    records, seen, speakers = [], set(), {}
    for manifest in (original, extra):
        if manifest is None:
            continue
        for row in json.loads(manifest.read_text()):
            split, digest = row['split'], row['sha256']
            if split == 'train' and digest not in retained:
                continue  # quarantined originals and all their descendants stay excluded
            if (split not in {'train', 'validation'} or (manifest == extra and split != 'train') or
                    any(row.get(k) for k in ('family_inputs_used', 'reference_audio_used',
                        'evaluation_only', 'frozen_holdout', 'real_child', 'parent_sha256', 'ancestry_parents')) or
                    not row.get('synthetic') or not row.get('admitted_to_training') or
                    row.get('content_review') != 'passed' or row.get('pronunciation_review') != 'passed' or
                    row.get('target_contract') != 'hi-piku-piko-v2' or digest in protected):
                raise ValueError('Tempo inputs must be admitted unprotected synthetic TRAIN/DEV originals')
            if digest in seen or speakers.setdefault(row['speaker'], split) != split:
                raise ValueError('Duplicate source or speaker crosses tempo partitions')
            seen.add(digest)
            records.append((row, manifest.parent))
    if not any(r['split'] == 'train' and r['label'] for r, _ in records):
        raise ValueError('Admitted TRAIN positives required')
    if {r['label'] for r, _ in records if r['split'] == 'validation'} != {0, 1}:
        raise ValueError('Complete positive and negative DEV required')
    return records


def variants(row, config):
    """Deterministic TRAIN-only continuous tempo; DEV stays exactly unchanged."""
    count = config.get('TRAIN_continuous_variants_per_source')
    if count is None or row['split'] != 'train':
        return [(f, f'tempo-v1/{row["split"]}/{row["sha256"]}/{f}', False)
                for f in config['factors']]
    if count != 6 or config.get('TRAIN_acoustic_augmentation') is not True:
        raise ValueError('Only predeclared six-view continuous TRAIN experiment is supported')
    result = []
    for i in range(count):
        key = f'tempo-continuous-v1/train/{row["sha256"]}/{i}'
        seed = hashlib.sha256(key.encode()).digest()
        rng = np.random.default_rng(int.from_bytes(seed[:8], 'little'))
        low, high = ((1.0, 1.15), (1.15, 1.3), (1.3, 1.5))[i % 3]
        result.append((float(rng.uniform(low, high)), key, True))
    return result


def verify_dev_reference(features, metadata, reference, expected_provenance):
    if sha(reference/'provenance.json') != expected_provenance:
        raise ValueError('Declared DEV reference changed')
    proof = json.loads((reference/'provenance.json').read_text())
    for name in ('dev-features.npz', 'dev-metadata.json'):
        if sha(reference/name) != proof['files_sha256'][name]:
            raise ValueError('Reference DEV cache changed')
    with np.load(reference/'dev-features.npz') as data:
        same = np.array_equal(np.asarray(features), data['x'])
    original = json.loads((reference/'dev-metadata.json').read_text())
    # This added bookkeeping flag has no effect on the waveform, clock or label.
    without_flag = lambda rows: [{k: v for k, v in r.items() if k != 'acoustic_augmentation'} for r in rows]
    if not same or without_flag(metadata) != without_flag(original):
        raise ValueError('Derived DEV features, source labels or timing changed')


def prepare(x, y, w, metadata, events, groups, original, extra, protected_path, config_path, output, reuse=None):
    from hi_pikoo_review import validate
    from hi_pikoo_train import read_audio, example
    from hi_pikoo_timing import view
    config = json.loads(config_path.read_text())
    if (config.get('method') != 'ffmpeg-atempo-pitch-preserving' or
            config.get('factors') != [1.15, 1.3, 1.5] or config.get('TRAIN_only_augmentation') is not True):
        raise ValueError('Exact finite tempo experiment required')
    if config.get('TRAIN_continuous_variants_per_source') is not None:
        variants({'split': 'train', 'sha256': 'configuration-check'}, config)
    ffmpeg = Path(config['ffmpeg']).resolve()
    if sha(ffmpeg) != config['ffmpeg_sha256']:
        raise ValueError('Declared tempo backend changed')
    protected = set(json.loads(protected_path.read_text())['audio_sha256'].values())
    retained = {m['sha256'] for m in metadata if m.get('sha256_domain') != 'prepared-TRAIN-feature-example'}
    sources = source_rows(original, extra, retained, protected)
    folder = output/'tempo'
    folder.mkdir(exist_ok=False)
    if reuse is not None:
        proof = json.loads((reuse/'provenance.json').read_text())
        if proof['config_sha256'] != sha(config_path):
            raise ValueError('Cached tempo configuration differs')
        for name, digest in proof['files_sha256'].items():
            if Path(name).name != name or sha(reuse/name) != digest:
                raise ValueError('Cached tempo output changed')
        expected = [(r['sha256'], r['split'], f) for r, _ in sources for f, _, _ in variants(r, config)]
        actual = [(r['source_sha256'], r['source_split'], r['factor'])
                  for r in json.loads((reuse/'lineage.json').read_text())]
        if actual != expected:
            raise ValueError('Cached tempo TRAIN/DEV source lineage differs')
        for row, root in sources:
            validate(row, root, protected)  # recheck original hashes and protection without re-transforming
        for name in proof['files_sha256']:
            shutil.copyfile(reuse/name, folder/name)
        train_meta = json.loads((folder/'train-metadata.json').read_text())
        dev_meta = json.loads((folder/'dev-metadata.json').read_text())
        with np.load(folder/'train-features.npz') as data:
            arrays = [data[k] for k in ('x', 'y', 'w')]
        with np.load(folder/'dev-features.npz') as data:
            dev_features = data['x']
        if (len(train_meta) != proof['TRAIN_appended_examples'] or len(dev_meta) != proof['DEV_derived_cases'] or
                any(len(a) != len(train_meta) or a.shape[1:] != b.shape[1:]
                    for a, b in zip(arrays, (x, y, w))) or len(dev_features) != len(dev_meta)):
            raise ValueError('Cached tempo interface differs')
        proof = {**proof, 'reused_verified_preparation': True, 'reused_provenance_sha256': sha(reuse/'provenance.json')}
        (folder/'provenance.json').write_text(json.dumps(proof, indent=2)+'\n')
        return (*(np.concatenate([base, extra]) for base, extra in zip((x, y, w), arrays)),
            [*metadata, *train_meta], {**events, 'records': [*events['records'], *train_meta]},
            [*groups, *['legacy-positive' if m['label'] else 'legacy-negative' for m in train_meta]],
            proof, (dev_features, dev_meta))
    additions, train_meta, dev_features, dev_meta = [], [], [], []
    lineage = []
    for number, (row, root) in enumerate(sources, 1):
        path = validate(row, root, protected)
        # Only the existing exterior-padding view is removed; never cut words.
        base, _ = view(read_audio(path))
        for factor, seed_key, acoustic in variants(row, config):
            pcm = stretch(base, factor, ffmpeg)
            seed = hashlib.sha256(seed_key.encode()).digest()
            rng = np.random.default_rng(int.from_bytes(seed[:8], 'little'))
            if acoustic:
                # Room/filter/gain variation is independent of tempo. Never call
                # example(augment=True), which couples historical speed/pitch.
                from acoustic_augment import augment as room
                pcm = room(pcm, rng)
                pcm = pcm + rng.normal(0, rng.uniform(1, 30), len(pcm))
            a, b, c, meta = example(pcm, row, rng, augment=False)
            meta.update(tempo_factor=factor, tempo_method=config['method'],
                source=row['source'], source_split=row['split'], source_speaker=row['speaker'],
                sha256_domain='original-source-audio', tempo_derived=True, acoustic_augmentation=acoustic)
            lineage.append({'source_sha256': row['sha256'], 'source_split': row['split'],
                'factor': factor, 'derived_PCM16_sha256': hashlib.sha256(
                    np.asarray(np.clip(pcm, -32768, 32767), '<i2').tobytes()).hexdigest()})
            if row['split'] == 'train':
                additions.append((a, b, c)); train_meta.append(meta)
            else:
                dev_features.append(a); dev_meta.append(meta)
        if number % 50 == 0:
            print(json.dumps({'tempo_sources_prepared': number, 'total': len(sources)}), flush=True)
    arrays = [np.asarray([r[i] for r in additions], dtype=base.dtype)
              for i, base in enumerate((x, y, w))]
    for array, base in zip(arrays, (x, y, w)):
        if array.shape[1:] != base.shape[1:]:
            raise ValueError('Tempo frontend ABI differs')
    if config.get('DEV_reference_preparation'):
        verify_dev_reference(dev_features, dev_meta, Path(config['DEV_reference_preparation']),
                             config['DEV_reference_provenance_sha256'])
    np.savez_compressed(folder/'train-features.npz', x=arrays[0], y=arrays[1], w=arrays[2])
    np.savez_compressed(folder/'dev-features.npz', x=np.asarray(dev_features))
    (folder/'train-metadata.json').write_text(json.dumps(train_meta)+'\n')
    (folder/'dev-metadata.json').write_text(json.dumps(dev_meta)+'\n')
    (folder/'lineage.json').write_text(json.dumps(lineage)+'\n')
    proof = {'config_sha256': sha(config_path), 'backend': config['method'],
        'ffmpeg_sha256': sha(ffmpeg), 'factors': config['factors'],
        'TRAIN_source_count': sum(r['split'] == 'train' for r, _ in sources),
        'TRAIN_appended_examples': len(train_meta), 'DEV_derived_cases': len(dev_meta),
        'original_TRAIN_prefix_unchanged': True, 'original_DEV_unchanged': True,
        'derived_DEV_is_independent_TEST': False, 'household_used': False, 'TEST_opened': False,
        'tempo_does_not_shift_pitch': True, 'no_acoustic_or_pitch_augmentation_on_new_derivatives': True,
        'files_sha256': {p.name: sha(p) for p in sorted(folder.iterdir()) if p.is_file()}}
    if config.get('TRAIN_continuous_variants_per_source'):
        proof.update(TRAIN_continuous_variants_per_source=6, TRAIN_acoustic_augmentation=True,
            TRAIN_speed_range=[1.0, 1.5], DEV_speed_factors_unchanged=True,
            pitch_augmentation=False, no_acoustic_or_pitch_augmentation_on_new_derivatives=False)
    if config.get('DEV_reference_preparation'):
        proof['DEV_reference_provenance_sha256'] = config['DEV_reference_provenance_sha256']
        proof['all_derived_DEV_features_labels_timing_unchanged'] = True
    (folder/'provenance.json').write_text(json.dumps(proof, indent=2)+'\n')
    full_events = {**events, 'records': [*events['records'], *train_meta]}
    return (*(np.concatenate([base, extra]) for base, extra in zip((x, y, w), arrays)),
        [*metadata, *train_meta], full_events,
        [*groups, *['legacy-positive' if m['label'] else 'legacy-negative' for m in train_meta]],
        proof, (dev_features, dev_meta))


def evaluate(evaluator, data, temporary, folder, content_review=None):
    from hi_pikoo_model import policy_metrics
    from wake_dev_content_review import reviewed_cohorts
    features, metadata = data
    cases = []
    for feat, meta in zip(features, metadata):
        probabilities, _ = evaluator.run(feat[:meta['valid_steps']*3], temporary)
        cases.append({**meta, 'probabilities': probabilities.tolist()})
    reports = []
    for factor in (1.15, 1.3, 1.5):
        part = [r for r in cases if r['tempo_factor'] == factor]
        historical = policy_metrics(part, 3, .9)
        reviewed = policy_metrics(reviewed_cohorts(part, content_review), 3, .9) if content_review else historical
        shortfall = max(sum(max(0, math.ceil(v['targets']*.9)-v['hits']) for v in r['groups'].values())
                        for r in (historical, reviewed))
        reports.append({'factor': factor, 'historical_groups': historical, 'reviewed_groups': reviewed,
            'positive_shortfall': shortfall, 'qualified': historical['passed'] and reviewed['passed']})
    (folder/'tempo-dev-cases.json').write_text(json.dumps(cases)+'\n')
    return {'factors': reports, 'qualified': all(r['qualified'] for r in reports),
        'failure_penalty': sum(r['positive_shortfall'] + 2*r['historical_groups']['false_wakes'] +
            2*r['historical_groups']['early_wakes'] for r in reports),
        'scope': 'derived reused synthetic DEV, not independent TEST', 'fixed_policy': {'rolling': 3, 'threshold': .9}}


def apply_gate(quality, tempo):
    """Keep a legacy-qualified checkpoint from bypassing a failing tempo gate."""
    quality = dict(quality)
    if not tempo['qualified']:
        if quality['qualified']:
            quality['selection_score'] -= 1000
        quality['qualified'] = False
    quality['selection_score'] -= tempo['failure_penalty']
    return quality


def preservation_cases(original_cases, donor_cases, donor_evaluation):
    """Use the installed candidate's proven DEV scores as the preservation floor."""
    from hi_pikoo_model import policy_metrics
    keys = ('sha256', 'label', 'cohort', 'valid_steps', 'completion_ms', 'times_ms')
    if (len(original_cases) != len(donor_cases) or
            any(any(a[k] != b[k] for k in keys) for a, b in zip(original_cases, donor_cases)) or
            donor_evaluation.get('household_used') is not False or
            donor_evaluation.get('TEST_opened') is not False or
            policy_metrics(donor_cases, 3, .9) != donor_evaluation['old_DEV']):
        raise ValueError('Current-candidate DEV preservation proof differs')
    return donor_cases
