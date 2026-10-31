# SPDX-License-Identifier: Apache-2.0
"""Explicit target revisions; never silently reinterpret a frozen experiment."""
import re

TARGETS = {'hi-piku-v1': ['piku'], 'hi-piku-piko-v2': ['piku', 'piko']}


def validate_contract(contract):
    target = contract.get('target')
    if target not in TARGETS or contract.get('accepted_names') != TARGETS[target]:
        raise ValueError('Unknown target contract/name list')
    if contract.get('declared_before_corpus_training') is not True:
        raise ValueError('Target scope must be declared before corpus training')
    return contract


def relabel_for_contract(row, target):
    if target not in TARGETS:
        raise ValueError('Unknown target revision')
    result = {**row, 'target_contract': target}
    if target == 'hi-piku-piko-v2' and re.fullmatch(r'hi[\s,!.-]+piko[!.]?', row['text'], re.I):
        result.update(label=1, original_label=row['label'],
            label_change_reason='user-expanded target to piku OR piko before corpus training; raw manifest unchanged')
    return result
