#!/usr/bin/env python3
"""Build bundled knowledge pack from Creatio_Interview + optional local CREATIO folder.

Does not embed absolute developer paths in chunk payloads.
Answers from live interviews are never part of this pack.
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "knowledge" / "pack"
SOURCES_LOCAL = ROOT / "knowledge" / "sources.local.json"
SOURCES_EXAMPLE = ROOT / "knowledge" / "sources.example.json"

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def load_sources() -> dict:
    path = SOURCES_LOCAL if SOURCES_LOCAL.exists() else SOURCES_EXAMPLE
    return json.loads(path.read_text(encoding="utf-8"))


def col_row(cell_ref: str) -> tuple[str, int]:
    m = re.match(r"([A-Z]+)(\d+)", cell_ref)
    if not m:
        return "A", 1
    return m.group(1), int(m.group(2))


def read_shared_strings(z: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    strings = []
    for si in root.findall("m:si", NS):
        texts = [t.text or "" for t in si.findall(".//m:t", NS)]
        strings.append("".join(texts))
    return strings


def cell_value(cell, shared: list[str]) -> str:
    ref_type = cell.attrib.get("t")
    v = cell.find("m:v", NS)
    if v is None:
        return ""
    raw = v.text or ""
    if ref_type == "s":
        try:
            return shared[int(raw)]
        except Exception:
            return raw
    return raw


def iter_xlsx_rows(xlsx_path: Path):
    with zipfile.ZipFile(xlsx_path) as z:
        shared = read_shared_strings(z)
        workbook = ET.fromstring(z.read("xl/workbook.xml"))
        sheets = []
        for sh in workbook.findall("m:sheets/m:sheet", NS):
            sheets.append((sh.attrib.get("name", "Sheet"), sh.attrib.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {}
        for rel in rels:
            rid_to_target[rel.attrib.get("Id")] = rel.attrib.get("Target")

        for name, rid in sheets:
            target = rid_to_target.get(rid)
            if not target:
                continue
            target = target.lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            root = ET.fromstring(z.read(target))
            rows = {}
            for c in root.findall(".//m:sheetData/m:row/m:c", NS):
                ref = c.attrib.get("r", "A1")
                col, row = col_row(ref)
                rows.setdefault(row, {})[col] = cell_value(c, shared)
            yield name, rows


def completeness_of(answer: str) -> str:
    a = (answer or "").strip()
    if len(a) < 40:
        return "empty"
    if len(a) < 180:
        return "partial"
    return "full"


def chunks_from_interview_xlsx(xlsx_path: Path) -> list[dict]:
    chunks = []
    if not xlsx_path.exists():
        print(f"WARN: missing {xlsx_path}", file=sys.stderr)
        return chunks

    for sheet_name, rows in iter_xlsx_rows(xlsx_path):
        if not rows:
            continue
        # Heuristic: find header row with вопрос/ответ
        header_row = None
        col_q = col_a = None
        for r in sorted(rows)[:8]:
            vals = {c: (rows[r].get(c) or "").strip().lower() for c in rows[r]}
            for c, v in vals.items():
                if "вопрос" in v or v == "question":
                    col_q = c
                if "что сказать" in v or "ответ" in v or v == "answer":
                    col_a = c
            if col_q and col_a:
                header_row = r
                break
        if not header_row or not col_q:
            # fallback: first two columns
            sample = rows[min(rows)]
            cols = sorted(sample.keys())
            if len(cols) < 1:
                continue
            col_q = cols[0]
            col_a = cols[1] if len(cols) > 1 else None
            header_row = min(rows)

        for r, cols in rows.items():
            if r <= header_row:
                continue
            q = (cols.get(col_q) or "").strip()
            a = (cols.get(col_a) or "").strip() if col_a else ""
            if len(q) < 8:
                continue
            text = q if not a else f"Вопрос: {q}\nЧто сказать: {a}"
            chunks.append(
                {
                    "id": f"interview:{sheet_name}:{r}",
                    "title": f"{sheet_name}: {q[:80]}",
                    "source": "Creatio_Interview",
                    "sheet": sheet_name,
                    "completeness": completeness_of(a),
                    "text": text[:4000],
                }
            )
    return chunks


def chunks_from_text_tree(base: Path, allow_dirs: list[str], exts: set[str]) -> list[dict]:
    chunks = []
    if not base.exists():
        print(f"WARN: local CREATIO path missing: {base}", file=sys.stderr)
        return chunks

    allow = [base / d for d in allow_dirs]
    # also root-level allowed files
    candidates: list[Path] = []
    for p in allow:
        if p.exists():
            candidates.extend([x for x in p.rglob("*") if x.is_file()])
    for p in base.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            candidates.append(p)

    skip_parts = {".git", "node_modules", "бэкап", "backup"}
    for file in candidates:
        if any(part.lower() in skip_parts for part in file.parts):
            continue
        if file.suffix.lower() not in exts:
            continue
        if file.stat().st_size > 400_000:
            continue
        try:
            text = file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        text = text.strip()
        if len(text) < 40:
            continue
        rel = str(file.relative_to(base)).replace("\\", "/")
        # do not store absolute path
        chunks.append(
            {
                "id": f"local:{rel}",
                "title": rel,
                "source": "local_creatio_pack",
                "completeness": "partial",
                "text": text[:4000],
            }
        )
    return chunks


def main() -> int:
    cfg = load_sources()
    chunks: list[dict] = []

    interview = Path(cfg.get("creatio_interview_xlsx", ""))
    if not interview.is_absolute():
        interview = (ROOT / interview).resolve()
    chunks.extend(chunks_from_interview_xlsx(interview))

    local_root = cfg.get("local_creatio_root")
    if local_root:
        chunks.extend(
            chunks_from_text_tree(
                Path(local_root),
                cfg.get("local_allow_dirs", []),
                {e.lower() if e.startswith(".") else f".{e.lower()}" for e in cfg.get("local_exts", [".md", ".txt", ".sql", ".cs", ".js"])},
            )
        )

    # Dedup by id
    seen = set()
    unique = []
    for c in chunks:
        if c["id"] in seen:
            continue
        seen.add(c["id"])
        unique.append(c)

    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "chunkCount": len(unique),
        "chunks": unique,
    }
    (OUT / "index.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(unique)} chunks -> {OUT / 'index.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
