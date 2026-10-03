# 验证记录

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
