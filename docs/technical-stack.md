# VTE Anticoagulation Assistant v0.7.0：技术实现与论文写法

核实日期：2026-10-07。本版替代旧版的整份病例提取与纯关键词检索说明。

## 可用于方法初稿的段落

系统采用本地浏览器—服务端架构，前端以 HTML5、CSS3 和原生 JavaScript 构建英文界面，后端采用 Python 3.11.9 与标准库 ThreadingHTTPServer。病例 Word 通过 ZIP/XML 解析正文、段落顺序及图片关系，按显式就诊日期或阶段标题组织时间节点，再切分为至多 3,000 字符、2 张图片的提取块。提取任务由线程池、异步调用和全局信号量控制，最多同时读取 3 块；服务器发送事件（SSE）向前端持续推送提取、审核与节点完成状态。每块完整响应经结构及来源校验后保存，成功块在重试时复用。同一患者的临床判断按时间点依次执行，不同患者最多同时处理 2 例。

多 Agent 工作流包括 A 的治疗获益与疗程评估、B 的临床药学与处方审核、C 的患者状态和变化评估，以及 D 的协调汇总。ABC 并行独立评估，D 汇总后交回各角色审核其负责内容；D 根据问题单修订，程序按实际修改及依赖关系重新分派受影响角色。B 核对既往及当前药物的使用状态、途径、剂量、相互作用、适应条件和给药可行性，C 判断症状、检验和病情变化及监测需求。各节点综合输出当前判断、较前变化、建议措施、理由和适用条件。一般缺项通过明确假设、备选分支和针对性补充问题处理。

知识库以 SQLite 保存资料、来源、版本和角色，按约 1,200 字符、150 字符重叠分段。混合检索使用 SQLite FTS5/BM25 与多语言语义向量排序：嵌入模型为 sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2，通过 FastEmbed 和 ONNX Runtime 在本地 CPU 推理，输出 384 维向量。长片段按 480 字符窗口、440 字符步长编码后归一化聚合，语义相似度采用余弦计算；两路结果使用倒数排名融合（RRF，常数 60），各路候选池为 max(20, 4k)，默认每角色返回 k=4 条证据。向量按模型标识、编码算法版本和内容哈希缓存在 SQLite 中；整个患者时间线冻结证据快照，保存检索排名和引用轨迹。

患者历史以不可变时间线版本及各节点来源保存，区分提取资料、记录的临床治疗和既往模型建议。后续判断只访问当前及更早节点的源片段和相关图片，历史检验不会直接覆盖为当前值。医生确认的独立患者记忆保存在 SQLite 中并保留时间与修订，模型建议不自动成为已确认事实。追加随访建立新版本；相同上下文、模型/提示配置及证据快照的已完成节点可复用。模型请求通过 httpx 对接配置的 Responses 或 Chat Completions 服务，结构化输出经 Python 校验；临床计算与来源读取由角色授权工具执行。

## 实际技术栈

| 层次 | 技术 | 对应代码 |
|---|---|---|
| 前端 | HTML/CSS/JavaScript、Hash 路由、Fetch、EventSource、英文蓝白界面 | web/ |
| 后端 | Python 3.11.9、ThreadingHTTPServer、线程和 asyncio | server.py、longitudinal.py |
| Agent 编排 | ABC 并行、D 唯一修改、依赖传播、定向复核、有界循环 | workflow.py、contracts.py |
| 文档/图片 | ZIP/XML 按 DOCX 关系表定位图片；Pillow 12.3.0 校验 | intake.py |
| 知识库 PDF | pypdf 6.19.0 提取文本层 | server.py |
| 关键词检索 | SQLite 3.45.1 / FTS5 / BM25；标题权重 5、正文 1 | knowledge.py |
| 向量检索 | FastEmbed 0.8.1、ONNX Runtime 1.30.0、NumPy 2.4.6；多语言 MiniLM 384 维；余弦 + RRF | vector.py |
| 持久化 | SQLite 知识库/向量/医生确认记忆；JSON 时间线版本与来源；JSONL 审核事件 | knowledge.py、vector.py、patient_memory.py、longitudinal.py |
| 模型连接 | httpx 0.28.1；Responses / Chat Completions；JSON 与 function calling | providers.py |
| 临床工具 | CrCl、单位/数量/疗程计算、有限说明书规则、证据与原图查询 | clinical.py、clinical_tools.py |
| 验证 | unittest、隔离模型夹具、本地真实向量检索、浏览器交互 | tests/、verification.md |

## 参数与数据位置

| 参数 | 当前值 |
|---|---|
| 提取块 | 最多 3,000 字符 / 2 图；保留段落与图片关联；无标点长段落按长度切分 |
| 提取并发 / 单块超时 | 全局 3 / 120 秒 |
| 患者并发 | 2；同一患者建议顺序生成 |
| ABC 并发 / D 修订上限 | 3 / 3，可配置 |
| 格式/引用修复 | 同一 Agent 最多重试修复 1 次，仍在原会话超时预算内；校验不放宽 |
| 默认 Top-K | 每角色 4，可配置 |
| FE 启动器 | Sol；Responses；low 推理强度；最多 6,000 输出 token；每 Agent 会话 240 秒 |
| 通用服务默认 | 每会话 60 秒；最多 3,000 输出 token；模型由配置指定 |
| 温度 | 未显式设置，不写成 0.1 |
| 提示版本 | 2026-10-07.en.v7 |
| 计算位置 | 嵌入模型在本机 CPU；临床 LLM 在配置的 API 服务端 |
| 本机入口 | http://127.0.0.1:8774/#/new |

- runs/knowledge.sqlite3：知识文档、片段及 FTS5。
- runs/vectors.sqlite3：模型/内容寻址的 float32 向量缓存。
- runs/embedding-models/：公开嵌入模型权重。
- runs/sources/：上传文件、按时间隔离的片段及图片。
- runs/extraction_cache/：按块和模型/提示配置缓存的原始及校验后结果。
- runs/series/SER-*/：患者时间线、证据快照和事件；支持失败/重启后重试。
- runs/<run-id>/：各时间点的病例、证据、retrieval_trace.json、草案、审核与签署。
- runs/patients.sqlite3：医生确认的历史记忆；模型建议需明确审核。

上述私有运行数据、数据库和权重被 Git 忽略。没有引入 Milvus、PostgreSQL、FastGPT，也没有本机 A100 临床大模型推理。安装命令：python -m pip install -e ".[llm,pdf,images,vector]"。首次使用向量检索下载公开模型，后续使用本地缓存；未安装 vector 或 VTE_VECTOR_ENABLED=0 时明确显示关键词检索，已启用的向量编码故障明确报错。

## 研究解释边界

流式是分块完成与节点进度流，不把未校验的部分 JSON 逐 token 展示为结论。自动时间分组依赖明确标题；无可靠分界的材料保留在同一节点，日期不明保持未知。知识库内容不会因增加向量算法而自动扩充；药品和疾病覆盖不足仍需补充来源。软件测试和合成病例实跑不等于临床效能验证。
