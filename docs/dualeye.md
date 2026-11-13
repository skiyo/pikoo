# Dual-eye display

**English** | [简体中文](dualeye.zh-CN.md)

Two circular 240 × 240 panels share the C++ renderer in `pikoo_eyes`. ESP and desktop use the same pose and pixel drawing code. Device lifecycle and output level drive expressions; preview-only poses never change Agent state.

Run the offline [eye preview](getting-started.md). It does not capture audio or contact providers. A slow browser receives the latest pose instead of an unbounded frame backlog. Hardware frame rate and transfer time must be measured on the target board.
