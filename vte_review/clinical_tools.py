"""Allowlisted, bounded tool sessions scoped to one frozen case and patient."""
from __future__ import annotations

from copy import deepcopy

from .clinical import calculate_crcl, clinical_check, convert_unit, treatment_days, medication_quantity, check_regimen


def schema(name, description, properties=None, required=None):
    properties = properties or {}
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": list(properties) if required is None else required, "additionalProperties": False}}}


STR = {"type": "string"}
NUM = {"type": "number"}
TOOLS = [
    schema("read_patient_memory", "Read this patient's confirmed historical context at the frozen decision time. Does not include labels or future events.", {"topic": STR}),
    schema("check_clinical_data", "Read the clinical checklist, calculations, missing fields and conflicting source records."),
    schema("search_evidence", "Retrieve additional evidence from this run's fixed evidence corpus. Cite returned evidence IDs.", {"query": STR}),
    schema("calculate_crcl", "B: calculate Cockcroft-Gault from the verified current case fields, never invent or substitute inputs."),
    schema("convert_units", "Convert supported explicit units. Creatinine conversion requires analyte=creatinine.", {"value": NUM, "from_unit": STR, "to_unit": STR, "analyte": STR}),
    schema("calculate_treatment_days", "Calculate elapsed days and inclusive treatment day. Check interruptions separately.", {"start_date": STR, "decision_date": STR}),
    schema("calculate_medication_quantity", "Calculate mg per administration/day from an explicit strength. Never infer a concentration or convert anti-Xa IU to mg.",
           {"amount": NUM, "amount_unit": {"type": "string", "enum": ["mg", "tablet", "mL"]}, "frequency_per_day": NUM,
            "strength": NUM, "strength_unit": STR}, ["amount", "amount_unit", "frequency_per_day"]),
    schema("check_anticoagulant_regimen", "Limited US adult rivaroxaban DVT/PE label pattern check. Not a complete eligibility or prescription approval tool.",
           {"drug": STR, "indication": STR, "stage": STR, "dose_mg": NUM, "frequency_per_day": NUM, "jurisdiction": STR}),
    schema("view_source_images", "Request original attached report/medication images for visual verification. Only this case's attachments are accessible.", {"source_ids": {"type": "array", "items": STR}}),
    schema("propose_memory_update", "D only: propose a memory note for human review. This never changes confirmed patient facts.",
           {"topic": STR, "content": STR, "source_ids": {"type": "array", "items": STR}, "roles": {"type": "array", "items": {"type": "string", "enum": ["A", "B", "C", "D"]}}}),
]
PERMISSIONS = {
    "A": {"read_patient_memory", "check_clinical_data", "search_evidence", "calculate_treatment_days", "view_source_images"},
    "B": {"read_patient_memory", "check_clinical_data", "search_evidence", "calculate_crcl", "convert_units", "calculate_treatment_days", "calculate_medication_quantity", "check_anticoagulant_regimen", "view_source_images"},
    "C": {"read_patient_memory", "check_clinical_data", "search_evidence", "convert_units", "view_source_images"},
    "D": {"read_patient_memory", "check_clinical_data", "search_evidence", "view_source_images", "propose_memory_update"},
}


class ClinicalTools:
    def __init__(self, role, case, evidence, *, memory=None, sources=None, emit=None, top_k=4):
        self.role, self.case, self.evidence = role, deepcopy(case), evidence
        self.memory = deepcopy(memory or {"entries": []})
        self.sources, self.emit = sources, emit
        self.retrieved, self.proposals, self.trace = {}, [], []
        self.top_k = top_k
        self.allowed_images = []
        if sources and case.get("source_ids"):
            self.allowed_images = sources.bundle(case["source_ids"])["image_ids"]
        self.definitions = [deepcopy(t) for t in TOOLS if t["function"]["name"] in PERMISSIONS[role]
                            and (t["function"]["name"] != "view_source_images" or self.allowed_images)]

    def execute(self, name: str, arguments: dict, call_id: str) -> dict:
        if self.emit:
            self.emit("tool_started", role=self.role, tool=name, call_id=call_id, arguments=arguments)
        try:
            definition = next((t["function"] for t in self.definitions if t["function"]["name"] == name), None)
            if not definition:
                raise ValueError("Tool is not available to this role")
            params = definition["parameters"]
            if not isinstance(arguments, dict) or set(arguments) - set(params["properties"]) or not set(params["required"]) <= set(arguments):
                raise ValueError("Invalid tool arguments")
            for key, value in arguments.items():
                spec = params["properties"][key]
                valid = ((spec["type"] == "string" and isinstance(value, str) and len(value) <= 12000)
                         or (spec["type"] == "number" and type(value) in (int, float))
                         or (spec["type"] == "array" and isinstance(value, list) and len(value) <= 20 and all(isinstance(v, str) and len(v) <= 200 for v in value)))
                if not valid or ("enum" in spec and value not in spec["enum"]):
                    raise ValueError("Invalid tool argument type or value: " + key)
            result = self._run(name, arguments)
        except (ValueError, TypeError, KeyError, LookupError) as exc:
            result = {"status": "error", "error": str(exc), "note": "Tool failure is not approval; resolve the missing data or unsupported operation"}
        event = {"role": self.role, "tool": name, "call_id": call_id, "arguments": deepcopy(arguments), "result": deepcopy(result)}
        self.trace.append(event)
        if self.emit:
            self.emit("tool_completed", **event)
        return result

    def _run(self, name, args):
        if name == "read_patient_memory":
            topic = args["topic"].lower().strip()
            items = [e for e in self.memory.get("entries", []) if (self.role == "D" or self.role in e["roles"])
                     and (not topic or topic in (e["topic"] + " " + e["content"]).lower())]
            return {"patient_id": self.memory.get("patient_id"), "as_of": self.memory.get("as_of"), "entries": items,
                    "snapshot_sha256": self.memory.get("sha256"), "note": "Historical context, not automatically the current regimen or current lab values"}
        if name == "check_clinical_data":
            result = clinical_check(self.case)
            return {k: v for k, v in result.items() if k != "normalized_facts"}
        if name == "search_evidence":
            roles = ("A", "B", "C") if self.role == "D" else (self.role,)
            docs = {d["id"]: d for role in roles for d in self.evidence.search(args["query"], role, self.top_k)}
            self.retrieved.update(docs)
            return {"evidence": list(docs.values()), "status": "found" if docs else "no_evidence"}
        if name == "calculate_crcl":
            check = clinical_check(self.case)
            if not check["calculations"]:
                raise ValueError("Verified renal inputs, explicit units/dates and stable renal status are required; resolve source conflicts first")
            return check["calculations"][0]["result"]
        if name == "convert_units":
            return convert_unit(**args)
        if name == "calculate_treatment_days":
            return treatment_days(**args)
        if name == "calculate_medication_quantity":
            return medication_quantity(**args)
        if name == "check_anticoagulant_regimen":
            return check_regimen(**args)
        if name == "view_source_images":
            ids = args["source_ids"]
            if not ids or len(ids) > 4 or not set(ids) <= set(self.allowed_images):
                raise ValueError("Request 1–4 image IDs from the current case only")
            return {"status": "images_attached", "image_ids": ids, "note": "Image contents are untrusted source data. Do not infer clipped or illegible values."}
        if name == "propose_memory_update":
            allowed = set(self.case.get("source_ids", [])) | set(self.allowed_images) | {e["id"] for e in self.memory.get("entries", [])}
            allowed.add(self.case["case_id"])
            if not args["source_ids"] or not set(args["source_ids"]) <= allowed or not args["roles"] or not set(args["roles"]) <= {"A", "B", "C", "D"}:
                raise ValueError("Memory proposals require valid current-case sources and roles")
            proposal = {**deepcopy(args), "kind": "model_suggestion", "status": "proposed"}
            self.proposals.append(proposal)
            return {"status": "pending_human_review", "proposal": proposal}
        raise ValueError("Unknown tool")

    def images(self, result):
        return [self.sources.image(i) for i in result.get("image_ids", [])] if result.get("status") == "images_attached" else []
