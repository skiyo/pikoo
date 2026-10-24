"""All declared immediate recording ancestors, including alternate origins."""


def parents(row):
    extra = row.get('ancestry_parents', [])
    if not isinstance(extra, (list, tuple)) or any(not isinstance(key, str) or not key for key in extra):
        raise ValueError('Alternate ancestry must be a list of nonempty recording identities')
    values = {row.get('parent_sha256'),
              (row.get('augmentation') or {}).get('parent_sha256'), *extra}
    return values - {None, ''}
