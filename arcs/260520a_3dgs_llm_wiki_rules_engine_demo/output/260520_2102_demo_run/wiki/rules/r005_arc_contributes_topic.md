---
id: r005_arc_contributes_topic
when:
  - {subj: "?A", pred: introduces_doc, obj: "?D"}
  - {subj: "?D", pred: has_topic,      obj: "?T"}
then:
  - {subj: "?A", pred: contributes_to, obj: "?T"}
---

# r005 · arc 引入的 doc 所属 topic → arc 贡献了该 topic

让 topic 维度成为可查询的：每个 topic 都自动得到一份"被哪些 arc 贡献了内容"清单。
