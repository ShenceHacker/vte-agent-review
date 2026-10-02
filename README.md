# VTE Agent Review

VTE 研究原型：**ABC 并行初判 → D 汇总 → ABC 并行审核各自部分 → D 定向修改 → 相关专家复核，直到通过或停止。**

这个仓库实现通信与审核循环，包含离线演示、可配置的真实模型接口、简易本地 RAG、运行记录。尚未接入正式病例、冻结版指南库或临床规则审计；程序内 `approved` 不等于临床验证通过。

## 立即运行

Python 3.11 及以上。从仓库根目录执行，离线演示不需要 API key 或额外依赖：

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
2. 审核结果为 `approve`、`revise` 或 `needs_information`，异议携带稳定问题 ID、理由、引用、修改要求与相关角色。
3. A 不通过就由 D 修改后交回 A。B/C 已通过且不受影响时不再调用。
4. 程序比较新旧草案的实际内容。D 修改了 B 部分，即使没申报，也必须请 B 重审。
5. `depends_on` 记录部分间依赖；变更传播使用新旧依赖图的传递闭包。删除旧依赖不能抹去此次重审要求。
6. `shared_plan` 保存药物、治疗阶段、总体方案等共同前提。它发生任何变化都会触发 ABC 重审。D 及审核者还可额外申报受影响角色。
7. 默认最多 3 次 D 修订；最后一次修改仍需复核。缺信息、无实际修改、达到上限时返回未决状态。超时、格式错误、无效引用不当作通过。
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

病例由调用者整理为结构化事实；本版本没有额外调用 LLM 自动抽取病历。

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

RAG 当前按角色过滤，用英文词与中文双字词的重合排序，缓存同查询；第二轮可用问题单补充检索。检索不到证据时停止，不拿任意条目填充。所有引用必须来自当前调用实际收到的证据。可以替换 `EvidenceIndex.search` 为已有检索服务。

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

安装 `.[llm]` 后会运行 HTTP 模拟测试；没有 httpx 时这部分明确跳过。测试包含真实协程同步屏障，验证初判和审核确实重叠执行，并覆盖定向循环、依赖传播、共同方案重审、轮次限制、无变化、缺资料、格式错误、虚构引用和超时。

当前验证状态见 [docs/verification.md](docs/verification.md)。

## 当前限制

- 没有正式指南库、药物规则引擎、肾功能计算器或临床评测集，不生成演示性真实处方。
- 引用检查验证 ID 是否存在，不证明引文足以支持医学结论。
- 依赖正确性依赖 D 的声明和专家审核；程序无法可靠推断所有潜在医学关联。修改共同前提必须放到 `shared_plan`，否则可能漏触发。
- 使用审核波次屏障，等待本轮必要审核完成后再修订；尚未实现“某专家先回复就先修订”的异步版本协调。
- 尚未做真实端点联调、结果准确性/安全性评价、持久化断点恢复或网页界面。

下一步应先确定模型端点与正式证据，再用脱敏/合成病例验证真实输出契约；论文的临床结论需要独立专家与预注册指标评估。
