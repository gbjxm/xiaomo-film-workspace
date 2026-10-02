# 方法来源与取舍

2026-09-24 查阅原始仓库及相关文档。本技能按小陌的任务重新编写，不安装或执行这些仓库。阅读来源不代表已经验证其还原效果。

- [CLIP Interrogator](https://github.com/pharmapsychotic/clip-interrogator)：借鉴从画面到生成描述的方向；不复制相似词堆叠、艺术家标签或特定 Stable Diffusion 参数。
- [JoyCaption](https://github.com/fpgaminer/joycaption)：借鉴客观描述与提示词表达分开；不继承猜相机、光圈、快门等无法从图像确定的选项。官方说明部分模式仍不稳定。
- [image-to-prompt-skill](https://github.com/fluentlc/shiny-skills/blob/main/image-to-prompt-skill/SKILL.md)：借鉴具体比例和空间关系。其可复用模板属于后续功能二，本版不实现；不继承猜原始模型参数或固定十栏输出。
- [video-prompt-reverse](https://github.com/LunarXuan/video-prompt-reverse)：借鉴逐镜证据、时间线、观察与推测分离。不复制一律输出负面提示词、每次全量哈希或自动生成优化流程；目标工具与授权按本次实际核实。
- [PySceneDetect](https://www.scenedetect.com/docs/latest/cli.html)：作为可选镜头边界工具参考，不能替代实际视觉和声音判断。

不以“更多形容词”“更长提示词”或“存在自动评分脚本”作为质量证明。首版是否有效，以用户真实参考上的纯提示词生成和实际对照为准。

## 2026-09-25 顺序与权重核查

- [Higgsfield官方开源提示说明](https://github.com/higgsfield-ai/skills/blob/d071406147a37b835bed09543d85ab3e9bd85c7d/higgsfield-generate/references/prompt-engineering.md)：借鉴具体主体、场景、成像与模式区别。短提示建议不是跨模型统一上限，也不是词位数值权重的证明。
- [Higgsfield Seedance 2.5 提示指南](https://higgsfield.ai/blog/seedance-2-5-prompting-guide)：带标签分段、全局视觉条件与逐镜动作配合。它说明分块本身并不低级；不把视频示例直接套到纯文生图。
- [OpenAI 图像提示指南](https://developers.openai.com/api/docs/guides/image-prompting)：以清楚的场景、主体、细节与约束组织内容；具体型号须看实际调用，不因格式器名称判定。
- [OpenAI 图像生成文档](https://developers.openai.com/api/docs/guides/image-generation)：精确布局仍有限制，Responses接口可返回改写提示。只据此检查当前工具有没有暴露相应证据，不推断本次原生工具必定使用该链路或已经改写。

此次借鉴仅支持信息组织与验证方法；不声称已通过80%—85%真实还原，不引入通用数值权重或自动生成。
