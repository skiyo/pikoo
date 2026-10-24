#!/usr/bin/env python3
"""Evaluate one immutable candidate into a fresh, non-overwritable directory.

No candidate letter is embedded in paths. Existing full development rules and
reference backend are retained; no independent test, recording or flash occurs.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def fingerprint(files):
    return {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files}


def check_fingerprints(expected):
    if fingerprint([Path(path) for path in expected]) != expected:
        raise ValueError('Candidate or evaluation input changed during the run')


def new_output(path):
    # Refuse even an existing empty directory: each run has one identity.
    path.mkdir(parents=True, exist_ok=False, mode=0o700)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('model', 'saved', 'original-manifest', 'additional-manifest',
                 'protected-hashes', 'context-baseline', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    for name, value in vars(args).items():
        setattr(args, name, value.resolve())
    if args.output.is_relative_to(args.saved):
        raise ValueError('Evaluation output must not modify the saved model directory')
    os.umask(0o077)
    here = Path(__file__).resolve().parent
    files = [args.model, args.original_manifest, args.additional_manifest,
             args.protected_hashes, args.context_baseline,
             *sorted(path for path in args.saved.rglob('*') if path.is_file()),
             *[here / name for name in ('evaluate_candidate.py', 'evaluate_additional.py',
               'check_quantization.py', 'level_tone_scope.py', 'generalization_gate.py',
               'evaluate_context.py', 'evaluate.py', 'streaming_runtime.py', 'streaming_gate.py',
               'self_test.py', 'policies/dualeye-pikoo-level-v1.json')]]
    snapshot = fingerprint(files)
    new_output(args.output)
    model_sha = snapshot[str(args.model.resolve())]
    report = {'model_sha256': model_sha,
              'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'stages': {}, 'device_modified': False, 'household_or_independent_used': False}
    (args.output / 'input-fingerprints.json').write_text(json.dumps(snapshot, indent=2) + '\n')

    def save():
        (args.output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')

    def run(stage, command, allowed=(0,)):
        check_fingerprints(snapshot)
        report['stage'] = stage
        save()
        with (args.output / (stage + '.log')).open('w') as log:
            code = subprocess.run([sys.executable, *map(str, command)],
                                  cwd=here.parent, stdout=log, stderr=subprocess.STDOUT).returncode
        report['stages'][stage] = {'exit_code': code}
        check_fingerprints(snapshot)
        if code not in allowed:
            raise RuntimeError(stage + ' failed; inspect its log')
        return code

    try:
        quant = run('quantization', [here / 'check_quantization.py', '--model', args.model,
            '--saved', args.saved, '--manifest', args.original_manifest,
            '--protected-hashes', args.protected_hashes, '--output', args.output / 'quantization.json',
            '--limit', '8'], (0, 2))
        run('original-development', [here / 'level_tone_scope.py', 'evaluate', '--model', args.model,
            '--manifest', args.original_manifest, '--protected-hashes', args.protected_hashes,
            '--output', args.output / 'original.json'])
        run('additional-development', [here / 'evaluate_additional.py', '--model', args.model,
            '--manifest', args.additional_manifest, '--protected-hashes', args.protected_hashes,
            '--base-gate', args.output / 'original.gate.json', '--output', args.output / 'additional.json'])
        original = json.loads((args.output / 'original.gate.json').read_text())
        additional = json.loads((args.output / 'additional.gate.json').read_text())
        report.update(original_development=original, additional_development=additional)
        if quant or not original['passed'] or not additional['passed']:
            report.update(stage='rejected-prerequisite-development-no-flash',
                          development_qualified=False, continuous_development='not run: failed prerequisite')
            save()
            return
        run('continuous-development', [here / 'evaluate_context.py', '--model', args.model,
            '--manifest', args.original_manifest, '--protected-hashes', args.protected_hashes,
            '--include-non-targets', '--output', args.output / 'continuous.json'])
        continuous = json.loads((args.output / 'continuous.json').read_text())
        baseline = json.loads(args.context_baseline.read_text())
        if (not continuous.get('completed') or not baseline.get('completed')
                or continuous['prefix_recording_sha256'] != baseline['prefix_recording_sha256']
                or {(r['target_sha256'], r['condition']) for r in continuous['cases']}
                != {(r['target_sha256'], r['condition']) for r in baseline['cases']}):
            raise ValueError('Incomplete or changed continuous-development coverage')
        failures = [key for key, value in continuous['summary'].items()
                    if (value['targets'] and value['hits'] / value['targets'] < .9)
                    or value.get('false_wakes', 0) or value['prefix_above_threshold_windows']]
        report.update(stage='completed-development-only-not-release',
                      development_qualified=not failures, continuous_failures=failures,
                      continuous_development=continuous['summary'])
        save()
    except Exception as error:
        report.update(stage='failed-needs-inspection', error=str(error))
        save()
        raise


if __name__ == '__main__':
    main()
