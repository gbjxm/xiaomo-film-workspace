# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice

---

## [LRN-20260825-002] correction

**Logged**: 2026-08-25T16:05:00+08:00
**Priority**: medium
**Status**: resolved
**Area**: docs

### Summary
有效对白的节奏和人物味道成立时，不应仅为迁就单次 AI 视频生成时长而压缩剧本内容。

### Details
场次 05 的电话误会对白虽超过原 30 秒预算，但用户明确认为压缩会损失节奏与口吻，并提出用“举手机／边走边完成对白／挂断后转场”的连续分段吸收生成限制。正确处理是延长场次并保留文本功能，把模型时长限制转为制作拆分备注，而不是反向削弱剧情。

### Suggested Action
后续遇到类似冲突时，先判断内容是否有效，再比较延长场次、拆分生成和压缩文本；只有内容重复或无功能时才优先删减。B 只记录表演块和生成风险，Vxx 与提示词仍交 C。

### Metadata
- Source: user_feedback
- Related Files: D:/ProgramData/UserDesktop/毫无意义的工作_专业剧本工作稿_v01.docx
- Tags: screenplay, runtime, ai-production, dialogue, scene-splitting

### Resolution
- **Resolved**: 2026-08-25T16:05:00+08:00
- **Notes**: 本轮将场次 05 延长为 40 秒并保留对白内容。

---

## [LRN-20260825-001] correction

**Logged**: 2026-08-25T15:01:54+08:00
**Priority**: medium
**Status**: resolved
**Area**: docs

### Summary
逐场协作中的专业 Word 工作稿应原位修改，不为每场局部修订另存新版本。

### Details
用户在左侧持续查看同一份剧本文档，并按幕、按场提出局部修改。此前建议为场次 01 另存 v02，与用户期望的实时逐场协作不符。正确方式是只替换当前场次，保持文件名和其他场次不变。

### Suggested Action
后续收到单场修改授权时，先确认当前文档未发生未识别的外部变化，然后在同一 DOCX 中原位修改精确场次；只有整体里程碑、用户明确要求或需要正式归档时才创建新版本。

### Metadata
- Source: user_feedback
- Related Files: D:/ProgramData/UserDesktop/毫无意义的工作_专业剧本工作稿_v01.docx
- Tags: word, screenplay, in-place-edit, scene-by-scene

### Resolution
- **Resolved**: 2026-08-25T15:01:54+08:00
- **Notes**: 本轮改为连接当前打开的 Word 文档并只修改场次 01。

---
## [LRN-20260826-001] best_practice

**Logged**: 2026-08-26T17:44:00+08:00
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
跨岗位完成门应由源岗位写自己的交付，再由目标文件所有者任务做哈希复核与状态确认。

### Details
B 完成采用剧本和 Sxx 后，A 的单一目标、里程碑与输入指针必须由现有 A｜总控流程任务重读并确认。主任务可以准备精确交接事实，但不应仅凭同一上下文把跨岗位状态变化当成所有者已经验收。

### Suggested Action
后续 B→A→C 交接固定使用：B 写回并给出精确哈希 → 向现有 A 任务发送最小复核 → 等待 A 返回当前 A 哈希和唯一下一步 → 再定位现有 C 任务。没有现有目标任务时再向用户请求创建授权。

### Metadata
- Source: conversation
- Related Files: A_总控.md, B_故事剧本.md
- Tags: workflow, ownership, handoff, sha256

---
## [LRN-20260826-002] correction

**Logged**: 2026-08-26T21:26:00+08:00
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
用户指定某个 Word 版本为最终版时，必须原样锁定该文件，不能擅自规范段落样式或重排内容。

### Details
本次用户要求把微信传回的“内版”直接作为最终版。助手错误地把其中一条嵌在动作段的心声拆成标准对白段落，造成现行文件哈希变化。用户纠正后，项目改为锁定桌面微信内版原文件，并冻结旧整理版和十一分钟专业稿。

### Suggested Action
后续遇到“这一版就是最终版”“直接用这一版”时，先判断用户要的是内容采用还是文件原样锁定；若用户强调版本本身，保持字节、段落、样式和分页不变，只更新 B/A/C 路径、哈希和消费边界。任何格式优化必须另取授权。

### Metadata
- Source: user_feedback
- Related Files: B_故事剧本.md, A_总控.md, C_视觉生成.md
- Tags: word, final-version, fidelity, freeze, sha256

---
