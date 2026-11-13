# Dual-eye display

**English** | [简体中文](dualeye.zh-CN.md)

Two circular 240 × 240 panels share the C++ renderer in `pikoo_eyes`. ESP and desktop use the same pose and pixel drawing code. Device lifecycle and output level drive expressions; preview-only poses never change Agent state.

Run the offline [eye preview](getting-started.md). It does not capture audio or contact providers. A slow browser receives the latest pose instead of an unbounded frame backlog. Hardware frame rate and transfer time must be measured on the target board.

## Preview and board validation

## Run the preview

```sh
(cd firmware/simulator && npm ci --ignore-scripts)
bash tools/start-dualeye.sh
```

Open `http://127.0.0.1:8793/dualeye`. Use state/expression controls to compare idle, listening, thinking and speaking poses. English is the default UI; use its language control for Chinese. Stop with Ctrl+C or `bash tools/stop-dualeye.sh`. The preview runs locally and uses no microphone, speaker or model key.

## Change expressions carefully

Keep pose/state mapping separate from provider messages. A decorative expression does not confirm network readiness or a saved tool action. Check both panels, clipping at the circular boundary and transitions at different expression intensities. Use the shared renderer to avoid platform drift.

For hardware, verify brightness, orientation and SPI timing with audio running. Set orientation through USB (`rotate 90` / `rotate 270`) and restart to check persistence. Browser smoothness cannot establish the panel frame rate; collect board timing and heap/queue metrics separately.
