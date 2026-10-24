"""Repair only byte-verified duplicate TRAIN negative ancestry metadata.

Restore identity copies to an existing non-self antecedent's recorded parents.
Keep every legitimate alternate origin of identical bytes, and every input
occurrence. No waveform, label, sampling weight or protected-source policy is
relaxed. This is not a general cycle-suppression or label-correction tool.
"""
import copy
import hashlib
from pathlib import Path
from clean_corpus import guard, parents, PUBLIC_CORPORA, SYNTHETIC


FIELDS = ('source', 'split', 'label', 'group', 'speaker', 'text',
          'pronunciation', 'synthetic_style', 'source_terms')


def repair(rows, root, protected):
    guard(rows, set(protected))
    result, changes = copy.deepcopy(rows), []

    def verified(row):
        if hashlib.sha256((Path(root) / row['path']).read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Identity copy or recorded antecedent file changed')

    def eligible(row):
        return (row['split'] == 'train' and row['label'] == 0
                and not row.get('augmentation')
                and (row['source'] in PUBLIC_CORPORA
                     or row['source'] in SYNTHETIC and row.get('synthetic') and not row.get('real_child')))

    for index, row in enumerate(rows):
        digest = row['sha256']
        if digest not in parents(row):
            continue
        if (row.get('parent_sha256') != digest or not eligible(row)
                or not row.get('mined_training_prefix') or parents(row) != {digest}):
            raise ValueError('Only a verified TRAIN negative identity prefix may repair a self edge')
        matches = [(i, candidate) for i, candidate in enumerate(rows)
                   if candidate['sha256'] == digest and digest not in parents(candidate)
                   and eligible(candidate)
                   and all(candidate.get(key) == row.get(key) for key in FIELDS)]
        if not matches:
            raise ValueError('No unchanged non-self antecedent matches the identity copy')
        original_index, antecedent = matches[0]
        if any(parents(candidate) != parents(antecedent) for i, candidate in matches):
            raise ValueError('Ambiguous identity antecedent; do not guess an origin')
        verified(row)
        verified(antecedent)
        for field in ('parent_sha256', 'ancestry_parents'):
            result[index].pop(field, None)
            if field in antecedent:
                result[index][field] = copy.deepcopy(antecedent[field])
        changes.append({'row_index': index, 'antecedent_row_index': original_index,
                        'sha256': digest, 'repair': 'restore-byte-identical-antecedent-ancestry',
                        'restored_parents': sorted(parents(antecedent))})
    groups = {}
    for index, row in enumerate(result):
        groups.setdefault(row['sha256'], []).append(index)
    merged = []
    for digest, indices in groups.items():
        if len({frozenset(parents(result[i])) for i in indices}) <= 1:
            continue
        group = [result[i] for i in indices]
        if (not all(eligible(row) for row in group)
                or any(not all(row.get(key) == group[0].get(key) for key in FIELDS) for row in group)):
            raise ValueError('Differently labeled or sourced bytes cannot merge ancestry')
        union = set().union(*(parents(row) for row in group))
        if digest in union:
            raise ValueError('Unresolved self cycle cannot be merged away')
        for row in group:
            verified(row)
            row['ancestry_parents'] = sorted(union)
        merged.append({'sha256': digest, 'row_indices': indices,
                       'all_recorded_parents_retained': sorted(union)})
    guard(result, set(protected))
    return result, {'changes': changes, 'alternate_origin_groups': merged,
                    'input_rows': len(rows), 'output_rows': len(result),
                    'labels_changed': 0, 'row_occurrences_removed': 0,
                    'audio_changed': False, 'private_or_test_admitted': False}
