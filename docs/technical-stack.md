# VTE Review v0.2.0：技术实现与论文写法

核实日期：2026-10-03。下述内容对应本仓库实际实现。

## 可用于初稿的方法段落

本系统采用本地部署的浏览器—服务端架构，在 Windows 11 工作站上运行。前端使用 HTML5、CSS3 与原生 JavaScript 构建，提供病例录入、证据导入、多专家协作监控、版本对比及医师审阅界面；后端基于 Python 3.11.9 实现，通过标准库 HTTP 服务与服务器发送事件（Server-Sent Events，SSE）向前端持续推送工作流进度。多 Agent 编排采用 asyncio 异步任务与信号量控制：A、B、C 分别围绕抗凝获益与疗程、药物适用性与用药安全、出血风险与患者约束进行独立评估，D 汇总形成版本化草案。各专家并行审核其负责部分，D 根据问题单统一修订，再依据实际修改及段落依赖关系触发受影响专家复核，从而减少无需重复的模型调用。

RAG 模块采用本地证据索引，保留每条证据的来源、版本、适用角色及原文片段。检索首先按角色筛选，再以英文词项和中文二元字组的重合数量排序，默认每个角色返回相关性最高的 4 条有效证据（k = 4），并缓存相同查询的检索结果。系统通过 httpx 0.28.1 对接兼容 Chat Completions 的模型接口，支持为不同角色指定不同模型，并使用 JSON 输出模式和结构校验约束模型响应。默认并发调用上限为 3，单次调用超时为 60 秒，D 的修订上限为 3 次，单次最大生成长度为 3,000 tokens。病例、事件日志、模型调用结果、草案版本与人工审阅记录以 JSON、JSONL 和 Markdown 文件保存在本地；人工审阅记录通过 SHA-256 草案指纹关联相应版本，以支持过程追溯。

## 实际技术栈

| 层次 | 已实现技术 | 对应代码 |
|---|---|---|
| 前端 | HTML5、CSS3、原生 JavaScript；Hash 路由；Fetch；EventSource；SVG 协作图；响应式布局 | `vte_review/web/` |
| 本地界面 | Windows 启动脚本；Edge / Chrome `--app` 窗口，回退默认浏览器 | `启动系统.bat`、`server.py` |
| HTTP 服务 | Python 标准库 `ThreadingHTTPServer`，JSON API 与 SSE | `server.py` |
| Agent 编排 | `asyncio.gather`、Semaphore、版本草案、依赖传播、定向复核 | `workflow.py`、`contracts.py` |
| 检索 | 本地词项重合评分、角色过滤、内存缓存、来源与版本信息 | `retrieval.py` |
| 模型连接 | httpx 异步客户端；Chat Completions 兼容接口；JSON mode | `providers.py` |
| 提示模板 | 按角色及 assess/synthesize/review/revise 阶段组织；固定提示版本 | `prompts.py` |
| 数据 | JSON / JSONL / Markdown；浏览器 localStorage 保存表单和非密钥配置 | `server.py`、`cli.py`、`web/app.js` |
| 验证 | Python unittest、httpx MockTransport、浏览器交互与布局检查 | `tests/`、`docs/verification.md` |

## 参数与本机环境

| 项目 | 当前值 |
|---|---|
| 操作系统 | Windows 11 家庭版，系统版本 10.0.26200 |
| CPU | AMD Ryzen 7 7840H |
| 系统报告可用物理内存总量 | 约 15.2 GiB |
| 系统显示适配器 | AMD Radeon 780M Graphics |
| Python / httpx | 3.11.9 / 0.28.1 |
| 本地服务地址 | 默认 `127.0.0.1:8765`；端口占用时尝试后续端口 |
| Top-K / 并发 / 修订 / 超时 | 4 / 3 / 3 / 60 秒，可在运行配置中调整 |
| max_completion_tokens | 3000 |
| temperature | 当前请求不显式设置，由所连接端点的默认行为决定 |
| 提示版本 | `2026-10-02.v1` |

这些硬件承载本地界面、检索和流程编排。实际模型推理位于配置的 API 服务端；本次未启动本机大模型推理。

## 后续研究需冻结的实验信息

实际实验时补充：服务端模型标识与版本、推理部署位置与硬件、明确的采样参数、知识库冻结日期与版本、重复运行次数，以及按病例记录的端到端耗时、模型调用数和 token 使用量。

当前代码没有 FastGPT、Milvus、PostgreSQL、向量嵌入或加权混合检索，也没有统计分析模块。不能把示例中的 A100、temperature=0.1、k=5、低于 100 毫秒延迟或 SciPy/Statsmodels 写为本版本已完成的实现。演示的 0.8 秒调用节奏是为可视化设置的模拟等待，不是实际模型性能。
