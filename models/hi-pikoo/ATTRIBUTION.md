# Wake-model sources and attribution

This inventory describes the current 1.0.0 weights. No original or generated training audio is distributed.

| Source | Use | License / terms |
|---|---|---|
| [ChildMandarin, BAAI](https://huggingface.co/datasets/BAAI/ChildMandarin) | Real Chinese children's ordinary-speech TRAIN negatives; not target-phrase recordings | CC BY-NC-SA 4.0 plus the published gated academic/non-commercial access conditions |
| [LibriSpeech, Panayotov et al.](https://www.openslr.org/12) | English ordinary-speech TRAIN negatives, train-clean-100 | CC BY 4.0 |
| [ESC-50, Karol J. Piczak](https://github.com/karolpiczak/ESC-50) | Environmental sound TRAIN negatives | CC BY-NC 3.0; preserve original source-specific notices |
| Public speech excerpts | Reviewed ordinary-speech negatives | Source-specific rights; no source recordings redistributed and no blanket rights claim |
| [OpenAI speech generation](https://openai.com/policies/terms-of-use/) | Reviewed synthetic target phrases and confusables | Provider terms; synthetic, not recorded children |
| [Google Gemini speech generation](https://ai.google.dev/gemini-api/terms) | Reviewed synthetic target phrases | Provider terms; synthetic, not recorded children |
| [Qwen3-TTS VoiceDesign](https://github.com/QwenLM/Qwen3-TTS) | Local text-only synthetic childlike TRAIN phrases | Apache-2.0 model/code; preserve output-source provenance; no reference family voice |
| [microWakeWord](https://github.com/OHF-Voice/micro-wake-word) | Streaming layers / conversion dependency | Apache-2.0; separately installed |

The core prepared TRAIN grouping contains 2,940 legacy positive windows, 2,440 legacy negative windows, 1,268 ChildMandarin, 2,640 LibriSpeech, 1,200 ESC-50 and 424 public-speech windows. Reviewed additions and tempo descendants are present; window counts are not independent speakers or original recordings. Family recordings were not used for training, augmentation, calibration or model selection.

ChildMandarin citation: Jiaming Zhou, Shiyao Wang, Shiwan Zhao, Jiabei He, Haoqin Sun, Hui Wang, Cheng Liu, Aobo Kong, Yujie Guo and Yong Qin. *ChildMandarin: A Comprehensive Mandarin Speech Dataset for Young Children Aged 3–5*. [Paper](https://aclanthology.org/2025.acl-long.614/), 2025; [original preprint](https://arxiv.org/abs/2409.18584), 2024.

ESC-50 citation: Karol J. Piczak. *ESC: Dataset for Environmental Sound Classification*, ACM Multimedia, 2015. LibriSpeech citation: Vassil Panayotov, Guoguo Chen, Daniel Povey and Sanjeev Khudanpur. *LibriSpeech: An ASR corpus based on public domain audio books*, ICASSP, 2015.

Attribution does not establish a blanket permission to redistribute datasets or a commercial license for the weights. See LICENSE.md. Synthetic childlike voices are not evidence of real-child wake accuracy.
