"""Validate all model-controlled boundaries before changing workflow state."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

ROLES = ("A", "B", "C")
ROLE_NAMES = {
    "A": "Anticoagulation benefit and duration",
    "B": "Drug eligibility and medication safety",
    "C": "Bleeding risk and patient constraints",
    "D": "Coordination and revision",
}


class ContractError(ValueError):
    pass


def object_fields(value: Any, required: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != required:
        raise ContractError(f"{label}: expected fields {sorted(required)}")
    return value


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{label}: expected nonempty string")
    return value


def strings(value: Any, label: str, allowed: set[str] | None = None) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise ContractError(f"{label}: expected string list")
    if len(set(value)) != len(value):
        raise ContractError(f"{label}: duplicates are not allowed")
    if allowed is not None and not set(value) <= allowed:
        raise ContractError(f"{label}: contains unknown identifiers")
    return value


def citations(value: Any, evidence_ids: set[str], label: str) -> None:
    strings(value, label, evidence_ids)
    if not value:
        raise ContractError(f"{label}: at least one retrieved evidence ID is required")


def validate_case(value: Any) -> dict:
    required = {"case_id", "question", "facts", "missing_information"}
    optional = {"patient", "task_type", "candidate_plan", "observations", "source_ids", "source_context"}
    if not isinstance(value, dict) or not required <= set(value) or set(value) - required - optional:
        raise ContractError("case: expected core fields and supported patient/source fields; keep research labels separate")
    text(value["case_id"], "case_id")
    text(value["question"], "question")
    if not isinstance(value["facts"], dict) or (not value["facts"] and not value.get("observations")):
        raise ContractError("facts: expected nonempty object")
    strings(value["missing_information"], "missing_information")
    from .patient_memory import identifier, instant
    from .intake import SOURCE_ID
    try:
        if "patient" in value:
            p = object_fields(value["patient"], {"patient_id", "encounter_id", "decision_at"}, "patient")
            identifier(p["patient_id"])
            identifier(p["encounter_id"])
            instant(p["decision_at"])
        if value.get("task_type", "generate_plan") not in {"generate_plan", "review_plan"}:
            raise ContractError("task_type: generate_plan or review_plan")
        if value.get("candidate_plan"):
            if value.get("task_type") != "review_plan":
                raise ContractError("candidate_plan is input only for review_plan; save it separately as a research label")
            text(value["candidate_plan"], "candidate_plan")
        ids = strings(value.get("source_ids", []), "source_ids")
        if len(ids) > 12 or any(not SOURCE_ID.fullmatch(i) for i in ids):
            raise ContractError("source_ids: at most 12 uploaded source IDs")
        context = value.get("source_context", {})
        if not isinstance(context, dict) or set(context) != set(ids):
            raise ContractError("source_context: supply available_at and reviewer for each source")
        for item in context.values():
            object_fields(item, {"available_at", "reviewer"}, "source context")
            instant(item["available_at"])
            text(item["reviewer"], "source reviewer")
        rows = value.get("observations", [])
        if not isinstance(rows, list) or len(rows) > 200:
            raise ContractError("observations: expected at most 200 records")
        if rows and not ids:
            raise ContractError("Observations require attached source_ids")
        for obs in rows:
            object_fields(obs, {"key", "value", "unit", "observed_at", "available_at", "source_id", "location", "status"}, "observation")
            for key in ("key", "source_id", "location"):
                text(obs[key], key)
            if not isinstance(obs["unit"], str) or obs["status"] not in {"confirmed", "unverified", "excluded"}:
                raise ContractError("Invalid observation unit/status")
            if obs["status"] == "confirmed":
                if obs["value"] is None:
                    raise ContractError("A confirmed observation needs a readable value")
                if instant(obs["available_at"]) < instant(obs["observed_at"]):
                    raise ContractError("Observation availability cannot precede its clinical date")
        import json
        json.dumps(value, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ContractError(str(exc)) from None
    return deepcopy(value)


def validate_assessment(value: Any, evidence_ids: set[str]) -> dict:
    object_fields(value, {"summary", "evidence_ids", "uncertainties"}, "assessment")
    text(value["summary"], "summary")
    citations(value["evidence_ids"], evidence_ids, "assessment evidence_ids")
    strings(value["uncertainties"], "uncertainties")
    return deepcopy(value)


def validate_draft(value: Any, evidence_ids: set[str]) -> dict:
    object_fields(value, {"shared_plan", "sections"}, "draft")
    text(value["shared_plan"], "shared_plan")
    object_fields(value["sections"], set(ROLES), "sections")
    for role, section in value["sections"].items():
        object_fields(section, {"text", "evidence_ids", "depends_on"}, f"section {role}")
        text(section["text"], f"section {role} text")
        citations(section["evidence_ids"], evidence_ids, f"section {role} evidence_ids")
        strings(section["depends_on"], "depends_on", set(ROLES) - {role})
    return deepcopy(value)


def validate_review(value: Any, evidence_ids: set[str]) -> dict:
    object_fields(value, {"verdict", "issues", "note"}, "review")
    if value["verdict"] not in ("approve", "revise", "needs_information"):
        raise ContractError("review verdict: unknown value")
    text(value["note"], "review note")
    if not isinstance(value["issues"], list):
        raise ContractError("issues: expected list")
    if (value["verdict"] == "approve") != (len(value["issues"]) == 0):
        raise ContractError("approve must have no issues; other verdicts must have issues")
    for issue in value["issues"]:
        object_fields(issue, {"id", "problem", "requested_change", "evidence_ids", "related_roles"}, "issue")
        for key in ("id", "problem", "requested_change"):
            text(issue[key], f"issue {key}")
        strings(issue["evidence_ids"], "issue evidence_ids", evidence_ids)
        strings(issue["related_roles"], "related_roles", set(ROLES))
    if len({x["id"] for x in value["issues"]}) != len(value["issues"]):
        raise ContractError("issue IDs must be unique within a review")
    return deepcopy(value)


def validate_revision(value: Any, evidence_ids: set[str]) -> dict:
    object_fields(value, {"draft", "reason", "affected_roles"}, "revision")
    validate_draft(value["draft"], evidence_ids)
    text(value["reason"], "revision reason")
    strings(value["affected_roles"], "affected_roles", set(ROLES))
    return deepcopy(value)


def dependencies(draft: dict, role: str) -> set[str]:
    """Transitive dependencies; cycles are legal and terminate via visited set."""
    found = {role}
    queue = [role]
    while queue:
        current = queue.pop()
        for other in draft["sections"][current]["depends_on"]:
            if other not in found:
                found.add(other)
                queue.append(other)
    return found - {role}


def affected_roles(old: dict, new: dict, declared: list[str]) -> set[str]:
    if old["shared_plan"] != new["shared_plan"]:
        return set(ROLES)
    changed = {r for r in ROLES if old["sections"][r] != new["sections"][r]}
    affected = changed | set(declared)
    # Use BOTH graphs: removing a dependency must not erase the need to re-review.
    for role in ROLES:
        if (dependencies(old, role) | dependencies(new, role)) & changed:
            affected.add(role)
    return affected
