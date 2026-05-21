---
id: r002_doc_used_by_arc
when:
  - {subj: "?A", pred: introduces_doc, obj: "?D"}
  - {subj: "?B", pred: mentions_doc,   obj: "?D"}
constraint: "?A != ?B"
then:
  - {subj: "?D", pred: used_by_arc, obj: "?B"}
---

# r002 · 复用监测：doc 被引入后又被其他 arc 提到

A 引入 D，B 也提到 D（B≠A） → D 被 B 复用。这是整个 wiki 里"知识在跨 arc 流动"的硬证据。

被 r009 链式消费（co_used_with）。
