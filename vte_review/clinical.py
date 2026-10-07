"""Deterministic research checks. Bounded rules never certify clinical safety."""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone

from .patient_memory import instant

RULE_VERSION = "2026-10-07.v4"
CG_SOURCE = "https://www.kidney.org/professionals/kdoqi/cockcroft-gault-equation-estimating-creatinine-clearance"
RIVA_SOURCE = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=7e9ab975-db2f-423c-a089-bc5a73313609"
NICE_SOURCE = "https://www.nice.org.uk/guidance/ng158/chapter/Recommendations"

# Canonical fields are deliberately explicit; absent, false and unknown are different.
FIELD_SPECS = [
    ("age_years", "Age (years)", "BC", True),
    ("sex", "Sex used for renal estimate", "B", True),
    ("weight_kg", "Weight (kg)", "B", True),
    ("vte_type_site", "Confirmed VTE type and site", "A", True),
    ("diagnosis_date", "Diagnosis date", "A", True),
    ("treatment_stage", "Decision / treatment stage", "AB", True),
    ("prior_vte", "Previous VTE (yes/no/unknown and details)", "A", False),
    ("provoking_factors", "Recent / persistent risk factors and dates", "A", False),
    ("mobility", "Current mobility", "AC", False),
    ("serum_creatinine", "Creatinine {value,unit,observed_at}", "BC", True),
    ("renal_stable", "Stable renal function (true/false/unknown)", "BC", True),
    ("hemoglobin", "Haemoglobin {value,unit,observed_at}", "C", True),
    ("platelets", "Platelets {value,unit,observed_at}", "BC", True),
    ("liver_status", "Liver disease and available liver tests", "BC", True),
    ("active_bleeding", "Current active bleeding (true/false/unknown)", "C", True),
    ("bleeding_history", "Previous bleeding / gastrointestinal history", "C", False),
    ("current_anticoagulation", "Anticoagulation already received (or explicitly none)", "AB", True),
    ("concomitant_medications", "Current other drugs, doses and indication (or none)", "BC", True),
    ("allergies", "Drug allergies and HIT history", "B", False),
    ("comorbidities", "Relevant comorbidities and disease activity", "ABC", False),
    ("vitals", "Blood pressure, pulse, oxygen / support if applicable", "AC", False),
    ("patient_constraints", "Adherence, preferences, cost and follow-up", "C", False),
]
ALIASES = {
    "age": "age_years", "年龄": "age_years", "sex": "sex", "性别": "sex",
    "weight": "weight_kg", "体重": "weight_kg", "vte type & site": "vte_type_site",
    "diagnosis date": "diagnosis_date", "serum creatinine": "serum_creatinine",
    "platelets": "platelets", "liver function": "liver_status", "bleeding history": "bleeding_history",
    "concomitant medication": "concomitant_medications",
}


def number(value, name: str, low: float = 0, high: float = 1e7) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be a finite number between {low} and {high}")
    return float(value)


def convert_unit(value, from_unit: str, to_unit: str, analyte: str = "") -> dict:
    value = number(value, "value")
    units = {"μmol/L": "umol/L", "µmol/L": "umol/L", "mcg": "ug"}
    src, dst = units.get(from_unit, from_unit), units.get(to_unit, to_unit)
    factors = {("mg", "ug"): 1000, ("ug", "mg"): .001,
               ("g", "mg"): 1000, ("mg", "g"): .001,
               ("g/dL", "g/L"): 10, ("g/L", "g/dL"): .1}
    if analyte == "creatinine":
        factors.update({("mg/dL", "umol/L"): 88.4, ("umol/L", "mg/dL"): 1 / 88.4})
    if src == dst and src in {"mg", "ug", "g", "g/dL", "g/L", "umol/L", "mg/dL"}:
        factor = 1
    elif (src, dst) in factors:
        factor = factors[(src, dst)]
    else:
        raise ValueError("Unsupported conversion; mL requires the actual product concentration")
    return {"input": value, "from_unit": src, "value": round(value * factor, 6), "unit": dst, "factor": factor}


def calculate_crcl(age_years, sex: str, weight_kg, creatinine, creatinine_unit: str,
                   renal_stable: bool, weight_basis: str = "actual") -> dict:
    age, weight, scr = number(age_years, "age", 18, 120), number(weight_kg, "weight", 10, 350), number(creatinine, "creatinine", .01, 10000)
    if sex not in {"female", "male"} or type(renal_stable) is not bool:
        raise ValueError("Specify female/male formula coefficient and renal stability explicitly")
    if weight_basis != "actual":
        raise ValueError("Only actual-weight calculation is implemented; another weight basis requires specialist review")
    if not renal_stable:
        return {"status": "not_applicable", "reason": "Unstable renal function / AKI: do not use a steady-state estimate", "source": CG_SOURCE}
    if creatinine_unit not in {"mg/dL", "umol/L", "μmol/L", "µmol/L"}:
        raise ValueError("Creatinine unit must be mg/dL or umol/L")
    mgdl = scr if creatinine_unit == "mg/dL" else scr / 88.4
    value = (140 - age) * weight / (72 * mgdl) * (.85 if sex == "female" else 1)
    return {"status": "calculated", "value": round(value, 2), "unit": "mL/min", "method": "Cockcroft-Gault",
            "formula": "(140-age)*weight_kg/(72*creatinine_mg_dl) * (0.85 if female else 1)",
            "inputs": {"age_years": age, "sex": sex, "weight_kg": weight, "creatinine_mg_dl": mgdl, "weight_basis": weight_basis},
            "limitations": "Estimate, not eGFR or a drug dose. Check contemporaneous inputs, body composition and clinical applicability.", "source": CG_SOURCE}


def treatment_days(start_date: str, decision_date: str) -> dict:
    try:
        start, end = datetime.fromisoformat(start_date).date(), datetime.fromisoformat(decision_date).date()
    except (TypeError, ValueError):
        raise ValueError("Use ISO dates") from None
    elapsed = (end - start).days
    if elapsed < 0:
        raise ValueError("Treatment cannot start after the decision date")
    return {"elapsed_days": elapsed, "treatment_day_inclusive": elapsed + 1, "assumption": "Continuous treatment; verify interruptions and transitions"}


def medication_quantity(amount, amount_unit: str, frequency_per_day, strength=None, strength_unit=None) -> dict:
    amount, frequency = number(amount, "amount", .0001), number(frequency_per_day, "frequency", .0001, 48)
    if amount_unit in {"tablet", "mL"}:
        expected = "mg/tablet" if amount_unit == "tablet" else "mg/mL"
        if strength_unit != expected or strength is None:
            return {"status": "needs_information", "required": expected, "reason": "Do not infer product concentration"}
        dose = amount * number(strength, "strength", .0001)
    elif amount_unit == "mg":
        dose = amount
    else:
        raise ValueError("Supported quantities: mg, tablet, mL with explicit mg strength; anti-Xa IU is not mg")
    return {"status": "calculated", "single_dose_mg": dose, "frequency_per_day": frequency,
            "daily_total_mg": dose * frequency, "note": "Equal daily totals do not imply interchangeable regimens"}


def check_regimen(drug: str, indication: str, stage: str, dose_mg, frequency_per_day, jurisdiction: str) -> dict:
    dose, freq = number(dose_mg, "dose", .0001), number(frequency_per_day, "frequency", .0001, 48)
    base = {"rule_version": RULE_VERSION, "jurisdiction": jurisdiction, "source": RIVA_SOURCE,
            "scope": "Limited US adult rivaroxaban DVT/PE label pattern; not a patient-specific prescribing decision"}
    if drug.lower() != "rivaroxaban" or indication != "adult_dvt_pe" or jurisdiction != "US":
        return {**base, "status": "not_covered", "reason": "Use the applicable local product label and specialist review"}
    patterns = {"initial_days_1_21": [(15, 2)], "treatment_from_day_22": [(20, 1)],
                "recurrence_prevention_after_6_months": [(10, 1)]}
    if stage not in patterns:
        return {**base, "status": "needs_information", "reason": "Confirm exact treatment stage, duration and indication"}
    match = (dose, freq) in patterns[stage]
    return {**base, "status": "pattern_matches" if match else "requires_review", "stage": stage,
            "observed": {"dose_mg": dose, "frequency_per_day": freq},
            "note": "Independently check renal/hepatic eligibility, bleeding, interactions, food requirements and prior anticoagulation. A pattern match is not approval."}


def known(value) -> bool:
    if value is None or (isinstance(value, str) and value.strip().lower() in {"", "null", "unknown", "not recorded", "未知", "未记录", "未提供"}):
        return False
    return not (isinstance(value, dict) and not value)


def clinical_check(case: dict) -> dict:
    from .information import resolved_facts
    facts, response_conflicts = resolved_facts(case)
    issues, observations = [], [o for o in case.get("observations", []) if o["status"] != "excluded"]
    decision = case.get("patient", {}).get("decision_at")
    automatic = case.get("input_mode") == "automatic"
    def issue(code, text, roles="D", severity="warning"):
        issues.append({"code": code, "message": text, "roles": list(roles), "severity": severity})
    for key in response_conflicts:
        issue("response_conflict_" + key, f"Clinician response for {key} conflicts with an existing fact; reconcile the source fact", "D", "blocking")
    if not decision and not automatic:
        issue("decision_time", "Specify the decision time with timezone", "D", "blocking")
    groups = {}
    usable = []
    def observation_time(obs):
        try:
            return instant(obs["observed_at"]) if obs.get("observed_at") else None
        except ValueError:
            return None
    for obs in observations:
        key = obs["key"]
        if obs["status"] != "confirmed":
            if not automatic:
                issue("unverified_observation", f"Verify {key} against source {obs['source_id']} ({obs['location']})", "D", "blocking")
                continue
            issue("model_extracted", f"{key} was extracted by a model, not confirmed by a clinician; retain source and qualify dependent decisions", "ABC", "condition")
        if obs["value"] is None:
            continue
        try:
            when = observation_time(obs)
            available = instant(obs["available_at"]) if obs.get("available_at") else None
        except ValueError:
            issue("ambiguous_source_date", f"{key} has an ambiguous date; do not infer a treatment timeline", "ABC", "condition")
            when, available = observation_time(obs), None
        if automatic and (when is None or available is None):
            issue("undated_source", f"{key} has incomplete dates; do not assume it is current or available at a historical decision time", "ABC", "condition")
            if decision:
                continue
        groups.setdefault((key, when.isoformat() if when else "unknown"), []).append(obs)
        if decision and any(t and t > instant(decision) for t in (when, available)):
            issue("future_information", f"{key} was not available at the decision time", "D", "blocking")
            continue
        usable.append(obs)
    for (key, when), rows in groups.items():
        values = {json.dumps([r["value"], r["unit"]], sort_keys=True, ensure_ascii=False) for r in rows}
        if len(values) > 1:
            issue("ambiguous_extraction" if automatic else "conflicting_observations", f"Conflicting {key} records at {when}; give conditional alternatives rather than choose a reading", "ABC", "condition" if automatic else "blocking")
    # Observations do not overwrite explicit facts; inconsistent representations block approval.
    for key in {o["key"] for o in observations}:
        rows = [o for o in usable if o["key"] == key]
        if automatic and len({json.dumps([o["value"], o["unit"]], sort_keys=True) for o in rows}) > 1 and (
                any(observation_time(o) is None for o in rows) or any(len({json.dumps([r["value"], r["unit"]], sort_keys=True) for r in g}) > 1 for (k, _), g in groups.items() if k == key)):
            issue("ambiguous_extraction", f"{key} has incompatible readings; no single value selected", "ABC", "condition")
            continue
        rows.sort(key=lambda o: observation_time(o) or datetime.min.replace(tzinfo=timezone.utc))
        if rows:
            latest = rows[-1]
            scalar_unit = ((key == "age_years" and latest["unit"].lower() in {"years", "year", "yr", "y", "岁"})
                           or (key == "weight_kg" and latest["unit"].lower() in {"kg", "公斤"}))
            if key in facts:
                existing = facts[key].get("value") if isinstance(facts[key], dict) and "value" in facts[key] else facts[key]
                unit = facts[key].get("unit", "") if isinstance(facts[key], dict) else ""
                if existing != latest["value"] or (unit != latest["unit"] and not (scalar_unit and not unit)):
                    issue("fact_source_conflict", f"Fact {key} differs from its latest confirmed source; reconcile explicitly", "D", "blocking")
            else:
                facts[key] = {"value": latest["value"], "unit": latest["unit"], "observed_at": latest["observed_at"], "available_at": latest["available_at"]} if latest["unit"] and not scalar_unit else latest["value"]
    checks = []
    for key, label, roles, critical in FIELD_SPECS:
        present = known(facts.get(key))
        checks.append({"key": key, "label": label, "roles": list(roles), "critical": critical, "present": present})
        if not present:
            issue("missing_" + key, label + " is not recorded; state a condition if this changes the recommendation", roles, "condition" if critical else "optional")
    if facts.get("active_bleeding") is True:
        issue("active_bleeding", "Active bleeding requires clinician-led assessment before routine anticoagulation planning", "BC", "blocking")
    elif known(facts.get("active_bleeding")) and type(facts["active_bleeding"]) is not bool:
        issue("bleeding_status_type", "Record current active bleeding as true, false or unknown", "C", "blocking")
    raw = json.dumps(facts, ensure_ascii=False)
    if "10余天" in raw and "10余年前" in raw:
        issue("onset_conflict", "Both 10+ days and 10+ years appear in the history; confirm onset", "A", "blocking")
    if re.search(r"否认[^。；\n]{0,20}肝病", raw) and re.search(r"乙肝|乙型肝炎|hepatitis B", raw, re.I):
        issue("liver_history_conflict", "Denied liver disease conflicts with documented hepatitis B", "B", "blocking")
    if "术后" in raw and not known(facts.get("index_procedure")):
        issue("procedure_unclear", "A postoperative label is present without an index procedure/date", "A")
    for key in ("diagnosis_date", "anticoagulation_start_date"):
        if facts.get(key) and decision:
            try:
                if datetime.fromisoformat(str(facts[key])).date() > instant(decision).date():
                    issue("future_" + key, key + " follows the decision time", "AB", "blocking")
            except ValueError:
                issue("invalid_" + key, key + " needs an ISO date", "AB", "blocking")
    for key, low, high in (("age_years", 18, 120), ("weight_kg", 10, 350)):
        if known(facts.get(key)):
            try:
                number(facts[key], key, low, high)
            except ValueError as exc:
                issue("invalid_" + key, str(exc), "B", "blocking")
    calculations = []
    valid_labs = set()
    for key in ("serum_creatinine", "hemoglobin", "platelets"):
        item = facts.get(key)
        if known(item):
            if not isinstance(item, dict) or not all(known(item.get(k)) for k in ("value", "unit", "observed_at")):
                issue("lab_metadata_" + key, key + " has incomplete measurement/date metadata; use only as explicitly dated or undated evidence", "BC", "condition")
            else:
                try:
                    number(item["value"], key)
                    when = instant(item["observed_at"])
                    units = {"serum_creatinine": {"mg/dL", "umol/L", "μmol/L", "µmol/L"},
                             "hemoglobin": {"g/L", "g/dL"}, "platelets": {"10^9/L", "x10^9/L", "10^3/uL"}}
                    if item["unit"] not in units[key]:
                        raise ValueError(key + " has an unsupported or ambiguous unit")
                    if decision and (when > instant(decision) or (item.get("available_at") and instant(item["available_at"]) > instant(decision))):
                        issue("future_lab", key + " is after the decision time", "BC", "blocking")
                    else:
                        valid_labs.add(key)
                except ValueError as exc:
                    issue("invalid_lab_" + key, str(exc), "BC", "blocking")
    if "serum_creatinine" in valid_labs and not any(i["code"] in {"fact_source_conflict", "conflicting_observations", "unverified_observation"} for i in issues) and all(known(facts.get(k)) for k in ("age_years", "sex", "weight_kg", "serum_creatinine", "renal_stable")):
        try:
            scr = facts["serum_creatinine"]
            calc = calculate_crcl(facts["age_years"], facts["sex"], facts["weight_kg"], scr["value"], scr["unit"], facts["renal_stable"])
            calculations.append({"tool": "calculate_crcl", "result": calc})
            if calc["status"] != "calculated":
                issue("renal_unstable", "Steady-state renal estimation is not applicable; renal-dependent decisions require clinical review", "B", "blocking")
        except (ValueError, TypeError, KeyError) as exc:
            issue("renal_calculation", "CrCl could not be calculated: " + str(exc), "B", "blocking")
    if case.get("task_type", "generate_plan") == "review_plan" and not case.get("candidate_plan"):
        issue("candidate_plan", "Prescription review requires the plan to review", "D", "blocking")
    for source_id, context in case.get("source_context", {}).items():
        if decision and context.get("available_at") and instant(context["available_at"]) > instant(decision):
            issue("future_source", "Source " + source_id + " was not available at the decision time", "D", "blocking")
    data_errors = {"decision_time", "conflicting_observations", "fact_source_conflict", "unverified_observation"}
    return {"rule_version": RULE_VERSION, "checklist": checks, "issues": issues, "calculations": calculations,
            "input_blocked": any(i["code"] in data_errors or i["code"].startswith(("future_", "response_conflict_")) for i in issues),
            "normalized_facts": facts, "blocking": any(i["severity"] == "blocking" for i in issues),
            "conditional": any(i["severity"] == "condition" for i in issues),
            "missing_policy": "Unprovided routine information is optional and non-blocking. Decision-dependent gaps become explicit assumptions; absence requires clinician confirmation.",
            "scope": "Deterministic core checks plus specialist review; not an exhaustive clinical rule system", "source": NICE_SOURCE}
