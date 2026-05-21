"""
smoke_test.py — end-to-end kernel smoke test.

Exercises all 5 modules in sequence:
  1. Create empty store, add 5 atom cards
  2. Register 1 rule, run to fixpoint, assert derived count
  3. Register 1 macro, expand it, assert generated cards
  4. Create 1 view card, materialize it
  5. Create 2 near-dupe cards (80%+), run dedup, verify restart fires
  6. dump_edn → load_edn → assert equivalence (roundtrip)

Expected stdout: printed summary + "SMOKE TEST PASSED"
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from wiki.lib.cardstore import Card, CardStore
from wiki.lib.macro import MacroEngine
from wiki.lib.rules import RuleEngine
from wiki.lib.view import materialize, resolve_lazy
from wiki.lib.dedup import similarity, find_near_dupes, resolve_conflict


def main():
    print("=" * 60)
    print("SMOKE TEST — wiki kernel phase 1")
    print("=" * 60)

    # -------------------------------------------------------------------
    # Step 1: Create store with 5 atom cards
    # -------------------------------------------------------------------
    print("\n[1] Create store + 5 atom cards")
    store = CardStore()

    atoms = [
        Card(id="atom:p1", type="atom", kvs={
            "subj": "doc:paper_3dgs", "pred": "has_topic", "obj": "topic:rendering",
            "body": "3D Gaussian splatting achieves real-time novel view synthesis.",
        }),
        Card(id="atom:p2", type="atom", kvs={
            "subj": "arc:260508b", "pred": "introduces_doc", "obj": "doc:paper_3dgs",
            "body": "Arc 260508b introduced the 3DGS paper.",
        }),
        Card(id="atom:p3", type="atom", kvs={
            "subj": "doc:paper_nerf", "pred": "has_topic", "obj": "topic:rendering",
            "body": "NeRF represents scenes as continuous volumetric functions.",
        }),
        Card(id="atom:p4", type="atom", kvs={
            "subj": "arc:260508b", "pred": "introduces_doc", "obj": "doc:paper_nerf",
            "body": "Arc 260508b also introduced the NeRF paper.",
        }),
        Card(id="atom:p5", type="atom", kvs={
            "subj": "doc:paper_3dgs", "pred": "competes_with", "obj": "doc:paper_nerf",
            "body": "3DGS explicitly competes with NeRF on rendering speed.",
        }),
    ]
    for a in atoms:
        store.add(a)

    atom_count = len(store.find_by_type("atom"))
    print(f"  atom count = {atom_count}")
    assert atom_count == 5, f"Expected 5 atoms, got {atom_count}"

    # -------------------------------------------------------------------
    # Step 2: Register 1 rule, run to fixpoint
    # -------------------------------------------------------------------
    print("\n[2] Rule engine — introduces_doc reverse + topic sharing")
    engine = RuleEngine()

    # r001: ?arc introduces_doc ?doc  →  ?doc introduced_by ?arc
    r001 = Card(id="rule:r001_reverse", type="rule", kvs={
        "when": [["?arc", "introduces_doc", "?doc"]],
        "then": [["?doc", "introduced_by", "?arc"]],
    })
    engine.register(r001)
    store.add(r001)

    all_derived = engine.run_to_fixpoint(store, max_iters=10)
    derived_count = len(store.find_by_type("derived"))
    print(f"  derived count after fixpoint = {derived_count}")
    assert derived_count >= 2, f"Expected >= 2 derived cards, got {derived_count}"

    # Verify specific derived fact
    derived_facts = store.find_links_from("doc:paper_3dgs", link_pred="introduced_by")
    assert len(derived_facts) >= 1, "Missing derived introduced_by for paper_3dgs"
    print(f"  doc:paper_3dgs introduced_by: {[c.kvs['obj'] for c in derived_facts]}")

    # -------------------------------------------------------------------
    # Step 3: Macro expansion
    # -------------------------------------------------------------------
    print("\n[3] Macro engine — paper → 3 experiment suggestions")
    macro_engine = MacroEngine()

    macro = Card(
        id="macro:paper_to_exps",
        type="macro",
        kvs={
            "name": "paper-to-experiments",
            "params": ["?paper-id", "?topic"],
            "body": [
                {
                    "type": "derived",
                    "subj": "?paper-id",
                    "pred": "suggests_experiment",
                    "obj": "exp:baseline_?paper-id",
                    "body": "Replicate baseline from ?paper-id on ?topic",
                },
                {
                    "type": "derived",
                    "subj": "?paper-id",
                    "pred": "suggests_experiment",
                    "obj": "exp:ablation_?paper-id",
                    "body": "Ablation: vary hyperparams from ?paper-id on ?topic",
                },
                {
                    "type": "derived",
                    "subj": "?paper-id",
                    "pred": "suggests_experiment",
                    "obj": "exp:extension_?paper-id",
                    "body": "Extend ?paper-id to domain beyond ?topic",
                },
            ],
        },
    )
    store.add(macro)
    macro_engine.register(macro)

    new_exp_cards = macro_engine.expand(
        "paper-to-experiments",
        {"paper-id": "doc:paper_3dgs", "topic": "rendering"},
        source_card_id="atom:p1",
    )
    for c in new_exp_cards:
        store.add(c)

    macro_derived = [c for c in store.find_by_type("derived")
                     if c.kvs.get("pred") == "suggests_experiment"]
    print(f"  macro expanded {len(new_exp_cards)} new suggestion cards")
    assert len(new_exp_cards) == 3, f"Expected 3 macro cards, got {len(new_exp_cards)}"
    for c in new_exp_cards:
        assert "atom:p1" in c.kvs["parents"]
        assert "macro:paper_to_exps" in c.kvs["parents"]
    print(f"  suggestion objs: {[c.kvs['obj'] for c in new_exp_cards]}")

    # -------------------------------------------------------------------
    # Step 4: View card — materialize
    # -------------------------------------------------------------------
    print("\n[4] View card — materialize all 'suggests_experiment' derived cards")
    view = Card(
        id="view:experiment_suggestions",
        type="view",
        kvs={
            "query": {
                "filter_type": "derived",
                "filter_pred": "suggests_experiment",
            }
        },
    )
    store.add(view)
    materialized = materialize(view, store)
    view_count = len(materialized)
    print(f"  view materialize count = {view_count}")
    assert view_count == 3, f"Expected 3 materialized cards, got {view_count}"

    # Also test lazy ref
    lazy_card = Card(
        id="atom:lazy_demo",
        type="atom",
        kvs={"body": "Summary ref: <eval>latest-of atom:p1</eval>"},
    )
    store.add(lazy_card)
    resolved = resolve_lazy(lazy_card, store)
    assert "<eval>" not in resolved.kvs["body"], "Lazy ref not resolved"
    print(f"  lazy ref resolved: {resolved.kvs['body'][:60]!r}...")

    # -------------------------------------------------------------------
    # Step 5: Dedup — near-duplicate cards + restart protocol
    # -------------------------------------------------------------------
    print("\n[5] Dedup — near-duplicate restart")
    # Two nearly-identical cards (intentional for dedup demo)
    dup_a = Card(id="dup:a", type="atom", kvs={
        "subj": "doc:paper_3dgs", "pred": "claims", "obj": "result:realtime",
        "body": "3D Gaussian splatting renders at 100+ FPS in real-time on a consumer GPU.",
        "on-dedup-conflict": ["keep-both"],
    })
    dup_b = Card(id="dup:b", type="atom", kvs={
        "subj": "doc:paper_3dgs", "pred": "claims", "obj": "result:realtime",
        "body": "3D Gaussian splatting renders at 100+ FPS on a consumer GPU in real-time.",
        "on-dedup-conflict": ["keep-both"],
    })
    store.add(dup_a)
    store.add(dup_b)

    sim_score = similarity(dup_a, dup_b)
    print(f"  similarity(dup_a, dup_b) = {sim_score:.3f}")
    assert sim_score >= 0.80, f"Expected >= 0.80 similarity, got {sim_score:.3f}"

    dupes = find_near_dupes(dup_a, store, threshold=0.80)
    dupe_ids = [d.id for d, _ in dupes]
    print(f"  near dupes of dup:a (threshold=0.80): {[(d.id, f'{s:.3f}') for d, s in dupes[:3]]}")
    assert "dup:b" in dupe_ids, "dup:b not found as near dupe"

    action = resolve_conflict(dup_a, [(dup_b, sim_score)], store)
    print(f"  restart action = {action!r}")
    assert action == "keep-both"

    # Both cards should have see-also
    ra = store.get("dup:a")
    rb = store.get("dup:b")
    assert "dup:b" in (ra.kvs.get("see-also") or [])
    assert "dup:a" in (rb.kvs.get("see-also") or [])
    print("  see-also links verified on both dup cards")

    # -------------------------------------------------------------------
    # Step 6: EDN roundtrip
    # -------------------------------------------------------------------
    print("\n[6] EDN dump → load → equivalence check")
    with tempfile.NamedTemporaryFile(suffix=".edn", delete=False, mode="w") as f:
        edn_path = f.name
    try:
        store.dump_edn(edn_path)
        store2 = CardStore()
        store2.load_edn(edn_path)

        original_ids = {c.id for c in store.all_cards()}
        reloaded_ids = {c.id for c in store2.all_cards()}
        missing = original_ids - reloaded_ids
        assert not missing, f"Cards missing after reload: {missing}"

        # Spot-check atom:p1
        p1 = store2.get("atom:p1")
        assert p1 is not None
        assert p1.type == "atom"
        assert p1.kvs.get("pred") == "has_topic"
        assert p1.kvs.get("body") == "3D Gaussian splatting achieves real-time novel view synthesis."

        print(f"  {len(original_ids)} cards dumped → {len(reloaded_ids)} cards reloaded (all match)")
    finally:
        os.unlink(edn_path)

    # -------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------
    print("\n" + "=" * 60)
    total_cards = len(store.all_cards())
    print(f"SMOKE TEST SUMMARY:")
    print(f"  atom count              = {len(store.find_by_type('atom'))}")
    print(f"  rule count              = {len(store.find_by_type('rule'))}")
    print(f"  macro count             = {len(store.find_by_type('macro'))}")
    print(f"  derived count           = {len(store.find_by_type('derived'))}")
    print(f"  view count              = {len(store.find_by_type('view'))}")
    print(f"  total cards in store    = {total_cards}")
    print(f"  view materialize count  = {view_count}")
    print(f"  dedup sim score         = {sim_score:.3f}")
    print(f"  dedup restart action    = keep-both")
    print("=" * 60)
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
