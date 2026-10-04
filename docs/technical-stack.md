# VTE Anticoagulation Assistant v0.4.0：技术实现与论文写法

核实日期：2026-10-04。下述内容对应本仓库实际实现；硬件信息沿用 2026-10-03 的本机检查。

## 可用于初稿的方法段落

本系统采用本地部署的浏览器—服务端架构，在 Windows 11 工作站上运行。前端使用 HTML5、CSS3 与原生 JavaScript 构建英文交互界面，提供病例录入、知识库管理、多专家协作监控、版本对比及医师审阅功能；后端基于 Python 3.11.9 实现，通过标准库 HTTP 服务与服务器发送事件（Server-Sent Events，SSE）向前端持续推送工作流进度。多 Agent 编排采用 asyncio 异步任务与信号量控制：A、B、C 分别围绕抗凝获益与疗程、药物适用性与用药安全、出血风险与患者约束进行独立评估，D 汇总形成版本化草案。各专家并行审核其负责部分，D 根据问题单统一修订，再依据实际修改及段落依赖关系触发受影响专家复核，从而减少无需重复的模型调用。

知识库使用 SQLite 3.45.1 持久化保存资料正文、来源、版本和适用角色，支持文本录入及 PDF、TXT、Markdown、JSON 导入；PDF 文本提取使用 pypdf 6.16.2。资料按约 1,200 字符分段并保留 150 字符重叠上下文，通过 SQLite FTS5 建立全文索引。RAG 对英文词项和中文二元字组进行规范化处理，按角色筛选后采用 BM25 排序，标题与正文权重分别为 5 和 1，默认每个角色返回最多 4 条匹配证据（k = 4），并缓存相同查询的检索结果。每次审核固定选中资料的原文快照，确保后续引用可追溯至当时使用的来源与版本。

系统通过 httpx 0.28.1 对接 Chat Completions 或 Responses 模型接口，支持按角色配置模型，并以 JSON 输出和结构校验约束响应。Agent 可通过函数调用请求角色授权的证据检索、患者历史、临床资料核查、确定性计算或原图复查，程序执行后将结果返回同一模型会话。默认并行 Agent 会话数为 3，每个会话含工具往返的总超时为 60 秒，工具最多 4 轮、每轮最多 8 次，D 的修订上限为 3 次，每个模型请求最大生成长度为 3,000 tokens。运行记录区分会话数、已完成会话中的实际模型请求数、工具次数和返回的 token 用量。

患者记忆独立保存于 SQLite，以患者及就诊标识组织记录，区分临床发生时间与资料可获得时间。每次评估按决策时点生成不可变记忆快照，模型建议以待确认记录保存，不直接改写患者事实。Word 正文及内嵌截图通过本地文件解析和模型视觉接口进入核查流程，提取结果保留数值、单位、日期、来源、位置及人工确认状态。Cockcroft–Gault、单位换算、药物数量与疗程天数由确定性 Python 工具执行。医生参考方案、专家审计及结局标签另存于运行目录，不进入独立生成任务的模型上下文。病例、证据、记忆快照、工具事件、草案版本及人工审核保存在 JSON/JSONL/Markdown 中，人工审核通过 SHA-256 关联对应草案。

## 实际技术栈

| 层次 | 已实现技术 | 对应代码 |
|---|---|---|
| 前端 | HTML5、CSS3、原生 JavaScript；英文蓝白界面；Hash 路由；Fetch；EventSource；四个本地 SVG 机器人；响应式布局 | `vte_review/web/` |
| 本地界面 | Windows 启动脚本；Edge / Chrome `--app` 窗口，回退默认浏览器 | `启动系统.bat`、`server.py` |
| HTTP 服务 | Python 标准库 `ThreadingHTTPServer`，JSON API 与 SSE | `server.py` |
| Agent 编排 | `asyncio.gather`、Semaphore、版本草案、依赖传播、定向复核 | `workflow.py`、`contracts.py` |
| 知识库 | SQLite 3.45.1；documents / chunks / FTS5 表；WAL；去重；归档恢复；不可变资料版本 | `knowledge.py` |
| 知识库 RAG | FTS5 / BM25；角色过滤；运行时固定快照；内存缓存；来源与版本信息 | `knowledge.py` |
| 文件证据检索 | 直接导入证据 JSON / CLI 仍采用词项重合排序 | `retrieval.py` |
| PDF 解析 | pypdf 6.16.2 提取文本层；不包含 OCR | `server.py` |
| 模型连接 | httpx 异步客户端；Chat Completions / Responses；JSON 输出；有界 function-calling 会话 | `providers.py` |
| 临床工具 | Cockcroft–Gault、单位/数量/疗程计算、有限说明书模式检查、分角色权限 | `clinical.py`、`clinical_tools.py` |
| 患者记忆 | SQLite 追加记录、双时间截断、来源、修订、模型建议人工审核 | `patient_memory.py` |
| 病例文档/图片 | ZIP/XML 提取 DOCX 正文及内嵌图；Pillow 校验；模型视觉读数；人工确认 | `intake.py`、`workspace.py` |
| 提示模板 | 按角色及 assess/synthesize/review/revise 阶段组织；固定提示版本 | `prompts.py` |
| 数据 | 知识库保存在 SQLite；审核记录使用 JSON / JSONL / Markdown；浏览器 localStorage 保存表单和非密钥配置 | `knowledge.py`、`server.py`、`cli.py`、`web/app.js` |
| 验证 | Python unittest、httpx MockTransport、浏览器交互与布局检查 | `tests/`、`docs/verification.md` |

## 参数与本机环境

| 项目 | 当前值 |
|---|---|
| 操作系统 | Windows 11 家庭版，系统版本 10.0.26200 |
| CPU | AMD Ryzen 7 7840H |
| 系统报告可用物理内存总量 | 约 15.2 GiB |
| 系统显示适配器 | AMD Radeon 780M Graphics |
| Python / httpx | 3.11.9 / 0.28.1 |
| SQLite / pypdf | 3.45.1 / 6.16.2 |
| 本地服务地址 | 默认 `127.0.0.1:8765`；端口占用时尝试后续端口 |
| Top-K / 并发 / 修订 / 超时 | 4 / 3 / 3 / 60 秒，可在运行配置中调整 |
| max_completion_tokens | 3000 |
| temperature | 当前请求不显式设置，由所连接端点的默认行为决定 |
| 提示版本 | `2026-10-04.en.v3`，要求模型输出英文 |
| 工具会话 | 最多 4 轮工具调用，每轮最多 8 次；最后输出最多共 5 个模型请求 |
| 图片提取 | D 角色配置的视觉模型；整体超时 120 秒；最多 12 张图片 |

默认数据库为 `runs/knowledge.sqlite3` 与 `runs/patients.sqlite3`，随 `--runs` 指定的目录改变。数据库自动初始化，无需独立服务。知识库版本以新增资料保留，归档可恢复；每次评估保存 `evidence.json` 与 `memory_snapshot.json`。显式执行的参考资料导入脚本支持 4 个固定官方来源 URL；本机已导入 4 份、386 个片段，原件与抓取摘要存于 `reference_sources/`。程序不会在运行模型时自动更新这些来源。

这些硬件承载本地界面、检索和流程编排。实际模型推理位于配置的 API 服务端；本次未启动本机大模型推理。

## 后续研究需冻结的实验信息

实际实验时补充：服务端模型标识与版本、推理部署位置与硬件、明确的采样参数、知识库冻结日期与版本、重复运行次数，以及按病例记录的端到端耗时、模型调用数和 token 使用量。

当前代码没有 FastGPT、Milvus、PostgreSQL、向量嵌入或加权混合检索，也没有统计分析模块。不能把示例中的 A100、temperature=0.1、k=5、低于 100 毫秒延迟或 SciPy/Statsmodels 写为本版本已完成的实现。演示的 0.8 秒调用节奏是为可视化设置的模拟等待，不是实际模型性能。


## 2026-10-04 FE 接口联调配置

产品名改为 **VTE Anticoagulation Assistant**；主入口为 New recommendation / Generate recommendations，原有处方核查与内部定向审核保留。Python 包及仓库路径不变。

用户指定使用 FE（https://api.forceeasyai.com/v1）的 `gpt-6-astra` 与 `gpt-5.6-sol`。本机启动器只读已有 FE 配置，在服务进程内设置密钥，不复制到项目文件。采用 Responses 流式接收：以 response.completed 的完整对象继续工具会话，仅有输出片段而无完成事件时不返回有效答案；保留兼容端点的完整 JSON 响应。JSON 模式要求在输入消息中明确 JSON，适配器已处理。

本次真实运行配置：每组四个角色使用同一个指定模型，reasoning.effort=low，max_output_tokens=6000，top_k=4，并发上限3，最多3次修订，每个Agent含工具会话总上限240秒。通用启动入口仍默认60秒/3000输出token/未指定推理强度；FE启动入口采用上述覆盖值。温度依然未显式指定。连接与参数存入每次运行meta，密钥除外。

本轮以基线资料作回顾性软件展示，原临床决策时点及部分检验时间未确认；原始后续处方和结局未进入模型。不能把此次单病例联调写成时间截断已冻结的临床评测或效果验证。
