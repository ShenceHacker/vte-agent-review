# v0.4：患者记忆、图片输入与工具调用

日期：2026-10-04。

## 操作顺序

1. 在 **Settings** 配置服务地址、模型与 API 协议（Chat Completions 或 Responses）。模型需要支持 JSON 输出、function calling；处理图片还需支持视觉输入。密钥仅在页面/服务运行内存中使用，不保存到数据库或运行日志。
2. 在 **Patients** 输入脱敏患者 ID，保存已有病史、偏好、医生决策或实际用药记录。每条记录填写临床发生时间、信息可获得时间、来源、记录者；医生决策还必须填写就诊 ID。
3. 在 **New recommendation → Case details** 填写患者 ID、就诊 ID、决策时点和任务类型。可点 **Clinical example** 查看完全虚构的结构化示例，或导入 JSON。
4. 在 **Source documents & images** 上传 DOCX、PNG、JPEG、WebP、TXT、MD。填写整份资料的可获得时间及核对人；如果整份资料包含决策后事件或待留出的医生方案，先在本地拆分/遮去这些部分，再附到本次评估。
5. **Extract with model** 把选中文本/图片送到配置的模型服务，提取数值、单位、日期及位置。所有模型读数自动标为 `unverified`；逐项核对原图、补全日期和单位，再改为 `confirmed`，不用于本次评估的行设为 `excluded`。截断/模糊值保持未知，不能猜测；本版本读取报告和处方截图，不解释原始 CT 影像。
6. **Check clinical data** 显示缺项、矛盾与计算结果。来自未来的记录、未确认读数、事实/来源冲突会阻止进入模型评估；其他关键缺项允许生成供医生查看的条件性草案，但不能得到通过状态。普通非关键缺项不阻止工作流。
7. 在 **Knowledge base** 搜索并选择本次使用的资料，再运行 ABCD 审核。每次运行固定患者记忆与证据快照；后续修改库内容不会改变这次运行。
8. 在运行的 **Audit** 中查看临床检查、记忆快照、工具参数/结果、待审核记忆建议及研究标签。人工接受模型建议后，它仍是“已审核模型建议”；确认新事实需另建有来源的临床记录。

## 输入与标签

| 任务 | 模型输入 | 单独保存的参照标签 |
|---|---|---|
| Generate an independent plan | 决策时点可用的事实及既往治疗；本次医生方案不输入 | Physician plan、Expert audit、Outcome |
| Review an existing prescription | 同上，加 Candidate plan | Expert audit、Outcome |

研究标签写入 `research_labels.json`，不会进入 Workflow、检索查询、工具上下文或模型请求。新建病例与已完成运行均可添加标签。自由文本若手工混入答案/未来结局，程序不能保证自动发现；资料时间边界需在入库时核对。

## 工具分工

| 角色 | 可调用工具 |
|---|---|
| A | 患者记忆、病例核查、证据检索、疗程天数、当前病例原图 |
| B | 同上，加 Cockcroft–Gault、单位换算、片数/剂量计算、有限的处方模式核查 |
| C | 患者记忆、病例核查、证据检索、单位换算、原图 |
| D | 患者记忆、病例核查、证据检索、原图、提出记忆更新 |

每轮是“模型提出函数调用 → 程序校验参数和权限 → 执行 → 将结果返回同一会话 → 模型继续”。同一会话最多 4 轮工具调用、每轮最多 8 次；加最后输出最多 5 次模型请求。角色并行数仍为 3，D 修订仍为最多 3 次。日志分别统计 Agent 会话数、已完成会话的模型请求数、工具调用数与返回的 token 用量。

Cockcroft–Gault 工具只计算成人实际体重公式，在不稳定肾功能时不输出估算值，不把 eGFR 当作 CrCl。剂量数量工具保留单次用量与频次差异，不把 mg 和 anti-Xa IU 换算；mL/片数必须提供明确浓度/规格。处方模式工具目前只覆盖**美国成人利伐沙班 DVT/PE 说明书的阶段—剂量—频次模式**，不覆盖其他药品/地区，也不自动确定肾功能适用性或治疗阶段。相互作用、出血及合并病的判断依赖实际资料、检索证据与专家 Agent；不是完整规则引擎。

## 本地数据

| 路径（相对于运行目录） | 内容 |
|---|---|
| `knowledge.sqlite3` | 知识正文、片段、版本、FTS5 索引 |
| `patients.sqlite3` | 追加式患者记录与模型建议审核记录 |
| `sources/SRC-…/` | 原始资料、内容散列及内嵌图片 |
| `intakes/INT-….json` | 未经人工确认的提取结果、模型及用量 |
| `<run>/case.json` | 提交的病例，包含被排除观察值供追溯 |
| `<run>/memory_snapshot.json` | 仅本患者、在临床/可获得时间截断后的确认资料及 SHA-256 |
| `<run>/evidence.json` | 本次选择的知识语料快照 |
| `<run>/research_labels.json` | 与模型隔离的研究标签 |
| `<run>/memory_updates.json` | D 提出的待确认记录；GUI 自动入患者建议区 |
| `<run>/events.jsonl`、`result.json` | 调用、工具、修订、复核与结果 |

历史记忆只有两个时间都不晚于决策时点才可进入快照；修订按其当时可用性替代旧记录。同一就诊医生方案在独立生成任务中被排除；实际治疗必须早于该决策时点。旧文件保持不变。数据库与文件默认位于 `runs/`，已被 Git 忽略。浏览器草稿也保存在本机 localStorage。

上传上限：单文件 6 MB，单次资料合计 24 MB、最多 12 份/12 张图片；图片最多 2500 万像素。DOCX 解压后最多 24 MB/500 项，正文最多 20 万字符。知识库 PDF 导入继续使用独立的 5 MB/300 页限制。

## 参考资料包

运行 `python scripts/import_reference_pack.py --runs runs` 会从固定公开 URL 下载 4 份资料，校验内容标记、保留原文件/文本/SHA-256，再事务入库。不是模型训练，也不会上传病例。每条资料标题保留适用地区，版本包含抓取日期和原文件摘要；正式研究应再确定适用的指南版本与本地药品规格。

- NICE NG158：VTE 诊断、治疗、癌症相关情况、疗程与随访。
- DailyMed XARELTO：剂量、器官功能、出血、相互作用及适用人群。
- DailyMed Methotrexate：骨髓、肝肾安全与合并药物。
- DailyMed Sulfamethoxazole/Trimethoprim：甲氨蝶呤/华法林等相互作用。病例仅写“SMZ”时仍需确认具体药名，不能自动当作复方制剂。

API 实现依据：[OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)、[image inputs](https://developers.openai.com/api/docs/guides/images-vision)。临床工具出处位于 `clinical.py` 的来源常量，原始资料出处位于导入脚本及本地 `reference_sources/manifest.json`。

CLI 同样可用 `--workspace runs` 读取患者和原图快照；CLI 的模型记忆建议保留在结果中，不自动加入数据库。GUI 提供完整的建议保存与人工审核入口。
