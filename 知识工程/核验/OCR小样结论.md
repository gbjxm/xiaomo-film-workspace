# G01 OCR小样结论

## 样本

- 《救猫咪1》《救猫咪2》《救猫咪3》和 Egri 各12个代表页，共48页。
- 覆盖封面、版权或前言、目录、章节标题、普通正文、密集正文、图文页、列表和后部特殊版式。
- 每本另取一个正文裁切，人工逐字转录，共378个真值字符。
- 原图统一以180 DPI渲染。

## 环境

- RapidOCR 3.9.1：ONNX Runtime CPU，PP-OCRv6 small检测与识别模型。
- PaddleOCR 3.7.0：PaddlePaddle 3.3.1 CPU，PP-OCRv6 medium检测与识别模型。
- Paddle在Windows CPU上的默认oneDNN后端触发PIR转换错误；显式设置 `enable_mkldnn=False` 后恢复推理。

## 结果

| 引擎 | 运行范围 | 运行结果 | 速度 | 加权CER |
|---|---|---|---:|---:|
| RapidOCR | 48个完整页＋4个裁切 | 52/52成功 | 首轮平均3.87秒/图；最终裁切平均3.19秒/图 | 2.381% |
| PaddleOCR | 48个完整页＋4个裁切 | 完整页运行超过30分钟，按吞吐门槛停止 | 裁切平均10.81秒/图 | 1.323% |

逐书正文裁切：

| 资料 | RapidOCR CER | PaddleOCR CER | 判断 |
|---|---:|---:|---|
| 《救猫咪1》 | 5.882% | 3.922% | 两者均未达到2%；必须人工核对引用片段 |
| 《救猫咪2》 | 1.042% | 0% | 达标 |
| 《救猫咪3》 | 1.064% | 1.064% | 达标 |
| Egri | 1.163% | 0% | 达标 |

CER保留标点和全角／半角差异，没有通过忽略标点人为压低错误率。Rapid在《救猫咪1》的主要差异包括语气词、破折号和中英文括号；Paddle减少了破折号错误，但仍把一个语气词识别错误，并保留半角括号。

## 阅读顺序抽查

人工对照了目录页、普通正文、带图片正文和中英术语列表：

- RapidOCR在单栏正文中的阅读顺序稳定。
- 目录页能保持章节、页码和简介的大体顺序。
- 图文页会把图片说明混入正文流，但位置可辨认。
- 中英术语列表能保持条目顺序。
- 上述结果只证明代表页，不代表全书每页已经验收。

## OCR路由决定

1. 使用 RapidOCR 作为后续扫描书籍的快速首轮引擎。
2. 使用 PaddleOCR 只复核低置信页、关键术语、人名和两引擎分歧片段。
3. 《救猫咪1》整体标记为 `conditional`；所有进入知识卡的证据片段必须逐段对照页面，不能凭OCR结果直接标记 `ocr_verified`。
4. 其他三本的样本达到门槛，但正式知识卡中的标题、人名、术语、数字和关键主张仍须人工视觉核对。
5. 任何未核片段保持 `ocr_unverified`，不得支撑 `reviewed` 或 `approved` 知识卡。
6. G01不运行全书OCR。全书OCR只在对应逐书来源地图目标启动，并保存页级置信度和复核状态。

## 证据文件

- `ocr-sample-plan.json`
- `ocr-environment.json`
- `ocr-rapidocr-results.json`
- `ocr-rapidocr-cer-results.json`
- `ocr-paddleocr-cer-results.json`
- `ocr-cer-comparison.json`
- `ocr-paddleocr-onednn-failure.json`
- `ocr-paddle-fullpage-timeout.json`
- `ocr-ground-truth.json`

