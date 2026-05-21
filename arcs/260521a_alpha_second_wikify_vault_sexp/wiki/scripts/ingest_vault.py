"""
ingest_vault.py — structured ingest of the auto_research_experiment Obsidian vault
into the sexp/EDN card store (Phase 2 of arc 260521a).

Strategy: pure structural parsers — frontmatter YAML, body sections (## headings),
double-link `[[...]]` extraction, slugified section names. No LLM in this phase.

Output:
  - one .edn file per source .md in <out>/<source-stem>.edn
  - log file at output/phase2_ingest.log

Usage:
  python -m wiki.scripts.ingest_vault \\
      --vault /Users/han/project/alpha/alpha_second_v1/auto_research_experiment \\
      --out   wiki/cards/atoms/
"""

from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

# Make wiki package importable when run as `python -m wiki.scripts.ingest_vault`
HERE = Path(__file__).resolve().parent
ARC_ROOT = HERE.parent.parent  # arc workspace root
sys.path.insert(0, str(ARC_ROOT))

from wiki.lib.cardstore import Card, CardStore  # noqa: E402


# ---------------------------------------------------------------------------
# Constants — typed-link predicates we lift from frontmatter and body
# ---------------------------------------------------------------------------

FRONTMATTER_LINK_FIELDS = {
    "parent_arc",
    "parent_lineage",
    "derived_from",
    "competes_with",
    "falsifies",
    "reports_to",
}

# Body "Lineage" bullets — Chinese / English mixed. Key = predicate name, regex matches the bold label.
BODY_LINK_LABELS = {
    "derived_from",
    "competes_with",
    "falsifies",
    "falsifies_lineage",
    "builds_on",
    "builds_against",
    "also_explored_by",
    "inherits_failure_pattern",
    "shared_axis",
    "co_champion_at_peak",
    "anti_pattern_shared",
}

# Section name → slug. Chinese & mixed handled. Anything not in this map is auto-slugified.
SECTION_SLUG_MAP = {
    "假设 (hypothesis)": "hypothesis",
    "假设": "hypothesis",
    "hypothesis": "hypothesis",
    "实现 (implementation)": "implementation",
    "实现": "implementation",
    "implementation": "implementation",
    "past-only window 处理": "past_only_window",
    "past-only window": "past_only_window",
    "结果 (results)": "results",
    "结果": "results",
    "results": "results",
    "风险 & overfit 嫌疑": "risk_overfit",
    "风险": "risk_overfit",
    "lineage（双链网）": "lineage_links",
    "lineage": "lineage_links",
    "reports": "reports",
    "notes / 下次迭代": "notes",
    "notes": "notes",
    "round 演进时间线（nav 排序，每轮选 top）": "round_table",
    "round 演进时间线": "round_table",
    "round 演进时间线（按 nav 排序，每轮选 top）": "round_table",
    "决策点 / 反思": "decisions_reflections",
    "跨 lineage 关系": "cross_lineage_relations",
    "终态判定理由（plateau）": "terminal_judgement",
    "for future sub-agent": "for_future_sub_agent",
    "备注": "remarks",
}

# Anti-pattern field labels inside each `## <pattern name>` block.
AP_FIELD_LABELS = {
    "触发条件": "trigger",
    "症状": "symptom",
    "root cause": "root_cause",
    "mitigation / 防御": "mitigation",
    "实战案例": "case_examples",
    "给未来 sub-agent": "advice_to_future_subagent",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def _hash8(*parts: Any) -> str:
    s = "|".join(str(p) for p in parts)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def _slugify(name: str) -> str:
    """Map a section heading to its canonical slug.

    Try literal map first (handles Chinese sections); else fall back to
    auto-slug: lowercase, non-alnum → underscore, strip leading/trailing _.
    """
    key = name.strip().lower()
    if key in SECTION_SLUG_MAP:
        return SECTION_SLUG_MAP[key]
    # auto-slug
    s = re.sub(r"[^\w]+", "_", key, flags=re.UNICODE).strip("_")
    return s or "section"


def _parse_double_links(s: str) -> list[str]:
    """Extract every [[target]] from string."""
    if not isinstance(s, str):
        return []
    return [m.group(1).strip() for m in re.finditer(r"\[\[([^\]]+)\]\]", s)]


def _link_target_to_namespaced(target: str) -> str:
    """
    `[[arcs/260516a]]` → `arc:260516a`
    `[[lineages/arc_260516a__team_h__sizing]]` → `lin:arc_260516a__team_h__sizing`
    `[[reports/arc_260516a__reporter_20260517_0547]]` → `report:arc_260516a__reporter_20260517_0547`
    `[[experiments/arc_260516a__team_b__B-R10-2__blacklist_low_amt]]` → `exp:B-R10-2_blacklist_low_amt`
    `[[arc_260516a__team_b__B-R10-2__blacklist_low_amt]]` (bare exp) → `exp:B-R10-2_blacklist_low_amt`
    Unknown prefix → kept as `ref:<raw>` so it's still queryable.
    """
    raw = target.strip()
    # split prefix folder if present
    if "/" in raw:
        prefix, body = raw.split("/", 1)
    else:
        prefix, body = "", raw

    if prefix == "arcs":
        return f"arc:{body}"
    if prefix == "lineages":
        return f"lin:{body}"
    if prefix == "reports":
        return f"report:{body}"
    if prefix == "experiments":
        return f"exp:{_exp_id_from_stem(body)}"
    # bare — heuristic: if it matches the experiment-stem shape, treat as exp
    if re.match(r"^arc_\d{6}[a-z]__team_[a-z_0-9]+__", body):
        # could be experiment or lineage — lineage usually has 3 fields, experiment 4
        # (arc__team__id__short) vs (arc__team__axis); count "__" pieces
        pieces = body.split("__")
        if len(pieces) >= 4:
            return f"exp:{_exp_id_from_stem(body)}"
        else:
            return f"lin:{body}"
    return f"ref:{raw}"


def _exp_id_from_stem(stem: str) -> str:
    """
    From `arc_260516a__team_b__B-R10-2__blacklist_low_amt` → `B-R10-2_blacklist_low_amt`
    Anchor case: `arc_260516a__team_anchor__anchor_g2__baseline` → `anchor_g2_baseline`
    Fallback: last two `__`-split pieces joined by `_`. If only 1 piece, return as-is.
    """
    pieces = stem.split("__")
    if len(pieces) >= 2:
        return "_".join(pieces[-2:])
    return stem


def _lin_id_from_stem(stem: str) -> str:
    """Lineage stem is used verbatim (arc_260516a__team_b__blacklist_axis)."""
    return stem


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """
    Split YAML frontmatter from body. Returns (fm_dict, body_text).
    If no frontmatter, returns ({}, text).
    """
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm_raw = m.group(1)
    body = m.group(2)
    try:
        fm = yaml.safe_load(fm_raw) or {}
    except yaml.YAMLError as e:
        print(f"  WARN: YAML parse error: {e}", file=sys.stderr)
        fm = {}
    return fm if isinstance(fm, dict) else {}, body


def _split_sections(body: str) -> list[tuple[str, str]]:
    """
    Split body into [(heading, content), ...] using `## ` H2 headings.
    Content before first H2 (e.g. title H1 + TL;DR) is returned under heading `_intro`.
    """
    sections = []
    # Split lines, find H2 indices
    lines = body.split("\n")
    intro_lines: list[str] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for ln in lines:
        if ln.startswith("## "):
            # flush previous
            if current_heading is None:
                if intro_lines:
                    sections.append(("_intro", "\n".join(intro_lines).strip()))
            else:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = ln[3:].strip()
            current_lines = []
        else:
            if current_heading is None:
                intro_lines.append(ln)
            else:
                current_lines.append(ln)
    # flush tail
    if current_heading is None:
        if intro_lines:
            sections.append(("_intro", "\n".join(intro_lines).strip()))
    else:
        sections.append((current_heading, "\n".join(current_lines).strip()))
    return sections


def _extract_tldr(intro_text: str) -> str | None:
    """Find the first blockquote starting with `> **TL;DR**`. Returns the TL;DR text (no markers)."""
    m = re.search(r"^>\s*\*\*TL;DR\*\*\s*[—\-]*\s*(.+?)(?=^\s*$|\Z)", intro_text, re.DOTALL | re.MULTILINE)
    if not m:
        return None
    body = m.group(1).strip()
    # Collapse leading `> ` markers on subsequent lines
    body = re.sub(r"\n\s*>\s?", "\n", body).strip()
    return body or None


def _extract_body_links(body_text: str) -> list[tuple[str, str]]:
    """
    From body lines like `- **derived_from**: [[xxx]] ...`, extract (label, link_target) pairs.
    Returns list of (predicate, target) where target is the raw `[[..]]` content.
    Predicate label is normalized: lowercased, spaces→_.
    """
    results: list[tuple[str, str]] = []
    for m in re.finditer(
        r"^\s*[\-\*]\s*\*\*([A-Za-z][A-Za-z0-9_ ]*?)\*\*\s*:\s*(.+?)$",
        body_text,
        re.MULTILINE,
    ):
        label = m.group(1).strip().lower().replace(" ", "_")
        rest = m.group(2)
        for tgt in _parse_double_links(rest):
            results.append((label, tgt))
    return results


# ---------------------------------------------------------------------------
# Card builders
# ---------------------------------------------------------------------------

def _atom(subj: str, pred: str, obj: Any, source: str, extra: dict | None = None) -> Card:
    obj_repr = obj if isinstance(obj, (int, float, bool)) or obj is None else str(obj)
    aid = "a_" + _hash8(subj, pred, obj_repr)
    kvs = {
        "subj": subj,
        "pred": pred,
        "obj": obj,
        "source": source,
        "ingested_at": NOW,
    }
    if extra:
        kvs.update(extra)
    return Card(id=aid, type="atom", kvs=kvs)


def _root_card(subj: str, root_type: str, body: str, path: Path, source_rel: str) -> Card:
    """The 'paper' card — one per source .md, holds full body & metadata."""
    mtime = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    rid = subj  # use the subj itself as the canonical id for the root
    return Card(
        id=rid,
        type=root_type,
        kvs={
            "subj": subj,
            "body": body,
            "path": source_rel,
            "source_mtime": mtime,
            "ingested_at": NOW,
        },
    )


# ---------------------------------------------------------------------------
# Per-document ingest
# ---------------------------------------------------------------------------

def ingest_experiment(path: Path, vault_root: Path, log: list[str], stats: dict) -> list[Card]:
    text = path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)
    stem = path.stem
    exp_id = _exp_id_from_stem(stem)
    subj = f"exp:{exp_id}"
    source_rel = str(path.relative_to(vault_root))

    cards: list[Card] = [_root_card(subj, "experiment", text, path, source_rel)]

    # --- frontmatter ---
    cards += _ingest_frontmatter(subj, fm, source_rel, log, stats)

    # --- body sections ---
    sections = _split_sections(body)
    for heading, content in sections:
        slug = _slugify(heading)
        if heading == "_intro":
            tldr = _extract_tldr(content)
            if tldr:
                cards.append(_atom(subj, "has_tl_dr", tldr, source_rel))
            # also keep the raw intro for reference
            cards.append(_atom(subj, "has_section_intro", content, source_rel))
            continue

        # body-level typed links (lineage / reports sections etc.)
        for label, tgt in _extract_body_links(content):
            if label in BODY_LINK_LABELS or label in FRONTMATTER_LINK_FIELDS:
                ns_target = _link_target_to_namespaced(tgt)
                cards.append(_atom(subj, label, ns_target, source_rel))
                stats["body_links"][label] += 1
            else:
                # unknown link label — keep but tag warning
                ns_target = _link_target_to_namespaced(tgt)
                cards.append(_atom(subj, label, ns_target, source_rel))
                stats["body_links_unknown"][label] += 1
                log.append(f"  warn: {source_rel}: unknown body link label '{label}' → {tgt}")

        # raw section content (one atom per section)
        cards.append(_atom(subj, f"has_section_{slug}", content, source_rel))

    return cards


def ingest_lineage(path: Path, vault_root: Path, log: list[str], stats: dict) -> list[Card]:
    text = path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)
    stem = path.stem
    subj = f"lin:{_lin_id_from_stem(stem)}"
    source_rel = str(path.relative_to(vault_root))

    cards: list[Card] = [_root_card(subj, "lineage", text, path, source_rel)]
    cards += _ingest_frontmatter(subj, fm, source_rel, log, stats)

    # body sections — same logic as experiment, but the Round 表 section is preserved verbatim
    for heading, content in _split_sections(body):
        slug = _slugify(heading)
        if heading == "_intro":
            cards.append(_atom(subj, "has_section_intro", content, source_rel))
            continue
        # typed links inside body
        for label, tgt in _extract_body_links(content):
            ns_target = _link_target_to_namespaced(tgt)
            cards.append(_atom(subj, label, ns_target, source_rel))
            if label in BODY_LINK_LABELS or label in FRONTMATTER_LINK_FIELDS:
                stats["body_links"][label] += 1
            else:
                stats["body_links_unknown"][label] += 1
        cards.append(_atom(subj, f"has_section_{slug}", content, source_rel))

    return cards


def ingest_anti_pattern_catalog(path: Path, vault_root: Path, log: list[str], stats: dict) -> list[Card]:
    """
    Each `## <N>. <name>` block becomes a pattern with subj `ap:<slug>`.
    Inner labelled paragraphs ('**触发条件**:', '**症状**:', ...) become atom triples.
    """
    text = path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)
    source_rel = str(path.relative_to(vault_root))

    # top-level doc card
    catalog_subj = "doc:anti_pattern_catalog"
    cards: list[Card] = [_root_card(catalog_subj, "doc", text, path, source_rel)]
    cards += _ingest_frontmatter(catalog_subj, fm, source_rel, log, stats)

    # split on ## headings; first heading is title catalog-wide → skip "附录" / "维护规则"
    # but still pick them up as `ap_meta:` cards
    for heading, content in _split_sections(body):
        if heading == "_intro":
            cards.append(_atom(catalog_subj, "has_section_intro", content, source_rel))
            continue

        # Detect numbered pattern: "1. Train-pass-Test-fail 综合症"
        m = re.match(r"^(\d+)\.\s+(.+)$", heading)
        if m:
            num = m.group(1)
            name = m.group(2).strip()
            slug = re.sub(r"[^\w]+", "_", name.lower(), flags=re.UNICODE).strip("_")
            ap_subj = f"ap:{num}_{slug}"
            cards.append(_atom(catalog_subj, "contains_anti_pattern", ap_subj, source_rel))
            cards.append(_root_card(ap_subj, "anti_pattern", content, path, source_rel))
            cards.append(_atom(ap_subj, "has_name", name, source_rel))
            cards.append(_atom(ap_subj, "has_number", int(num), source_rel))

            # extract labelled fields (**触发条件**: ... etc)
            for label_zh, slug_en in AP_FIELD_LABELS.items():
                # match `**<label>**: ... ` until next `**X**:` or blank line+block boundary
                m2 = re.search(
                    rf"\*\*{re.escape(label_zh)}\*\*\s*:?\s*(.+?)(?=\n\*\*[A-Za-z一-鿿 /]+\*\*\s*:|\n---|\Z)",
                    content,
                    re.DOTALL | re.IGNORECASE,
                )
                if m2:
                    val = m2.group(1).strip()
                    cards.append(_atom(ap_subj, f"has_{slug_en}", val, source_rel))
                    # also pull double-links inside this field
                    for tgt in _parse_double_links(val):
                        ns_target = _link_target_to_namespaced(tgt)
                        cards.append(_atom(ap_subj, f"references_in_{slug_en}", ns_target, source_rel))
                        stats["body_links"]["ap_references"] += 1
        else:
            # meta sections (附录, 维护规则)
            slug = _slugify(heading)
            cards.append(_atom(catalog_subj, f"has_section_{slug}", content, source_rel))

    return cards


def ingest_doc(path: Path, vault_root: Path, doc_id: str, log: list[str], stats: dict) -> list[Card]:
    """Generic doc ingest for VAULT_DESIGN.md and README.md — keep whole body, light frontmatter."""
    text = path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)
    source_rel = str(path.relative_to(vault_root))
    subj = f"doc:{doc_id}"
    cards: list[Card] = [_root_card(subj, "doc", text, path, source_rel)]
    cards += _ingest_frontmatter(subj, fm, source_rel, log, stats)
    # one atom per H2 section so future queries can navigate
    for heading, content in _split_sections(body):
        if heading == "_intro":
            cards.append(_atom(subj, "has_section_intro", content, source_rel))
        else:
            cards.append(_atom(subj, f"has_section_{_slugify(heading)}", content, source_rel))
    return cards


def ingest_report(path: Path, vault_root: Path, log: list[str], stats: dict) -> list[Card]:
    text = path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)
    stem = path.stem
    subj = f"report:{stem}"
    source_rel = str(path.relative_to(vault_root))
    cards: list[Card] = [_root_card(subj, "report", text, path, source_rel)]
    cards += _ingest_frontmatter(subj, fm, source_rel, log, stats)
    for heading, content in _split_sections(body):
        if heading == "_intro":
            cards.append(_atom(subj, "has_section_intro", content, source_rel))
            continue
        for label, tgt in _extract_body_links(content):
            ns_target = _link_target_to_namespaced(tgt)
            cards.append(_atom(subj, label, ns_target, source_rel))
            stats["body_links"][label] += 1
        cards.append(_atom(subj, f"has_section_{_slugify(heading)}", content, source_rel))
    # plain double-links in "## 链接到的 candidate" section get caught above via _extract_body_links
    # but that regex requires `**label**:` — for plain `- [[...]]` we add a fallback
    for tgt in _parse_double_links(body):
        ns_target = _link_target_to_namespaced(tgt)
        # only emit if not already covered (cheap dedup happens at hash-id level)
        if ns_target.startswith("exp:"):
            cards.append(_atom(subj, "links_to_experiment", ns_target, source_rel))
            stats["body_links"]["links_to_experiment"] += 1
    return cards


def _ingest_frontmatter(subj: str, fm: dict, source_rel: str, log: list[str], stats: dict) -> list[Card]:
    """
    Lift every YAML frontmatter key into an atom triple. Special-cases:
      - typed link fields (FRONTMATTER_LINK_FIELDS): parse [[...]] target, namespace it.
      - tags: list — emit one (subj, has_tag, tag:<value>) per element.
      - axis: list — emit one (subj, has_axis, axis:<value>) per element + one (subj, has_axis_list, [list]) summary.
      - null / None: skip silently.
      - scalar with `[[...]]` string: also lift as typed link if key matches FRONTMATTER_LINK_FIELDS.
    """
    cards: list[Card] = []
    for key, val in fm.items():
        if val is None:
            continue

        # typed link fields
        if key in FRONTMATTER_LINK_FIELDS:
            targets: list[str] = []
            if isinstance(val, str):
                targets = _parse_double_links(val)
                if not targets:
                    # plain string fallback
                    targets = [val]
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        ts = _parse_double_links(item)
                        targets.extend(ts if ts else [item])
            for tgt in targets:
                ns_target = _link_target_to_namespaced(tgt)
                cards.append(_atom(subj, key, ns_target, source_rel))
                stats["fm_links"][key] += 1
            continue

        # tags list
        if key == "tags" and isinstance(val, list):
            for tag in val:
                if not isinstance(tag, str):
                    continue
                cards.append(_atom(subj, "has_tag", f"tag:{tag}", source_rel))
                stats["tags"][f"tag:{tag}"] += 1
            continue

        # axis list (scalar list of strings)
        if key == "axis" and isinstance(val, list):
            for ax in val:
                if isinstance(ax, str):
                    cards.append(_atom(subj, "has_axis", f"axis:{ax}", source_rel))
            cards.append(_atom(subj, "has_axis_list", val, source_rel))
            continue

        # status / outcome / leak_audit / champion etc. — keep as has_<field>
        # If it's a scalar string in the controlled-vocab set, prefix with the field name to namespace.
        if isinstance(val, list):
            # generic list — keep as has_<key>_list with the list
            cards.append(_atom(subj, f"has_{key}_list", val, source_rel))
            continue
        if isinstance(val, dict):
            # rare — flatten one level
            for subk, subv in val.items():
                cards.append(_atom(subj, f"has_{key}_{subk}", subv, source_rel))
            continue

        # scalar
        cards.append(_atom(subj, f"has_{key}", val, source_rel))
    return cards


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--log", default=ARC_ROOT / "output" / "phase2_ingest.log", type=Path)
    args = ap.parse_args()

    vault = args.vault.resolve()
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    args.log.parent.mkdir(parents=True, exist_ok=True)

    log: list[str] = []
    stats = {
        "fm_links": Counter(),
        "body_links": Counter(),
        "body_links_unknown": Counter(),
        "tags": Counter(),
        "by_source_type": Counter(),
        "atoms_by_source": {},
    }

    t0 = dt.datetime.now()
    total_atoms = 0
    total_sources = 0

    def _ingest_one(path: Path, kind: str, builder) -> None:
        nonlocal total_atoms, total_sources
        cards = builder(path, vault, log, stats)
        n = _write_edn(cards, out_dir / f"{path.stem}.edn")
        stats["by_source_type"][kind] += 1
        stats["atoms_by_source"][path.name] = n
        total_atoms += n
        total_sources += 1

    # 1. experiments/
    for path in sorted((vault / "experiments").glob("*.md")):
        _ingest_one(path, "experiment", ingest_experiment)

    # 2. lineages/
    for path in sorted((vault / "lineages").glob("*.md")):
        _ingest_one(path, "lineage", ingest_lineage)

    # 3. reports/
    rpt_dir = vault / "reports"
    if rpt_dir.is_dir():
        for path in sorted(rpt_dir.glob("*.md")):
            _ingest_one(path, "report", ingest_report)

    # 4. ANTI_PATTERN_CATALOG.md
    apc = vault / "ANTI_PATTERN_CATALOG.md"
    if apc.is_file():
        _ingest_one(apc, "anti_pattern_catalog", ingest_anti_pattern_catalog)

    # 5. VAULT_DESIGN.md
    vd = vault / "VAULT_DESIGN.md"
    if vd.is_file():
        _ingest_one(vd, "doc", lambda p, v, l, s: ingest_doc(p, v, "vault_design", l, s))

    # 6. README.md
    rd = vault / "README.md"
    if rd.is_file():
        _ingest_one(rd, "doc", lambda p, v, l, s: ingest_doc(p, v, "vault_readme", l, s))

    elapsed = (dt.datetime.now() - t0).total_seconds()

    # ---- log ----
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append(f"PHASE 2 VAULT INGEST — {NOW}")
    lines.append("=" * 70)
    lines.append(f"vault         : {vault}")
    lines.append(f"out_dir       : {out_dir}")
    lines.append(f"elapsed_sec   : {elapsed:.2f}")
    lines.append(f"total_sources : {total_sources}")
    lines.append(f"total_atoms   : {total_atoms}")
    lines.append("")
    lines.append("by source type:")
    for k, v in stats["by_source_type"].most_common():
        lines.append(f"  {k:25s} {v}")
    lines.append("")
    lines.append("frontmatter typed-link counts:")
    for k, v in stats["fm_links"].most_common():
        lines.append(f"  {k:25s} {v}")
    lines.append("")
    lines.append("body typed-link counts:")
    for k, v in stats["body_links"].most_common():
        lines.append(f"  {k:25s} {v}")
    lines.append("")
    lines.append("body links with unknown label (kept but flagged):")
    for k, v in stats["body_links_unknown"].most_common():
        lines.append(f"  {k:25s} {v}")
    lines.append("")
    lines.append(f"unique tag values: {len(stats['tags'])}")
    lines.append("top tag values:")
    for k, v in stats["tags"].most_common(20):
        lines.append(f"  {k:35s} {v}")
    lines.append("")
    lines.append("warnings:")
    if log:
        lines.extend(log)
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append("atoms per source (sorted desc):")
    for src, n in sorted(stats["atoms_by_source"].items(), key=lambda x: -x[1]):
        lines.append(f"  {n:5d}  {src}")

    args.log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- stdout summary ----
    print(f"sources    : {total_sources}")
    print(f"atoms      : {total_atoms}")
    print(f"fm-links   : {sum(stats['fm_links'].values())}")
    print(f"body-links : {sum(stats['body_links'].values())}")
    print(f"unique tags: {len(stats['tags'])}")
    print(f"elapsed    : {elapsed:.2f}s")
    if log:
        print(f"warnings   : {len(log)} (see {args.log})")


def _write_edn(cards: list[Card], path: Path) -> int:
    """Build a tiny store, dump it to path. Return count of unique cards actually written."""
    s = CardStore()
    seen: set[str] = set()
    for c in cards:
        if c.id in seen:
            # collision on hash8 (e.g. duplicate triple) — skip silently
            continue
        seen.add(c.id)
        s.add(c)
    s.dump_edn(str(path))
    return len(seen)


if __name__ == "__main__":
    main()
