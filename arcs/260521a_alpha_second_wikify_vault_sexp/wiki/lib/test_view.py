"""Tests for view.py — 2 tests: view materialize / lazy ref resolve."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from wiki.lib.cardstore import Card, CardStore
from wiki.lib.view import materialize, resolve_lazy


def test_view_materialize():
    """View card with query filter_pred='falsifies' should return only matching atoms."""
    store = CardStore()
    store.add(Card(id="a1", type="atom", kvs={"subj": "doc:A", "pred": "falsifies", "obj": "claim:X"}))
    store.add(Card(id="a2", type="atom", kvs={"subj": "doc:B", "pred": "supports", "obj": "claim:X"}))
    store.add(Card(id="a3", type="derived", kvs={"subj": "doc:C", "pred": "falsifies", "obj": "claim:Y"}))
    store.add(Card(id="a4", type="rule", kvs={"name": "r001"}))

    # View card: all atoms with pred=falsifies
    view = Card(
        id="view:falsifies_atoms",
        type="view",
        kvs={
            "query": {
                "filter_type": "atom",
                "filter_pred": "falsifies",
            }
        },
    )
    results = materialize(view, store)
    ids = {c.id for c in results}
    assert "a1" in ids, "a1 (atom, falsifies) should be in results"
    assert "a2" not in ids, "a2 (atom, supports) should not be in results"
    assert "a3" not in ids, "a3 (derived) should not be in results (filter_type=atom)"
    assert "a4" not in ids, "a4 (rule) should not be in results"
    print(f"  View materialized {len(results)} card(s): {ids}")

    # View with wildcard
    view_all_falsifies = Card(
        id="view:all_falsifies",
        type="view",
        kvs={"query": {"filter_type": "?_", "filter_pred": "falsifies"}},
    )
    all_falsifies = materialize(view_all_falsifies, store)
    all_ids = {c.id for c in all_falsifies}
    assert "a1" in all_ids
    assert "a3" in all_ids
    assert len(all_falsifies) == 2
    print(f"  Wildcard view: {all_ids}")
    print("PASS test_view_materialize")


def test_lazy_ref_resolve():
    """Card with <eval>latest-of X</eval> in :body resolves to target card's :body."""
    store = CardStore()
    # Referenced card
    store.add(Card(id="target_card", type="atom", kvs={"body": "This is the resolved body content."}))
    # Card with lazy reference
    lazy_card = Card(
        id="lazy_card",
        type="atom",
        kvs={"body": "Preamble: <eval>latest-of target_card</eval> — end."},
    )
    store.add(lazy_card)

    resolved = resolve_lazy(lazy_card, store)
    expected_body = "Preamble: This is the resolved body content. — end."
    assert resolved.kvs["body"] == expected_body, f"Got: {resolved.kvs['body']!r}"
    # Original card should be untouched
    original = store.get("lazy_card")
    assert "<eval>" in original.kvs["body"], "Original should still have <eval> tag"
    print(f"  Resolved body: {resolved.kvs['body']!r}")
    print("PASS test_lazy_ref_resolve")


if __name__ == "__main__":
    test_view_materialize()
    test_lazy_ref_resolve()
    print("ALL view tests PASSED")
