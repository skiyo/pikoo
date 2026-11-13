# Public repository checks

**English** | [简体中文](public-audit.zh-CN.md)

Original source and documentation use Apache-2.0. Model weights and third-party components have separate terms.

## Technical checks

`tools/check-public-repo.py` validates tracked artifacts, example placeholders, local Markdown links and model checksums. CI runs redacted Gitleaks history scanning. Never commit credentials, device backups, recordings or user data. A passing scan is not a guarantee that every possible secret has been detected.

## Model permission

The inference weights and training checkpoint are tracked in [models/hi-pikoo](../models/hi-pikoo/README.md). [ChildMandarin access terms](https://huggingface.co/datasets/BAAI/ChildMandarin) restrict distributing research derivatives outside a research group without written permission and do not expressly name trained weights. Publication permission is confirmed by the project maintainer and recorded in [PERMISSION.md](../models/hi-pikoo/PERMISSION.md). Availability in Git is not proof of clearance.

[distribution-status.json](../models/hi-pikoo/distribution-status.json) binds the status to the model hash. Packaging verifies the hash-bound permission record before producing model-containing artifacts. Source Apache-2.0 does not override upstream restrictions; non-commercial model terms are not an OSI open-source license. Retain [source attribution](../models/hi-pikoo/ATTRIBUTION.md) and dependency notices.

[Engineering verification](release.md) is separate from redistribution permission.
