"""Append-only, patient-scoped memory with clinical-time cutoffs and provenance."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
KINDS = {"fact", "preference", "clinician_decision", "actual_treatment", "model_suggestion"}


def instant(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("A timestamp with timezone is required")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Use an ISO timestamp with timezone") from None
    if result.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")
    return result.astimezone(timezone.utc)


def identifier(value: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError("Use a de-identified ID containing letters, digits, dot, underscore or hyphen")
    return value


class PatientMemory:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS memory (
                    id TEXT PRIMARY KEY, patient_id TEXT NOT NULL,
                    recorded_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS memory_patient ON memory(patient_id, recorded_at);
                CREATE TABLE IF NOT EXISTS resolutions (
                    id TEXT PRIMARY KEY, memory_id TEXT NOT NULL UNIQUE,
                    recorded_at TEXT NOT NULL, payload TEXT NOT NULL);
            """)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def add(self, patient_id: str, value: dict, *, actor: str, model: bool = False) -> dict:
        identifier(patient_id)
        if not isinstance(value, dict):
            raise ValueError("Memory entry must be an object")
        required = {"kind", "topic", "content", "occurred_at", "available_at", "source", "roles"}
        if not required <= set(value) or set(value) - required - {"supersedes", "encounter_id"}:
            raise ValueError("Memory requires kind, topic, content, occurred_at, available_at, source and roles")
        if value["kind"] not in KINDS or (model and value["kind"] != "model_suggestion"):
            raise ValueError("Invalid memory kind; models can only propose suggestions")
        for field in ("topic", "content", "source"):
            if not isinstance(value[field], str) or not value[field].strip() or len(value[field]) > 16000:
                raise ValueError(f"Memory {field} is required and must be at most 16000 characters")
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("A recording person or model identity is required")
        occurred, available = instant(value["occurred_at"]), instant(value["available_at"])
        if available < occurred:
            raise ValueError("available_at cannot precede occurred_at")
        roles = value["roles"]
        if not isinstance(roles, list) or not roles or not set(roles) <= {"A", "B", "C", "D"}:
            raise ValueError("Select applicable roles")
        if value.get("encounter_id"):
            identifier(value["encounter_id"])
        if value["kind"] == "clinician_decision" and not value.get("encounter_id"):
            raise ValueError("Physician decisions require encounter_id to separate reference labels from history")
        entry = {**value, "id": "MEM-" + uuid4().hex, "patient_id": patient_id,
                 "occurred_at": occurred.isoformat(), "available_at": available.isoformat(),
                 "recorded_at": datetime.now(timezone.utc).isoformat(), "actor": actor.strip(),
                 "status": "proposed" if model else "confirmed"}
        with self.db() as db:
            if value.get("supersedes"):
                prior = db.execute("SELECT payload FROM memory WHERE id=? AND patient_id=?",
                                   (value["supersedes"], patient_id)).fetchone()
                if not prior or instant(json.loads(prior[0])["available_at"]) > available:
                    raise ValueError("Correction must reference an earlier entry of the same patient")
            db.execute("INSERT INTO memory VALUES (?,?,?,?)",
                       (entry["id"], patient_id, entry["recorded_at"], json.dumps(entry, ensure_ascii=False)))
        return entry

    def resolve(self, patient_id: str, entry_id: str, value: dict) -> dict:
        identifier(patient_id)
        if not isinstance(value, dict) or not isinstance(value.get("actor"), str):
            raise ValueError("A reviewer and accept/reject decision are required")
        action, actor = value.get("action"), value["actor"].strip()
        if action not in {"accept", "reject"} or not actor:
            raise ValueError("A reviewer and accept/reject decision are required")
        # Accepting a suggestion does not silently turn it into a clinical fact.
        with self.db() as db:
            row = db.execute("SELECT payload FROM memory WHERE id=? AND patient_id=?", (entry_id, patient_id)).fetchone()
            if not row or json.loads(row[0])["status"] != "proposed":
                raise ValueError("Only pending model suggestions can be resolved")
            item = {"action": action, "actor": actor, "note": str(value.get("note", ""))[:4000],
                    "recorded_at": datetime.now(timezone.utc).isoformat()}
            try:
                db.execute("INSERT INTO resolutions VALUES (?,?,?,?)",
                           ("RES-" + uuid4().hex, entry_id, item["recorded_at"], json.dumps(item)))
            except sqlite3.IntegrityError:
                raise ValueError("This suggestion has already been resolved") from None
        return item

    def history(self, patient_id: str) -> list[dict]:
        identifier(patient_id)
        with self.db() as db:
            rows = db.execute("SELECT m.payload,r.payload AS resolution FROM memory m LEFT JOIN resolutions r ON r.memory_id=m.id WHERE patient_id=? ORDER BY m.recorded_at,m.id", (patient_id,)).fetchall()
        return [{**json.loads(row[0]), "resolution": json.loads(row[1]) if row[1] else None} for row in rows]

    def snapshot(self, patient_id: str, as_of: str, *, task_type: str = "generate_plan", encounter_id: str = "") -> dict:
        if task_type not in {"generate_plan", "review_plan"}:
            raise ValueError("Invalid snapshot task type")
        cutoff = instant(as_of)
        eligible = [e for e in self.history(patient_id)
                    if e["status"] == "confirmed" and e["kind"] != "model_suggestion"
                    and instant(e["occurred_at"]) <= cutoff and instant(e["available_at"]) <= cutoff]
        if task_type == "generate_plan":
            eligible = [e for e in eligible if not (
                e["kind"] == "clinician_decision" and
                (e.get("encounter_id") == encounter_id or instant(e["occurred_at"]) >= cutoff))
                and not (e["kind"] == "actual_treatment" and instant(e["occurred_at"]) >= cutoff)]
        replaced = {e.get("supersedes") for e in eligible}
        entries = [e for e in eligible if e["id"] not in replaced]
        payload = {"patient_id": patient_id, "as_of": cutoff.isoformat(), "task_type": task_type,
                   "encounter_id": encounter_id, "entries": entries,
                   "note": "Historical context, not automatically current facts. Confirm current medication, lab values and preferences."}
        payload["sha256"] = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return payload

    def patients(self) -> list[dict]:
        with self.db() as db:
            return [dict(row) for row in db.execute("SELECT patient_id,count(*) AS entries,max(recorded_at) AS updated_at FROM memory GROUP BY patient_id ORDER BY updated_at DESC")]
