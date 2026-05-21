"""Tests for macro.py — 3 tests: register / expand paper→3 suggestions / parents chain."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from wiki.lib.cardstore import Card
from wiki.lib.macro import MacroEngine


# Macro definition: paper → 3 experiment-suggestion cards
PAPER_TO_SUGGESTIONS_MACRO = Card(
    id="macro:paper_to_experiments",
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
                "body": "Ablation study: vary key hyperparams from ?paper-id",
            },
            {
                "type": "derived",
                "subj": "?paper-id",
                "pred": "suggests_experiment",
                "obj": "exp:extension_?paper-id",
                "body": "Extend ?paper-id to new domain beyond ?topic",
            },
        ],
    },
)


def test_register():
    engine = MacroEngine()
    engine.register(PAPER_TO_SUGGESTIONS_MACRO)
    assert "paper-to-experiments" in engine._macros
    print("PASS test_register")


def test_expand_paper_to_3_suggestions():
    engine = MacroEngine()
    engine.register(PAPER_TO_SUGGESTIONS_MACRO)

    source_card_id = "doc:paper_abc123"
    new_cards = engine.expand(
        "paper-to-experiments",
        {"paper-id": "doc:paper_abc123", "topic": "3dgs"},
        source_card_id,
    )
    assert len(new_cards) == 3, f"Expected 3 cards, got {len(new_cards)}"
    preds = {c.kvs["pred"] for c in new_cards}
    assert "suggests_experiment" in preds

    # Check that ?var substitution happened
    bodies = [c.kvs.get("body", "") for c in new_cards]
    for b in bodies:
        assert "?paper-id" not in b, f"Unsubstituted placeholder in: {b!r}"
        assert "doc:paper_abc123" in b or "3dgs" in b, f"Missing substituted value in: {b!r}"

    # Check obj substitution
    objs = {c.kvs.get("obj") for c in new_cards}
    assert "exp:baseline_doc:paper_abc123" in objs
    print(f"  Generated cards: {[c.kvs.get('obj') for c in new_cards]}")
    print("PASS test_expand_paper_to_3_suggestions")


def test_parents_chain():
    engine = MacroEngine()
    engine.register(PAPER_TO_SUGGESTIONS_MACRO)

    source_id = "doc:my_paper"
    cards = engine.expand("paper-to-experiments", {"paper-id": "doc:my_paper", "topic": "nerf"}, source_id)
    for c in cards:
        assert source_id in c.kvs["parents"], f"Missing source_id in parents: {c.kvs['parents']}"
        assert PAPER_TO_SUGGESTIONS_MACRO.id in c.kvs["parents"], f"Missing macro id in parents: {c.kvs['parents']}"
        assert c.kvs.get("derived_from") == PAPER_TO_SUGGESTIONS_MACRO.id
    print("PASS test_parents_chain")


if __name__ == "__main__":
    test_register()
    test_expand_paper_to_3_suggestions()
    test_parents_chain()
    print("ALL macro tests PASSED")
