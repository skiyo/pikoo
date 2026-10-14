# Security policy

**English** | [简体中文](SECURITY.zh-CN.md)

## Supported versions

Pikoo is an unreleased development preview. Security fixes target the latest `main`; older snapshots are not supported production releases. The firmware baseline has not enabled Flash/NVS encryption or secure boot, and hardware acceptance remains pending.

## Report privately

Use GitHub's [Report a vulnerability](https://github.com/skiyo/pikoo/security/advisories/new) to report privately. Include the affected commit/component, reproduction steps, impact and a minimal sanitized example. Do not include real keys, device tokens, private recordings or household information. Do not publish exploit details in an issue before a coordinated fix. No response-time guarantee or bug bounty is offered.

If you exposed a credential, revoke or rotate it immediately; deleting a post does not revoke access. Provider/network incidents and memory timeouts without a security impact can be reported as sanitized bugs.

## Deployment boundaries

The simulator listens on loopback and checks Host/Origin. Do not remove those checks to expose it publicly. Device tokens are separate from provider keys; management access stays behind SSH. Protect configuration/state/backup files and use trusted TLS validation. Third-party dependencies retain their own security status: passing Pikoo tests is not a claim that all dependencies are vulnerability-free. See [server operations](server/README.md).
