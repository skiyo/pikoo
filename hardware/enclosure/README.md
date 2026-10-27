# Pikoo cat enclosure files

**English** | [简体中文](README.zh-CN.md) · [Project](../../README.md) · [Website](https://pikoo.lol/)

Three printed parts house the Waveshare ESP32-S3-DualEye-LCD-1.28 with its original transparent backplate and screws intact. Part 01 integrates the cat face, base and carrier; no separate spring latch or muzzle panel is needed. The STL bytes are identical to the original household delivery.

**Physical feedback, 2026-10-27: the project family reports successful printing, assembly verification and use at home.** This is owner-reported evidence. Dedicated drop tests, 20 opening cycles, 60-minute operation and slicer statistics were not individually reported. Use the checklist for each new printer/hardware combination.

## The three original STLs

| File | Function | Print envelope, millimetres X × Y × Z |
|---|---|---|
| [01_main_body.stl](stl/01_main_body.stl) | Integrated cat face, base and carrier | 110.00 × 102.60 × 52.97 |
| [02_rear_cover.stl](stl/02_rear_cover.stl) | Removable thick rear cover | 109.85 × 60.30 × 33.60 |
| [03_rotary_lock.stl](stl/03_rotary_lock.stl) | Quarter-turn mechanical cover lock | 26.00 × 26.00 × 31.80 |

Open a file for the GitHub preview, then use **Download raw file**. Cloning the repository also retrieves the files directly; no ZIP is required.

## Instructions and records

- [Illustrated printing, support removal, assembly and acceptance guide](guide.html): download the raw HTML and open it in a browser. English and Chinese text, diagram callouts and illustrations are embedded in this single offline file.
- [Acceptance checklist CSV](acceptance-checklist.csv): a blank Chinese worksheet for each new build. Its initial “未验证” entries are unfilled checks, not a withdrawal of the family’s report above.
- [Dimensions, SHA-256 and evidence scope](manifest.json), plus [file checksums](checksums.sha256).

Use the **English / 中文** button at the top to switch in place. A saved choice takes priority over browser language; HTTP(S) uses the `pikoo_language` cookie and a local-storage fallback also supports offline files. If storage is blocked, switching still works for the current page. Switching preserves checklist entries and notes. Printing uses the current language; JSON keeps stable checklist IDs and your original notes, and records the selected language. Its filename is `pikoo-acceptance.json` in both languages. No translation service or network request is needed.

For changes to this guide, run `node --test hardware/enclosure/tests/guide.test.cjs` from the repository root. The checks cover language selection, blocked storage, legacy record recovery, diagram translation coverage and JSON export; they do not perform hardware acceptance.

## Print settings and order

Print **03 rotary lock → 01 integrated main body → 02 rear cover**, one STL per run. Part 03 remains in the finished assembly.

Designed around X-MAKER JOY AI+, PLA and a 0.4 mm nozzle. Select **fine quality, all supports, millimetres and 100% scale**. Keep the supplied orientation; disable auto scaling/reorientation. The original setup uses no raft. A brim differs from a raft: confirm all added brim/support margins fit inside the 120 × 120 mm bed. Inspect your slicer preview for actual toolpaths, time and material; these statistics have not been recorded here.

Allow the bed and print to cool. Remove supports in small pieces as illustrated, keeping the structural ledges, guides and lock receiver intact. Stop if a lock lug, ear root, eye frame or receiver cracks or whitens.

## Assemble and verify

1. Check cover guidance and lock insertion/rotation with an empty enclosure first.
2. Insert the complete dual-eye module from the rear of 01, retaining the original backplate/screws. Structural edges rest on the ledges; the display glass must not carry clamping force. Reference input: approximately 10 mm module thickness, approximately 11 mm including screw heads.
3. Use the speaker’s original adhesive on its complete rear housing to attach it to the lower flat pad, with the sound face rearward. No additional adhesive fastener is used for enclosure/module retention.
4. Fully insert USB, leaving its rigid strain relief straight and allowing the flexible cable to turn rearward naturally. Reference connector: 10 mm wide and 28 mm rigid body excluding the metal plug. Keep USB and the short speaker wire clear of seams and guides.
5. Fit 02, then insert 03 and turn approximately 90° to lock. **01 supports the module; positive mechanical retention requires both 02 and 03. Do not invert an open 01 to test retention.**

With power off, support the assembly over a soft surface and verify that the cover cannot pull off, the module cannot rattle against glass, the four feet sit steadily and the cable is not pulling on USB. Target at least approximately 5 mm flexible-cable clearance above the table. Power up and check both displays, buttons, playback, capture, wake and supply stability. Use the illustrated guide/checklist for detailed stop criteria.

To open, disconnect power, support the module/cover, reverse the lock approximately 90°, remove it and lift the cover along its guides without pulling the speaker wire. Inspect after impacts; household fit/use feedback is not a drop-resistance certification.

Pikoo-authored enclosure files and instructions follow the repository’s [Apache-2.0 license](../../LICENSE). No supplier CAD or reference hardware meshes are included; obtain board references from [Waveshare](https://www.waveshare.net/shop/ESP32-S3-DualEye-LCD-1.28.htm).
