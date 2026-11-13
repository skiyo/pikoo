# Public repository quality

**English** | [简体中文](public-audit.zh-CN.md)

Public documentation describes the product, its interfaces and reproducible workflows. Examples use placeholders. Personal deployment details, private endpoints, credentials, device backups, recordings and user snapshots do not belong in source or release packages.

## Technical review

Run `python tools/check-public-repo.py` from the repository root. It checks tracked artifacts, placeholder secrets in examples, local Markdown targets and the model checksum set. CI adds redacted Gitleaks history scanning. Review findings without printing the matching secret. A clean result covers implemented patterns, not every possible private value.

Before publishing, inspect the exact tracked diff and archive file list. Ensure English/Chinese navigation and commands agree, binary downloads point to the intended release, and examples are structurally valid. Keep generated build outputs out of source commits. A private full-Flash backup remains private even if it is useful for reproducing a device failure.

## Licensing boundaries

Original source and documentation use Apache-2.0. Model weights have separate non-commercial terms; dependencies retain their own licenses. See [third-party attribution](../THIRD_PARTY.md), [model terms](../models/hi-pikoo/LICENSE.md) and the [publication record](../models/hi-pikoo/PERMISSION.md). Preserve those documents in redistribution.

`distribution-status.json` binds publication metadata to the model hash. The package tool checks the record and file integrity before creating model-containing artifacts. This does not grant a new commercial license or rights to redistribute raw training recordings. Non-commercial model terms are not an OSI open-source license.

## Review checklist

- Source and examples contain no personal credentials or data.
- All advertised capabilities map to implemented adapters/tools.
- English is the default; Chinese instructions describe the same configuration and behavior.
- Links, artifact names and checksums resolve to actual files.
- Software and hardware results identify their environment and limitations.
- License, source attribution and model terms accompany relevant assets.

[Security](../SECURITY.md) · [Release process](release.md) · [Contributing](../CONTRIBUTING.md)
