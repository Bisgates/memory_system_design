---
id: r003_arc_ref_reverse
when:
  - {subj: "?A", pred: mentions_arc, obj: "?B"}
then:
  - {subj: "?B", pred: referenced_by_arc, obj: "?A"}
---

# r003 · mentions_arc → referenced_by_arc

跨 arc 引用的反向边。"我被哪些 arc 提到过" — 这条让 arc 一侧直接答得出。
