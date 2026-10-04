"""Clinician-supplied information, kept separate from missing-data assumptions."""
from copy import deepcopy

from .patient_memory import instant

ABSENT_VALUES = {
    "active_bleeding": False, "prior_vte": False, "bleeding_history": "None, confirmed by clinician",
    "current_anticoagulation": "None, confirmed by clinician",
    "concomitant_medications": "None, confirmed by clinician", "allergies": "None, confirmed by clinician",
    "comorbidities": "None, confirmed by clinician", "provoking_factors": "None identified by clinician",
}
ZH_LABELS = dict(zip(
    ["age_years", "sex", "weight_kg", "vte_type_site", "diagnosis_date", "treatment_stage", "prior_vte",
     "provoking_factors", "mobility", "serum_creatinine", "renal_stable", "hemoglobin", "platelets",
     "liver_status", "active_bleeding", "bleeding_history", "current_anticoagulation",
     "concomitant_medications", "allergies", "comorbidities", "vitals", "patient_constraints"],
    ["年龄", "性别", "体重", "血栓类型与部位", "确诊日期", "治疗阶段", "既往血栓史", "诱因",
     "活动能力", "肌酐及检验时间", "肾功能是否稳定", "血红蛋白及检验时间", "血小板及检验时间",
     "肝病与肝功能", "当前是否出血", "既往出血及胃肠病史", "此前已接受的抗凝治疗", "合并用药",
     "过敏与HIT史", "合并疾病", "血压、脉搏等生命体征", "用药支持与随访条件"]))


def validate_responses(rows):
    from .clinical import FIELD_SPECS, known
    keys = {f[0] for f in FIELD_SPECS}
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("Information responses must be an array of at most 100 entries")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"field", "status", "value", "note", "clinician", "recorded_at"}:
            raise ValueError("Response requires field, status, value, note, clinician and recorded_at")
        if row["field"] not in keys or row["field"] in seen:
            raise ValueError("Unknown or duplicate information field")
        seen.add(row["field"])
        if row["status"] not in {"provided", "absent", "not_relevant", "unknown"}:
            raise ValueError("Unknown information response status")
        if not isinstance(row["clinician"], str) or not row["clinician"].strip():
            raise ValueError("Record the clinician confirming the information")
        if not isinstance(row["note"], str) or len(row["note"]) > 8000:
            raise ValueError("Response note must be text (max 8000 characters)")
        instant(row["recorded_at"])
        if row["status"] == "provided" and not known(row["value"]):
            raise ValueError("Provided information requires a value")
        if row["status"] != "provided" and row["value"] is not None:
            raise ValueError("Only provided information may carry a value")
        if row["status"] == "absent" and row["field"] not in ABSENT_VALUES:
            raise ValueError("Absence is not a valid measurement/date; use unknown or not relevant")
        if row["status"] == "not_relevant" and not row["note"].strip():
            raise ValueError("Briefly state why this field is not relevant to this decision")
    return deepcopy(rows)


def resolved_facts(case):
    """Explicit confirmations may fill a gap; they cannot silently erase known facts."""
    from .clinical import ALIASES, known
    facts = {ALIASES.get(k.lower(), k): deepcopy(v) for k, v in case["facts"].items()}
    conflicts = []
    for row in case.get("information_responses", []):
        if row["status"] not in {"provided", "absent"}:
            continue
        key = row["field"]
        value = row["value"] if row["status"] == "provided" else ABSENT_VALUES[key]
        previous = facts.get(key)
        # Allow adding dates/source metadata to the same measured value.
        compatible = (isinstance(previous, dict) and isinstance(value, dict)
                      and all(not known(v) or value.get(k) == v for k, v in previous.items()))
        if known(previous) and previous != value and not compatible:
            conflicts.append(key)
        else:
            facts[key] = deepcopy(value)
    return facts, conflicts


def information_table(case, checks=None):
    from .clinical import FIELD_SPECS, clinical_check, known
    checks = checks or clinical_check(case)
    facts = checks["normalized_facts"]
    responses = {r["field"]: r for r in case.get("information_responses", [])}
    return [{"field": key, "label": label, "label_zh": ZH_LABELS[key], "roles": list(roles),
             "priority": "decision_dependent" if critical else "optional",
             "value": facts.get(key), "present": known(facts.get(key)), "allow_absent": key in ABSENT_VALUES,
             "response": responses.get(key),
             "issues": [i for i in checks["issues"] if i["code"] in {"missing_" + key, "lab_metadata_" + key, "invalid_lab_" + key, "response_conflict_" + key}]
             } for key, label, roles, critical in FIELD_SPECS]
