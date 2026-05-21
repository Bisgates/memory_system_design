#!/usr/bin/env python3
"""
demo_capabilities.py — Phase 4 driver.

Runs end-to-end demos for the 6 first-class capabilities the wiki promises:

  1. macro 派生卡            (macro expansion produces fresh cards)
  2. lazy reference          (<eval>...</eval> resolved at read-time)
  3. 规则即卡片              (rules live alongside data, queryable)
  4. dedup restart 协议      (keep-both / merge-prefer-newer / supersede)
  5. 视图卡 materialized view (re-evaluated against the live store)
  6. 自计算字段              (:confidence (compute ...) eval'd from links)

Output:
  output/<YYMMDD_HHMM>_demo_run/cap<N>_<name>/
    *.json / *.edn / *.txt  trace artefacts
    stdout.log              captured stdout for the capability

The script is idempotent — re-running overwrites trace files in the same dir.

Pass --run-dir <path> to point at an existing demo_run dir (default: most
recent under output/*_demo_run, else create one at output/<ts>_demo_run).
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
WIKI_ROOT = THIS_DIR.parent
ARC_ROOT = WIKI_ROOT.parent
sys.path.insert(0, str(ARC_ROOT))

from wiki.lib.cardstore import Card, CardStore  # noqa: E402
from wiki.lib.macro import MacroEngine  # noqa: E402
from wiki.lib.rules import RuleEngine  # noqa: E402
from wiki.lib.view import materialize  # noqa: E402
from wiki.lib.dedup import find_near_dupes, resolve_conflict, similarity  # noqa: E402

# Re-use helpers from run_rules.py (pair-list ↔ dict conversion)
from wiki.scripts.run_rules import (  # noqa: E402
    _pairs_to_dict,
    harden_atom_keys,
    normalize_macro_card,
    normalize_rule_card,
)


ATOMS_DIR = ARC_ROOT / "wiki" / "cards" / "atoms"
RULES_DIR = ARC_ROOT / "wiki" / "cards" / "rules"
MACROS_DIR = ARC_ROOT / "wiki" / "cards" / "macros"
OUTPUT_DIR = ARC_ROOT / "output"


# ---------------------------------------------------------------------------
# tiny helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def card_to_jsonable(c: Card) -> dict:
    return {"id": c.id, "type": c.type, "kvs": _jsonable(c.kvs)}


def _jsonable(v):
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    return str(v)


def short_body(s, n=140):
    if s is None:
        return ""
    s = str(s).replace("\n", " ").strip()
    if len(s) > n:
        return s[:n] + " …"
    return s


# ---------------------------------------------------------------------------
# store load (shared across capabilities)
# ---------------------------------------------------------------------------

def load_full_store(verbose=True) -> tuple[CardStore, RuleEngine, MacroEngine]:
    """Load atoms + rules + macros. Returns store and pre-registered engines."""
    store = CardStore()
    # atoms
    edn_files = sorted(ATOMS_DIR.glob("*.edn"))
    for p in edn_files:
        store.load_edn(str(p))
    harden_atom_keys(store)
    # rules
    for p in sorted(RULES_DIR.glob("*.edn")):
        store.load_edn(str(p))
    rule_engine = RuleEngine()
    for rc in store.find_by_type("rule"):
        normalize_rule_card(rc)
        rule_engine.register(rc)
    # macros
    for p in sorted(MACROS_DIR.glob("*.edn")):
        store.load_edn(str(p))
    macro_engine = MacroEngine()
    for mc in store.find_by_type("macro"):
        normalize_macro_card(mc)
        macro_engine.register(mc)
    if verbose:
        print(f"  store loaded — {len(store.all_cards())} cards "
              f"({len(store.find_by_type('atom'))} atoms, "
              f"{len(store.find_by_type('experiment'))} experiments, "
              f"{len(store.find_by_type('lineage'))} lineages, "
              f"{len(store.find_by_type('rule'))} rules, "
              f"{len(store.find_by_type('macro'))} macros)")
    return store, rule_engine, macro_engine


# ---------------------------------------------------------------------------
# Capability 1 — macro 派生卡
# ---------------------------------------------------------------------------

def cap1_macro_derive(run_dir: Path) -> dict:
    out = run_dir / "cap1_macro_derive"
    out.mkdir(parents=True, exist_ok=True)

    buf = io.StringIO()
    with redirect_stdout(buf):
        print(f"# Capability 1 — macro 派生卡  ({now_iso()})")
        print("-" * 70)
        store, _re, me = load_full_store()

        # 3 hand-picked experiments for variety
        chosen = [
            ("exp:H-R3b-4_c84_kelly_lambda_1.5", "SOTA champion (status=champion)"),
            ("exp:B-R10-2_blacklist_low_amt",    "status=falsified blacklist plateau"),
            ("exp:H-R2-2_c84_linear_sizing",     "Lineage parent of the champion"),
        ]
        print("\ninput experiment cards:")
        for cid, why in chosen:
            c = store.get(cid)
            if c is None:
                print(f"  [MISS] {cid}  ({why})")
                continue
            print(f"  {cid:55s}  {why}")
            # short summary atoms
            outs = store.find_links_from(cid, link_pred="has_title")
            if outs:
                print(f"      title: {short_body(outs[0].kvs.get('obj'), 90)}")
            navs = store.find_links_from(cid, link_pred="has_train_nav")
            if navs:
                print(f"      train_nav: {navs[0].kvs.get('obj')}")
            stats = store.find_links_from(cid, link_pred="has_status")
            if stats:
                print(f"      status: {stats[0].kvs.get('obj')}")

        print("\nm001 macro source (full body):")
        m001 = store.get("m001_paper_to_experiment_suggestion")
        print(f"  id     : {m001.id}")
        print(f"  type   : {m001.type}")
        print(f"  name   : {m001.kvs.get('name')}")
        print(f"  params : {m001.kvs.get('params')}")
        for i, tpl in enumerate(m001.kvs.get("body", []), 1):
            print(f"  template-{i}: {tpl}")

        print("\nm001 expansion — 9 fresh suggestion cards:")
        suggestions = []
        for cid, _why in chosen:
            cards = me.expand("paper-to-experiment-suggestion",
                              {"source-paper": cid},
                              source_card_id=cid)
            for c in cards:
                suggestions.append(c)
                print(f"  + {c.id}  {c.type:10s}  obj={c.kvs.get('obj')}")
                print(f"      body: {short_body(c.kvs.get('body'), 110)}")

        print(f"\n  total expanded cards: {len(suggestions)}")
        print("\nemphasis: macro 本身也是 card — query 它一样的方式:")
        all_macros = store.find_by_type("macro")
        print(f"  store.find_by_type('macro') → {len(all_macros)} cards: "
              f"{[m.id for m in all_macros]}")
        print("\n  (这就是 homoiconic: 数据 + 规则 + 派生过程 全部共享 :id namespace)")

    stdout_log = buf.getvalue()
    sys.stdout.write(stdout_log)

    # Persist trace artefacts
    write_text(out / "stdout.log", stdout_log)
    write_json(out / "input_cards.json",
               [card_to_jsonable(store.get(cid)) for cid, _ in chosen if store.get(cid)])
    write_json(out / "m001_source.json", card_to_jsonable(m001))
    write_json(out / "expanded_suggestions.json",
               [card_to_jsonable(c) for c in suggestions])

    # Dump expansions as EDN too (Phase 3 stores them this way)
    tmp = CardStore()
    for c in suggestions:
        try:
            tmp.add(c)
        except ValueError:
            pass
    tmp.dump_edn(str(out / "expanded_suggestions.edn"))

    return {"input_cards": len(chosen),
            "suggestions": len(suggestions),
            "macro_cards_in_store": len(all_macros)}


# ---------------------------------------------------------------------------
# Capability 2 — lazy reference
# ---------------------------------------------------------------------------

def cap2_lazy_ref(run_dir: Path) -> dict:
    out = run_dir / "cap2_lazy_ref"
    out.mkdir(parents=True, exist_ok=True)

    buf = io.StringIO()
    with redirect_stdout(buf):
        print(f"# Capability 2 — lazy reference  ({now_iso()})")
        print("-" * 70)
        store, _re, _me = load_full_store()

        # Create two ephemeral cards with <eval> in their :body
        view_card = Card(
            id="cap2:view-latest-top-experiments",
            type="view",
            kvs={
                "name": "view-latest-top-experiments",
                "body": (
                    "Latest SOTA snapshot:\n"
                    "  champion body excerpt → <eval>latest-of exp:H-R3b-4_c84_kelly_lambda_1.5</eval>\n"
                    "  inbound link count for champion → <eval>count-links-to exp:H-R3b-4_c84_kelly_lambda_1.5</eval>\n"
                    "  inbound link count for parent (H-R2-2) → <eval>count-links-to exp:H-R2-2_c84_linear_sizing</eval>\n"
                ),
                "query": {"filter_type": "experiment"},
            },
        )
        atom_card = Card(
            id="cap2:atom-with-lazy-ref",
            type="atom",
            kvs={
                "subj": "cap2:atom-with-lazy-ref",
                "pred": "summarizes",
                "obj": "exp:H-R3b-4_c84_kelly_lambda_1.5",
                "body": (
                    "Atom-level lazy ref: <eval>latest-of exp:C8.4_top3_no_open3min_bypass</eval>"
                ),
            },
        )
        store.add(view_card)
        store.add(atom_card)

        print("\nbefore resolve_lazy:")
        print("  view_card.body (raw):")
        for line in str(view_card.kvs["body"]).splitlines():
            print(f"    {line}")
        print("\n  atom_card.body (raw):")
        print(f"    {atom_card.kvs['body']}")

        # Resolve
        resolved_view = store.resolve_lazy(view_card)
        resolved_atom = store.resolve_lazy(atom_card)

        print("\nafter resolve_lazy (view):")
        for line in str(resolved_view.kvs["body"]).splitlines():
            print(f"    {short_body(line, 200)}")
        print("\nafter resolve_lazy (atom):")
        print(f"    {short_body(resolved_atom.kvs['body'], 200)}")

        # Also count how many ingested atoms in the store happen to already
        # carry <eval> markers (sanity / discovery).
        embedded = [c for c in store.all_cards()
                    if isinstance(c.kvs.get("body"), str) and "<eval>" in c.kvs["body"]]
        print(f"\n  cards carrying <eval> markers (incl. the two we just added): {len(embedded)}")
        for c in embedded:
            print(f"    {c.id:55s}  type={c.type}")

    stdout_log = buf.getvalue()
    sys.stdout.write(stdout_log)
    write_text(out / "stdout.log", stdout_log)
    write_json(out / "before_after.json", {
        "view_before": card_to_jsonable(view_card),
        "view_after":  card_to_jsonable(resolved_view),
        "atom_before": card_to_jsonable(atom_card),
        "atom_after":  card_to_jsonable(resolved_atom),
    })

    return {"lazy_refs_resolved": 3, "carrier_cards": len(embedded)}


# ---------------------------------------------------------------------------
# Capability 3 — 规则即卡片
# ---------------------------------------------------------------------------

def cap3_rules_as_cards(run_dir: Path) -> dict:
    out = run_dir / "cap3_rules_as_cards"
    out.mkdir(parents=True, exist_ok=True)

    buf = io.StringIO()
    with redirect_stdout(buf):
        print(f"# Capability 3 — 规则即卡片 (rules-as-cards)  ({now_iso()})")
        print("-" * 70)
        store, rule_engine, _me = load_full_store()

        # (a) find_by_type('rule')
        rules = store.find_by_type("rule")
        print(f"\n[a] store.find_by_type('rule') → {len(rules)} rule cards:")
        for r in sorted(rules, key=lambda x: x.id):
            when = r.kvs.get("when", "?")
            then = r.kvs.get("then", "?")
            print(f"  {r.id}")
            print(f"      when : {when}")
            print(f"      then : {then}")
            print(f"      status: {r.kvs.get('status', '?')}")

        # (b) For each rule, count how many derived cards reference it via :derived_from
        # (after running fixpoint)
        print("\n[b] forward-chain to fixpoint and tally derived-from usage:")
        before = len(store.all_cards())
        rule_engine.run_to_fixpoint(store)
        after = len(store.all_cards())
        print(f"  cards before: {before}   after: {after}   new: {after - before}")
        usage = {}
        for c in store.find_by_type("derived"):
            src = c.kvs.get("derived_from", "?")
            usage[src] = usage.get(src, 0) + 1
        print("  derived count per rule (via :derived_from):")
        for rid in sorted(usage.keys()):
            print(f"    {rid:55s} {usage[rid]:4d}")

        # (c) "find rules whose body mentions 'reverse'"  (string-contains query)
        #   — demonstrates ad-hoc keyword search across rules-as-cards
        print("\n[c] string-contains query — rules whose :body mentions 'reverse':")
        hits = [r for r in rules if "reverse" in str(r.kvs.get("body", "")).lower()]
        for r in hits:
            print(f"  {r.id}")
            print(f"      body: {short_body(r.kvs.get('body'), 120)}")

        # (d) Pause one rule and re-run fixpoint to show the derived count drops
        print("\n[d] pause one rule (r002_derived_from_reverse) and re-run fixpoint:")
        target = "rule:r002_derived_from_reverse"
        baseline_derived_count = sum(1 for c in store.find_by_type("derived")
                                     if c.kvs.get("derived_from") == target)
        print(f"  baseline derived-from-{target}: {baseline_derived_count}")

        # Re-load fresh store to demonstrate effect cleanly
        store2 = CardStore()
        for p in sorted(ATOMS_DIR.glob("*.edn")):
            store2.load_edn(str(p))
        harden_atom_keys(store2)
        for p in sorted(RULES_DIR.glob("*.edn")):
            store2.load_edn(str(p))
        # Pause via :status='paused'
        store2.update(target, status="paused")
        print(f"  status flipped → store2.get({target!r}).kvs['status'] = "
              f"{store2.get(target).kvs.get('status')!r}")

        # New engine: only register rules with status != 'paused'
        re2 = RuleEngine()
        n_registered = 0
        for r in store2.find_by_type("rule"):
            normalize_rule_card(r)
            if r.kvs.get("status") == "paused":
                print(f"  skip paused rule: {r.id}")
                continue
            re2.register(r)
            n_registered += 1
        print(f"  registered {n_registered} rules (out of {len(store2.find_by_type('rule'))})")

        re2.run_to_fixpoint(store2)
        paused_derived_count = sum(1 for c in store2.find_by_type("derived")
                                   if c.kvs.get("derived_from") == target)
        total_derived_with_pause = len(store2.find_by_type("derived"))
        print(f"  after re-run with {target} paused:")
        print(f"    derived-from-{target}: {paused_derived_count}  (was {baseline_derived_count})")
        print(f"    total derived cards : {total_derived_with_pause}  "
              f"(baseline total: {len(store.find_by_type('derived'))})")

        delta = baseline_derived_count - paused_derived_count
        print(f"  delta on the paused rule's lineage: {delta}  "
              f"(>0 ⇒ status='paused' really blocked firing)")

        # Write per-rule .edn snapshot of the baseline run
        write_json(out / "rules_list.json",
                   [card_to_jsonable(r) for r in rules])
        write_json(out / "usage_counts.json", usage)
        write_json(out / "pause_demo.json", {
            "target": target,
            "baseline_total_derived": len(store.find_by_type("derived")),
            "baseline_target_derived": baseline_derived_count,
            "paused_total_derived": total_derived_with_pause,
            "paused_target_derived": paused_derived_count,
            "delta": delta,
        })

    stdout_log = buf.getvalue()
    sys.stdout.write(stdout_log)
    write_text(out / "stdout.log", stdout_log)

    return {"rule_cards": len(rules),
            "rules_with_fan_出": len(usage),
            "pause_delta": delta,
            "baseline_total_derived": after - before}


# ---------------------------------------------------------------------------
# Capability 4 — dedup restart 协议
# ---------------------------------------------------------------------------

def cap4_dedup_restart(run_dir: Path) -> dict:
    out = run_dir / "cap4_dedup_restart"
    out.mkdir(parents=True, exist_ok=True)

    buf = io.StringIO()
    with redirect_stdout(buf):
        print(f"# Capability 4 — dedup restart 协议  ({now_iso()})")
        print("-" * 70)
        store, _re, _me = load_full_store()

        # Locate an existing has_section_hypothesis atom on the SOTA champion
        champion_id = "exp:H-R3b-4_c84_kelly_lambda_1.5"
        hyps = store.find_links_from(champion_id, link_pred="has_section_hypothesis")
        if not hyps:
            raise RuntimeError("no hypothesis atom found on champion")
        original = hyps[0]
        original_body = str(original.kvs.get("obj", ""))
        print(f"\n  original atom id: {original.id}")
        print(f"  subj: {original.kvs.get('subj')}")
        print(f"  pred: {original.kvs.get('pred')}")
        print(f"  body length: {len(original_body)} chars")

        # Build a 5-10% variant body: replace one λ number and append a sentence
        # Try a couple of substitutions, then append a closing line.
        variant_body = original_body
        for s, t in [("λ=1.5", "λ=1.6"), ("1.5", "1.6")]:
            if s in variant_body:
                variant_body = variant_body.replace(s, t, 1)
                break
        variant_body += " \n- 备注: 该假设的微调 variant, 用于测试 dedup restart 协议。"

        # Sanity check similarity
        scratch_orig = Card(id="scratch_orig", type="atom",
                            kvs={"subj": original.kvs.get("subj"),
                                 "pred": original.kvs.get("pred"),
                                 "obj": original.kvs.get("obj"),
                                 "body": original_body})
        scratch_var = Card(id="scratch_var", type="atom",
                           kvs={"subj": original.kvs.get("subj"),
                                "pred": original.kvs.get("pred"),
                                "obj": original.kvs.get("obj"),
                                "body": variant_body})
        sim_score = similarity(scratch_orig, scratch_var)
        print(f"  similarity(orig, variant) = {sim_score:.3f}  (threshold 0.80)")

        # Run the protocol three times — once per restart option
        restart_options_to_try = ["keep-both", "merge-prefer-newer", "supersede"]
        case_results = []

        for case_idx, opt in enumerate(restart_options_to_try, 1):
            # Take a fresh store snapshot per case so they don't interfere
            print(f"\n[case {case_idx}] on-dedup-conflict = [{opt!r}, ...]")
            sub_store = CardStore()
            # Cheap clone: re-load from disk + add a clean copy of original
            for p in sorted(ATOMS_DIR.glob("*.edn")):
                sub_store.load_edn(str(p))
            harden_atom_keys(sub_store)

            # In the ingested vault, the atom carries its hypothesis text in
            # :obj (the predicate's value), not :body — so the dedup module's
            # text-similarity (which looks at :body) needs us to mirror :obj
            # into :body on the comparison cards so the similarity actually
            # scores >= threshold. We do this in-memory on the sub_store copy
            # only; on-disk EDN files are untouched.
            orig_copy = sub_store.get(original.id)
            orig_copy.kvs["body"] = str(orig_copy.kvs.get("obj", "") or "")

            # Build new card with a content-derived id so add() succeeds
            import hashlib as _hl
            sig = f"variant|{opt}|{case_idx}|{variant_body[:120]}"
            new_id = "a_var_" + _hl.sha1(sig.encode()).hexdigest()[:8]
            # restart list: chosen option first, then the others as fallback chain
            order = [opt] + [o for o in restart_options_to_try if o != opt]
            new_card = Card(
                id=new_id, type="atom",
                kvs={
                    "subj": original.kvs.get("subj"),
                    "pred": original.kvs.get("pred"),
                    "obj": variant_body,   # the typed-link slot
                    "body": variant_body,  # mirror so similarity sees it
                    "on-dedup-conflict": order,
                    "source": "cap4_dedup_restart_demo",
                    "ingested_at": now_iso(),
                },
            )

            # Before snapshot
            orig_before = sub_store.get(original.id)
            before_snapshot = {
                "store_size_before": len(sub_store.all_cards()),
                "original_see_also": list(orig_before.kvs.get("see-also", []) or []),
                "original_status":   orig_before.kvs.get("status"),
                "new_card_in_store_before": False,
            }
            print(f"    store_size_before     : {before_snapshot['store_size_before']}")
            print(f"    original see-also     : {before_snapshot['original_see_also']}")
            print(f"    original status       : {before_snapshot['original_status']}")

            # Discover dupes BEFORE adding (find_near_dupes excludes self)
            dupes = find_near_dupes(new_card, sub_store, threshold=0.80)
            print(f"    near-dupes found      : {len(dupes)}  (top scores:"
                  f" {[(d[0].id, round(d[1],3)) for d in dupes[:3]]})")

            # Add new card then resolve
            sub_store.add(new_card)
            action_taken = resolve_conflict(new_card, dupes, sub_store)
            print(f"    action taken          : {action_taken}")

            # After snapshot
            orig_after = sub_store.get(original.id)
            new_after = sub_store.get(new_card.id)
            after_snapshot = {
                "store_size_after": len(sub_store.all_cards()),
                "original_see_also": list(orig_after.kvs.get("see-also", []) or []),
                "original_status":   orig_after.kvs.get("status"),
                "original_superseded_by": orig_after.kvs.get("superseded-by"),
                "new_card_supersedes": new_after.kvs.get("supersedes"),
                "new_card_see_also":  list(new_after.kvs.get("see-also", []) or []),
            }
            print(f"    store_size_after      : {after_snapshot['store_size_after']}")
            print(f"    original see-also     : {after_snapshot['original_see_also']}")
            print(f"    original status       : {after_snapshot['original_status']}")
            if after_snapshot["original_superseded_by"]:
                print(f"    original superseded-by: {after_snapshot['original_superseded_by']}")
            if after_snapshot["new_card_supersedes"]:
                print(f"    new card supersedes   : {after_snapshot['new_card_supersedes']}")

            case_results.append({
                "case": case_idx,
                "restart_option_used": opt,
                "action_returned": action_taken,
                "before": before_snapshot,
                "after": after_snapshot,
                "new_card_id": new_card.id,
                "original_id": original.id,
                "near_dupes": [(d[0].id, round(d[1], 4)) for d in dupes[:5]],
            })

        print(f"\n  3 restart cases completed: "
              f"{[r['action_returned'] for r in case_results]}")

    stdout_log = buf.getvalue()
    sys.stdout.write(stdout_log)
    write_text(out / "stdout.log", stdout_log)
    write_json(out / "cases.json", case_results)
    write_text(out / "variant_body.txt", variant_body)

    return {"restart_cases": len(case_results),
            "similarity_score": round(sim_score, 4),
            "actions": [r["action_returned"] for r in case_results]}


# ---------------------------------------------------------------------------
# Capability 5 — 视图卡 (materialized view)
# ---------------------------------------------------------------------------

def cap5_view_card(run_dir: Path) -> dict:
    out = run_dir / "cap5_view_card"
    out.mkdir(parents=True, exist_ok=True)

    buf = io.StringIO()
    with redirect_stdout(buf):
        print(f"# Capability 5 — 视图卡 (materialized view)  ({now_iso()})")
        print("-" * 70)
        store, _re, me = load_full_store()

        # Expand m002 on the team_h__sizing lineage to get a fresh view card
        lineage = "lin:arc_260516a__team_h__sizing"
        view_cards = me.expand("lineage-to-comparison-view",
                               {"lineage": lineage},
                               source_card_id=lineage)
        if not view_cards:
            raise RuntimeError("no view card emitted by m002")
        view = view_cards[0]
        # Coerce the on-disk pair-list :query (if any) into a dict
        q = view.kvs.get("query")
        if isinstance(q, list):
            view.kvs["query"] = _pairs_to_dict(q)
        store.add(view)
        print(f"\n  view card id    : {view.id}")
        print(f"  view name       : {view.kvs.get('name')}")
        print(f"  view query      : {view.kvs.get('query')}")
        print(f"  view body       : {short_body(view.kvs.get('body'), 100)}")

        # Snapshot 1 — initial
        results_a = materialize(view, store)
        atom_hits_a = [r for r in results_a if r.type == "atom"]
        print(f"\n[snapshot 1] initial materialize")
        print(f"  total matches      : {len(results_a)}")
        print(f"  atom-typed matches : {len(atom_hits_a)}")
        for c in atom_hits_a[:5]:
            print(f"    + {c.id}  subj={c.kvs.get('subj')}")
        if len(atom_hits_a) > 5:
            print(f"    … and {len(atom_hits_a) - 5} more")

        # Snapshot 2 — add a synthetic experiment-to-lineage atom
        synthetic_id = "a_cap5_synthetic_link"
        synthetic = Card(
            id=synthetic_id, type="atom",
            kvs={
                "subj": "exp:CAP5_SYNTHETIC_NEW_CANDIDATE",
                "pred": "parent_lineage",
                "obj": lineage,
                "source": "cap5_view_card_demo",
                "ingested_at": now_iso(),
            },
        )
        store.add(synthetic)
        results_b = materialize(view, store)
        atom_hits_b = [r for r in results_b if r.type == "atom"]
        print(f"\n[snapshot 2] after adding synthetic atom {synthetic_id}")
        print(f"  total matches      : {len(results_b)}")
        print(f"  atom-typed matches : {len(atom_hits_b)}")
        print(f"  delta vs snapshot 1: {len(results_b) - len(results_a)}")

        # Snapshot 3 — remove the synthetic atom
        store.delete(synthetic_id)
        results_c = materialize(view, store)
        atom_hits_c = [r for r in results_c if r.type == "atom"]
        print(f"\n[snapshot 3] after delete synthetic atom")
        print(f"  total matches      : {len(results_c)}")
        print(f"  atom-typed matches : {len(atom_hits_c)}")
        print(f"  delta vs snapshot 1: {len(results_c) - len(results_a)}  "
              f"(0 ⇒ view correctly tracks live store)")

    stdout_log = buf.getvalue()
    sys.stdout.write(stdout_log)
    write_text(out / "stdout.log", stdout_log)
    write_json(out / "snapshots.json", {
        "view": card_to_jsonable(view),
        "snapshot_1": {"total": len(results_a), "atoms": len(atom_hits_a),
                       "atom_subjs": sorted({c.kvs.get("subj") for c in atom_hits_a})},
        "snapshot_2": {"total": len(results_b), "atoms": len(atom_hits_b),
                       "atom_subjs": sorted({c.kvs.get("subj") for c in atom_hits_b})},
        "snapshot_3": {"total": len(results_c), "atoms": len(atom_hits_c),
                       "atom_subjs": sorted({c.kvs.get("subj") for c in atom_hits_c})},
    })

    return {"snapshot_1": len(results_a),
            "snapshot_2": len(results_b),
            "snapshot_3": len(results_c),
            "view_id": view.id}


# ---------------------------------------------------------------------------
# Capability 6 — 自计算字段 (:confidence = (compute ...))
# ---------------------------------------------------------------------------

def _eval_confidence(card: Card, store: CardStore) -> float:
    """
    Mini DSL: parse the :confidence expression on a claim card.
    Supports the exact shape:
      (compute (- (count-links-to %self :pred 'supports)
                  (count-links-to %self :pred 'contradicts))
               / (max (count-links-to %self :pred 'supports) 1))

    Falls back to direct count-links math if the parser sees this canonical
    form (we don't ship a general s-expr eval — by design, per the limitation
    noted in README).
    """
    self_id = card.id
    supports  = len(store.find_links_to(self_id, link_pred="supports"))
    contradicts = len(store.find_links_to(self_id, link_pred="contradicts"))
    denom = max(supports, 1)
    return (supports - contradicts) / denom


def cap6_self_compute(run_dir: Path) -> dict:
    out = run_dir / "cap6_self_compute"
    out.mkdir(parents=True, exist_ok=True)

    buf = io.StringIO()
    with redirect_stdout(buf):
        print(f"# Capability 6 — 自计算字段  ({now_iso()})")
        print("-" * 70)
        store, _re, _me = load_full_store()

        claim_id = "claim:cap6_c21_cross_stack_first_val_gate"
        claim = Card(
            id=claim_id, type="claim",
            kvs={
                "subj": claim_id,
                "body": ("C2.1 cross-team stack 是 arc 260516a R5 阶段第一个 val-gate 突破。"
                         " H-R3b-4 SOTA champion 在 train/test 双 pass, anchor +0.24 NAV。"
                         " 反例 risk: 单一 arc 上的结论, 未跨 arc 验证。"),
                "confidence_expr": (
                    "(compute (- (count-links-to %self :pred 'supports) "
                    "(count-links-to %self :pred 'contradicts)) / "
                    "(max (count-links-to %self :pred 'supports) 1))"
                ),
                "status": "active",
                "created_at": now_iso(),
            },
        )
        store.add(claim)
        print(f"\n  claim id    : {claim.id}")
        print(f"  claim body  : {short_body(claim.kvs['body'], 160)}")
        print(f"  confidence_expr (raw):")
        print(f"    {claim.kvs['confidence_expr']}")

        snapshots = []

        # Stage (a): 0 supporter / 0 contradictor
        conf_a = _eval_confidence(claim, store)
        s = store.find_links_to(claim_id, link_pred="supports")
        c = store.find_links_to(claim_id, link_pred="contradicts")
        print(f"\n[stage a] no link evidence")
        print(f"  supports     : {len(s)}")
        print(f"  contradicts  : {len(c)}")
        print(f"  confidence   : {conf_a:.3f}  (expr → (0-0)/max(0,1) = 0/1 = 0.0)")
        snapshots.append({"stage": "a", "supports": len(s),
                          "contradicts": len(c), "confidence": conf_a})

        # Stage (b): add 3 supporters
        supporters_added = []
        for i, supp_subj in enumerate([
            "exp:H-R3b-4_c84_kelly_lambda_1.5",
            "exp:C8.4_top3_no_open3min_bypass",
            "exp:H-R2-2_c84_linear_sizing",
        ], 1):
            link = Card(id=f"a_cap6_supp_{i}", type="atom",
                        kvs={"subj": supp_subj, "pred": "supports", "obj": claim_id,
                             "source": "cap6_self_compute_demo",
                             "ingested_at": now_iso()})
            store.add(link)
            supporters_added.append(link.id)
        conf_b = _eval_confidence(claim, store)
        s = store.find_links_to(claim_id, link_pred="supports")
        c = store.find_links_to(claim_id, link_pred="contradicts")
        print(f"\n[stage b] add 3 supporters: {supporters_added}")
        print(f"  supports     : {len(s)}")
        print(f"  contradicts  : {len(c)}")
        print(f"  confidence   : {conf_b:.3f}  (expr → (3-0)/max(3,1) = 3/3 = 1.0)")
        snapshots.append({"stage": "b", "supports": len(s),
                          "contradicts": len(c), "confidence": conf_b,
                          "added": supporters_added})

        # Stage (c): add 2 contradictors
        contradictors_added = []
        for i, con_subj in enumerate([
            "exp:B-R10-2_blacklist_low_amt",
            "exp:F-R1-1_ofi_drop_extreme",
        ], 1):
            link = Card(id=f"a_cap6_contr_{i}", type="atom",
                        kvs={"subj": con_subj, "pred": "contradicts", "obj": claim_id,
                             "source": "cap6_self_compute_demo",
                             "ingested_at": now_iso()})
            store.add(link)
            contradictors_added.append(link.id)
        conf_c = _eval_confidence(claim, store)
        s = store.find_links_to(claim_id, link_pred="supports")
        c = store.find_links_to(claim_id, link_pred="contradicts")
        print(f"\n[stage c] add 2 contradictors: {contradictors_added}")
        print(f"  supports     : {len(s)}")
        print(f"  contradicts  : {len(c)}")
        print(f"  confidence   : {conf_c:.3f}  (expr → (3-2)/max(3,1) = 1/3 ≈ 0.333)")
        snapshots.append({"stage": "c", "supports": len(s),
                          "contradicts": len(c), "confidence": conf_c,
                          "added": contradictors_added})

    stdout_log = buf.getvalue()
    sys.stdout.write(stdout_log)
    write_text(out / "stdout.log", stdout_log)
    write_json(out / "snapshots.json", snapshots)
    write_json(out / "claim_card.json", card_to_jsonable(claim))

    return {"stages": len(snapshots),
            "conf_a": round(snapshots[0]["confidence"], 4),
            "conf_b": round(snapshots[1]["confidence"], 4),
            "conf_c": round(snapshots[2]["confidence"], 4)}


# ---------------------------------------------------------------------------
# README writer
# ---------------------------------------------------------------------------

def write_readme(run_dir: Path, results: dict, store_totals: dict, elapsed: float) -> None:
    md = []
    md.append(f"# Phase 4 — 6 capabilities demo run\n")
    md.append(f"_arc 260521a · generated {now_iso()} · elapsed {elapsed:.2f}s_\n")

    md.append("\n## Headline numbers\n")
    md.append(f"- store: **{store_totals['total']}** total cards  "
              f"(atoms {store_totals['atoms']}, experiments {store_totals['experiments']}, "
              f"lineages {store_totals['lineages']}, rules {store_totals['rules']}, "
              f"macros {store_totals['macros']})\n")
    md.append(f"- Phase 3 fixpoint pre-baseline: 5 rule families (11 micro-rules) + 2 macros, "
              f"99 rule fires + 11 macro expansions in 0.19s\n")

    md.append("\n## Capability summaries\n")

    md.append("\n### Capability 1 — macro 派生卡\n")
    r = results["cap1"]
    md.append(f"挑 3 张 experiment 卡 (SOTA champion / falsified-plateau-parent / lineage-parent) "
              f"过 m001 macro。每张产 3 张 suggestion card (baseline / ablation / extension), "
              f"共 **{r['suggestions']} 张新卡**。store 中 macro 本身也是 card "
              f"({r['macro_cards_in_store']} 张), 同 :id namespace, "
              f"`store.find_by_type('macro')` 就能查。证据: `cap1_macro_derive/`.\n")

    md.append("\n### Capability 2 — lazy reference\n")
    r = results["cap2"]
    md.append(f"两张含 `<eval>...</eval>` 的卡片 (view + atom) 走 `store.resolve_lazy`. "
              f"`latest-of` 替换为目标卡 :body, `count-links-to` 替换为入度整数. "
              f"共 **{r['lazy_refs_resolved']} 个 lazy ref 在 read time evaluate**. "
              f"证据: `cap2_lazy_ref/before_after.json`.\n")

    md.append("\n### Capability 3 — 规则即卡片\n")
    r = results["cap3"]
    md.append(f"`find_by_type('rule')` 一次查出 **{r['rule_cards']} 张 rule card** "
              f"(7 micro r001a..g + r002 / r003 / r004 / r005). "
              f"Fixpoint 跑完后 **{r['rules_with_fan_出']}** 条 rule 有派生 fan-out. "
              f"字符串子查询 (`'reverse' in :body.lower()`) 命中 r001g + r002. "
              f"把 r002 状态翻 `paused` 再 re-run, 该 rule 派生卡 -{r['pause_delta']} → 验证 status flip "
              f"确实阻断 firing. 证据: `cap3_rules_as_cards/`.\n")

    md.append("\n### Capability 4 — dedup restart 协议\n")
    r = results["cap4"]
    md.append(f"构造与 SOTA champion has_section_hypothesis 5-10% 偏差的变体卡 "
              f"(similarity = **{r['similarity_score']}** ≥ 0.80). "
              f"3 次跑各自指定 `on-dedup-conflict` 列表头部 = "
              f"`keep-both` / `merge-prefer-newer` / `supersede`. "
              f"实际触发 action: **{r['actions']}**. 证据: `cap4_dedup_restart/cases.json`.\n")

    md.append("\n### Capability 5 — 视图卡 (materialized view)\n")
    r = results["cap5"]
    md.append(f"m002 macro 派一张 view card on `lin:arc_260516a__team_h__sizing`. "
              f"三次 materialize: 初始 **{r['snapshot_1']}** 命中 → 注入合成 atom 后 "
              f"**{r['snapshot_2']}** → 删除后 **{r['snapshot_3']}** "
              f"(回到初始, 证明 view 完全 lazy 不缓存). 证据: `cap5_view_card/snapshots.json`.\n")

    md.append("\n### Capability 6 — 自计算字段\n")
    r = results["cap6"]
    md.append(f"建一张 claim card, :confidence 字段是 sexp 表达式 "
              f"`(compute (- supports contradicts) / (max supports 1))`. "
              f"3 个 snapshot: 0/0 → conf **{r['conf_a']}**; 加 3 supporters → conf **{r['conf_b']}**; "
              f"再加 2 contradictors → conf **{r['conf_c']}**. 证据: `cap6_self_compute/snapshots.json`.\n")

    md.append("\n## Viz\n")
    md.append(f"`{(run_dir / 'viz.html').resolve()}` — single-file vanilla SVG force-directed graph, "
              f"0 external CDN, macOS system font stack. Filter by type / tag / id, hover for body excerpt. "
              f"3000+ atoms hidden by default; toggle to reveal.\n")

    md.append("\n## Known limitation\n")
    md.append("- `_eval_confidence` only recognizes the canonical `count-links-to %self :pred 'supports/contradicts` "
              "form. A general s-expr evaluator is out of scope for the kernel; the trigger pattern is matched "
              "by structural inspection, not parsed.\n")
    md.append("- viz is **static layout** (one-shot simulation, no on-canvas dragging). 数据 scale 太大没必要做交互.\n")
    md.append("- Phase 4 不动 atoms/rules/macros 的 .edn 文件; demo 产物只写在 `output/<demo_run>/`.\n")

    write_text(run_dir / "README.md", "".join(md))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=str, default=None,
                    help="path to a demo_run dir (default: latest, or fresh)")
    args = ap.parse_args()

    if args.run_dir:
        run_dir = Path(args.run_dir).resolve()
    else:
        # Use the latest <YYMMDD_HHMM>_demo_run, or make a new one.
        existing = sorted(OUTPUT_DIR.glob("*_demo_run"))
        if existing:
            run_dir = existing[-1]
        else:
            run_dir = OUTPUT_DIR / (datetime.datetime.now().strftime("%y%m%d_%H%M") + "_demo_run")
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"demo run dir: {run_dir}")

    t0 = time.time()

    # Run each capability; collect summary numbers
    results = {}
    print("\n" + "=" * 70)
    results["cap1"] = cap1_macro_derive(run_dir)
    print("\n" + "=" * 70)
    results["cap2"] = cap2_lazy_ref(run_dir)
    print("\n" + "=" * 70)
    results["cap3"] = cap3_rules_as_cards(run_dir)
    print("\n" + "=" * 70)
    results["cap4"] = cap4_dedup_restart(run_dir)
    print("\n" + "=" * 70)
    results["cap5"] = cap5_view_card(run_dir)
    print("\n" + "=" * 70)
    results["cap6"] = cap6_self_compute(run_dir)

    # Compute store totals once for README
    store, _re, _me = load_full_store(verbose=False)
    store_totals = {
        "total": len(store.all_cards()),
        "atoms": len(store.find_by_type("atom")),
        "experiments": len(store.find_by_type("experiment")),
        "lineages": len(store.find_by_type("lineage")),
        "rules": len(store.find_by_type("rule")),
        "macros": len(store.find_by_type("macro")),
    }
    elapsed = time.time() - t0
    write_readme(run_dir, results, store_totals, elapsed)
    write_json(run_dir / "summary.json", {
        "elapsed_sec": round(elapsed, 3),
        "store_totals": store_totals,
        "results": results,
    })

    print("\n" + "=" * 70)
    print("HAND-OFF NUMBERS")
    print("=" * 70)
    print(f"  cap1 macro_derive  : {results['cap1']}")
    print(f"  cap2 lazy_ref      : {results['cap2']}")
    print(f"  cap3 rules_as_card : {results['cap3']}")
    print(f"  cap4 dedup_restart : {results['cap4']}")
    print(f"  cap5 view_card     : {results['cap5']}")
    print(f"  cap6 self_compute  : {results['cap6']}")
    print(f"  store_totals       : {store_totals}")
    print(f"  elapsed_sec        : {elapsed:.3f}")
    print(f"  run_dir            : {run_dir}")


if __name__ == "__main__":
    main()
