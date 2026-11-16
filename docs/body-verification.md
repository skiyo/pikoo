# Body control acceptance / 身体控制验收

Product version: 2.0.0. No IMU is included. Body control is tracked by commit and binary digest without a product-version bump.

## Candidate status

The source, installed application and release plan retain version 2.0.0. The direction-corrected application SHA256 is `2815ddde2db691b6897533d721959f82b5f753c547787d4d2b82734eb3a448c3`. Its application digest was verified after flashing, and every non-application partition digest remained unchanged. Full local software checks and ESP-IDF 5.5.5 compilation passed.

On-device observation identified reversed left/right winks and horizontal gaze in the earlier candidate. The installed correction swaps the commanded blink side and reverses horizontal gaze at the board rendering boundary. A dedicated board-mapping regression covers both directions and unchanged vertical/opening values. Directions follow the user's view facing the screens. An earlier targeted revision passed 3/6 cases (Chinese/English 50% volume and Chinese dimming passed; English dimming and two left-wink cases had no applied receipt). A separate English dimming diagnostic queued a provider delegation but received no interaction-decision event, and the delegation expired. Subsequent revisions passed 5/6 targeted cases; one encountered a transport failure and another lacked an interaction decision. These subsets do not establish acceptance. The latest continuous-session microphone batch completed 11/11 cases successfully and was then stopped at the user's request to avoid repetitive testing. This is a partial batch, not a completed 30-case acceptance result. The 4 compound / 6 negative-or-quoted voice batches were not completed on this exact binary. The revision also holds early provider body delegations until the 2.5-second quiet boundary, keeps trailing transcript fragments across that window, and routes English eye requests such as "dim your eyes". A split-transcript test verifies that an early provider delegation cannot dispatch before the trailing phrase arrives.

Earlier measurements below apply to the previous test application, labelled 2.1.1 (SHA256 `f9b318771d090a955e5e5bfbd10c63a15d439d5c6098d153931ede970fcbee5a`). Its logical receipts did not establish physical left/right correctness. The existing published 2.0.0 release assets and tag have not been replaced.

An intermediate direction-only build failed acceptance: 10/16 completed synthetic voice cases passed before the run was stopped. Failures included unexecuted requests and an incorrect percentage; an eye request also received success wording without an action receipt. These results are retained and are not counted as an accepted 30-case run.

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

The earlier voice figures apply to the previous binary identified above. Fresh microphone and compound-action results are required for the direction-corrected binary. Preview images and tool receipts do not certify physical flicker, distortion, acoustic dB SPL or AEC.

The current revision also preserves coalesced transcript prefixes, rejects stale out-of-order decisions, and retains ignored negation/quotation tails as context without granting new authorization. This follows the [Live transcript-trigger delivery contract](https://developers.openai.com/api/docs/guides/decisions-voice#react-to-transcripts). Inference transport failure receives at most one same-request retry within the original deadline; cancellation and HTTP errors are not retried. Fault injection verifies those limits. The acoustic harness rejects muted Mac output, uses a five-second connection warm-up after wake and checks actual playback-level silence; continuous silent network audio packets do not prevent readiness, and keeps periodic mute/export/unmute stress opt-in via `--snapshot-every`. Negative cases require decision evidence and an active, unmuted conversation, in addition to zero writes.

## Latest candidate software checks

- ASan/UBSan body tests: bounds, full model argument validation, same-ID receipts, expiry, channel priority, persistence/hardware failures, both protocol schemas, compound multi-round steps and proof after a committed step crosses its deadline.
- Live routing tests: missing provider delegation fallback, late provider joining, ignored ambient speech, immediate verified progress.
- Existing Agent services: 18 passed. Python tools: 67 passed. Audio/session core and both eye renderers passed.
- Shared C++ preview generated for ten actions. Explicit unilateral blink overrides the automatic binocular blink.

## Remaining acceptance

The latest candidate is installed as version 2.0.0. Remaining checks include the uncompleted microphone cases, compound/negative voice cases, physical sound/eyes, upper-limit feedback and disconnected-USB-reader checks. Two-hour/eight-hour mixed voice endurance has not been completed. The separate eight-hour muted standby run passed; it does not establish mixed voice endurance. Testing was stopped by request. Keep the completed results and use targeted validation for actual changes or new failures; do not automatically repeat completed acoustic batches.
