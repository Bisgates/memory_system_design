"""Tests for rules.py — 2 tests: single rule fire / multi-rule fixpoint."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from wiki.lib.cardstore import Card, CardStore
from wiki.lib.rules import RuleEngine


def make_store_with_atoms():
    """Helper: store with 3 arc→doc intro atoms."""
    store = CardStore()
    store.add(Card(id="a1", type="atom", kvs={"subj": "arc:260508b", "pred": "introduces_doc", "obj": "doc:paper_A"}))
    store.add(Card(id="a2", type="atom", kvs={"subj": "arc:260509c", "pred": "introduces_doc", "obj": "doc:paper_B"}))
    store.add(Card(id="a3", type="atom", kvs={"subj": "arc:260508b", "pred": "introduces_doc", "obj": "doc:paper_C"}))
    return store


def test_single_rule_fire():
    """Rule r001: ?doc introduced_by ?arc ← ?arc introduces_doc ?doc."""
    store = make_store_with_atoms()
    engine = RuleEngine()
    rule = Card(
        id="rule:r001_introduces_reverse",
        type="rule",
        kvs={
            "when": [["?arc", "introduces_doc", "?doc"]],
            "then": [["?doc", "introduced_by", "?arc"]],
        },
    )
    engine.register(rule)
    new_cards = engine.run_once(store)
    assert len(new_cards) == 3, f"Expected 3 derived cards, got {len(new_cards)}"
    preds = {c.kvs["pred"] for c in new_cards}
    assert "introduced_by" in preds
    # Verify parents set
    for c in new_cards:
        assert c.kvs.get("derived_from") == "rule:r001_introduces_reverse"
        assert len(c.kvs.get("parents", [])) >= 1
    # Second run: dedup — no new cards
    second_run = engine.run_once(store)
    assert second_run == [], f"Dedup failed: got {second_run}"
    print(f"  r001 fired {len(new_cards)} times, dedup OK")
    print("PASS test_single_rule_fire")


def test_multi_rule_fixpoint():
    """
    Two chain rules:
      r_intro: ?doc introduced_by ?arc ← ?arc introduces_doc ?doc
      r_cite:  ?arc cites_paper ?doc   ← ?doc introduced_by ?arc   (inverse chain)
    Fixpoint should fire both in order until stable.
    """
    store = make_store_with_atoms()
    engine = RuleEngine()
    # Rule 1: reverse
    r1 = Card(id="rule:r001", type="rule", kvs={
        "when": [["?arc", "introduces_doc", "?doc"]],
        "then": [["?doc", "introduced_by", "?arc"]],
    })
    # Rule 2: chain off derived facts
    r2 = Card(id="rule:r002", type="rule", kvs={
        "when": [["?doc", "introduced_by", "?arc"]],
        "then": [["?arc", "cites_paper", "?doc"]],
    })
    engine.register(r1)
    engine.register(r2)
    all_new = engine.run_to_fixpoint(store, max_iters=10)
    preds = {c.kvs["pred"] for c in all_new}
    # Both rules should fire
    assert "introduced_by" in preds, "r001 never fired"
    assert "cites_paper" in preds, "r002 never fired (chain broke)"
    # No duplicate (subj, pred, obj) in store
    triples = set()
    dupes = 0
    for c in store.all_cards():
        s, p, o = c.kvs.get("subj"), c.kvs.get("pred"), c.kvs.get("obj")
        if s and p and o:
            key = (s, p, o)
            if key in triples:
                dupes += 1
            triples.add(key)
    assert dupes == 0, f"Found {dupes} duplicate (subj,pred,obj) triples"
    print(f"  Fixpoint: {len(all_new)} total derived cards, preds={preds}")
    print("PASS test_multi_rule_fixpoint")


if __name__ == "__main__":
    test_single_rule_fire()
    test_multi_rule_fixpoint()
    print("ALL rules tests PASSED")
