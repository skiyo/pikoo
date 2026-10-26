# Contributing to Pikoo

**English** | [简体中文](CONTRIBUTING.zh-CN.md)

Pikoo is an open-source realtime voice AI Agent for families, currently in development preview. Contributions to documentation, original expressions, simulator behavior, board bring-up and tests are welcome. Open an issue before a major redesign or dependency upgrade so the approach can be discussed.

## A useful contribution

1. Fork the repository and use a focused branch.
2. Follow [Development](docs/development.md) and run `bash tools/check.sh` after installing dependencies.
3. Add meaningful regression coverage for behavior changes. Documentation-only edits need link/example review, not new tests that mirror prose.
4. Keep English and Chinese core documents in sync. Use the PR template to explain the problem, change, verification and remaining limitations.

Report the board/PCB revision, OS, versions, reproduction steps and sanitized errors for bugs. Distinguish simulation, synthesized audio, real microphone tests and real-board acceptance. Never turn a successful compile into a claim about AEC or child-voice accuracy.

## Licensing and privacy

Submit only work you have the right to contribute. Your intentional Pikoo code/documentation contributions are provided under Apache-2.0, consistent with the repository license; no separate CLA is currently required. Keep third-party licenses, copyright headers and modification notices. Document new dependencies and references in THIRD_PARTY.

Do not upload credentials, personal profiles, voice recordings, session transcripts, restricted datasets or model weights without documented publication rights. Use placeholders in examples. Model weights are intentionally absent from the current public tree; historic research models are not relicensed by code contributions.

Be respectful, keep discussions constructive and focus on reproducible behavior. Security reports belong in the [private reporting channel](SECURITY.md), not public issues. Maintainers review contributions before merging; there is no guarantee of a response time or release date.
