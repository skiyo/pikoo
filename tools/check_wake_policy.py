#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate a frozen Hi Pikoo policy against its exact model before a build."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def frontend_fingerprint():
    source = (Path(__file__).parents[1]/'firmware/main/wake_model.cpp').read_text()
    config = source[source.index('cfg.window.size_ms'):source.index('if (!FrontendPopulateState')]
    return hashlib.sha256(re.sub(r'\s+', '', config).encode()).hexdigest()


def validate(model, policy):
    targets = {'hi-piku-v1': ['piku'], 'hi-piku-piko-v2': ['piku', 'piko']}
    if policy.get('target') not in targets or policy.get('schema_version') != 1:
        raise ValueError('Unknown wake target/policy version')
    if policy['target'] != 'hi-piku-v1' and policy.get('accepted_names') != targets[policy['target']]:
        raise ValueError('Target pronunciation list mismatch')
    if hashlib.sha256(model.read_bytes()).hexdigest() != policy.get('model_sha256'):
        raise ValueError('Policy belongs to a different model')
    if policy.get('rolling') not in (3, 5) or policy.get('threshold') not in (.8, .85, .9, .95):
        raise ValueError('Policy was not in the declared DEV grid')
    if policy.get('frontend') != {'sample_rate': 16000, 'feature_bins': 40,
        'window_ms': 30, 'feature_step_ms': 10, 'inference_step_ms': 30}:
        raise ValueError('Frontend configuration mismatch')
    if policy.get('development_passed') is not True or not policy.get('candidate_frozen_at'):
        raise ValueError('A frozen, DEV-qualified candidate is required')
    fingerprint = policy.get('frontend_fingerprint', '')
    if fingerprint != frontend_fingerprint():
        raise ValueError('Frontend fingerprint differs from this firmware')
    return policy


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--policy', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = validate(a.model, json.loads(a.policy.read_text()))
    a.output.write_text('#pragma once\n'
        f'#define PIKOO_WAKE_ROLLING {result["rolling"]}\n'
        f'#define PIKOO_WAKE_THRESHOLD {result["threshold"]:.2f}f\n')


if __name__ == '__main__':
    main()
