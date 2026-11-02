#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Two bounded negative-refresh candidates, preserving the installed model ABI.

Reuses an audited TRAIN/DEV cache and its original checkpoint. Household and
consumed TEST never become inputs. Fixed 3-score / .90 policy; no threshold
search. Results are development evidence only and never auto-flash a device.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from importlib.metadata import version

import numpy as np
from hi_pikoo_model import build, stream, sequence_loss, policy_metrics, event_scores
from hi_pikoo_train import example, features_and_times, replay
from wake_playback_negatives import load_rows, read_pcm, native_probabilities, sha


DEPLOYED_MODEL = 'b0ef4100e6728859894d2b2f162d2d6de1e1cce9703007608908c78b8812d478'


def windows(samples, length=64000, stride=32000):
    """Cover the entire negative; no suffix silently disappears from training."""
    if len(samples) <= length:
        return [(0, samples)]
    starts = list(range(0, len(samples)-length+1, stride))
    if starts[-1] != len(samples)-length:
        starts.append(len(samples)-length)
    return [(start, samples[start:start+length]) for start in starts]


def recall_preserved(baseline, candidate):
    return (candidate['false_wakes'] <= baseline['false_wakes'] and
            candidate['early_wakes'] <= baseline['early_wakes'] and
            set(candidate['groups']) == set(baseline['groups']) and
            all(candidate['groups'][g]['targets'] == v['targets'] and
                candidate['groups'][g]['hits'] >= v['hits']
                for g, v in baseline['groups'].items()))


def fixed_metrics(probabilities, info):
    cases = [{**meta, 'probabilities': prob[:meta['valid_steps']].tolist()}
             for prob, meta in zip(probabilities, info)]
    return policy_metrics(cases, 3, .9)


def hard_training_sources(report):
    """Only TRAIN scores can change training inclusion/weights."""
    return {row['sha256'] for row in report['cases']
            if row['split'] == 'train' and row['peak'] >= .3}


def lift_head(original, larger):
    """Start the wider classifier with exactly the original float function."""
    for source, target in zip(original.layers, larger.layers, strict=True):
        old, new = source.get_weights(), target.get_weights()
        if [v.shape for v in old] == [v.shape for v in new]:
            target.set_weights(old)
        elif old[0].shape == (1, 1, 24, 32) and new[0].shape == (1, 1, 24, 64):
            new[0] *= .1
            new[0][..., :32] = old[0]
            new[1][:32], new[1][32:] = old[1], .01
            target.set_weights(new)
        elif old[0].shape == (1, 1, 32, 1) and new[0].shape == (1, 1, 64, 1):
            new[0][:] = 0
            new[0][:, :, :32] = old[0]
            new[1] = old[1]
            target.set_weights(new)
        else:
            raise ValueError('Unexpected architecture change during head lift')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-run', 'negative-manifest', 'baseline-negative-report',
                 'protected-hashes', 'upstream', 'micro', 'output'):
        p.add_argument('--'+name, required=True, type=Path)
    p.add_argument('--hard-negative-weight', type=int, choices=(4, 12), default=4)
    p.add_argument('--freeze-acoustic', action='store_true')
    p.add_argument('--learning-rate', type=float, choices=(.00005, .0001), default=.0001)
    p.add_argument('--positive-anchor-weight', type=int, choices=(1, 2), default=1)
    p.add_argument('--max-epochs', type=int, choices=(8, 20), default=8)
    p.add_argument('--warm-frontend', action='store_true',
                   help='Add TRAIN-only windows computed with continuous frontend state')
    p.add_argument('--head-units', type=int, choices=(32, 64), default=32)
    a = p.parse_args()
    os.umask(0o077)
    revision = subprocess.check_output(['git', '-C', str(a.upstream), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != '4665173cd35f1cff9a61e06fc427f124766c488e' or subprocess.check_output(
            ['git', '-C', str(a.upstream), 'status', '--porcelain'], text=True).strip():
        raise ValueError('Pinned clean microWakeWord checkout required')
    runtime = {name: version(name) for name in ('tensorflow', 'numpy', 'pymicro-features')}
    if runtime != {'tensorflow': '2.18.1', 'numpy': '2.0.2', 'pymicro-features': '2.0.2'}:
        raise ValueError('Pinned training runtime required')
    rows = load_rows(a.negative_manifest, a.protected_hashes)
    baseline_folder = a.baseline_run/'context-20-seed-43'
    base_model = baseline_folder/'hi_pikoo.tflite'
    if sha(base_model) != DEPLOYED_MODEL:
        raise ValueError('Baseline differs from the installed model')
    provenance = json.loads((a.baseline_run/'provenance.json').read_text())
    if provenance.get('household_used') is not False or provenance.get('sealed_test_opened') is not False:
        raise ValueError('Audited original TRAIN/DEV provenance required')
    old_info = json.loads((baseline_folder/'dev-cases.json').read_text())
    protected = set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values())
    if any(m['sha256'] in protected for m in old_info):
        raise ValueError('Protected DEV waveform')
    baseline_negative = json.loads(a.baseline_negative_report.read_text())
    if baseline_negative['model_sha256'] != DEPLOYED_MODEL or baseline_negative['manifest_sha256'] != sha(a.negative_manifest):
        raise ValueError('Negative baseline provenance differs')
    baseline_old = policy_metrics(old_info, 3, .9)
    baseline_new = baseline_negative['summary']['validation']['false_clips']
    hard_train = hard_training_sources(baseline_negative)
    if baseline_new == 0:
        raise ValueError('No reproduced DEV error; collect a better challenge before selecting a fix')
    a.output.mkdir(parents=True, exist_ok=False)
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(4)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    with np.load(a.baseline_run/'features.npz') as cache:
        x, y, w = [cache[k] for k in ('train_x', 'train_y', 'train_w')]
        vx, vy, vw = [cache[k] for k in ('dev_x', 'dev_y', 'dev_w')]
        original_labels = cache['train_binary_labels'] if 'train_binary_labels' in cache.files else y.max(axis=1)>0
    w = w.copy()
    w[y > 0] *= a.positive_anchor_weight
    extras = {split: [] for split in ('train', 'validation')}
    continuous_dev = []
    warm_views = 0
    for row in rows:
        samples = read_pcm(a.negative_manifest.parent/row['path'])
        if row['split'] == 'validation':
            features, _ = features_and_times(np.pad(samples, (16000, 16000)))
            continuous_dev.append((row, features))
        # Two overlapping views cover every sample, including original tails.
        for offset, samples_window in windows(samples):
            rng = np.random.default_rng(int(hashlib.sha256(
                f"{row['sha256']}:{offset}".encode()).hexdigest()[:8], 16))
            data, labels, weight, _ = example(samples_window, row, rng, augment=row['split']=='train')
            # Same source-family partition; loudness/room variation is TRAIN only.
            weight *= a.hard_negative_weight if row['sha256'] in hard_train else 4
            extras[row['split']].append((data, labels, weight))
        if a.warm_frontend and row['split'] == 'train':
            # A television is not a sequence of cold frontend resets. Compute
            # the complete recording first, then slice the features; preserve
            # the frontend's running noise/PCAN history inside each original.
            features, _ = features_and_times(np.pad(samples, (16000, 16000)))
            for _, chunk in windows(features, length=600, stride=300):
                n = len(chunk)//3
                data = np.zeros((600, 40), np.float32)
                data[:n*3] = chunk[:n*3]
                weight = np.zeros(200, np.float32)
                weight[:n] = a.hard_negative_weight if row['sha256'] in hard_train else 4
                extras['train'].append((data, np.zeros(200, np.float32), weight))
                warm_views += 1
    extra_train = extras['train']
    x = np.concatenate([x, np.asarray([r[0] for r in extra_train])])
    y = np.concatenate([y, np.asarray([r[1] for r in extra_train])])
    w = np.concatenate([w, np.asarray([r[2] for r in extra_train])])
    records = {'baseline_cache_sha256': sha(a.baseline_run/'features.npz'),
        'baseline_checkpoint_sha256': sha(baseline_folder/'checkpoint.weights.h5'),
        'baseline_model_sha256': DEPLOYED_MODEL,
        'negative_manifest_sha256': sha(a.negative_manifest),
        'protected_sha256': sha(a.protected_hashes),
        'upstream_commit': revision, 'runtime': runtime,
        'baseline_old_dev': baseline_old, 'baseline_new_dev_false_clips': baseline_new,
        'train_examples': len(x), 'new_train_windows': len(extra_train),
        'existing_dev_cases': len(vx), 'new_dev_recordings': len(continuous_dev),
        'fixed_policy': {'rolling': 3, 'threshold': .9},
        'seeds': [42, 43], 'learning_rate': a.learning_rate, 'maximum_epochs_each': a.max_epochs,
        'positive_anchor_weight': a.positive_anchor_weight,
        'hard_negative_weight': a.hard_negative_weight, 'hard_training_sources': len(hard_train),
        'acoustic_encoder_frozen': a.freeze_acoustic,
        'continuous_frontend_training_views': warm_views,
        'household_used': False, 'old_or_new_test_opened': False,
        'deployment_changed': False, 'architecture_changed': a.head_units != 32,
        'head_units': a.head_units}
    (a.output/'provenance.json').write_text(json.dumps(records, indent=2)+'\n')
    for path in [Path(__file__), *[Path(__file__).with_name(name) for name in
                ('wake_playback_negatives.py', 'hi_pikoo_model.py', 'hi_pikoo_train.py', 'streaming_runtime.py')]]:
        shutil.copyfile(path, a.output/path.name)
    reports = []
    for seed in (42, 43):
        folder = a.output/f'seed-{seed}'
        folder.mkdir()
        model = build(a.upstream, 20, seed, 24, False)
        model.load_weights(baseline_folder/'checkpoint.weights.h5')
        if a.head_units == 64:
            larger = build(a.upstream, 20, seed, 24, False, head_units=64)
            lift_head(model, larger)
            initial_error = float(np.max(np.abs(np.asarray(model(vx, training=False))-
                                                  np.asarray(larger(vx, training=False)))))
            if initial_error > 1e-6:
                raise ValueError('Wider-head initialization changes the baseline float function')
            (folder/'initialization-parity.json').write_text(json.dumps({
                'full_DEV_max_absolute_error': initial_error, 'gradient_updates': 0,
                'weights_transferred_from_baseline': True})+'\n')
            model = larger
        if a.freeze_acoustic:
            for layer in model.layers:
                if layer.name == 'ordered_context':
                    break
                layer.trainable = False
        model.compile(optimizer=tf.keras.optimizers.Adam(a.learning_rate), loss=sequence_loss)
        epochs = []

        class Quality(tf.keras.callbacks.Callback):
            def on_epoch_end(self, epoch, logs=None):
                probabilities = np.asarray(self.model(vx, training=False))
                old = fixed_metrics(probabilities, old_info)
                new = []
                for row, features in continuous_dev:
                    # All selected recordings are <=5s plus 2s padding. Keep
                    # sequence ordering and context across the entire recording.
                    # A separate streaming export below verifies full originals;
                    # train-model DEV uses overlapping <=6s views at this stage.
                    peaks = []
                    for _, chunk in windows(features, length=600, stride=300):
                        data = np.zeros((600, 40), np.float32)
                        n = len(chunk)//3
                        data[:n*3] = chunk[:n*3]
                        prob = np.asarray(self.model(data[None], training=False))[0, :n]
                        peaks.append(float(max(event_scores(prob, 3), default=0)))
                    new.append(max(peaks))
                misses = sum(max(0, v['hits']-old['groups'][g]['hits']) for g, v in baseline_old['groups'].items())
                false = sum(peak >= .9 for peak in new)
                margins = []
                for prob, meta in zip(probabilities, old_info):
                    if not meta['label']:
                        continue
                    scores = event_scores(prob[:meta['valid_steps']], 3)
                    times = np.asarray(meta['times_ms'])
                    event = scores[(times >= meta['completion_ms']-120) & (times <= meta['completion_ms']+800)]
                    margins.append(float(max(event, default=0)))
                # Any original DEV recognition regression is penalized before
                # noise rejection; a silent model cannot be selected as a fix.
                # Small confidence terms break count ties; final INT8/native
                # gates still decide eligibility, never this float proxy alone.
                tie_break = .001*(float(np.mean(margins))-float(np.mean(np.square(new))))
                score = -10*misses-10*old['false_wakes']-10*old['early_wakes']-false/len(new)+tie_break
                logs['val_refresh_quality'] = score
                epochs.append({'epoch': epoch+1, 'old_dev': old,
                    'new_dev_window_false_clips': false, 'selection_score': score,
                    'confidence_tie_break': tie_break})
                (folder/'dev-epochs.json').write_text(json.dumps(epochs, indent=2)+'\n')

        history = model.fit(x, y, sample_weight=w, epochs=a.max_epochs, batch_size=16,
            callbacks=[Quality(), tf.keras.callbacks.ModelCheckpoint(str(folder/'best.weights.h5'),
                monitor='val_refresh_quality', mode='max', save_best_only=True, save_weights_only=True),
                tf.keras.callbacks.EarlyStopping(monitor='val_refresh_quality', mode='max', patience=5,
                    start_from_epoch=8 if a.max_epochs == 20 else 0),
                tf.keras.callbacks.CSVLogger(str(folder/'epochs.csv'))], verbose=2)
        model.load_weights(folder/'best.weights.h5')
        deploy = stream(model)
        archive = tf.keras.export.ExportArchive()
        archive.track(deploy)
        archive.add_endpoint(name='serve', fn=deploy.call,
                            input_signature=[tf.TensorSpec(deploy.input.shape, tf.float32)])
        archive.write_out(str(folder/'saved'), verbose=False)
        from sequence_export_check import check
        parity = check(model, folder/'saved', x[:len(original_labels)], original_labels)
        if parity['status'] != 'passed-trained-sequence-export-parity':
            raise ValueError('Batch/stream parity failed')
        converter = tf.lite.TFLiteConverter.from_saved_model(str(folder/'saved'))
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        converter._experimental_variable_quantization = True
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type, converter.inference_output_type = tf.int8, tf.uint8
        indexes = [i for label in (0, 1) for i in np.flatnonzero(original_labels == label)[:40]]
        indexes += list(range(len(original_labels), min(len(x), len(original_labels)+40)))
        converter.representative_dataset = lambda: ([x[j:j+1, i:i+3]]
            for j in indexes for i in range(0, 600, 3))
        target = folder/'hi_pikoo.tflite'
        target.write_bytes(converter.convert())
        from check_esp32_model import check as static_check
        static = static_check(target, Path(__file__).parents[1]/'firmware/main/wake_model.cpp', 524288)
        from streaming_runtime import interpreter
        # Full old DEV, fixed policy; no substituted synthetic or household test.
        cases = [{**meta, 'probabilities': replay(interpreter(target), data)[:meta['valid_steps']]}
                 for data, meta in zip(vx, old_info)]
        old = policy_metrics(cases, 3, .9)
        (folder/'dev-cases.json').write_text(json.dumps(cases)+'\n')
        from wake_playback_negatives import score
        score(a.negative_manifest, a.protected_hashes, target, a.micro.resolve(), folder/'continuous')
        new_report = json.loads((folder/'continuous/report.json').read_text())
        false = new_report['summary']['validation']['false_clips']
        reduction = 1-false/baseline_new
        # DEV is used for selection, not renamed as a fresh TEST or board result.
        candidate = {'seed': seed, 'epochs': len(history.history['loss']), 'static': static,
            'sequence_parity': parity, 'old_dev': old,
            'new_dev_false_clips': false, 'baseline_new_dev_false_clips': baseline_new,
            'relative_false_clip_reduction': reduction,
            'old_dev_recognition_preserved': recall_preserved(baseline_old, old),
            'development_eligible': recall_preserved(baseline_old, old) and reduction >= .8,
            'new_test_opened': False, 'device_accepted': False, 'flashed': False}
        (folder/'report.json').write_text(json.dumps(candidate, indent=2)+'\n')
        reports.append(candidate)
        (a.output/'comparison.json').write_text(json.dumps(reports, indent=2)+'\n')
        print(json.dumps({'seed': seed, 'development_eligible': candidate['development_eligible'],
            'recognition_preserved': candidate['old_dev_recognition_preserved'], 'new_dev_false': false}), flush=True)
        tf.keras.backend.clear_session()


if __name__ == '__main__':
    main()
