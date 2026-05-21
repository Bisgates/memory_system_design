"""Tests for dedup.py — 2 tests: similarity / restart 'keep-both' protocol."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from wiki.lib.cardstore import Card, CardStore
from wiki.lib.dedup import similarity, find_near_dupes, resolve_conflict


def test_similarity():
    """High similarity for near-identical cards; low for dissimilar."""
    # Nearly identical bodies + same (subj, pred, obj)
    card_a = Card(id="sim_a", type="atom", kvs={
        "subj": "doc:foo", "pred": "cites", "obj": "doc:bar",
        "body": "The neural radiance field approach achieves state-of-the-art quality.",
    })
    card_b = Card(id="sim_b", type="atom", kvs={
        "subj": "doc:foo", "pred": "cites", "obj": "doc:bar",
        "body": "The neural radiance field approach achieves state-of-the-art rendering quality.",
    })
    score_high = similarity(card_a, card_b)
    print(f"  High sim score: {score_high:.3f}")
    assert score_high >= 0.80, f"Expected >= 0.80, got {score_high:.3f}"

    # Completely different bodies and structure
    card_c = Card(id="sim_c", type="atom", kvs={
        "subj": "arc:xyz", "pred": "falsifies", "obj": "claim:Q",
        "body": "This experiment shows the opposite effect entirely.",
    })
    score_low = similarity(card_a, card_c)
    print(f"  Low sim score: {score_low:.3f}")
    assert score_low < 0.50, f"Expected < 0.50, got {score_low:.3f}"

    # Same struct, empty body — structural only (0.4 * 1.0 = 0.4)
    card_d = Card(id="sim_d", type="atom", kvs={"subj": "doc:foo", "pred": "cites", "obj": "doc:bar"})
    card_e = Card(id="sim_e", type="atom", kvs={"subj": "doc:foo", "pred": "cites", "obj": "doc:bar"})
    score_struct = similarity(card_d, card_e)
    print(f"  Struct-only sim score: {score_struct:.3f}")
    assert abs(score_struct - 0.4) < 0.01, f"Expected ~0.40, got {score_struct:.3f}"

    print("PASS test_similarity")


def test_keep_both_restart():
    """Deliberately create 2 near-duplicate cards; verify keep-both restart fires."""
    store = CardStore()
    existing = Card(id="old_card", type="atom", kvs={
        "subj": "doc:paper1", "pred": "claims", "obj": "result:XYZ",
        "body": "Gaussian splatting achieves real-time rendering at 100+ FPS.",
    })
    store.add(existing)

    new_card = Card(id="new_card", type="atom", kvs={
        "subj": "doc:paper1", "pred": "claims", "obj": "result:XYZ",
        "body": "Gaussian splatting achieves real-time rendering at 110+ FPS.",
        "on-dedup-conflict": ["keep-both"],
    })
    store.add(new_card)

    dupes = find_near_dupes(new_card, store, threshold=0.80)
    print(f"  Near dupes found: {[(d.id, f'{s:.3f}') for d, s in dupes]}")
    assert len(dupes) >= 1, "Expected at least 1 near dupe"
    assert dupes[0][0].id == "old_card"

    action = resolve_conflict(new_card, dupes, store)
    assert action == "keep-both", f"Expected keep-both, got {action!r}"

    # Both cards should now have :see-also links
    reloaded_new = store.get("new_card")
    reloaded_old = store.get("old_card")
    assert "old_card" in (reloaded_new.kvs.get("see-also") or []), \
        f"new_card missing see-also to old_card: {reloaded_new.kvs}"
    assert "new_card" in (reloaded_old.kvs.get("see-also") or []), \
        f"old_card missing see-also to new_card: {reloaded_old.kvs}"

    print(f"  new_card see-also: {reloaded_new.kvs.get('see-also')}")
    print(f"  old_card see-also: {reloaded_old.kvs.get('see-also')}")
    print("PASS test_keep_both_restart")


if __name__ == "__main__":
    test_similarity()
    test_keep_both_restart()
    print("ALL dedup tests PASSED")
