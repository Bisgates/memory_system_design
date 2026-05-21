"""
verify_ingest.py — load all atoms .edn and run 5 sample queries.
Phase 2 step 8: prove the ingested store behaves like a real card store.

Usage:
  python -m wiki.scripts.verify_ingest --atoms wiki/cards/atoms/ \
      --log output/phase2_ingest_query.log
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARC_ROOT = HERE.parent.parent
sys.path.insert(0, str(ARC_ROOT))

from wiki.lib.cardstore import CardStore  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atoms", required=True, type=Path)
    ap.add_argument("--log", required=True, type=Path)
    args = ap.parse_args()

    store = CardStore()
    loaded_files = 0
    for path in sorted(args.atoms.glob("*.edn")):
        store.load_edn(str(path))
        loaded_files += 1

    all_cards = store.all_cards()
    lines: list[str] = []

    def emit(s: str) -> None:
        print(s)
        lines.append(s)

    emit("=" * 70)
    emit("PHASE 2 INGEST — QUERY VERIFICATION")
    emit("=" * 70)
    emit(f"loaded edn files : {loaded_files}")
    emit(f"total cards      : {len(all_cards)}")
    emit("")

    # ---------- Q1: count of experiment root cards ----------
    emit("Q1: find :type 'experiment' (should equal 53)")
    exps = store.find_by_type("experiment")
    emit(f"  count = {len(exps)}")
    assert len(exps) == 53, f"expected 53 experiments, got {len(exps)}"
    sample = [c.id for c in exps[:5]]
    emit(f"  sample subj ids: {sample}")
    emit("")

    # ---------- Q2: atoms tagged axis/blacklist ----------
    emit("Q2: find :pred 'has_tag :obj 'tag:axis/blacklist' (should be > 0)")
    blacklist_atoms = [c for c in all_cards
                       if c.kvs.get("pred") == "has_tag"
                       and c.kvs.get("obj") == "tag:axis/blacklist"]
    emit(f"  count = {len(blacklist_atoms)}")
    assert len(blacklist_atoms) > 0, "expected at least 1 blacklist axis tag"
    subjs = sorted({c.kvs["subj"] for c in blacklist_atoms})
    emit(f"  unique subjects (showing 10): {subjs[:10]}")
    emit("")

    # ---------- Q3: any falsifies links ----------
    emit("Q3: find :pred 'falsifies (typed link extracted)")
    falsifies = [c for c in all_cards if c.kvs.get("pred") == "falsifies"]
    emit(f"  count = {len(falsifies)}")
    if falsifies:
        for c in falsifies[:5]:
            emit(f"    ({c.kvs['subj']}) --falsifies--> ({c.kvs['obj']})")
    # falsifies might come up as a body-link or as a frontmatter field; we check both
    # We don't assert > 0 in the strict sense if no source contains it, but the test
    # vault should have at least one (we saw the warning catalog reference falsifies in mitigations).
    falsifies_lineage = [c for c in all_cards if c.kvs.get("pred") == "falsifies_lineage"]
    emit(f"  falsifies_lineage count = {len(falsifies_lineage)}")
    if falsifies_lineage:
        for c in falsifies_lineage[:5]:
            emit(f"    ({c.kvs['subj']}) --falsifies_lineage--> ({c.kvs['obj']})")
    assert (len(falsifies) + len(falsifies_lineage)) > 0, \
        "expected at least one falsifies/falsifies_lineage link in vault"
    emit("")

    # ---------- Q4: outgoing links from a specific exp ----------
    target = "exp:H-R3b-4_c84_kelly_lambda_1.5"
    emit(f"Q4: find_links_from({target!r}) — all outgoing predicates from SOTA champion")
    out_links = store.find_links_from(target)
    # group by pred
    by_pred: dict[str, list[str]] = {}
    for c in out_links:
        p = c.kvs.get("pred", "?")
        by_pred.setdefault(p, []).append(repr(c.kvs.get("obj")))
    emit(f"  outgoing card count = {len(out_links)}")
    for p in sorted(by_pred):
        objs = by_pred[p]
        if len(objs) > 4:
            sample_objs = objs[:4] + [f"...(+{len(objs)-4})"]
        else:
            sample_objs = objs
        emit(f"    :pred {p:<28s} ({len(objs)}x)  e.g. {sample_objs}")
    assert len(out_links) > 0, f"expected outgoing links from {target}"
    emit("")

    # ---------- Q5: reverse lookup on a tag value ----------
    tag_value = "tag:status/falsified"
    emit(f"Q5: reverse lookup — all cards with :pred 'has_tag :obj '{tag_value}'")
    refs = [c for c in all_cards if c.kvs.get("obj") == tag_value and c.kvs.get("pred") == "has_tag"]
    emit(f"  count = {len(refs)}")
    subjs = sorted({c.kvs["subj"] for c in refs})
    emit(f"  subjects ({len(subjs)} unique):")
    for s in subjs:
        emit(f"    - {s}")
    assert len(refs) > 0, "expected at least one status/falsified tag"
    emit("")

    # ---------- bonus stats ----------
    emit("=" * 70)
    emit("BONUS STATS")
    emit("=" * 70)
    type_counts: dict[str, int] = {}
    for c in all_cards:
        type_counts[c.type] = type_counts.get(c.type, 0) + 1
    for t in sorted(type_counts):
        emit(f"  cards of type {t!r:25s} {type_counts[t]}")
    pred_counts: dict[str, int] = {}
    for c in all_cards:
        if c.type == "atom":
            p = c.kvs.get("pred", "?")
            pred_counts[p] = pred_counts.get(p, 0) + 1
    emit("")
    emit("  top-20 predicates:")
    for p, n in sorted(pred_counts.items(), key=lambda x: -x[1])[:20]:
        emit(f"    {p:<35s} {n}")

    emit("")
    emit("VERIFICATION PASSED")

    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
