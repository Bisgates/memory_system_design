"""Tests for cardstore.py — 6 tests covering all spec requirements."""
import tempfile, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from wiki.lib.cardstore import Card, CardStore


def test_add_get():
    store = CardStore()
    c = Card(id="a1", type="atom", kvs={"subj": "doc:foo", "pred": "has_topic", "obj": "topic:ml"})
    store.add(c)
    got = store.get("a1")
    assert got is c
    assert got.kvs["pred"] == "has_topic"
    print("PASS test_add_get")


def test_update():
    store = CardStore()
    c = Card(id="b1", type="atom", kvs={"status": "active"})
    store.add(c)
    store.update("b1", status="done", confidence=0.9)
    got = store.get("b1")
    assert got.kvs["status"] == "done"
    assert got.kvs["confidence"] == 0.9
    print("PASS test_update")


def test_query():
    store = CardStore()
    store.add(Card(id="c1", type="atom", kvs={"pred": "derived_from"}))
    store.add(Card(id="c2", type="atom", kvs={"pred": "has_topic"}))
    store.add(Card(id="c3", type="rule", kvs={"pred": "derived_from"}))
    results = store.query(lambda c: c.type == "atom" and c.kvs.get("pred") == "derived_from")
    assert len(results) == 1
    assert results[0].id == "c1"
    print("PASS test_query")


def test_versioning():
    store = CardStore()
    c = Card(id="d1", type="atom", kvs={"body": "v1"})
    store.add(c)
    store.update("d1", body="v2")
    store.update("d1", body="v3")
    got = store.get("d1")
    assert got.kvs["body"] == "v3"
    assert len(got.history) == 2
    assert got.history[0][1]["body"] == "v1"
    assert got.history[1][1]["body"] == "v2"
    print("PASS test_versioning")


def test_find_links():
    store = CardStore()
    store.add(Card(id="e1", type="atom", kvs={"subj": "doc:A", "pred": "cites", "obj": "doc:B"}))
    store.add(Card(id="e2", type="atom", kvs={"subj": "doc:C", "pred": "cites", "obj": "doc:B"}))
    store.add(Card(id="e3", type="atom", kvs={"subj": "doc:A", "pred": "uses", "obj": "doc:C"}))
    to_B = store.find_links_to("doc:B")
    assert len(to_B) == 2
    from_A = store.find_links_from("doc:A")
    assert len(from_A) == 2
    from_A_cites = store.find_links_from("doc:A", link_pred="cites")
    assert len(from_A_cites) == 1
    print("PASS test_find_links")


def test_edn_roundtrip():
    store = CardStore()
    store.add(Card(id="f1", type="atom", kvs={"subj": "arc:260521a", "pred": "has_topic", "obj": "topic:sexp",
                                               "confidence": 0.95, "body": "hello world"}))
    store.add(Card(id="f2", type="rule", kvs={"name": "r001", "when": ["?A", "pred", "?B"], "then": ["?B", "inv", "?A"]}))
    with tempfile.NamedTemporaryFile(suffix=".edn", delete=False, mode="w") as f:
        path = f.name
    try:
        store.dump_edn(path)
        store2 = CardStore()
        store2.load_edn(path)
        got_f1 = store2.get("f1")
        assert got_f1 is not None, "f1 missing after reload"
        assert got_f1.type == "atom"
        assert got_f1.kvs.get("pred") == "has_topic"
        assert got_f1.kvs.get("body") == "hello world"
        got_f2 = store2.get("f2")
        assert got_f2 is not None, "f2 missing after reload"
        assert got_f2.type == "rule"
    finally:
        os.unlink(path)
    print("PASS test_edn_roundtrip")


if __name__ == "__main__":
    test_add_get()
    test_update()
    test_query()
    test_versioning()
    test_find_links()
    test_edn_roundtrip()
    print("ALL cardstore tests PASSED")
