---
id: r007_doc_co_topic_neighbor
when:
  - {subj: "?D", pred: has_topic, obj: "?T"}
  - {subj: "?E", pred: has_topic, obj: "?T"}
constraint: "?D != ?E"
then:
  - {subj: "?D", pred: shares_topic_with, obj: "?E"}
---

# r007 · 两个 doc 共享 topic → 互为 topic 邻居

是"按 topic 找相关 doc"的基础。output 数量约为 sum_T (N_T choose 2) × 2（有方向）—— 单个 topic 下有 K 个 doc，就派出 K×(K-1) 条边。topic 越热的 doc 越拥挤。
