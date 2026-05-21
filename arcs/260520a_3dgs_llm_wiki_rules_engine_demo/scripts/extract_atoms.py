"""Extract atoms from 3dgs markdown sources — deterministic, no LLM."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml

from utils.atom import Atom


PROJECT_ROOT = Path("/Users/han/project/work/3dgs")

SOURCE_GLOBS = [
    ("arc",      "arcs/all/*/9_summary.md"),
    ("note",     "docs/notes/*.md"),
    ("decision", "docs/decisions/*.md"),
    ("paper",    "docs/paper_read/*.md"),
    ("spec",     "SPECS/*.md"),
]

INDEX_FILES = {"00_index.md"}  # skip — these are catalogs, not content

ARC_PATH_RE = re.compile(r"arcs/all/(\d{6}[a-z])(?:[/_])")
ARC_ID_BARE_RE = re.compile(r"\barc\s+(\d{6}[a-z])\b")
PATH_NOTE_RE     = re.compile(r"`(docs/notes/[A-Za-z0-9_./-]+\.md)`|\[\[(docs/notes/[A-Za-z0-9_./-]+\.md)\]\]|(?<![A-Za-z0-9_/])(docs/notes/[A-Za-z0-9_./-]+\.md)\b")
PATH_DECISION_RE = re.compile(r"`(docs/decisions/[A-Za-z0-9_./-]+\.md)`|\[\[(docs/decisions/[A-Za-z0-9_./-]+\.md)\]\]|(?<![A-Za-z0-9_/])(docs/decisions/[A-Za-z0-9_./-]+\.md)\b")
PATH_PAPER_RE    = re.compile(r"`(docs/paper_read/[A-Za-z0-9_./-]+\.md)`|\[\[(docs/paper_read/[A-Za-z0-9_./-]+\.md)\]\]|(?<![A-Za-z0-9_/])(docs/paper_read/[A-Za-z0-9_./-]+\.md)\b")
PATH_SPEC_RE     = re.compile(r"`(SPECS/[A-Za-z0-9_./-]+\.md)`|\[\[(SPECS/[A-Za-z0-9_./-]+\.md)\]\]|(?<![A-Za-z0-9_/])(SPECS/[A-Za-z0-9_./-]+\.md)\b")
PATH_CODE_RE = re.compile(
    r"`((?:utils|tools|scripts|src|drivestudio|street_gaussians|sam3|dggt|Depth-Anything-3|spark-viewer|multi_angle_dataset|tests)/[A-Za-z0-9_./-]+\.(?:py|sh|yaml|yml|md))`"
)

H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
NEW_DOC_RE = re.compile(
    r"\[NEW\][^\n]*?`?((?:docs|SPECS)/[A-Za-z0-9_./-]+\.md)`?",
    re.IGNORECASE,
)
UPDATE_DOC_RE = re.compile(
    r"\[UPDATE\][^\n]*?`?((?:docs|SPECS)/[A-Za-z0-9_./-]+\.md)`?",
    re.IGNORECASE,
)
STALE_DOC_RE = re.compile(
    r"\[STALE\??\][^\n]*?`?((?:docs|SPECS)/[A-Za-z0-9_./-]+\.md)`?",
    re.IGNORECASE,
)


def normalize_doc_subj(rel_path: str) -> str:
    """docs/notes/foo.md → doc:notes/foo.md;  SPECS/foo.md → doc:specs/foo.md."""
    rel_path = rel_path.strip()
    if rel_path.startswith("docs/"):
        return f"doc:{rel_path[len('docs/'):]}"
    if rel_path.startswith("SPECS/"):
        return f"doc:specs/{rel_path[len('SPECS/'):]}"
    return f"doc:{rel_path}"


def source_subj(kind: str, abs_path: Path) -> str:
    rel = abs_path.relative_to(PROJECT_ROOT).as_posix()
    if kind == "arc":
        m = ARC_PATH_RE.search(rel)
        return f"arc:{m.group(1)}" if m else f"doc:{rel}"
    return normalize_doc_subj(rel)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    fm_text = text[4:end]
    body = text[end + 4 :].lstrip("\n")
    try:
        meta = yaml.safe_load(fm_text) or {}
        if not isinstance(meta, dict):
            return {}, text
        return meta, body
    except yaml.YAMLError:
        return {}, text


def collect_doc_mentions(body: str) -> list[str]:
    subjs: list[str] = []
    for regex in (PATH_NOTE_RE, PATH_DECISION_RE, PATH_PAPER_RE, PATH_SPEC_RE):
        for m in regex.finditer(body):
            raw = next((g for g in m.groups() if g), None)
            if raw:
                subjs.append(normalize_doc_subj(raw))
    return subjs


def collect_code_mentions(body: str) -> list[str]:
    return [f"code:{m.group(1)}" for m in PATH_CODE_RE.finditer(body)]


def collect_arc_mentions(body: str, self_arc: str | None) -> list[str]:
    out: list[str] = []
    for m in ARC_PATH_RE.finditer(body):
        out.append(f"arc:{m.group(1)}")
    for m in ARC_ID_BARE_RE.finditer(body):
        out.append(f"arc:{m.group(1)}")
    return [a for a in out if a != self_arc]


def extract_from_file(kind: str, path: Path) -> list[Atom]:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = parse_frontmatter(text)
    subj = source_subj(kind, path)
    rel_src = path.relative_to(PROJECT_ROOT).as_posix()
    atoms: list[Atom] = []

    atoms.append(Atom(subj, "has_type", f"type:{kind}", source=rel_src))
    h1 = H1_RE.search(body or text)
    if h1:
        atoms.append(Atom(subj, "has_title", h1.group(1).strip(), source=rel_src))

    if isinstance(meta.get("summary"), str):
        atoms.append(Atom(subj, "has_summary", meta["summary"].strip(), source=rel_src))
    if isinstance(meta.get("status"), str):
        atoms.append(Atom(subj, "has_status", meta["status"].strip(), source=rel_src))

    domain = meta.get("domain")
    if isinstance(domain, list):
        for d in domain:
            atoms.append(Atom(subj, "has_topic", f"topic:{d}", source=rel_src))
    elif isinstance(domain, str):
        atoms.append(Atom(subj, "has_topic", f"topic:{domain}", source=rel_src))

    related_code = meta.get("related_code")
    if isinstance(related_code, list):
        for rc in related_code:
            if isinstance(rc, str) and rc.strip():
                atoms.append(Atom(subj, "mentions_code", f"code:{rc.strip()}", source=rel_src))

    related_docs = meta.get("related_docs")
    if isinstance(related_docs, list):
        for rd in related_docs:
            if isinstance(rd, str) and rd.strip():
                atoms.append(Atom(subj, "mentions_doc", normalize_doc_subj(rd.strip()), source=rel_src))

    self_arc = subj if subj.startswith("arc:") else None
    for code in collect_code_mentions(body):
        atoms.append(Atom(subj, "mentions_code", code, source=rel_src))
    for doc_ref in collect_doc_mentions(body):
        if doc_ref != subj:
            atoms.append(Atom(subj, "mentions_doc", doc_ref, source=rel_src))
    for arc_ref in collect_arc_mentions(body, self_arc):
        atoms.append(Atom(subj, "mentions_arc", arc_ref, source=rel_src))

    if kind == "arc":
        for m in NEW_DOC_RE.finditer(body):
            doc = m.group(1)
            atoms.append(Atom(subj, "introduces_doc", normalize_doc_subj(doc), source=rel_src))
        for m in UPDATE_DOC_RE.finditer(body):
            doc = m.group(1)
            atoms.append(Atom(subj, "updates_doc", normalize_doc_subj(doc), source=rel_src))
        for m in STALE_DOC_RE.finditer(body):
            doc = m.group(1)
            atoms.append(Atom(subj, "flags_stale_doc", normalize_doc_subj(doc), source=rel_src))

    return atoms


def gather_sources() -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for kind, glob in SOURCE_GLOBS:
        for p in sorted(PROJECT_ROOT.glob(glob)):
            if p.name in INDEX_FILES:
                continue
            out.append((kind, p))
    return out


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="output dir; atoms/<source_stem>.yaml")
    ap.add_argument("--limit-per-kind", type=int, default=0, help="0 = all")
    args = ap.parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    seen_keys: set[tuple] = set()
    total = 0
    sources = gather_sources()
    by_kind: dict[str, int] = {}
    if args.limit_per_kind > 0:
        kept: list[tuple[str, Path]] = []
        counts: dict[str, int] = {}
        for k, p in sources:
            counts[k] = counts.get(k, 0) + 1
            if counts[k] <= args.limit_per_kind:
                kept.append((k, p))
        sources = kept

    for kind, p in sources:
        atoms = extract_from_file(kind, p)
        deduped = []
        for a in atoms:
            if a.key in seen_keys:
                continue
            seen_keys.add(a.key)
            deduped.append(a)
        rel_src = p.relative_to(PROJECT_ROOT).as_posix()
        stem = rel_src.replace("/", "__").replace(".md", "")
        out_file = out_dir / f"{stem}.yaml"
        with open(out_file, "w", encoding="utf-8") as fh:
            yaml.safe_dump([a.to_dict() for a in deduped], fh, sort_keys=False, allow_unicode=True)
        total += len(deduped)
        by_kind[kind] = by_kind.get(kind, 0) + len(deduped)
        print(f"{kind:8s}  {len(deduped):4d}  {rel_src}")

    print()
    print(f"TOTAL ATOMS: {total}")
    print(f"BY KIND: {by_kind}")
    print(f"OUT:    {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
