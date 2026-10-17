# “你好皮酷”训练与中文童声

目标是普通话本地唤醒，不识别家庭成员。当前公开文件树不分发模型权重，保留历史模型卡及汇总结果；早期公开基线为合成普通话实验模型，**真实童声样本数为 0**。不能用合成音色的成绩声称儿童唤醒已经达标。

家庭真人录音按用户要求仅用于独立评估：不参与训练、训练增强、量化校准、阈值调整或候选模型选择。新采集的独立测试录音放在单独的私密清单，标记 `split=test`、`evaluation_only=true`，冻结模型及阈值后再评分。`train.py` 在读取音频和加载特征缓存之前拒绝包含 `evaluation_only` 的清单。此前已查看得分的诊断录音只能标为诊断回归，不能重新宣称为全新盲测；所有家庭录音仍仅保存在本机，不提交 GitHub。

## 当前私密候选：V7B（2026-10-17）

V7B 在固定 0.90 阈值下，流式验证命中 44/46、负样本误触发 0/455，其中真实中国儿童普通讲话为 0/390。选定并冻结模型后，单独封存的六段成人录音命中 3/3，非唤醒词误触发 0/3；原始四秒录音及预先规定的三秒安静前缀条件分别报告，不合并成更多独立样本。这些录音没有进入训练、调参、量化或选模型。模型仍为 45,128 字节 INT8；静态兼容和主机 Micro/参考内核一致性通过。**这不代表板上 20 次真人唤醒、儿童目标词或长期误唤醒已经通过。**

增量语料为 88 条经整批标签审核的 Google 合成录音及 502 条真人普通话负样本，另有 28 条 Google 录音被整批剔除。训练保留 6,337 条真实儿童负样本，验证保留 390 条；合成童声单独标记。V7A 曾有 3 条儿童误触发，依据验证结果被淘汰；V7B 冻结后不再按家庭测试调参。摘要和哈希见 [实验记录](reports/wake-v7b-summary.json)。所有权重及音频仍仅在本机。

## 第 5 版历史基线与实机更正

**2026-10-17 实机更正：V5 真人唤醒未通过。** 成人用户反馈多次呼叫完全没有反应；模型正在计算不等于已经可用。已用设备采集验证特征提取与桌面逐项一致，稳定特征流的设备推理与桌面参考结果也一致。合成文件的离线成绩不能覆盖麦克风、房间声学和连续待机上下文的差异。当前正在试验完整 PCM 环境声上下文训练，尚未宣称修复；实测记录见 [设备验收](../docs/device-validation.md)。

`train.py --pcm-context` 将完整预测窗口的前后文从带低幅噪声的 PCM 提取，避免短正样本前方只使用全零特征填充。它是显式选项，历史训练默认保持不变。`--resume-weights` 可加载相同结构的本机权重继续训练，并在报告记录来源摘要。候选仍须完成流式评估、负样本回归和真实设备验证；不能用训练分数替代验收。

第 5 版在本机保留，模型 **45,128 字节**，仍低于 64 KiB 预算。正常音量合成留出测试 **52/54**，低音量 **52/54**，20dB 白噪声 **51/54**，10dB 白噪声 **39/54**，单次回声 **53/54**。每种条件下，168 条合成普通讲话/近似词和 410 条真实儿童普通讲话均未误触发。不同条件共享原始录音，不能合并成独立样本或换算成每小时误唤醒率。较强噪声仍漏唤醒，真人家庭和实板尚未验收。

本轮修正了正样本结束对齐，把窗口扩展至 399 帧（约 4 秒）、采用 6 层时间卷积，并加入负样本的因果前缀，抑制一句话未说完时提前触发。原有失败集已视为开发数据；第 4 版曾在小留出集很好，但扩大开发回归有 15/197 误触发，因此被替代。第 5 版在这批开发集上命中 74/77、误触发 0/197；这个成绩不作为盲测。

训练音色七种，验证 Sandy，测试 Shelley 与 Rocko（包括剔除旧 Rocko 训练录音）。儿童数据训练/验证/测试分别为 6,337 / 390 / 410 条，说话人与波形互斥。第 4 版测试结果见过后退为回归数据；第 5 版使用新语速、前后文、168 条更丰富负样本，候选仅按验证结果选定，冻结模型和清单哈希后评分。

桌面默认优化算子与 Micro 参考内核曾出现分数差异。现统一使用 TensorFlow Lite `BUILTIN_REF`、float32 和设备相同的半值向外取整量化，重新评分所选模型；权重和 0.90 阈值保持不变。6 组相同特征流的参考/Micro 分数与 3 次重置检查通过；Micro arena 主机使用 21,712 字节，ESP32-S3 编译通过。ESP-NN 内核的实机表现仍需到板检查。

复现本轮数据和训练（授权录音路径保持私密）：

```sh
python training/prepare_iteration.py --output training/data/iteration-v2 \
  --children training/runs/childmandarin-v1/children/manifest.json \
  --original training/data/synthetic/manifest.json --challenge training/runs/self-test-v1/manifest.json
python training/prepare_followup.py --previous training/data/iteration-v2/manifest.json \
  --challenge training/runs/self-test-v1/manifest.json --output training/data/iteration-v5
python training/train.py --upstream training/vendor/micro-wake-word \
  --manifest training/data/iteration-v5/manifest.json --output training/runs/iteration-v5 \
  --epochs 35 --window-frames 399 --positive-repeats 8 --negative-repeats 4 \
  --hard-negative-repeats 16 --min-snr 5 --negative-prefixes \
  --filters 32 --first-filters 24 --kernels 5,9,13,21,31,43 --defer-test
```

`evaluate_iteration.py` 显式选择 validation 或 test；候选选择阶段只用 validation。测试只在选定候选之后执行，完整结果记录来源、条件与模型 SHA-256。`verify_micro_parity.py` 校验与固件同版本 Micro 参考内核的实际分数；仅编译成功不代表正确识别语音。已使用的挑战集通过 `self_test.py --development-set` 标为开发回归，不能冒充新的盲测。

本机当前试用页为 `http://127.0.0.1:8793/wake-test`，依然需要爸爸、妈妈、两个孩子各自实测。受限儿童录音与衍生权重、含权重的固件不上传公共仓库。

## 数据来源与准入

| 来源 | 用途 | 当前状态 |
|---|---|---|
| macOS 本地普通话合成声音 | 打通特征、训练、INT8 转换和设备集成 | 已训练；音频不提交 |
| [Google Gemini TTS](https://ai.google.dev/gemini-api/docs/speech-generation) | 补充多音色目标词、近似词和合成童声；按音色互斥划分 | 本机实验生成；内容核对、切分和负样本回归通过后才进入候选训练 |
| [PolyAI MInDS-14 zh-CN](https://huggingface.co/datasets/PolyAI/minds14) | 真实普通话普通讲话负样本 | 固定提交 `40ce77cb32a384e4d50a568e1ec39ac804019d33`；502 条；CC-BY-4.0；缺少说话人/年龄编号，只用于训练 |
| [BAAI/ChildMandarin](https://huggingface.co/datasets/BAAI/ChildMandarin/blob/main/README.md) | 3–5 岁真实普通话儿童声学分布、普通聊天负样本 | 已授权下载并校验；7,137 条样本完成私密候选训练、流式评估及固件构建 |
| [ChildTalk](https://github.com/NKU-HLT/ChildTalk) | 后续更丰富的儿童/照护者场景 | 备选，未取得、未训练 |
| 家庭真人短句 | 独立测试目标词和普通讲话，不用于模型开发 | 已采集成人测试录音，单独封存；儿童目标词尚未实测；仅本地保存 |

ChildMandarin 官方说明：397 名 3–5 岁儿童、约 41.25 小时，16kHz WAV，训练/开发/测试说话人分别为 317/39/41。它需要申请，附有非商业研究和禁止转发等限制；不要通过镜像绕过访问门槛，也不要将原始录音或其衍生模型直接发布到公共仓库。数据卡的许可证标签不能代替完整使用条款。普通儿童聊天主要是负样本，并不自动提供目标唤醒词正样本。

不将成人变调、合成“童声”、中国儿童朗读英语、韩语儿童录音冒充真实普通话童声。“你好皮裤”“你好皮库”与目标近乎同音，不标成必须区分的负样本；“你好皮球”等不同发音可作困难负例。

## Google 多音色与真实普通话增量

`generate_google.py` 显式支持官方有免费层的 3.8 Flash TTS、3.8 Flash-Lite TTS、3.1 Flash TTS Preview 和 2.5 Flash Preview TTS。2.5 Pro Preview TTS 当前官方价格页没有免费层，不自动调用。实际可用额度以项目返回为准；分钟限额可以降低频率，日限额需要等待重置。不会升级计费或自动切换模型。各模型使用不同输出目录，可利用已验证缓存续跑；密钥只从私密文件读取，不放在参数值或日志中。

```sh
python training/generate_google.py \
  --key-file /private/google.env --output training/data/google-local \
  --model gemini-3.1-flash-tts-preview --batch-voices --interval 30 --limit 80 \
  --voices Kore Puck Autonoe Leda Achernar Charon Fenrir Orus Aoede Zephyr \
  --childlike-voices Leda Orus Aoede Zephyr Achernar
python training/review_google_corpus.py \
  --manifest training/data/google-local/manifest.json \
  --key-file /private/google.env --output training/data/google-local/review.json \
  --model gemini-2.5-flash --interval 15
```

可选 `--proxy` 仅作用于本次调用；不更改系统代理。3.8 使用 Interactions API，旧 TTS 使用 `generateContent`；都转换成经过抗混叠处理的 16kHz PCM16。`--items-per-voice 4` 可缩小批次。按长停顿切分，数量不符的批次整批弃用；自动转写只审核生成语音，不读取家庭录音。转写核对仍可能出错，不等于真人审听或唤醒验收。训练合并器在一个批次任一标签不符时丢弃整个批次，避免漏读使后续标签错位。

真实普通话增量使用 `requirements-data.txt` 的可选 PyArrow 导入器：先经命令行、固定版本和 LFS SHA-256 核对下载，再执行 `import_minds14.py --parquet /private/minds14-zh.parquet --sha256 EXPECTED_LFS_SHA256 --output training/data/minds14-zh`。保留 8kHz 电话频带来源，不将重采样说成新增高频信息。`prepare_google_iteration.py` 合并授权源、按音色限制历史 Mac 正样本占比，并用私密哈希排除清单拒绝家庭测试录音；新测试集不进入模型选择。

## 环境与训练

使用 Python 3.11。上游训练代码固定提交，避免默认分支变化：

```sh
python3.11 -m venv training/.venv
training/.venv/bin/pip install -r training/requirements.txt
mkdir -p training/vendor
git clone https://github.com/OHF-Voice/micro-wake-word.git training/vendor/micro-wake-word
git -C training/vendor/micro-wake-word checkout 4665173cd35f1cff9a61e06fc427f124766c488e
# 下面的语音生成器使用 macOS say/afconvert，其他系统直接导入有许可的 WAV。
training/.venv/bin/python training/generate_synthetic.py --output training/data/synthetic
training/.venv/bin/python training/train.py \
  --upstream training/vendor/micro-wake-word \
  --manifest training/data/synthetic/manifest.json \
  --output training/runs/my-model
training/.venv/bin/python training/evaluate.py \
  --model training/runs/my-model/nihao_pikoo.tflite \
  --manifest training/data/synthetic/manifest.json \
  --output training/runs/my-model/streaming-report.json
```

特征为 16kHz 单声道 PCM16 → 30ms 窗、10ms 步长、40 维 microfrontend 特征。MixedNet 每 3 帧推理一次，5 次滑动平均，实验阈值 0.90。先按说话人/录音组划分数据，再增强；缓存用清单和音频内容哈希校验。训练集可增加噪声、混响、语速和音量变化。独立测试集不参与训练和阈值选择。

训练输出含受限数据时 `report.json.restricted_data=true`，不得将模型复制到公开目录。早期合成权重已从当前分支移除，历史提交仍有权重且未授予 Apache-2.0 模型许可；本机副本保留。后续模型需明确训练及发布授权。历史实验模型见 [模型卡](models/MODEL_CARD.md)。

## 导入真实中文童声

### ChildMandarin 固定版本下载及本地任务

已验证的下载客户端为 `huggingface_hub==2.2.0`（提供 `hf` 命令）。先通过数据集访问审批，再把只读 Token 存入本机权限为 `600` 的私密文件；不要把 Token 写在命令行参数、仓库或文档里。

```sh
export HF_TOKEN_PATH=/private/huggingface-read-token
export HF_HOME=/private/huggingface-cache
bash training/download_childmandarin.sh
```

脚本设置 `HF_ENDPOINT=https://hf-mirror.com`、禁用 Xet 并清空该进程的代理环境变量。**这不保证绕过系统 TUN**：实际检查发现大文件会重定向至 `us.aws.cdn.hf.co`。若使用透明代理，应为镜像及实际存储域名配置 DIRECT，并检查连接记录；不能仅凭环境变量认定没有消耗代理流量。断点文件保留在忽略目录内。

固定版本的三个包已逐一校验 SHA-256。训练包有 1 条 JSON 标注缺少同名 WAV；流水线只在精确版本的大小和 SHA-256 均匹配后启用 `--skip-missing-audio`，将其排除并写入导入报告。通用导入默认仍拒绝缺失音频，避免把损坏下载静默当作正常数据。

目前固定版本为 `67a5579247989e071911b2e8d72952c2afd43ca3`，三包共 4,792,374,272 字节。下载完后运行：

```sh
cmake -S training/micro_check -B training/runs/micro-check-build
cmake --build training/runs/micro-check-build -j 4
python training/run_childmandarin.py \
  --archives training/data/childmandarin-original/new_data \
  --permission-record /private/dataset-permission.json \
  --upstream training/vendor/micro-wake-word \
  --micro-check training/runs/micro-check-build/pikoo_micro_check \
  --output training/runs/childmandarin-v1
```

Micro 检查依赖已由 ESP-IDF 固定并下载的 `esp-tflite-micro@1.4.1` 组件，先按固件文档完成配置。任务保留原始官方 train/dev/test 划分，按说话人固定哈希抽样（训练每人最多 20 条，验证/测试每人最多 10 条）。读取随 WAV 附带的 JSON 年龄和 speaker 元数据，拒绝说话人跨集合、危险归档路径和音频格式错误；排除目标词及同音词。年龄、时长、文件哈希和实际去重数量写入私密导入报告。

训练继续采用小型 MixedNet；真实儿童普通讲话作为负样本，长负样本在训练时随机取窗，最终流式评估覆盖所选完整录音。固定 0.90 阈值比较公开基线与私密候选模型，不按测试结果反复调整阈值。`job-status.json` 记录任务阶段，`comparison.json` 记录按来源、年龄分组的结果；未完成时不能视为通过。任务不自动替换公开模型，不发布童声录音或衍生权重。

### 通用人工审核导入

先由数据使用者取得访问权并下载到本机私密目录。按官方工具解包，保存完整许可/授权记录。审核音频与元数据，建立 `child-index.example.csv` 格式的私密索引，保留官方 speaker 和 split 映射；不要凭文件名猜测孩子身份或年龄。

```sh
python3 training/import_children.py \
  --root /private/authorized-child-data \
  --index /private/child-index.csv \
  --source ChildMandarin \
  --permission-record /private/dataset-permission.txt \
  --output training/data/children
python3 training/merge_manifests.py \
  training/data/synthetic/manifest.json training/data/children/manifest.json \
  --output training/data/combined/manifest.json
```

随后将训练和评估的 `--manifest` 换成合并后的清单。导入器拒绝目录逃逸、错误采样格式、跨集合重复录音、说话人泄漏、错误语言和唤醒同音词的负标签。输出使用匿名 speaker ID，保留年龄、来源、场次、真实童声标记和使用限制。评估输出按年龄、说话人、来源分别计数；只有负样本的组不会伪造“唤醒召回率”。大量语料先抽取每个孩子相近数量的短句，避免某位说话人支配训练。

家庭个性化阶段另外保留跨录制日期的盲测集，不能把同一段音频增强后分别放入训练和测试。当前训练器采取更严格的说话人互斥规则；个性化训练需要增加单独的“家庭跨场次评估”配置，不能偷偷绕过检查。

## 家庭录音安排（尚未执行）

### 先用电脑做四人实测

本机模拟器的 `/wake-test` 是独立唤醒测试页，不连接远程对话接口。通过 `PIKOO_WAKE_MODEL` 指定私密模型，`PIKOO_WAKE_LABEL` 设置可读名称；页面核对实际推理进程返回的模型 SHA-256，防止测错版本。成人 A、成人 B、儿童 A、儿童 B 分开计数，不从声音推断身份。

开启麦克风后，选择测试者并启动 20 轮引导测试：每轮 4 秒说话窗口、2 秒间隔，1 米处用平常音量说一次“你好皮酷”。每个人独立目标为 18/20。普通聊天模式累计时长与误触发次数。麦克风不录文件，结果导出只有角色编号、分数、时间与计数；刷新前由用户保存。页面转入后台会中止当前测试，未结束的唤醒轮次不计分。

首个私密候选的流式盲测：410 条儿童普通讲话负样本中，误触发从基线的 30 条降至 1 条；390 条验证负样本从 18 条降至 0 条。但合成唤醒词验证集仅 5 条，命中由 4/5 降至 3/5，合成测试集仍为 5/5。结果提示可能变得更保守，不能只宣传误触发下降。成人与儿童的真人目标词尚未验收，也没有通过 8 小时连续背景声测试。

### 新生成语音自测：当前版本效果未达交付要求

`self_test.py` 使用 macOS 本地合成生成五种音色、四档语速、孤立/停顿/带前后句的目标词，以及普通讲话和近似词。Tingting、Meijia 的音色名称此前未出现。300 条生成结果中有 6 条与旧语料波形完全相同（接近的语速参数可能生成相同波形），按 SHA-256 排除后，实际评分为 77 条正样本、197 条负样本；另 20 条同音词仅诊断，不进入误唤醒判定。每个条件下，主评分波形互不重复。五种数字扰动共享原始音频，不视为独立说话人。

2026-10-13 固定阈值 0.90、未调整模型，当前候选在正常条件下仅命中 **30/77**（原版 **39/77**），两者均误触发 **4/197**。候选在两个新音色中仅命中 **3/32**；带“你好，皮酷”停顿的说法 **0/20**；低音量 **26/77**，20dB 白噪声 **29/77**，10dB 白噪声 **15/77**，单次回声 **28/77**。这揭示了目标词音色和停顿覆盖不足；编译、内存检查通过不代表唤醒效果通过，当前模型不能作为稳定唤醒模型交付。

```sh
python training/self_test.py \
  --candidate training/runs/childmandarin-v1/model/nihao_pikoo.tflite \
  --baseline /private/retained-baseline.tflite \
  --output training/runs/self-test-v1
```

生成的录音及详细结果保持在本机。后续训练若使用这批失败样例，就应把它们视为已见数据，另建新的盲测集。仍需真人成人及儿童的目标词测试，不能把合成音色当作家庭成员。

### 后续采集（需用户主动录制）

先用成人录音验证流程。孩子愿意参与时，每人每次约 2–3 分钟：自然说“你好皮酷”，换语速、音量和 0.5/1/2 米距离，每次少量短句，中间留安静间隔；另录自然聊天和“你好皮球”等近似词。不同日期、房间和录制设备分开记录。两个孩子分别统计，不合并成一个儿童平均值。录音用匿名编号，不把姓名写入文件名，默认不上传任何平台。

最终验收仍需每人 1 米 20 次至少 18 次成功，以及 8 小时家庭背景声误唤醒不超过 1 次。短片段误触发率不能换算成已经通过 8 小时测试。

## ESP32 模型预算与验证

训练数据大小不等于部署模型大小。每次导出必须通过 `check_esp32_model.py`：模型不超过 **64 KiB**，输入为 INT8 `[1,3,40]`，输出为单个量化概率，不含浮点张量，所有算子均已在固件注册。固件构建也执行 64 KiB 上限检查。

2026-10-13 对现有公开合成基线实测：文件 **25,128 字节**；同版本 TFLM 的主机参考实现完成 **300 次推理、3 次重置**，主机 tensor arena 使用 **13,088 字节**；ESP32-S3 交叉编译通过，应用二进制 **3,111,488 字节**（6 MiB 应用分区仍余约 51%）。这些不是板上内存/延迟测量；固件仍预留 256 KiB arena，ESP-NN 内核、PSRAM、音频及显示的并行峰值需实机确认。

```sh
python training/check_esp32_model.py --model /private/nihao_pikoo.tflite \
  --output training/runs/esp32-static-check.json
training/runs/micro-check-build/pikoo_micro_check /private/nihao_pikoo.tflite
# 用私密候选编译，无需覆盖或提交公开模型：
idf.py -C firmware -B /private/pikoo-firmware-build \
  -DPIKOO_WAKE_MODEL=/private/nihao_pikoo.tflite build
```

模拟器可通过 `PIKOO_WAKE_MODEL=/private/nihao_pikoo.tflite` 选择私密模型。主机 TFLM 测试使用参考内核，能够暴露设备解释器不支持的模型结构，但不能代替 ESP32-S3 的 ESP-NN 内核实测。到板需记录实际 arena、剩余内部 RAM/PSRAM、推理耗时（每 30ms 输入需及时处理）、任务栈余量和音频缓冲溢出次数。
