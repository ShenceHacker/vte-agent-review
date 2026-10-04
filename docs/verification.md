# 验证记录

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
