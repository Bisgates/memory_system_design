"""Synthetic smoke: 10 atoms × 3 rules; expect ≥ 1 chained derivation in ≤ 5 iterations."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tempfile

from utils.atom import Atom
from utils.engine import run
from utils.rule import Rule, load_rules_dir


SEED_ATOMS = [
    Atom("arc:001", "introduces_doc", "doc:foo.md", source="syn"),
    Atom("arc:001", "introduces_doc", "doc:bar.md", source="syn"),
    Atom("arc:002", "mentions_doc",   "doc:foo.md", source="syn"),
    Atom("arc:002", "mentions_doc",   "doc:bar.md", source="syn"),
    Atom("arc:003", "mentions_doc",   "doc:foo.md", source="syn"),
    Atom("arc:003", "mentions_arc",   "arc:001",    source="syn"),
    Atom("arc:002", "mentions_arc",   "arc:001",    source="syn"),
    Atom("doc:foo.md", "has_topic",   "topic:lidar", source="syn"),
    Atom("doc:bar.md", "has_topic",   "topic:lidar", source="syn"),
    Atom("doc:bar.md", "has_topic",   "topic:depth", source="syn"),
]

RULE_FILES = {
    "r001_reverse_doc.md": """---
id: r001_reverse_doc
when:
  - {subj: "?A", pred: introduces_doc, obj: "?D"}
then:
  - {subj: "?D", pred: introduced_by, obj: "?A"}
---
# r001 · introduces_doc -> introduced_by (reverse edge)
""",
    "r002_used_by_arc.md": """---
id: r002_used_by_arc
when:
  - {subj: "?A", pred: introduces_doc, obj: "?D"}
  - {subj: "?B", pred: mentions_doc,   obj: "?D"}
constraint: "?A != ?B"
then:
  - {subj: "?D", pred: used_by_arc, obj: "?B"}
---
# r002 · two-pattern join: arc A introduces D, arc B mentions D, B != A
""",
    "r003_chain_co_used.md": """---
id: r003_chain_co_used
when:
  - {subj: "?D", pred: used_by_arc, obj: "?B"}
  - {subj: "?E", pred: used_by_arc, obj: "?B"}
constraint: "?D != ?E"
then:
  - {subj: "?D", pred: co_used_with, obj: "?E"}
---
# r003 · chain: consumes r002 output (used_by_arc), emits co_used_with
""",
}


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        rdir = Path(td) / "rules"
        rdir.mkdir()
        for fname, content in RULE_FILES.items():
            (rdir / fname).write_text(content)
        rules = load_rules_dir(rdir)
    print(f"loaded {len(rules)} rules: {[r.id for r in rules]}")

    result = run(SEED_ATOMS, rules, max_iter=10)
    print(f"extracted={result.extracted_count}  derived={result.derived_count}  iters={result.iterations}")
    print("per-rule yield:", result.per_rule_yield)

    chained = [s for s in result.trace if s.rule_id == "r003_chain_co_used"]
    print(f"chained derivations (from r003 consuming r002): {len(chained)}")
    for s in chained[:6]:
        print(f"  iter={s.iteration} {s.rule_id}  binding={s.binding}  parents={s.parents}")
        print(f"    -> {s.derived.subj}  {s.derived.pred}  {s.derived.obj}")

    ok = result.iterations <= 5 and len(chained) >= 1 and result.derived_count >= 3
    print(f"SMOKE {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
