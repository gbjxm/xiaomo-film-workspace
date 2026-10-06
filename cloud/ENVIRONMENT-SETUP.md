# 三套系统的 Codex Cloud 配置

环境名称建议：小陌的三系统资料工作区。选择三个仓库（可见性以 GitHub 当前设置为准）：gbjxm/knowledge-tree-workflows、gbjxm/xiaomo-learning-system、gbjxm/xiaomo-film-workspace。可读与候选编辑不需要模型 API key，也不需要启动本机网页、达芬奇或安装全局 Skills。

先检出/核对正式 main，再为云端候选选择 cloud-work 或新建独立分支。知识树 cloud-work 有专用入口和 Skill 镜像；不要将该分支直接合入正式 main。云端修改必须提交到候选分支，保留基线和来源，不自动同步覆盖本机。

设置对话可复制：

> 为我准备一个资料读取与候选编辑环境，挂载上述三个仓库。三个仓库均从 main 读取正式快照；知识树 cloud-work 只提供辅助入口和候选，不替代 main 正文。编辑时创建候选分支。只安装 Python 标准库所需运行环境及 Git，不启动本机网页服务或岗位 Claim，不上传凭据。依次读取各根 CLOUD-START.md、AGENTS.md 和 cloud/systems.json，找到实际 checkout 根，并核对资料与仓库 Skills 可读。验证知识树一篇新版正式课程、学习系统导出的数据库内容、工作流八个项目入口；随后检查 cloud-work 可写权限。将结果与未完成项报告给我，完成后发布环境。

仓库访问取决于当前 Codex/GitHub 连接授权；本机 gh CLI 有权限不代表云端连接也已经获得这些仓库。界面路径：新聊天 Work in > Cloud > Select environment > Create environment；或 Settings > Codex Cloud > Environments。授权时只选择本次三个仓库。需要在已登录的界面完成授权并显示 Environment published 后，才能报告云端环境已上线。

新任务的工作区相互独立；提交重要修改，云端 saved state 不替代 Git。多个仓库 Skills 如未自动发现，直接读取所在仓库的 .agents/skills/<name>/SKILL.md，并遵循本系统版本，不混用同名 Skill。
