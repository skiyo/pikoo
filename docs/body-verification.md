# Body control acceptance / 身体控制验收

Product version: 2.0.0. No IMU is included. Body control is tracked by commit and binary digest without a product-version bump.

## Candidate status

The source and release plan retain version 2.0.0. ESP-IDF 5.5.5 compilation and software checks passed. Deployment and audible acceptance of the latest per-step progress/multi-action changes are pending under a quiet-operation constraint.

The previously installed test binary used the temporary label 2.1.1 and SHA256 `f9b318771d090a955e5e5bfbd10c63a15d439d5c6098d153931ede970fcbee5a`. Hardware results below apply to that binary, not to the latest source. It has not been reflashed merely to change its displayed version. The published 2.0.0 release assets and tag have not been replaced.

## Measured hardware evidence

| Check | Result |
|---|---|
| Model arguments through the actual shared C++ executor | 30/30 direct synthetic text requests; 6/6 negated/quoted requests avoided mutation |
| Real microphone path on the installed candidate | 28/30 first-pass synthetic Chinese/English requests; each passing case had the expected result, exactly one write and a returned receipt |
| Two voice failures | One addressee classification did not accept the request; one connection ended before execution. No wrong action was applied in this batch |
| Spoken feedback snapshots | Ten private recent-history snapshots checked; no uncertainty/failure statement found after successful actions |
| Idempotency and memory stress | 128 unique call IDs plus an immediate same-ID relative retry passed; internal free RAM 79,315 to 79,307 bytes |
| USB controls | 25 checks passed, including volume, brightness 0/50/100%, expressions, unilateral blink, gaze expiry and microphone off/on |
| Muted standby endurance | 28,800.1 seconds, 3,831 observations; zero resets and zero audio RX/TX errors; microphone muted, upload/output inactive throughout |
| Preference reboot check | Gain -2 dB and brightness 100% retained |
| Upgrade preservation | Application digest checked; non-application partitions unchanged across each application flash |
| Recovery | Original 16 MiB Flash backup verified in 64 chunks and by local SHA256; private backup excluded from public artifacts |

The voice figures apply to the installed binary above. The latest candidate's changed progress/composite behavior still requires hardware voice acceptance. Preview images and tool receipts do not certify physical flicker, distortion, acoustic dB SPL or AEC.

## Latest candidate software checks

- ASan/UBSan body tests: bounds, full model argument validation, same-ID receipts, expiry, channel priority, persistence/hardware failures, both protocol schemas, compound multi-round steps and proof after a committed step crosses its deadline.
- Live routing tests: missing provider delegation fallback, late provider joining, ignored ambient speech, immediate verified progress.
- Existing Agent services: 18 passed. Python tools: 67 passed. Audio/session core and both eye renderers passed.
- Shared C++ preview generated for ten actions. Explicit unilateral blink overrides the automatic binocular blink.

## Remaining acceptance

Deploy the latest candidate after quiet-operation restrictions are lifted; run its microphone regressions and compound cases, negation/quotation, upper-limit feedback and disconnected-USB-reader checks. Verify physical sound/eyes and preserve non-test state. Two-hour/eight-hour mixed voice endurance has not been completed. The separate eight-hour muted standby run passed; it does not establish mixed voice endurance.
