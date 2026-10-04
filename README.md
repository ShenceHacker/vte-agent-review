# VTE Anticoagulation Assistant

VTE 抗凝决策助手：根据病例生成个体化治疗建议，并支持核查已有处方。内部采用 **ABC 并行初判 → D 汇总 → ABC 并行审核各自部分 → D 定向修改 → 相关专家复核，直到通过或停止。**

这个仓库实现通信与审核循环，包含英文研究工作台、SQLite 知识库与患者记忆、Word/图片资料输入、临床资料检查、真实工具调用、离线演示和可配置的模型接口。v0.5 支持根据已有资料给出带假设的建议，以及医生填写资料表、补传文件并生成新版；程序内 `approved` 表示工作流通过，不等于临床验证通过。

[v0.4 使用说明与数据边界](docs/workspace-v04.md)

### 病例资料表与条件性建议（v0.5）

报告页点击 **Review information**，或在新病例页面点击 **Information checklist**。表中有 22 项常见病例信息，涵盖血栓、既往治疗、检验、出血、合并用药及随访条件，**不要求全部填齐**。

- 一般未提供项默认不阻断，也不作为必填项反复追问；可能改变选择或剂量的未知项写入建议的 `assumptions`，说明适用条件和条件不成立时的处理分支。
- 医生可选择“已提供／确认无／本次不重要／暂不清楚”。“无”仅用于可否定的病史、症状或用药信息，不能用来代替检验数值；“本次不重要”保留为相关性判断，不制造阴性或正常结果。
- ABC 可以返回 `approve_conditional`。D 会继续处理引用和措辞等可修改的问题，不再因任一角色请求补资料就立即结束。共享假设变化后 ABC 重新审核，仍受修订次数上限约束。
- **Add records / update recommendation** 复用原病例、已保存的医生确认、模型设置及原证据快照。可在 Source documents & images 上传 Word、图片或文字，提取并核对后启动新运行；原报告及标签保持不变。
- `conditional` 表示带假设的建议完成 Agent 审核，尚待医生审阅；`recommendation` 提供当前草案，`review_complete` 和 `information_status` 分别表示审核与信息状态。为兼容原接口，只有 `approved` 会填入 `final`，不能用 `final` 是否为空来判断有无建议。

医生确认以追加批次保存在原运行的 `information_responses.json`，包含确认人、时间和备注；新版记录 `parent_run_id`。保存后需显式生成新版，才会将补充信息用于模型。

### 论文流程图

界面统一为英文。中英文流程图采用相同结构：病例与证据、ABC/D 审核与修订、医生审核和按需补充资料、拟定对比评价。

- 英文：[PNG](docs/figures/VTE_workflow_2026-10-04_en.png) · [SVG](docs/figures/VTE_workflow_2026-10-04_en.svg) · [PDF](docs/figures/VTE_workflow_2026-10-04_en.pdf)
- 中文：[PNG](docs/figures/VTE_workflow_2026-10-04_zh.png) · [SVG](docs/figures/VTE_workflow_2026-10-04_zh.svg) · [PDF](docs/figures/VTE_workflow_2026-10-04_zh.pdf)

矢量源可用 `python scripts/build_workflow_figures.py --lang en` 或 `--lang zh` 重建，需要 ReportLab 和 Windows Arial/微软雅黑字体；PNG 由 PDF 按 300 dpi 渲染。虚线回路表示医生按需补充后显式启动新运行，原报告保留；研究评价面板为拟定设计。


### FE 接口启动

本机双击 `启动系统.bat`，或运行：

```powershell
python scripts/serve_fe.py --open-browser
```

启动器只读当前用户 `.claude/settings.json` 中既有的 FE 地址和凭据，将连接配置放入本服务进程，不复制密钥或改写原配置。仅接受 `https://api.forceeasyai.com`；使用 Responses API，默认模型 `gpt-6-astra`，可以加 `--model gpt-5.6-sol`，也可在界面中按运行选择。FE 启动配置统一使用 low 推理强度、每个模型响应最多6000输出token、每个Agent会话240秒上限；默认端口8769，实际地址以启动输出为准。没有该配置的电脑仍可使用 `python -m vte_review gui` 并在 Settings 设置自己的接口。

界面的 **New recommendation** 默认生成治疗建议；**Review an existing prescription** 用于核查已有方案。内部 Specialist review 和定向修订机制保持不变。Python包、命令及GitHub仓库的技术标识继续使用 `vte_review` / `vte-review` / `vte-agent-review`，以保持已有命令与链接兼容。

## 立即运行

### 1. 图形化专家工作台（推荐医生与临床研究者使用）

本机 FE 启动见上节。使用通用、自行配置模型的入口时，在终端执行：

```powershell
python -m vte_review gui
```

系统会自动启动本地服务（默认绑定回环地址 `127.0.0.1:8765`），并以 Edge / Chrome 独立应用窗口打开英文蓝白研究工作台（浏览器不可用时使用系统默认浏览器）：

- **Overview**：四个白大褂机器人代表 A/B/C/D，可查看角色分工、近期建议与知识库概况。
- **Patients**：带来源和双时间戳的患者时间线；分别记录事实、偏好、医生决策、实际治疗与模型建议；更正保留旧记录，模型建议需人工审核。
- **Knowledge base**：添加文本、导入 PDF/TXT/Markdown/证据 JSON，保存来源和版本，自动分段，全文检索与角色筛选；选择资料后用于审核，支持归档与恢复。
- **治疗建议向导**：支持脱敏事实表单/JSON 双向录入、指南证据库拖拽校验、离线演示与真实模型（OpenAI 兼容端点）无缝切换。
- **实时协作看板**：展示 A/B/C 三位专家 Agent 并行思考、D 协调员动态连线、实时甘特图时序与事件流。
- **医生审阅与签署**：分段呈现实时草案、各专家意见与引用文献抽屉，支持采纳/修改/驳回并绑定 SHA-256 数字指纹，支持一键生成 A4 打印与 PDF 报告。
- **模型与设置**：可直接配置服务地址、默认模型及 A/B/C/D 的模型分配；地址和模型名称保存在此浏览器，API Key 仅保留在当前页面会话内存中。
- **使用指南与窄屏布局**：六步流程说明，窄屏底部导航、可横向滚动的数据表、键盘可操作的证据抽屉。

已经打开页面时，保存代码修改后刷新即可加载最新前端。后端代码更新需重启服务。仅启动服务而不打开桌面窗口：

```powershell
python -m vte_review gui --no-browser
```

运行记录保存在 `runs/`，知识库自动创建于 `runs/knowledge.sqlite3`，病例录入草稿保存在本浏览器；无需另装数据库服务或构建前端。图形界面是本地 Web 应用，目前通过启动脚本运行，未打包为独立 `.exe`。

PDF 文本提取和模型连接为可选依赖（本机已安装）：

```powershell
python -m pip install -e ".[llm,pdf,images]"
```

从 **Knowledge base → Add document** 导入文件或粘贴正文，填写标题、来源、版本和适用角色后保存。检索并勾选资料，点击 **Use for recommendation** 即可接入病例决策。PDF 支持带文本层的文件；扫描件需先做 OCR。界面单文件上限 5 MB，PDF 最多 300 页，正文最多 200 万字符；JSON 使用下文证据数组格式。

知识库保留原文，按约 1,200 字符分段、150 字符重叠；使用 SQLite FTS5 / BM25 全文检索，支持英文词项和中文二元字组。运行开始时固定选中资料的快照并写入 `evidence.json`，后续归档不会改变已有审核的来源。相同内容及元数据重复导入会去重，新版本可作为独立资料保存。新安装的知识库初始为空；可运行 `python scripts/import_reference_pack.py --runs runs` 导入 4 份公开官方来源资料。本机已导入 NICE NG158（英国）及利伐沙班、甲氨蝶呤、复方磺胺甲噁唑说明书（美国）。中国说明书和院内规范由研究者按实际品种补充。测试资料保存在隔离目录中。

[技术栈与论文方法段落](docs/technical-stack.md) · [验证记录](docs/verification.md)

### 2. 命令行运行

Python 3.11 及以上。离线演示不需要 API key 或额外依赖：

```powershell
python -m vte_review demo
```

默认演示的实际路径：

```text
A/B/C 并行初判
       ↓
D 生成草案 v1
       ↓
A：需修改    B：通过    C：通过
       ↓
D 只修改 A 部分 → 草案 v2
       ↓
只给 A 复核 → A 通过 → 输出原样的 v2
```

每次生成独立的 `runs/<UTC时间>-<随机ID>/`，包括 `case.json`、`events.jsonl`、`result.json` 和 `report.md`。指定 `--output` 时目录必须尚不存在，以防覆盖实验记录。

## 四个角色

| 角色 | 责任 |
|---|---|
| A | 抗凝获益、治疗阶段与疗程 |
| B | 药物适用性、用药条件、剂量相关因素与相互作用 |
| C | 出血风险、患者约束、监测需求 |
| D | 整合草案、按问题单修订，不代替专家作审核通过决定 |

ABC 第一轮互相不看答案。D 是唯一草案写入者，避免不同修改覆盖彼此。审核者只接收自己的部分、共同方案、已声明依赖、自己的初判及上轮问题单；不是全员反复读完整聊天。

## 循环规则

1. 首次审核 ABC 同时开始。每次审核波次收齐后，D 一次性处理本轮异议；不是每出现一个问题就并发运行多个 D。
2. 审核结果为 `approve`、`approve_conditional`、`revise` 或 `needs_information`，异议携带稳定问题 ID、理由、引用、修改要求与相关角色。条件性通过必须引用草案中明确属于该角色的假设。
3. A 不通过就由 D 修改后交回 A。B/C 已通过且不受影响时不再调用。
4. 程序比较新旧草案的实际内容。D 修改了 B 部分，即使没申报，也必须请 B 重审。
5. `depends_on` 记录部分间依赖；变更传播使用新旧依赖图的传递闭包。删除旧依赖不能抹去此次重审要求。
6. `shared_plan` 保存药物、治疗阶段、总体方案等共同前提。共同方案、假设或补充问题发生变化都会触发 ABC 重审。D 及审核者还可额外申报受影响角色。
7. 默认最多 3 次 D 修订；最后一次修改仍需复核。缺信息先尝试形成可审核的条件性分支；无实际修改、达到上限时保留草案及未决问题。超时、格式错误、无效引用不当作通过。
8. 全部有效审核通过后，直接输出经过审核的草案，**不再追加一次未经审核的最终润色**。

`approvals` 中 B 在 v1 通过、A 在 v2 通过是允许的，前提是 B 的内容、共同前提和依赖没有被修改。记录的是最后一次有效批准版本，不要求所有角色的版本号相同。

## 演示其他路径

```powershell
python -m vte_review demo --scenario dependency  # A 变化引发依赖 A 的 B 重审
python -m vte_review demo --scenario shared      # 共同方案变化，ABC 全部重审
python -m vte_review demo --scenario limit --max-revisions 2
python -m vte_review demo --scenario missing
python -m vte_review demo --scenario stagnant
```

后三种是预期的非通过结果，退出码为 2。演示使用人工编写的确定性响应与明确标记的合成协议，不能把它的输出或耗时作为真实模型效果。

## 接入真实模型

```powershell
python -m pip install -e ".[llm]"
$env:VTE_BASE_URL = "https://api.openai.com/v1"
$env:VTE_MODEL = "你的模型名称"
$env:VTE_API_KEY = "通过本机安全方式设置的密钥"
python -m vte_review run --case data/case.json --evidence data/evidence.json
```

支持具备 JSON mode 的 Chat Completions 兼容端点。默认所有角色使用同一个模型，可以通过 `VTE_MODEL_A` / `VTE_MODEL_B` / `VTE_MODEL_C` / `VTE_MODEL_D` 单独设置。程序不自动加载 `.env`，不自动选择模型或发送真实病例。

HTTP 适配器发送 `response_format: {"type":"json_object"}` 并在本地严格检查契约。JSON mode 仅保证 JSON 格式，不保证业务 schema；无效响应直接失败，不静默当成通过。截断、拒答、HTTP 错误也停止工作流。接口必须支持 `max_completion_tokens`；未对所有第三方端点作兼容性验证。

请求与边界依据：[OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat)、[JSON mode 与结构化输出](https://developers.openai.com/api/docs/guides/structured-outputs)。

## 病例及证据格式

CLI 病例由调用者整理为结构化事实；图形界面另提供模型提取和逐项人工确认。

```json
{
  "case_id": "DEIDENTIFIED-001",
  "question": "明确本次要解决的决策问题与时间点",
  "facts": {"实际已知字段": "已核对的取值"},
  "missing_information": ["尚未提供的必要信息"]
}
```

证据库是 JSON 数组，条目需包括：

```json
[
  {
    "id": "SOURCE-SECTION-001",
    "title": "实际来源标题",
    "source": "实际文献/说明书地址与章节位置",
    "version": "实际版本或日期",
    "text": "依法可使用、人工核对后的原文片段",
    "roles": ["A", "B", "C"],
    "synthetic": false
  }
]
```

这是格式示例，不是可用于临床推理的知识库。`run` 拒绝 `synthetic: true` 证据；`false` 只是提供者的声明，不代表程序验证了来源真实性。

从知识库选入审核时，RAG 在选中资料的固定快照上采用 FTS5 / BM25 排序与角色过滤；直接导入证据 JSON 或命令行运行时保留原词项重合检索。两者默认返回最多 4 条匹配证据并缓存查询，后续轮次可按问题单补充检索。检索不到证据时停止，不拿任意条目填充。所有引用必须来自当前调用实际收到的证据。

## 参数及输出

`--max-revisions`、`--concurrency`、`--timeout`（单次模型调用秒数）、`--top-k` 均可设置。并行是否节省真实等待时间取决于端点的并发能力。

| 状态 | 退出码 | `final` |
|---|---|---|
| `approved` | 0 | 已通过程序审核的原样草案 |
| `needs_human_review` | 2 | `null`，保留草案和问题单 |
| `failed` | 1 | `null`，保留已发生事件 |

运行记录包含模型名称、提示词版本、参数、输入/输出、证据版本、修订记录、耗时、调用次数及供应商返回的 token 用量。没有返回 token 用量时，用 `usage_reported_calls` 区分“未知”与零消耗。中途取消已产生的事件仍留在 JSONL 中。

`runs/`、`data/`、`.env*` 默认不入 Git。运行记录包含病例与模型输出，保存在本机；真实接口模式会把病例和证据发送到所配置的模型端点。密钥不写入运行记录。

## 验证

```powershell
python -m unittest discover -s tests -v
```

安装 `.[llm,pdf]` 后会运行 HTTP 模拟及 PDF 提取测试；未安装相应依赖时明确跳过。测试包含真实协程同步屏障，验证初判和审核确实重叠执行，并覆盖定向循环、依赖传播、共同方案重审、轮次限制、无变化、缺资料、格式错误、虚构引用和超时，以及知识库持久化、去重、角色过滤、排序、归档恢复与运行快照。

当前验证状态见 [docs/verification.md](docs/verification.md)。

## 当前限制

- 没有正式指南库、药物规则引擎、肾功能计算器或临床评测集，不生成演示性真实处方。
- 引用检查验证 ID 是否存在，不证明引文足以支持医学结论。
- 依赖正确性依赖 D 的声明和专家审核；程序无法可靠推断所有潜在医学关联。修改共同前提必须放到 `shared_plan`，否则可能漏触发。
- 使用审核波次屏障，等待本轮必要审核完成后再修订；尚未实现“某专家先回复就先修订”的异步版本协调。
- 尚未做真实端点联调、结果准确性/安全性评价或持久化断点恢复。

下一步应先确定模型端点与正式证据，再用脱敏/合成病例验证真实输出契约；论文的临床结论需要独立专家与预注册指标评估。
