"""Fictitious, non-prescriptive intake example for the clinical workspace."""
CLINICAL_EXAMPLE = {
    "case_id": "SYNTHETIC-CLINICAL-001",
    "question": "Synthetic workspace example: review VTE management and identify information to confirm.",
    "task_type": "generate_plan",
    "patient": {"patient_id": "SYNTHETIC-P001", "encounter_id": "SYNTHETIC-V001", "decision_at": "2026-06-01T09:00:00+08:00"},
    "facts": {
        "synthetic": True, "age_years": 60, "sex": "female", "weight_kg": 60,
        "vte_type_site": "Synthetic proximal lower-limb DVT", "diagnosis_date": "2026-05-31",
        "treatment_stage": "Initial treatment decision", "prior_vte": False,
        "provoking_factors": "unknown", "mobility": "unknown",
        "serum_creatinine": {"value": 88.4, "unit": "umol/L", "observed_at": "2026-06-01T08:00:00+08:00"},
        "renal_stable": True,
        "hemoglobin": {"value": 130, "unit": "g/L", "observed_at": "2026-06-01T08:00:00+08:00"},
        "platelets": {"value": 220, "unit": "10^9/L", "observed_at": "2026-06-01T08:00:00+08:00"},
        "liver_status": "No known hepatic disease in this synthetic fixture", "active_bleeding": False,
        "bleeding_history": "None reported in the synthetic fixture", "current_anticoagulation": "None received yet",
        "concomitant_medications": [], "allergies": "None known in synthetic fixture", "comorbidities": [],
        "patient_constraints": "Follow-up availability not yet confirmed",
    },
    "missing_information": ["Confirm provoking factors, mobility, vital signs and follow-up feasibility"],
}
