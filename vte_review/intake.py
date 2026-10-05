"""Local source storage and text/image ingestion, independent of model inference."""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import re
import zipfile
import threading
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET

SOURCE_ID = re.compile(r"^SRC-[a-f0-9]{32}$")
MAX_FILE = 6 * 1024 * 1024
MAX_TOTAL = 24 * 1024 * 1024
STORE_LOCK = threading.Lock()


class SourceStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _save(self, name: str, data: bytes, mime: str, text: str = "", images=None) -> dict:
        source_id = "SRC-" + hashlib.sha256(mime.encode() + b"\0" + data).hexdigest()[:32]
        folder = self.root / source_id
        folder.mkdir(exist_ok=True)
        item = {"id": source_id, "name": name[:180], "mime": mime, "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(), "text": text, "images": images or []}
        # Content address makes the stored source immutable and deduplicated.
        with STORE_LOCK:
            if (folder / "meta.json").exists():
                return self.get(source_id)
            (folder / "source.bin").write_bytes(data)
            temporary = folder / "meta.tmp"
            temporary.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
            temporary.replace(folder / "meta.json")
        return item

    def get(self, source_id: str) -> dict:
        if not isinstance(source_id, str) or not SOURCE_ID.fullmatch(source_id):
            raise ValueError("Invalid source ID")
        try:
            return json.loads((self.root / source_id / "meta.json").read_text(encoding="utf-8"))
        except OSError:
            raise LookupError("Source not found") from None

    def image(self, source_id: str) -> dict:
        item = self.get(source_id)
        if not item["mime"].startswith("image/"):
            raise ValueError("This source is not an image")
        raw = (self.root / source_id / "source.bin").read_bytes()
        return {"source_id": source_id, "data_url": "data:" + item["mime"] + ";base64," + base64.b64encode(raw).decode()}

    def ingest(self, name: str, encoded: str) -> dict:
        if not isinstance(name, str) or not isinstance(encoded, str) or len(encoded) > MAX_FILE * 1.4:
            raise ValueError("A file name and base64 payload up to 6 MB are required")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("Invalid base64 file") from None
        if not raw or len(raw) > MAX_FILE:
            raise ValueError("File must be between 1 byte and 6 MB")
        suffix = Path(name).suffix.lower()
        if suffix == ".docx":
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    if len(z.infolist()) > 500 or sum(f.file_size for f in z.infolist()) > MAX_TOTAL:
                        raise ValueError("Word document expands beyond the import limit")
                    doc = ET.fromstring(z.read("word/document.xml"))
                    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                    text = "\n".join("".join(t.text or "" for t in p.findall(".//w:t", ns)) for p in doc.findall(".//w:p", ns))
                    images = []
                    for entry in z.infolist():
                        if entry.filename.startswith("word/media/"):
                            if len(images) >= 12:
                                raise ValueError("At most 12 embedded images per document")
                            data = z.read(entry)
                            images.append(self._image(Path(entry.filename).name, data)["id"])
                if len(text) > 200000:
                    raise ValueError("Split case documents longer than 200000 characters before import")
                return self._save(name, raw, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", text, images)
            except (zipfile.BadZipFile, KeyError, ET.ParseError, RuntimeError):
                raise ValueError("Invalid DOCX file") from None
        if suffix in {".txt", ".md"}:
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeError:
                raise ValueError("Text must use UTF-8") from None
            if len(text) > 200000:
                raise ValueError("Split text files longer than 200000 characters before import")
            return self._save(name, raw, "text/plain", text)
        return self._image(name, raw)

    def _image(self, name: str, raw: bytes) -> dict:
        if not raw or len(raw) > MAX_FILE:
            raise ValueError("Image exceeds 6 MB")
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        elif raw.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        elif raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
            mime = "image/webp"
        else:
            raise ValueError("Supported sources: PNG, JPEG, WebP, DOCX and UTF-8 text")
        try:
            from PIL import Image
            with Image.open(io.BytesIO(raw)) as image:
                if image.width * image.height > 25_000_000 or image.width < 1 or image.height < 1:
                    raise ValueError("Image dimensions exceed the 25 megapixel limit")
                image.verify()
        except ImportError:
            raise ValueError('Image support requires: python -m pip install -e ".[images]"') from None
        except Exception:
            raise ValueError("Invalid image or image exceeds the 25 megapixel limit") from None
        return self._save(name, raw, mime)

    def bundle(self, source_ids: list[str]) -> dict:
        if not isinstance(source_ids, list) or not source_ids or len(source_ids) > 12:
            raise ValueError("Select 1–12 source files")
        sources = [self.get(i) for i in dict.fromkeys(source_ids)]
        if sum(s["size"] for s in sources) > MAX_TOTAL:
            raise ValueError("Selected sources exceed 24 MB")
        image_ids = list(dict.fromkeys(i for s in sources for i in ([s["id"]] if s["mime"].startswith("image/") else s["images"])))
        if len(image_ids) > 12:
            raise ValueError("Select at most 12 images per extraction")
        return {"sources": sources, "image_ids": image_ids}


def validate_extraction(value: dict, allowed: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != {"observations", "issues"} or not isinstance(value["observations"], list):
        raise ValueError("Extraction must contain observations and issues arrays")
    value = deepcopy(value)
    # Issues are explanatory notes, not clinical observations. Preserve structured
    # notes as JSON text instead of discarding a valid extraction for a display type.
    notes = value["issues"]
    if notes is None:
        notes = []
    elif isinstance(notes, (str, dict)):
        notes = [notes]
    if not isinstance(notes, list) or len(notes) > 100:
        raise ValueError("Extraction issues must be a list of at most 100 notes")
    normalized = []
    for note in notes:
        try:
            rendered = note if isinstance(note, str) else json.dumps(note, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError):
            raise ValueError("Extraction issue is not valid JSON data") from None
        if len(rendered) > 16000:
            raise ValueError("Extraction issue exceeds 16000 characters")
        normalized.append(rendered)
    if sum(map(len, normalized)) > 64000:
        raise ValueError("Extraction issues exceed 64000 characters")
    value["issues"] = normalized
    if len(value["observations"]) > 200 or len(value["issues"]) > 100:
        raise ValueError("Extraction is too large")
    required = {"key", "value", "unit", "observed_at", "available_at", "source_id", "location", "status"}
    for item in value["observations"]:
        if not isinstance(item, dict) or set(item) != required or item["source_id"] not in allowed:
            raise ValueError("Extraction contains an invalid observation or source")
        for k in required - {"value"}:
            if not isinstance(item[k], str):
                raise ValueError("Invalid extraction field")
        # Models cannot self-confirm their reading or fabricate a missing date.
        item["status"] = "unverified"
    return value
