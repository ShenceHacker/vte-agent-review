# Manuscript comparison generation

User-facing experiment records for this VTE project are always HTML (preference
confirmed 2026-10-14); manuscript results remain tables. The main local reading
entry is `data/vte_dataset/实验记录.html`, covering progress, configuration,
verification, retries and links to full answers and historical experiments.
Raw JSON/JSONL/CSV files remain reproducibility data, not the required reading
interface. The runner updates this HTML entry alongside progress and final status.

The four configurations are `baseline`, `rag`, `synthesis`, and `reviewed`.
The manuscript's third and fourth groups are paired stages of the existing
multi-role workflow. `synthesis` is copied verbatim from its first
`draft_created` event, before any specialist review. It is **not** a newly run
independent static multi-agent longitudinal system. This runner never invokes
the reviewed method.

## Inputs and interpretation

- Read the authoritative cohort `batch.json` and `series.json` pointers; freeze
  each timepoint's original `case.json`, library hash, source run and first
  ABC retrieval selections. Verify source IDs belong to the current or earlier
  nodes. Do not choose runs based on clinical approval or output quality.
- Baseline and RAG receive exactly the same source text and extracted patient
  observations. Remove the preceding reviewed model recommendation from both
  inputs; retain documented historical treatment. Reuse extraction as recorded,
  including errors, rather than correcting only the controls.
- The two single-generation groups use the same prompt. Baseline gets no
  evidence; RAG gets the deduplicated union of the initial ABC top-4 selections
  from the original frozen hybrid vector/BM25 library. No later searches,
  specialist conclusions, reviews or clinical checks are supplied to either.
  Both lack tools and direct screenshot access. The original workflow can
  inspect screenshots and use calculation/retrieval tools. Therefore this is a
  comparison of configurations on shared extracted records, not an isolated
  causal estimate of review or agent count.
- The paired synthesis/reviewed stages preserve the original longitudinal
  context, which can include prior reviewed model suggestions. This is a
  material difference from the two single-generation baselines. Within-pair
  pre/post review analysis remains possible; do not claim that all four groups
  have identical entire prompts or model-history inputs.
- Preserve original generation language by cohort: historical first 10 cases
  English, later cases Chinese. Chinese translations used by the rating website
  are presentation artifacts, not new clinical generations. Do not mix language
  strata without reporting this distinction.
- GPT-5.6 Sol, Responses, reasoning low, 6000 maximum output tokens, 240-second
  timeout, temperature not explicitly set. Persist requested and returned model
  identifiers; a gateway alias alone does not identify an immutable backend.

## Run and resume

From the repository root, prepare the frozen controls without model calls:

```powershell
.venv/Scripts/python.exe scripts/run_comparison_dataset.py
```

Smoke-test the first timepoint, then run all available points:

```powershell
.venv/Scripts/python.exe scripts/run_comparison_dataset.py --run --limit 1
.venv/Scripts/python.exe scripts/run_comparison_dataset.py --run --concurrency 4
.venv/Scripts/python.exe scripts/run_comparison_dataset.py --verify
```

Run again after a new cohort produces its initial drafts. Completed matching
requests are reused. Changed inputs/protocols are rejected; use a new directory
for a genuinely new experiment. Use only one runner per output directory.
`--ssh-tunnel` selects an already established encrypted forward from local
18881 to the same FE gateway; credentials remain in process memory. The runner
does not create a tunnel, change gateway settings, or write credentials.

Default private output is `data/vte_dataset/comparison-20261014/`:
`protocol.json`, `progress.json`, and `nodes/CASE##-T#/input.json`, with separate
`baseline`, `rag`, and `synthesis` result folders. API requests, received raw
responses, timing, transport failures, response identifiers, token usage and
content hashes are retained. Unknown citation IDs are flagged and retained,
not resampled until they look correct. Received schema-invalid responses and
refusals are terminal failures; only bounded transport retries are allowed.
Successful received responses can be recovered after a local interruption.
Only complete or review-required authoritative nodes are discovered, so an
in-flight retry cannot silently change a frozen source. `--verify` checks saved
responses against outputs and the initial draft against its source event, then
writes `verification.json`, `metrics.csv` and a searchable `clinical_results.html`.

For a finite cohort still being processed by the original workflow, start this
only after any existing runner has exited:

```powershell
.venv/Scripts/python.exe scripts/run_comparison_dataset.py --run --follow-target 146 --wait-minutes 180 --verify
```

This waits for authoritative completed/review-required source nodes, reuses
finished controls and stops at the target or time bound. `final-status.json`
distinguishes complete, failed outputs and source-wait timeout. It does not
start the full system, publish results, or schedule a recurring task.

All patient inputs, outputs, originals, credentials and local reports remain
Git-ignored. Only implementation, synthetic tests and documentation go to GitHub.
No physician ratings or clinical efficacy claims are generated by this runner.


## 2026-10-15：后续精简表达版本
提示版本升级至完整系统 `2026-10-15.en.v8`、单模型对照 `2026-10-15.comparison.v2`。后续生成采用医生会诊短建议：先给基于当前资料的倾向与可执行措施，再列真正改变决策的条件和复评项；减少重复病史、通用排查清单、过度前置核实和内部角色措辞。shared_plan 目标约400–700中文字或220–350英文词，属于软目标，不以删去关键剂量、疗程、禁忌和条件分支换取篇幅。ABC仍完整核查，但只报告实质问题，D避免重复展开。
已有2026-10-14对照438份及完整系统结果不重跑、不改写、不重新标记提示版本；已生成的HTML只改布局。新对照默认目录 `comparison-20261015-concise`，与旧队列隔离。审核前组仍提取真实首次汇总，其风格取决于源运行，不单独改写。此次仅检查提示词接入与程序测试，未调用模型验证实际字数或临床表现。
