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
    object_fields(value, {"case_id", "question", "facts", "missing_information"}, "case")
    text(value["case_id"], "case_id")
    text(value["question"], "question")
    if not isinstance(value["facts"], dict) or not value["facts"]:
        raise ContractError("facts: expected nonempty object")
    strings(value["missing_information"], "missing_information")
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
