# 验证记录

## 2026-10-12 — 中文病例库与医生评审站

- 本轮实现的完整软件检查为167项unittest通过；覆盖邮箱验证码、会话、访问隔离、评分校验、草稿版本、提交锁定、重复导入及不可替换已发布回答。复接会话时核对了原始测试输出，未把临床运行完成计作软件测试。
- 统一数据目录去重后30例：旧10例41个节点复用，新增20例66个节点全部产生最终建议。旧回答仅增加中文译文并保留英文原文，新回答直接中文生成。共96个节点完成内部审核、11个保留分歧；这些计数不是医生评价或临床正确率。
- `scripts/verify_rating_bundle.py --previous-archive runs/rating-portal-release-b.tar.gz`：107个回答与原运行/译文对应、来源不跨未来节点、旧48个已发布回答完全一致，139张引用图片PNG格式和SHA-256均通过。核验详情保存在Git忽略的`data/vte_dataset/final-verification.json`；仅检查已知个人编号/地址模式，不替代完整隐私审计或临床核对。
- 后台浏览器使用隔离合成病例完成七维评分、自动保存、提交后进入下一节点，以及回看已锁定评分/开放医生参照；1280×720无文档溢出，未观察到JS错误。测试截图和评分仅在`runs/rating-portal-qa`，不进入正式病例评分库。
- 评分规则为`VTE-R1-2026-10-12`研究初版。正式医生试评、量表校准、独立临床验证和统计分析尚未完成。邮件服务连接与认证已检查，真实收件须由授权医生正常发起验证码登录确认。

## 2026-10-07 — v0.7 longitudinal intake and hybrid retrieval

- Final automated check: 140 unittest tests pass; JavaScript syntax and Git whitespace checks pass. Regression coverage also ensures a coordinator draft is retained and marked incomplete when its review fails.

- Previous upload/format fixes were fast-forwarded into local main before this implementation. The new product flow uploads or pastes a case directly, separates Word files by patient, streams extraction-block and visit progress, and presents the coordinator answer. Demo HTTP endpoints are disabled in the product; CLI/debug fixtures remain available explicitly.
- Automated coverage includes DOCX relationship ordering, table rows, image/timepoint isolation, bounded block size, repeated visits, history preambles, archive handling, parallel extraction, per-block retry, restart recovery, follow-up version reuse, patient separation, historical labs versus current values, model-suggestion provenance, and credential exclusion from saved records.
- Hybrid retrieval tests use controlled semantic vectors for ranking/cache invariants: Chinese query without keyword overlap, role filtering, immutable returned evidence, persistent content deduplication, modified-text reindexing, archive/snapshot boundaries, and explicit embedding failures. These fixture tests do not claim neural retrieval quality.
- A separate real FastEmbed/ONNX run loaded multilingual MiniLM and indexed all 386 existing local knowledge passages. Two Chinese queries returned English source passages; the local vector cache held 388 document/query embeddings after the smoke test. First indexing plus both queries took 26.48 seconds on this workstation; this is not a latency benchmark or a clinical retrieval-quality evaluation.
- The ten new Word files were checked locally for section planning: 4, 5, 4, 5, 3, 4, 4, 4, 4, 4 timepoints. The duplicate follow-up heading in one file is merged; each source's embedded images remain linked to the correct section. These original patient files were not submitted to FE or committed to Git.
- Browser testing verified the English upload page, automatic transition to the patient timeline, partial block progress before final output, and the Retry control. The live test uses a wholly synthetic two-visit case with GPT-5.6 Sol, not any of the original patient cases. A first live C assessment returned an unknown citation identifier; strict validation rejected it. The workflow now offers one scoped structural/citation repair within the original call time budget, then applies the same validation again. Invalid citations are never silently accepted; regression tests cover correction and persistent rejection.
- Current parameters and distinctions between block/event streaming, local embeddings and remote clinical model inference are documented in technical-stack.md. Private QA files and model outputs remain under ignored runs/.
- Final live outcome: both dates in the synthetic Sol case reached `conditional` with specialist review complete. A second-visit attempt hit the 240-second call timeout; retry reused the first completed recommendation and all three extraction blocks, then completed the second visit. Browser knowledge search using a Chinese renal/dosing query and the B filter returned English label/guideline passages. No live result is described as a clinical validation or a latency guarantee. Test cases/runs are copied to `runs/qa-v07/`; originals remain intact with a software_test purpose tag and are hidden from product lists.

## 2026-10-04：英文页面与双语流程图

- 按用户要求将 v0.5 新增资料表、条件性建议标题、按钮、占位符、上传说明和提示统一为英文；移除重复中文字段标签。临床事实与既有模型回复保持原文，未重跑模型或代填医生确认。
- JavaScript 语法与 Git 差异检查通过；前端源码无中文界面字符串。后台浏览器核对英文资料表、四种回应选项、英文报告入口；当前可见页面无中文文案、无页面横向溢出、控制台无错误。本轮仅文案与图示修改，未重复运行已通过的108项后端测试。
- `docs/figures/` 新增中英各一份 PNG/SVG/PDF，四面板逻辑一致；明确附条件通过、定向修订、医生按需补充与新运行回路，保留拟定评价面板。共享脚本和中文标签表可重建；两份PDF均一页、PNG均2280×2390、SVG语法有效、关键文字完整、文字包围框无重叠，并完成渲染目视检查。
- 页面继续由8770服务提供，前端刷新已生效，无需重启后端。新截图仅保存在忽略的运行目录；论文主稿和2026-10-03旧版图未修改。

## 2026-10-04：v0.5 条件性建议与医生资料表

- 108 项 unittest 全部通过，0 跳过；JavaScript 语法、Python 编译及 Git 空白检查通过。新增测试覆盖“B 要修改引用、C 缺信息”仍交 D 修订后完成条件性审核，无假设不能条件性通过，共享假设变更使 ABC 批准失效，以及常规缺项不阻断。
- 22 项资料表支持 provided / absent / not_relevant / unknown，医生确认和时间严格校验。未知、无、不重要不会混为一个事实；已知阳性不因“不重要”消失，矛盾确认会报冲突；不能把肌酐等数值填为“无”。补齐同一检验的元数据、追加更正、保存原报告及标签、父运行关联和证据下载均有测试。
- 在隔离目录 `runs/qa-v05` 完成浏览器交互：合成病例确认“无出血”、活动能力“本次不重要”，保存后提示旧报告尚未应用补充资料；创建后续运行、上传合成文字资料并检查来源、执行离线演示。子运行保留父标识和医生确认，归一化出血值为 false，原病例和报告未改写。控制台无错误。演示结果及速度不代表真实模型效果。
- 以原脱敏基线、同一证据快照和 GPT-5.6 Sol 发起一次真实 FE 联调，没有代填临床事实。11.4 秒时发生 `RemoteProtocolError`，未生成新草案；失败记录保留，没有盲目重发。新条件性流程已通过确定性及接口验证，本次真实模型全流程未完成。
- 历史 Sol 报告保持原来的审核状态，不追溯改写为条件性通过。v0.5 的新规则适用于新启动的运行。

## 2026-10-04：产品改名与 FE 真实模型接入

- 产品名改为 **VTE Anticoagulation Assistant**，生成入口改为 New recommendation / Generate recommendations；保留已有处方核查、内部 Specialist review 和包/仓库技术标识。报告优先展示 D 的汇总建议，并显示 D 所用模型。
- FE 启动器只读当前用户既有本地配置，密钥仅注入本进程。固定 FE HTTPS 地址校验、两款模型选择、角色覆盖清除和不修改原配置均有测试；运行目录和私密配置未纳入 Git。
- Responses 适配器修正 JSON 模式的输入要求，采用 SSE 完成事件解析，保留加密 reasoning 与工具调用上下文；不把中断的文本片段当作完整结果。连接建立失败最多重试两次；不对读取中断盲目重发整个模型请求。远端错误不记录响应体或凭据。
- `python -m unittest discover -q`：99 项通过，0 跳过。Python 编译、JavaScript 语法、Git 空白检查通过。浏览器核对改名、生成/已有处方两种任务的按钮、实际模型报告；390×844 窄屏导航及报告无页面横向溢出，之后恢复默认视口。
- 已用用户指定的 FE 接口实际调用 `gpt-6-astra` 和 `gpt-5.6-sol`，两者均产生过 ABC 判断与 D 汇总建议。输入为人工核对后的脱敏基线文本，原始带标识图片、后续处方与结局没有发送；使用同一病例及选中的四份官方资料。真实工具调用和 RAG 检索记录保存在本地运行目录。
- 首轮联调发现 HTTP 400、连接中断和超时，各次失败记录均保留。早期生成 D 草案的两次运行未完成复核，不能视为全流程通过；后续同参数联调状态在下条记录。Astra 最后一轮在 A 初判会话达到240秒上限，仍可查看它此前生成的真实草案。
- 最后一轮 Sol 已完成 ABC 初判、D 汇总及 ABC 复核：117.0291 秒，7 个 Agent 会话、12 次模型请求、11 次工具调用；A=approve、B=revise、C=needs_information，按规则以 `needs_human_review / missing_information` 结束，v1、0次D修订，没有全部通过。该病例缺失事实需要补充，程序没有让 Agent 自行补齐后继续。浏览器已核对该状态和真实建议正文，控制台未见 JavaScript 错误。
- 最终 FE 入口为 `http://127.0.0.1:8769/`；本轮不是临床效果评测，未更新论文或流程图。模型配置及其与通用默认值的区别见 [technical-stack.md](technical-stack.md)。

## 2026-10-04：v0.4.0 患者记忆、图文输入与工具会话

- 接续中断时的 5 个未完成文件，原件备份在 `runs/resume-backup-20261004/`；保留 ABC 并行、D 单写者及定向复核语义。
- `python -m unittest discover -q`：93 项通过，0 跳过。覆盖真实 function-calling 协议往返（httpx MockTransport）、Chat Completions/Responses、原图消息、工具权限/参数/轮数上限、拒绝非有限 JSON、来源隔离、计算与单位边界、患者双时间截断/追加更正、模型建议不能自升为事实、同就诊医生方案留出、标签不入模型上下文、不可变快照、DOCX/图片导入及 HTTP 接口。
- Python 编译、JavaScript 语法、Git 空白检查通过。
- 后台浏览器在 `runs/qa-v04` 隔离目录验证患者新增/回显、完整病例 JSON 导入、图片上传与来源日期/核对人、资料核查、研究标签保存、审核和审计显示。合成审核 `20261004T032902Z-64860ee5`：v2，9 次模拟会话，审核 ABC → A；标签保存 1 条，检查 `events.jsonl` 未包含标签内容。控制台未见 JavaScript 错误。
- 用户指定桌面 Word 仅在临时目录做本地解析：正文 1,866 字符、6 张嵌入图片；未将原病例上传模型或复制进 Git。
- 显式导入 4 份公开官方原件：NICE NG158、DailyMed XARELTO、Methotrexate、Sulfamethoxazole/Trimethoprim。正式本地库 4 份、386 片段，关键词检索命中已核对；标题保留 UK/US，原件、文本、URL、SHA-256 与抓取日期保存在本地 manifest。NKF 页面由浏览检索核对，但自动下载返回 403，因此未加入导入包。
- 最终本地服务以 `--no-browser --port 8768 --runs runs` 后台运行；`/api/info` 核对 v0.4.0 与新功能列表。8767 的中途检查服务保留，请使用 8768。软件未配置真实模型名称/API key，视觉提取与工具往返均以模拟接口验证，未报告实际模型准确率或延迟。
- 技术栈及论文方法写法更新于 [technical-stack.md](technical-stack.md)，操作方式见 [workspace-v04.md](workspace-v04.md)。

## 2026-10-03：v0.3.0 英文界面与持久知识库

- 英文蓝白界面，首页四个白大褂机器人，移除原品牌副标题、宣传语与侧栏说明；新增 Knowledge base 入口。内置演示、提示模板及报告标题同步为英文，已有病例和历史数据不改写。
- `python -m unittest discover -s tests -v`：48 项通过，0 跳过（本机已安装 httpx 与 pypdf）。新增检查覆盖数据库重新打开后持久化、去重、整批校验事务、英文与中文检索、角色过滤、标题权重、无命中、归档恢复、原文分段偏移、不可变审核快照、知识库接入审核、拒绝合成证据进入模型模式，以及 PDF 正文提取与空白 PDF 报错。
- `node --check vte_review/web/app.js`、`python -m compileall -q vte_review` 与 Git 空白检查通过。
- 后台浏览器使用隔离目录 `runs/kb-ui-qa`：通过表单添加合成资料、关键词检索、按 B 过滤、选入审核、加载合成病例并执行定向循环。结果 v2、9 次模拟调用，审核角色 ABC → A；报告引用显示知识库片段 ID、原始来源 `local:ui-test`、版本 `test-v1` 和原文。
- 通过网页文件选择器导入生成的单页合成 PDF，确认正文预览、补全版本后保存；通过界面验证归档与恢复。数据库测试数据未复制到日常知识库。
- 默认桌面及 390 × 844 窄屏检查：首页机器人、知识库、导入抽屉无页面横向溢出。页面控制台未观察到 JavaScript 错误。
- 实现为本地 SQLite 全文检索，未接入向量模型；正式指南资料与真实模型调用未在本次验证中运行。真实配置与论文段落见 [technical-stack.md](technical-stack.md)。

## 2026-10-03：v0.2.0 本地软件

- 保留用户新增的本地 HTTP 服务、前端、SSE、签署、CLI 和启动脚本；修改前源码备份保存在本地忽略目录 `runs/local-before-workbench-20261003.zip`。
- `python -m unittest discover -s tests -v`：36 项通过，0 跳过。新增检查覆盖无效/非有限参数不创建运行、非法 SSE 游标、跨站请求拒绝，以及 SSE 回放、定向复核和报告导出的一致性。
- `node --check vte_review/web/app.js`、`python -m compileall -q vte_review`、`git diff --check` 通过。
- 在本机浏览器连接隔离运行目录 `runs/ui-qa`，完成定向演示：前端实时出现 ABC 并行初判，结束时自动更新，无需刷新；第一轮 ABC，D 修订一次，第二轮仅 A，最终 v2、9 次模拟调用。
- 手动浏览器验证：版本增删对比、证据原文抽屉、Esc 关闭与焦点恢复、合成记录签署并存档、病例表单/JSON 切换、错误 JSON 保留且阻止启动、内置证据导入、模型名称刷新后保留、使用指南。
- 默认桌面视口及 390 × 844 窄屏验证：工作台、病例向导均无页面横向溢出；窄屏步骤条采用紧凑样式，底部导航可用。数据表在自身容器内横向滚动。
- 页面控制台未观察到 JavaScript 错误。演示输出和测试签署均为合成内容，未发送真实病例或连接真实模型。
- 技术栈与可写入论文的方法段落见 [technical-stack.md](technical-stack.md)。

## 2026-10-02：初始工作流

日期：2026-10-02。

范围：工作流与接口契约原型，不是临床验证。

- 环境：Windows，Python 3.11.9，httpx 0.28.1。
- `python -m unittest discover -s tests -v`：26 项通过，0 跳过。
- `python -m vte_review demo --output runs/targeted-demo`：返回 0；先审核 ABC，再只审核 A；D 修订 1 次；共 9 次模拟模型调用。
- HTTP 适配器通过 httpx MockTransport 验证请求结构、按角色选模型、拒答/截断/格式错误及 HTTP 错误处理，没有调用真实服务。
- 演示病例和证据均为确定性合成数据。其耗时不能用于报告真实模型加速效果。

未执行：真实模型 API、真实患者数据、临床安全性审计、指南一致性评测。


## 2026-10-05 — v0.6 automatic case intake

- 118 Python unit/integration tests pass. New coverage: automatic unverified intake without dates, retained unknowns, null readings, conflicting readings, age/weight unit normalization, historical cutoff, strict research-input compatibility, empty knowledge base, no implicit demo default, and upload/extract/automatic-library-snapshot/workflow completion with an isolated test provider.
- JavaScript syntax and Git whitespace checks pass.
- Browser integration on isolated localhost:8879: selecting a synthetic TXT file triggered upload, extraction, automatic evidence selection and a complete ABC/D workflow without further clicks. Uploaded records retained unverified status. Mock provider results are software-test outputs, not real clinical/model validation.
- Empty-library failure preserved uploaded files and extracted data. Restoring the library and clicking Retry created a new run; extraction records stayed at one (no repeated extraction).
- Overview and Quick start contain no Run demo entry; the upload page has no mode selector, manual extraction button or evidence step. Knowledge base remains searchable/editable and is used automatically.
- Final production instance: localhost:8771, v0.6.0, GPT-5.6 Sol, API credentials available, 4 existing knowledge documents. Existing data remains in runs. No real patient record was submitted to the model during this change.
- The original service was retained after automatic approval rejected stopping/restarting it without a stated reason. Use 8771 for the final version; browser drafts on different ports are separate.


## 2026-10-05 — v0.6.1 extraction-note compatibility

- Reproduced user-visible boundary failure: Extraction issues must be strings. The failed extraction had completed its model response and had not created a recommendation run; this error is not evidence of a gateway timeout.
- Extraction notes now accept text, structured JSON notes, a single text/object note, or a null empty container. Structured notes are preserved as JSON text with count/size/finite-JSON limits. Clinical observation fields and allowed-source checks remain strict, and observations remain unverified.
- Raw model output is retained in the private local intake record alongside normalized output. Validation failures retain the raw response plus validation_error for diagnosis. Extraction prompts now explicitly require a plain string array.
- 123 tests pass, including 5 new regression tests for structured notes, container variants/limits, unchanged observation boundaries, retained raw output, and failed-response diagnosis. No real patient model call was made for this fix.
- Streaming remains unchanged: the Responses adapter requests stream=true and consumes SSE until response.completed; partial text is not exposed as a validated answer. The browser receives workflow events over SSE, while intake currently waits for its full JSON response. Chat Completions uses a non-streaming request.
- Final local service is 127.0.0.1:8772 (v0.6.1, prompt 2026-10-05.en.v6). The existing browser draft and source attachment were transferred through the case JSON UI so the physician can retry without uploading the Word file again.


## 2026-10-13：评分站R2直接替换

- Python完整测试174项通过；包含R2逐项1–3分/NA/NE理由、安全事件完整性和唯一ID、关键错误与总体判断冲突、严重度/安全评分不一致仲裁、CSV导出、旧版本请求拒绝及既有访问隔离/时间线/提交锁定。
- JavaScript语法检查通过。浏览器使用隔离的合成病例和本地验证码捕获器，未发送真实邮件或填写真实临床评分。
- 浏览器确认七维标签、按需展开、NA/NE及理由保存后刷新恢复、提交解锁下一随访、重度安全事件字段、冲突提示和提交后完整锁定回看；无控制台JavaScript错误。截图位于忽略目录 `runs/rating-portal-r2-qa/`。
- R2仍为待医生试评校准的研究草案。本次是软件验证，不是临床有效性验证。

- FE部署完成：`/opt/vte-review/releases/20261013T064703`；服务active，公网首页/health为200，未登录病例接口401。本机HTTPS health也返回 `VTE-R2-2026-10-13`，此前本机超时本轮未复现。
- 切换前只有一份由页面浏览计时生成的R1空草稿，无分数、意见或提交；备份后重置为R2空草稿。原30病例/107输出聚合内容哈希前后均为 `f027740e7520c8af1d93bbd3257584ba59760f9208630cefcb8174bb31abb5d1`。线上评分代码、前端与本地SHA256一致。

- 同日小数评分增补：评分站35项测试通过，新增小数保存/刷新/提交/CSV及低分、安全阈值检查；拒绝越界、布尔值、NaN/Infinity和数字字符串。浏览器用合成病例验证3.5、4.25、2.5输入、低分说明及刷新恢复，控制台无错误，截图 `runs/rating-decimal-qa/decimal-scores.png`。


## 2026-10-14：账号密码登录与四方法分组

- 183项完整测试通过，其中评分站42项；新覆盖随机盐/密码验证/限速/禁用即时失效、HTTP Origin和会话cookie、账号评分与导出隔离、方法时间线和导出隔离、空组/非法组、旧表事务迁移保留所有报告和评分。
- 后台浏览器用合成病例和独立测试密码验证错误密码提示、账号登录、四组列表、切组前自动保存、4.25小数返回恢复、空组待导入、不同账号评分不串用。未发送真实邮件，未给真实病例评分。
- 本次部署只分类已有报告并开通明确指定的五个账号，没有运行新的模型对照批次，也未把其他方法的结果复制到空组。
- FE正式发布 `/opt/vte-review/releases/20261014T033847`，SQLite备份 `/opt/vte-review/backups/r2-20261014T033847`。五个正式账号均通过公网HTTPS登录、身份读取、四组计数及退出验证，cookie带Secure/HttpOnly/SameSite=Strict；没有打开真实评分输出或新增评分。Python默认User-Agent遇Cloudflare 1010，使用明确的验证客户端User-Agent后通过。
- 发布后原107份报告的ID、病例、位置、哈希和payload与备份逐行一致；已有2条评分记录所有字段逐行一致。5账号使用5个不同的随机盐。只有reviewed组有30病例107输出，其他3组为0。

## 2026-10-14：新增病例批次隔离

- 57项相关测试通过（新批次准备/路径隔离、既有纵向流程及评分站）；新测试确认已完成病例不重建、已启动批次输入不可覆盖、当前处方留出和下一节点继承、路径不能逃出数据目录。知识库快照连接显式关闭，避免Windows文件占用。
- Y2025.12包含10份DOCX，与原30份文件和文本图片指纹均不重复；40个原始病例编号也无重复。新增CASE31–40共39时间点、40张原图；已目视检查图像归属，四幅仅去除残余页眉。准备结果核对初始3张检验图保留、当次处方图留出、下一节点带入既往处方以及已知标识字段去除；原30条manifest记录逐字段不变。
- 数据和模型结果均在Git忽略目录；新批使用独立processing/sol-20261014，冻结原107输出供发布前不可变校验。本记录不把输入准备或内部审核等同于临床正确性验证。
- 新批10例39节点全部完成：37份内部条件性完成、2份保留审核分歧，均原样保留。期间59次请求级流式失败自动重试，病例恢复尝试均为1次；没有为了得到通过结论而重跑报告。
- 全量导出40例146报告179张资料图，146个时间点的来源范围、报告与原运行对应关系、图片内容哈希均通过；原107份已发布报告逐项不变。41份旧中文译文和105份中文原生报告分别记录，整体内部状态为133 conditional、13 needs_human_review。
- FE仅增量导入数据，未重启评分站或其他业务。原107输出的所有列、已有2条评分及5个账号均与导入前逐行一致，SQLite quick_check=ok；服务数据包同时更新为最新40例。上传包SHA256为460d22a1956b2c4db5a7b086236e18521f08b6ef5a7a6df32c121a0100efa048。
- 本批HTML记录位于 `data/vte_dataset/processing/sol-20261014/实验记录.html`，包含进度、设置、核验、重试及完整原始回答，保留分歧节点不遗漏；浏览器检查无横向溢出。统一实验入口位于 `data/vte_dataset/实验记录.html`。
- 数据导入后5账号再次逐一经公网HTTPS登录、读取40例及四组计数、退出通过；仅reviewed为146，其余为0。服务active，公网health200，未登录病例接口401。数据库导入前备份为 `/home/ubuntu/vte-review-deploy-20261012/ratings-sync-20261014T053328.sqlite3`。
- 随后将评分说明中的旧固定病例数改为“以当前队列为准”，评分规则不变；只重启vte-review，未重启其他业务。最终release `/opt/vte-review/releases/20261014T053531`，备份 `/opt/vte-review/backups/r2-20261014T053531`；40病例、146输出、2评分、5账号所有列与更新前备份逐行一致，公网health200。
