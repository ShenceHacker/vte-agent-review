"""Deterministic synthetic fixture, deliberately not a medical model."""
from __future__ import annotations

import asyncio
from copy import deepcopy

from .contracts import ROLES
from .providers import ModelReply

DEMO_CASE = {
    "case_id": "SYNTHETIC-001",
    "question": "演示 VTE 抗凝方案的分工审核与定向返修；不产生真实处方。",
    "facts": {"synthetic": True, "scenario": "虚构的已确诊 VTE 病例，仅测试通信流程"},
    "missing_information": ["真实用药决策所需的临床资料未提供"],
}
DEMO_EVIDENCE = [{
    "id": "DEMO-PROTOCOL", "title": "VTE 演示审核协议（非临床指南）",
    "source": "local:synthetic-fixture", "version": "2026-10-02",
    "text": "VTE 抗凝获益与疗程演示部分必须包含复评节点；药物安全、出血风险只用占位文本。不得产生处方。",
    "roles": list(ROLES), "synthetic": True,
}]


class DemoModel:
    is_demo = True

    def __init__(self, scenario: str = "targeted", delay: float = 0.02):
        self.scenario = scenario
        self.delay = delay
        self.revision_count = 0

    async def complete(self, task: str, role: str, payload: dict) -> ModelReply:
        await asyncio.sleep(self.delay)
        evidence_ids = [payload["evidence"][0]["id"]]
        if task == "assess":
            data = {"summary": f"{role}：合成流程评估，不作医疗决策。", "evidence_ids": evidence_ids, "uncertainties": ["非临床证据"]}
        elif task == "synthesize":
            data = {
                "shared_plan": "合成演示：仅验证审核通信，不输出任何实际治疗建议。",
                "sections": {r: {"text": f"{r} 的演示段落。", "evidence_ids": evidence_ids, "depends_on": []} for r in ROLES},
            }
            if self.scenario == "dependency":
                data["sections"]["B"]["depends_on"] = ["A"]
        elif task == "review":
            requires_fix = role == "A" and ("复评节点" not in payload["section"]["text"] or self.scenario in {"limit", "stagnant", "missing"})
            if requires_fix:
                data = {
                    "verdict": "needs_information" if self.scenario == "missing" else "revise",
                    "issues": [{"id": "A-01", "problem": "演示协议要求的复评节点尚未满足。",
                                "requested_change": "补充演示复评节点。", "evidence_ids": evidence_ids, "related_roles": []}],
                    "note": "请 D 修改 A 部分，再交 A 审核。",
                }
            else:
                data = {"verdict": "approve", "issues": [], "note": "本角色负责的演示内容通过。"}
        elif task == "revise":
            self.revision_count += 1
            draft = deepcopy(payload["draft"])
            if self.scenario != "stagnant":
                draft["sections"]["A"]["text"] += f" 已增加演示复评节点（修订 {self.revision_count}）。"
            if self.scenario == "shared":
                draft["shared_plan"] += " 共同前提已更新。"
            data = {"draft": draft, "reason": "针对 A-01 补充演示内容。", "affected_roles": []}
        else:
            raise ValueError("unknown task")
        return ModelReply(data, "deterministic-demo")
