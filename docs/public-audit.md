# Public repository audit

**English** | [简体中文](public-audit.zh-CN.md)

Review date: 2026-11-13. Technical hygiene checks pass; model redistribution permission is unresolved. This is not an unconditional clearance for every artifact in Git or an existing release.

## Checked and corrected

- Scanned 1,995 reachable historical file blobs for the project's known credentials without printing values: no matches. All four public branch histories were covered by the local objects plus 13 remote-only commit trees; no unknown blobs remained in those trees. Deleted remote objects, forks and caches are outside this scope.
- Gitleaks 8.30.1, verified against its official checksum, found one historical browser-storage namespace false positive. Only that exact fingerprint is documented in `.gitleaksignore`; the reviewed scan passes with full redaction.
- Checked tracked files for private configuration, NVS, full Flash images, recordings, model checksums and local Markdown links. Checked documentation images for EXIF metadata: none present. Public examples use placeholders.
- Removed the training downloader's forced third-party mirror and proxy overrides. It defaults to the official Hugging Face origin and respects the operator's network settings.
- The current `main` server lockfile had seven npm advisories, including three high severity. Safe dependency updates and a pinned MCP SDK 1.32.2 override reduce the npm audit to zero known advisories; all 68 server regression cases pass under Node 24.22.3 using temporary fake configuration and loopback fixtures. These checks do not call cloud APIs or audio devices. The new Agent branch removes that server and audits its independent simulator dependency tree separately: zero npm advisories.
- Added `tools/check-public-repo.py` and a full-history redacted CI scan. This is a technical gate; its output reports model clearance separately. Runtime regression counts are recorded independently in the release documentation.

## Model redistribution is pending

[ChildMandarin's published access conditions](https://huggingface.co/datasets/BAAI/ChildMandarin) limit use to academic/educational non-commercial research and restrict distributing research derivatives beyond a research group without written permission. They do not explicitly name trained weights. No written authorization for publishing the current weights has been obtained. We therefore cannot conclude that public redistribution of the checkpoint, inference weights or firmware embedding them is cleared.

[distribution-status.json](../models/hi-pikoo/distribution-status.json) records the affected model hash. `tools/package-release.py` refuses public model/firmware packaging until documented clearance exists for that hash. Source Apache-2.0 and the project's non-commercial model notice cannot override upstream conditions. Non-commercial model terms are not an [OSI open-source license](https://opensource.org/osd).

Resolving this requires written authorization covering model distribution, or retraining and validating a replacement using sources with documented compatible rights. The current binaries and existing release assets have not been silently deleted or history-rewritten by this review. Removing current files alone would not remove earlier Git objects or release downloads. A coordinated withdrawal would need to cover those locations as well.

## Firmware acceptance is separate

The new service-configurable architecture remains on its development branch pending real-board resource checks. Prior firmware's physical tests do not certify the new architecture. No device was connected, flashed, recorded or played during this review. No new release or version tag was created.

## Repeat the technical checks

```sh
python3 tools/check-public-repo.py
python3 -m unittest discover -s tools -p test_public_repo.py
gitleaks git --redact=100 --log-opts=--all
# From each directory that contains a package-lock.json:
npm audit --omit=dev --ignore-scripts
```

Check both this report and the model status before describing the entire repository as cleared for redistribution. Retain upstream copyright, source/model terms and release-specific binary dependency notices.
