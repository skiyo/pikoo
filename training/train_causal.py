#!/usr/bin/env python3
"""Experimental frozen-encoder per-step supervision, never automatic flashing.

Requires an independently recorded all-class/all-step prototype parity proof.
The fixed final epoch is exported; legacy streaming development gates remain
external, unchanged, and mandatory. No validation/test waveform is decoded.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import numpy as np

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('upstream', 'manifest', 'checkpoint', 'protected-hashes', 'parity-proof', 'output'):
        p.add_argument('--'+name, required=True, type=Path)
    p.add_argument('--epochs', type=int, default=12)
    p.add_argument('--batch-size', type=int, default=16)
    p.add_argument('--short-context', action='store_true', help='Learn an ordered acoustic branch; requires its prototype proof')
    p.add_argument('--mask-completion-uncertainty', action='store_true', help='Ignore ambiguous target endings; never infer positive labels from energy')
    p.add_argument('--raw-branch', action='store_true', help='Learn a separate96-filter raw projection; requires its prototype proof')
    p.add_argument('--mil-target-completion', action='store_true', help='TRAIN positives using one eligible five-step event; inference is unchanged')
    p.add_argument('--mil-negative-events', action='store_true', help='Also reject the strongest valid negative five-step event; inference unchanged')
    a = p.parse_args()
    if a.raw_branch and not a.short_context:
        raise ValueError('Raw projection requires the explicit short-context architecture')
    if a.mil_target_completion and not a.mask_completion_uncertainty:
        raise ValueError('Positive MIL requires the explicit completion-uncertainty region')
    if a.mil_negative_events and not a.mil_target_completion:
        raise ValueError('Negative events require the explicit positive-event training objective')
    if not 1 <= a.epochs <= 32 or not 1 <= a.batch_size <= 64:
        raise ValueError('Invalid fixed training budget')
    os.umask(0o077)
    sys.path.insert(0, str(a.upstream.resolve()))
    import tensorflow as tf
    from microwakeword import mixednet
    from train import load
    from contrastive_readout import attach, resume_readout, attach_frozen_residual, PHRASES
    from causal_model import sequence_view, scalar_view, streaming
    from causal_data import training_rows, example
    from speech_context import SpeechContext
    from check_esp32_model import check
    tf.config.threading.set_intra_op_parallelism_threads(4)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    tf.keras.utils.set_random_seed(42)
    proof = json.loads(a.parity_proof.read_text())
    if (proof.get('status') != 'all-step-float-parity-and-static-export-passed-not-trained-or-flashed'
            or proof['source']['checkpoint_sha256'] != sha(a.checkpoint)
            or proof['graph']['input_frames'] != 600 or proof['graph']['source_pool_steps'] != 17
            or proof.get('causal_model_sha256') != sha(Path(__file__).with_name('causal_model.py'))
            or len(proof.get('cases', [])) < 8
            or any(c['all_class_max_difference'] > 1e-5 for c in proof['cases'])
            or proof['static']['status'] != 'static-check-passed'):
        raise ValueError('Missing compatible all-step prototype proof')
    if a.short_context:
        architecture = 'short-context-raw96-24x3-recent20-hidden32' if a.raw_branch else 'short-context-24x3-recent20-hidden32'
        if (proof['graph'].get('architecture') != architecture
                or proof.get('causal_branch_sha256') != sha(Path(__file__).with_name('causal_branch.py'))):
            raise ValueError('Missing compatible short-context branch proof')
    elif proof['graph'].get('architecture'):
        raise ValueError('Do not use a branch proof for the residual-only model')
    manifest_bytes = a.manifest.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    rows = json.loads(manifest_bytes)
    protection_bytes = a.protected_hashes.read_bytes()
    protection_sha256 = hashlib.sha256(protection_bytes).hexdigest()
    protection = json.loads(protection_bytes)
    selected = training_rows(rows, a.manifest.parent, set(protection['audio_sha256'].values()))
    pipeline = {name: sha(Path(__file__).with_name(name)) for name in
                ('train_causal.py', 'causal_model.py', 'causal_data.py',
                 'contrastive_readout.py', 'speech_context.py', 'acoustic_augment.py',
                 'sequence_export_check.py', 'train.py', 'review_google_corpus.py',
                 'epoch_provenance.py', 'check_esp32_model.py', 'calibration_extent.py')}
    if a.short_context:
        pipeline['causal_branch.py'] = sha(Path(__file__).with_name('causal_branch.py'))
    if a.mil_target_completion:
        pipeline['completion_mil.py'] = sha(Path(__file__).with_name('completion_mil.py'))
    # Fixed, balanced cold/warm repetitions; no held-out model score selection.
    jobs = []
    for row in selected:
        count = 8 if row['label'] else 4 if row.get('hard_negative') else 1 if row.get('real_child') else 2
        jobs.extend((row, repeat) for repeat in range(count))
    a.output.mkdir(parents=True, exist_ok=False)
    snapshot = a.output/'source-snapshot'
    snapshot.mkdir()
    for name, digest in pipeline.items():
        content = Path(__file__).with_name(name).read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError('Training source changed during snapshot: '+name)
        (snapshot/name).write_bytes(content)
    (a.output/'input-manifest.json').write_bytes(manifest_bytes)

    def assert_frozen_inputs():
        if sha(a.manifest) != manifest_sha256:
            raise ValueError('Training manifest changed during this run')
        if sha(a.protected_hashes) != protection_sha256:
            raise ValueError('Protection ledger changed during this run')
        for name, digest in pipeline.items():
            if sha(Path(__file__).with_name(name)) != digest:
                raise ValueError('Training source changed during this run: '+name)
    (a.output/'preparation.json').write_text(json.dumps({
        'stage': 'building-TRAIN-only-causal-cache', 'examples': len(jobs),
        'manifest_sha256': manifest_sha256, 'checkpoint_sha256': sha(a.checkpoint),
        'parity_proof_sha256': sha(a.parity_proof), 'fixed_epochs': a.epochs,
        'pipeline_sha256': pipeline,
        'protected_ledger_sha256': protection_sha256,
        'mask_completion_uncertainty': a.mask_completion_uncertainty,
        'mil_target_completion': a.mil_target_completion,
        'mil_negative_events': a.mil_negative_events,
        'class_order': PHRASES, 'household_or_development_used': False,
    }, indent=2)+'\n')
    x = np.lib.format.open_memmap(a.output/'causal-features.npy', mode='w+', dtype=np.float32, shape=(len(jobs), 600, 40))
    y = np.lib.format.open_memmap(a.output/'causal-labels.npy', mode='w+', dtype=np.uint8, shape=(len(jobs), 200))
    w = np.lib.format.open_memmap(a.output/'causal-mask.npy', mode='w+', dtype=np.float32, shape=(len(jobs), 200))
    context = SpeechContext(selected, a.manifest.parent, 43)
    summary = {'examples': len(jobs), 'warm': 0, 'cold': 0, 'partial_non_targets': 0,
               'valid_class_steps': [0]*14, 'household_or_development_used': False}
    last_path, pcm = None, None
    for index, (row, repeat) in enumerate(jobs):
        path = a.manifest.parent / row['path']
        if path != last_path:
            pcm, last_path = load(path), path
        seed = int(hashlib.sha256((row['sha256']+':causal-j:'+str(repeat)).encode()).hexdigest()[:16], 16)
        rng = np.random.default_rng(seed)
        warm = bool(rng.random() < .5)
        features, labels, weights, info = example(pcm, row, rng, context if warm else None,
            completion_uncertainty=a.mask_completion_uncertainty)
        if not np.all(np.isfinite(features)):
            raise ValueError('Non-finite MicroFrontend feature')
        x[index], y[index], w[index] = features, labels, weights
        summary['warm' if warm else 'cold'] += 1
        summary['partial_non_targets'] += int(not info['full_phrase_retained'])
        summary['valid_class_steps'] = (np.asarray(summary['valid_class_steps']) +
            np.bincount(labels[weights > 0], minlength=14)).tolist()
        if (index+1) % 500 == 0:
            print(json.dumps({'stage': 'prepare', 'completed': index+1, 'total': len(jobs)}), flush=True)
    x.flush(); y.flush(); w.flush()
    counts = np.asarray(summary['valid_class_steps'], np.float64)
    # Cap rare-class weights; ordinary-speech prefixes never lose their loss.
    class_weights = np.minimum(16., np.maximum(1., np.sqrt(counts[0]/np.maximum(counts, 1))))
    summary['class_weights'] = class_weights.tolist()
    (a.output/'dataset-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    assert_frozen_inputs()
    flags = SimpleNamespace(pointwise_filters=','.join(['128']*6), repeat_in_block=','.join(['1']*6),
        mixconv_kernel_sizes='[5],[9],[13],[21],[31],[43]', residual_connection=','.join(['0']*6),
        first_conv_filters=64, first_conv_kernel_size=3, stride=3, spatial_attention=0, pooled=1, max_pool=0)
    source, view = attach(mixednet.model(flags, (399, 40), None), warm_start=True)
    source_proof = resume_readout(source, view, a.checkpoint, np.asarray(x[:2, -399:], np.float32),
        {'filters': 128, 'first_filters': 64, 'kernels': [5, 9, 13, 21, 31, 43]})
    if a.short_context:
        from causal_branch import attach as attach_branch
        fit, graph = attach_branch(source, 600, raw_filters=96 if a.raw_branch else 0)
    else:
        residual, _ = attach_frozen_residual(source, 64)
        fit, graph = sequence_view(residual, 600)
    frozen = {layer.name: layer.get_weights() for layer in fit.layers if not layer.trainable}

    class Batches(tf.keras.utils.PyDataset):
        def __init__(self):
            super().__init__(workers=1, use_multiprocessing=False, max_queue_size=2)
            self.rng = np.random.default_rng(44)
            self.indices = self.rng.permutation(len(jobs))

        def __len__(self):
            return (len(jobs)+a.batch_size-1)//a.batch_size

        def __getitem__(self, batch):
            indices = self.indices[batch*a.batch_size:(batch+1)*a.batch_size]
            labels = np.asarray(y[indices], np.int32)
            return np.asarray(x[indices], np.float32), labels, np.asarray(w[indices])*class_weights[labels]

        def on_epoch_end(self):
            self.indices = self.rng.permutation(len(jobs))

    optimizer = tf.keras.optimizers.Adam(.0003, clipnorm=5)
    if a.mil_target_completion:
        from completion_mil import trainer
        learner = trainer(fit, negative_events=a.mil_negative_events)
        learner.compile(optimizer=optimizer)
    else:
        learner = fit
        learner.compile(optimizer=optimizer, loss='sparse_categorical_crossentropy')
    history = learner.fit(Batches(), epochs=a.epochs, verbose=2)
    assert_frozen_inputs()
    for name, weights in frozen.items():
        for expected, actual in zip(weights, fit.get_layer(name).get_weights()):
            np.testing.assert_array_equal(actual, expected)
    fit.save_weights(a.output/'checkpoint.weights.h5')
    (a.output/'training-history.json').write_text(json.dumps(history.history, indent=2)+'\n')
    wake = scalar_view(fit)
    if a.short_context:
        from causal_branch import integer_anchor
        anchored = integer_anchor(fit)
        before = fit(x[:8], training=False).numpy()
        after = anchored(x[:8], training=False).numpy()
        if np.max(abs(before-after)) > 1e-5:
            raise ValueError('Integer-state export anchor changed trained probabilities')
        wake = scalar_view(anchored)
    model = streaming(wake)
    archive = tf.keras.export.ExportArchive()
    archive.track(model)
    archive.add_endpoint(name='serve', fn=model.call, input_signature=[tf.TensorSpec(model.input.shape, tf.float32)])
    archive.write_out(str(a.output/'saved'), verbose=False)
    from sequence_export_check import check as check_sequence
    targets = np.asarray([row['label'] for row, repeat in jobs])
    sequence_parity = check_sequence(wake, a.output/'saved', x, targets)
    (a.output/'trained-sequence-parity.json').write_text(json.dumps(sequence_parity, indent=2)+'\n')
    if sequence_parity['status'] != 'passed-trained-sequence-export-parity':
        raise ValueError('Trained batch view and saved stateful stream differ')
    rng = np.random.default_rng(43)
    calibration = []
    for label in (0, 1):
        pool = np.flatnonzero(targets == label)
        calibration.extend(rng.choice(pool, min(50, len(pool)), replace=False).tolist())
    rng.shuffle(calibration)

    def representative():
        from calibration_extent import valid_steps
        for index in calibration:
            # An ignored interior target ending is real input, not padding.
            # Dropping its count from the extent truncated the actual tail.
            for step in range(valid_steps(w[index])):
                yield [np.asarray(x[index:index+1, step*3:step*3+3], np.float32)]

    converter = tf.lite.TFLiteConverter.from_saved_model(str(a.output/'saved'))
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter._experimental_variable_quantization = True
    converter._experimental_disable_per_channel_quantization_for_dense_layers = True
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type, converter.inference_output_type = tf.int8, tf.uint8
    converter.representative_dataset = representative
    (a.output/'nihao_pikoo.tflite').write_bytes(converter.convert())
    compatibility = check(a.output/'nihao_pikoo.tflite', Path(__file__).parents[1]/'firmware/main/wake_model.cpp', 524288)
    (a.output/'esp32-static-check.json').write_text(json.dumps(compatibility, indent=2)+'\n')
    report = {'status': 'experimental-final-fixed-epoch-not-evaluated-or-flashed',
        'epochs': a.epochs, 'filters': 128, 'first_filters': 64, 'kernels': [5, 9, 13, 21, 31, 43],
        'model_bytes': compatibility['bytes'], 'model_sha256': compatibility['sha256'],
        'training_manifest_sha256': manifest_sha256, 'source': source_proof,
        'training_source_snapshot': 'source-snapshot',
        'protected_ledger_sha256': protection_sha256,
        'parity_proof_sha256': sha(a.parity_proof), 'graph': graph, 'dataset': summary,
        'pipeline_sha256': pipeline, 'data_contract': 'causal-waveform-uncertainty-mask-v2' if a.mask_completion_uncertainty else 'causal-complete-waveform-v1',
        'repetitions': {'target': 8, 'hard_negative': 4, 'real_child_ordinary': 1, 'other': 2},
        'learning_rate': .0003, 'batch_size': a.batch_size,
        'positive_objective': 'one-eligible-five-step-event' if a.mil_target_completion else 'all-post-completion-frames',
        'trained_sequence_export_parity': {'passed': True, 'cases': len(sequence_parity['cases']),
            'max_absolute_error': max(c['max_absolute_error'] for c in sequence_parity['cases'])},
        'negative_objective': 'all-valid-frame-categorical-plus-worst-five-step-event' if a.mil_negative_events
            else 'unchanged-all-valid-frame-categorical-crossentropy',
        'classifier_readout': {'type': 'causal-frame-short-context' if a.short_context else 'causal-frame-frozen-residual',
            'classes': PHRASES, 'residual_hidden_units': 32 if a.short_context else 64,
            'original_encoder_and_logits_frozen': True},
        'threshold': .9, 'rolling_inferences': 5,
        'frozen_source_weights_unchanged': True, 'household_or_development_used': False,
        'checkpoint_weights_sha256': sha(a.output/'checkpoint.weights.h5'),
        'device_modified': False}
    (a.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'stage': 'exported-not-qualified', 'bytes': report['model_bytes'], 'sha256': report['model_sha256']}), flush=True)


if __name__ == '__main__':
    main()
