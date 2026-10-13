# “你好皮酷”训练与中文童声

目标是普通话本地唤醒，不识别家庭成员。公开仓库里的模型是合成普通话实验模型，**真实童声样本数为 0**。不能用合成音色的成绩声称儿童唤醒已经达标。

## 数据来源与准入

| 来源 | 用途 | 当前状态 |
|---|---|---|
| macOS 本地普通话合成声音 | 打通特征、训练、INT8 转换和设备集成 | 已训练；音频不提交 |
| [BAAI/ChildMandarin](https://huggingface.co/datasets/BAAI/ChildMandarin/blob/main/README.md) | 3–5 岁真实普通话儿童声学分布、普通聊天负样本 | 需要账号申请；未取得、未训练 |
| [ChildTalk](https://github.com/NKU-HLT/ChildTalk) | 后续更丰富的儿童/照护者场景 | 备选，未取得、未训练 |
| 经监护人同意的家庭短句 | 实际“你好皮酷”正样本和近似词负样本 | 尚未采集；仅本地保存 |

ChildMandarin 官方说明：397 名 3–5 岁儿童、约 41.25 小时，16kHz WAV，训练/开发/测试说话人分别为 317/39/41。它需要申请，附有非商业研究和禁止转发等限制；不要通过镜像绕过访问门槛，也不要将原始录音或其衍生模型直接发布到公共仓库。数据卡的许可证标签不能代替完整使用条款。普通儿童聊天主要是负样本，并不自动提供目标唤醒词正样本。

不将成人变调、合成“童声”、中国儿童朗读英语、韩语儿童录音冒充真实普通话童声。“你好皮裤”“你好皮库”与目标近乎同音，不标成必须区分的负样本；“你好皮球”等不同发音可作困难负例。

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

训练输出含受限数据时 `report.json.restricted_data=true`，不得将模型复制到公开目录。本次发布的合成模型人工审核后单独纳入版本管理。现有实验模型见 [模型卡](models/MODEL_CARD.md)。

## 导入真实中文童声

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

先用成人录音验证流程。孩子愿意参与时，每人每次约 2–3 分钟：自然说“你好皮酷”，换语速、音量和 0.5/1/2 米距离，每次少量短句，中间留安静间隔；另录自然聊天和“你好皮球”等近似词。不同日期、房间和录制设备分开记录。两个孩子分别统计，不合并成一个儿童平均值。录音用匿名编号，不把姓名写入文件名，默认不上传任何平台。

最终验收仍需每人 1 米 20 次至少 18 次成功，以及 8 小时家庭背景声误唤醒不超过 1 次。短片段误触发率不能换算成已经通过 8 小时测试。
