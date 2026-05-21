#!/usr/bin/env python3
"""
run_rules.py — Phase 3 driver.

Loads Phase 2 atom .edn files plus this phase's rule / macro .edn files,
runs the RuleEngine to fixpoint, dispatches the two macros against a small
set of source cards, then writes derived atoms back to disk under
wiki/cards/derived/.

EDN ↔ Python shape note
-----------------------
The kernel's sexp parser does not have a native dict literal — it parses
`(:k v :k v)` as a flat list of keyword/value tokens. The kernel's
`_edn_val` emits Python dicts in the same shape. So:

  - For *rule* :when / :then we already use list-of-triples form,
    which matches `[[subj, pred, obj], ...]` after parsing — works as-is.
  - For *macro* :body templates and :query specs we need to convert
    `[':type', 'foo', ':subj', '?bar', ...]` back into
    `{'type': 'foo', 'subj': '?bar', ...}` before handing them to
    MacroEngine.expand / View.materialize.

`_pairs_to_dict` does that conversion; it is a script-level concern (the
kernel libs stay untouched).
"""

from __future__ import annotations
import os
import sys
import time
import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
WIKI_ROOT = THIS_DIR.parent          # .../wiki
ROOT = WIKI_ROOT.parent              # .../arcs/all/<arc-id>
REPO_ROOT = ROOT                     # alias for clarity
sys.path.insert(0, str(ROOT))

from wiki.lib.cardstore import Card, CardStore  # noqa: E402
from wiki.lib.rules import RuleEngine  # noqa: E402
from wiki.lib.macro import MacroEngine  # noqa: E402
from wiki.lib.view import materialize  # noqa: E402


ATOMS_DIR = ROOT / "wiki" / "cards" / "atoms"
RULES_DIR = ROOT / "wiki" / "cards" / "rules"
MACROS_DIR = ROOT / "wiki" / "cards" / "macros"
DERIVED_DIR = ROOT / "wiki" / "cards" / "derived"
LOG_PATH = ROOT / "output" / "phase3_rules.log"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _pairs_to_dict(seq):
    """
    Convert a flat list [':k', v, ':k', v, ...] (the on-disk shape the EDN
    parser returns for dict literals) into a Python dict. Values that are
    themselves pair-lists get converted recursively; values that are lists
    of pair-lists (e.g. macro :body) become lists of dicts.
    """
    if not isinstance(seq, list):
        return seq
    # Heuristic: looks like pairs iff every other token starts with ':' and
    # length is even.
    if len(seq) >= 2 and len(seq) % 2 == 0 and all(
        isinstance(seq[i], str) and seq[i].startswith(":")
        for i in range(0, len(seq), 2)
    ):
        out = {}
        for i in range(0, len(seq), 2):
            key = seq[i][1:]
            val = seq[i + 1]
            if isinstance(val, list):
                # Try recursive pair conversion; else convert each element
                if val and isinstance(val[0], str) and val[0].startswith(":"):
                    val = _pairs_to_dict(val)
                else:
                    val = [_pairs_to_dict(x) for x in val]
            out[key] = val
        return out
    return seq


def load_dir(store: CardStore, dirpath: Path, label: str) -> int:
    """Load every *.edn file under dirpath into store; return count loaded."""
    n_before = len(store.all_cards())
    edn_files = sorted(dirpath.glob("*.edn"))
    for p in edn_files:
        store.load_edn(str(p))
    n_after = len(store.all_cards())
    print(f"  loaded {label:8s}: {n_after - n_before:4d} cards from {len(edn_files):3d} files")
    return n_after - n_before


def harden_atom_keys(store: CardStore) -> int:
    """
    Phase 2 ingest emits some atoms (notably has_axis_list, has_tag-list) with
    list-typed :obj because the source frontmatter field was a YAML list.
    RuleEngine builds a dedup keyset of (subj, pred, obj) tuples and requires
    those to be hashable. We tuple-ize list-typed slots in-place; this only
    affects in-memory representation, not the on-disk .edn files. Returns the
    number of atoms hardened.
    """
    n = 0
    for c in store.all_cards():
        for fld in ("subj", "pred", "obj"):
            v = c.kvs.get(fld)
            if isinstance(v, list):
                c.kvs[fld] = tuple(v)
                n += 1
    return n


def normalize_rule_card(rule: Card) -> Card:
    """
    The EDN parser may turn :when / :then into list-of-strings if a triple
    has no inner parens; in our files every triple is parenthesised, so the
    parser returns list-of-list-of-strings which is exactly what
    RuleEngine._match_patterns wants. This function is defensive only.
    """
    for field in ("when", "then"):
        val = rule.kvs.get(field)
        if not isinstance(val, list):
            continue
        normalized = []
        for item in val:
            if isinstance(item, list):
                normalized.append([str(x) for x in item])
            else:
                # flat triple stored without inner parens — split by spaces?
                # We don't expect this; skip.
                continue
        rule.kvs[field] = normalized
    return rule


def normalize_macro_card(macro: Card) -> Card:
    """Convert macro :body list-of-pair-lists into list-of-dicts."""
    body = macro.kvs.get("body")
    if isinstance(body, list):
        new_body = []
        for item in body:
            if isinstance(item, list):
                d = _pairs_to_dict(item)
                if isinstance(d, dict):
                    # convert nested :query pair-list to dict too
                    if "query" in d and isinstance(d["query"], list):
                        q = _pairs_to_dict(d["query"])
                        if isinstance(q, dict):
                            d["query"] = q
                    new_body.append(d)
            elif isinstance(item, dict):
                new_body.append(item)
        macro.kvs["body"] = new_body
    return macro


def dump_derived_per_rule(store: CardStore, derived_cards: list, out_dir: Path):
    """
    Write derived cards grouped by their :derived_from (rule/macro id) into
    one .edn file per source. Returns dict of {source_id: count}.
    """
    groups: dict[str, list[Card]] = {}
    for c in derived_cards:
        src = c.kvs.get("derived_from", "unknown")
        groups.setdefault(src, []).append(c)

    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for src, cards in groups.items():
        # Slug safe filename
        slug = (
            str(src)
            .replace("rule:", "")
            .replace("macro:", "")
            .replace(":", "_")
            .replace("/", "_")
            .replace(" ", "_")
        )
        if not slug:
            slug = "unknown"
        path = out_dir / f"{slug}.edn"
        tmp_store = CardStore()
        for c in cards:
            try:
                tmp_store.add(c)
            except ValueError:
                # id collision within batch (shouldn't happen — defensive)
                pass
        tmp_store.dump_edn(str(path))
        counts[src] = len(cards)
    return counts


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    t0 = time.time()
    log_lines: list[str] = []

    def log(s: str = ""):
        print(s)
        log_lines.append(s)

    log("=" * 70)
    log(f"PHASE 3 RULES + MACROS RUN — {datetime.datetime.now().isoformat(timespec='seconds')}")
    log("=" * 70)

    # -----------------------------------------------------------------
    # 1. Load all atoms
    # -----------------------------------------------------------------
    log("\n[1] Load atom store from Phase 2")
    store = CardStore()
    load_dir(store, ATOMS_DIR, "atoms")
    atom_count_initial = len(store.find_by_type("atom"))
    src_card_count = len(store.all_cards()) - atom_count_initial
    log(f"  atoms      : {atom_count_initial}")
    log(f"  src cards  : {src_card_count}  (experiment / lineage / doc / report / anti_pattern_catalog)")
    log(f"  total      : {len(store.all_cards())}")

    n_hardened = harden_atom_keys(store)
    log(f"  hardened   : {n_hardened} list-typed (subj|pred|obj) slots → tuple (in-memory only)")

    # -----------------------------------------------------------------
    # 2. Load rules + register engine
    # -----------------------------------------------------------------
    log("\n[2] Load rule cards from disk")
    rules_loaded_before = len(store.find_by_type("rule"))
    load_dir(store, RULES_DIR, "rules")
    rule_cards = store.find_by_type("rule")
    log(f"  rule cards in store: {len(rule_cards)} (was {rules_loaded_before}, new {len(rule_cards) - rules_loaded_before})")

    engine = RuleEngine()
    for rc in rule_cards:
        normalize_rule_card(rc)
        engine.register(rc)
    log(f"  registered with RuleEngine: {len(engine._rules)}")
    log("  rule ids:")
    for rid in sorted(engine._rules.keys()):
        rule = engine._rules[rid]
        when_summary = rule.kvs.get("when", "?")
        then_summary = rule.kvs.get("then", "?")
        log(f"    {rid}  when={when_summary}  →  then={then_summary}")

    # -----------------------------------------------------------------
    # 3. Forward-chain to fixpoint
    # -----------------------------------------------------------------
    log("\n[3] Forward-chain rules to fixpoint")
    t_rule_start = time.time()
    all_derived: list[Card] = []
    per_iter_counts = []
    max_iters = 12
    for it in range(1, max_iters + 1):
        batch = engine.run_once(store)
        per_iter_counts.append(len(batch))
        log(f"  iter {it:2d}: {len(batch):5d} new derived cards")
        if not batch:
            log(f"  fixpoint reached after {it} iterations")
            break
        all_derived.extend(batch)
    rule_elapsed = time.time() - t_rule_start
    log(f"  total derived from rules : {len(all_derived)}")
    log(f"  rule fixpoint elapsed_sec: {rule_elapsed:.3f}")

    # Per-rule fire counts
    fire_counts: dict[str, int] = {}
    for c in all_derived:
        src = c.kvs.get("derived_from", "?")
        fire_counts[src] = fire_counts.get(src, 0) + 1
    log("  per-rule fire counts:")
    for src in sorted(fire_counts.keys()):
        log(f"    {src:60s} {fire_counts[src]:5d}")

    # Sanity: dedup invariant
    triples = set()
    dupes = 0
    for c in store.all_cards():
        s = c.kvs.get("subj"); p = c.kvs.get("pred"); o = c.kvs.get("obj")
        if s and p and o:
            key = (s, p, o)
            if key in triples:
                dupes += 1
            triples.add(key)
    log(f"  (subj,pred,obj) dupe count after fixpoint: {dupes}  (expect 0)")

    # -----------------------------------------------------------------
    # 4. Load macros + dispatch
    # -----------------------------------------------------------------
    log("\n[4] Load macro cards and dispatch demos")
    load_dir(store, MACROS_DIR, "macros")
    macro_cards = store.find_by_type("macro")
    log(f"  macro cards in store: {len(macro_cards)}")

    macro_engine = MacroEngine()
    for mc in macro_cards:
        normalize_macro_card(mc)
        macro_engine.register(mc)
    log(f"  registered macro names: {sorted(macro_engine._macros.keys())}")

    # m001 — 3 source experiments hand-picked for variety
    m001_sources = [
        "exp:H-R3b-4_c84_kelly_lambda_1.5",        # SOTA champion
        "exp:C8.4_top3_no_open3min_bypass",         # trade-selector base used by H-R3b-4
        "exp:B-R8-1_no_open3min_bypass03",          # cross-team mechanism source
    ]
    m001_expansions: list[Card] = []
    log("\n  m001 paper-to-experiment-suggestion dispatch:")
    for src in m001_sources:
        cards = macro_engine.expand(
            "paper-to-experiment-suggestion",
            {"source-paper": src},
            source_card_id=src,
        )
        for c in cards:
            try:
                store.add(c)
                m001_expansions.append(c)
            except ValueError:
                log(f"    skip dup id {c.id}")
        log(f"    expanded {src} → {len(cards)} suggestion cards")

    # m002 — 2 source lineages.
    # Note: vault internal data has lineage *source* card ids (filename slug)
    # that don't always match the parent_lineage *target* ids experiments use
    # (frontmatter slug). For a meaningful materialization spot-check we
    # dispatch on the latter form — the ids that actually appear in
    # parent_lineage edges. These two are the top-2 by edge count.
    m002_sources = [
        "lin:arc_260516a__team_h__sizing",                 # 14 experiment edges
        "lin:arc_260516a__team_d__blacklist_default_admit",  # 7 experiment edges
    ]
    m002_expansions: list[Card] = []
    log("\n  m002 lineage-to-comparison-view dispatch:")
    for src in m002_sources:
        cards = macro_engine.expand(
            "lineage-to-comparison-view",
            {"lineage": src},
            source_card_id=src,
        )
        for c in cards:
            try:
                store.add(c)
                m002_expansions.append(c)
            except ValueError:
                log(f"    skip dup id {c.id}")
        log(f"    expanded {src} → {len(cards)} view card(s)")

    total_macro_expansions = len(m001_expansions) + len(m002_expansions)
    log(f"\n  total macro-expanded cards : {total_macro_expansions}")

    # Materialize each m002-derived view to validate the lazy query works
    log("\n  m002 view materialization spot-check:")
    for view_card in m002_expansions:
        # The view card was added to store; materialize it now.
        results = materialize(view_card, store)
        # Count just atoms (the parent_lineage edges) for clean reporting
        atom_hits = [r for r in results if r.type == "atom"]
        log(
            f"    {view_card.kvs.get('name', view_card.id)} → {len(results)} cards "
            f"({len(atom_hits)} atoms via parent_lineage)"
        )

    # -----------------------------------------------------------------
    # 5. Write derived to disk
    # -----------------------------------------------------------------
    log("\n[5] Write derived atoms to disk")
    all_derived_to_dump = all_derived + m001_expansions + m002_expansions
    counts = dump_derived_per_rule(store, all_derived_to_dump, DERIVED_DIR)
    log(f"  derived files written under: {DERIVED_DIR.relative_to(ROOT.parent)}")
    for src, n in sorted(counts.items()):
        log(f"    {src:60s} {n:5d} cards")

    # -----------------------------------------------------------------
    # 6. Final summary
    # -----------------------------------------------------------------
    total_elapsed = time.time() - t0
    log("\n" + "=" * 70)
    log("SUMMARY")
    log("=" * 70)
    log(f"  initial atom count           : {atom_count_initial}")
    log(f"  rules registered             : {len(engine._rules)}")
    log(f"  macros registered            : {len(macro_engine._macros)}")
    log(f"  rule fires (total derived)   : {len(all_derived)}")
    log(f"  fixpoint iterations          : {len([n for n in per_iter_counts if n > 0])}  ({per_iter_counts})")
    log(f"  macro expansions (m001+m002) : {total_macro_expansions}  (m001={len(m001_expansions)} m002={len(m002_expansions)})")
    log(f"  derived card files on disk   : {len(counts)}")
    log(f"  store total cards            : {len(store.all_cards())}")
    log(f"  dedup invariant ok           : {dupes == 0}")
    log(f"  rule fixpoint elapsed_sec    : {rule_elapsed:.3f}")
    log(f"  total elapsed_sec            : {total_elapsed:.3f}")
    log("=" * 70)

    # Write log
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")
    print(f"\nlog written to: {LOG_PATH}")

    # Single-line machine-readable summary for the caller
    print(
        f"\nHANDOFF: rule_fires={len(all_derived)} "
        f"macro_expands={total_macro_expansions} "
        f"derived_files={len(counts)} "
        f"fixpoint_iters={len([n for n in per_iter_counts if n > 0])} "
        f"elapsed_sec={total_elapsed:.3f} "
        f"dedup_ok={dupes == 0}"
    )


if __name__ == "__main__":
    main()
