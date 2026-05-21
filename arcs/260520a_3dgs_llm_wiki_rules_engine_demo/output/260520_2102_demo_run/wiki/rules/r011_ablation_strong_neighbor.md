---
id: r011_ablation_strong_neighbor
when:
  - {subj: "?D", pred: co_used_with,       obj: "?E"}
  - {subj: "?D", pred: shares_topic_with,  obj: "?E"}
then:
  - {subj: "?D", pred: strong_neighbor, obj: "?E"}
---

# r011 · ABLATION · 同时 co_used + shares_topic → strong_neighbor (CHAIN²)

**这条是 ablation：第 11 条 rule，它消费 r009（chains r002）AND r007 的输出**。
两个 derived predicate 的合取。

如果它贡献 ≥ 5 条 derivations → "rules × atoms 乘法效益" 成立，第 11 条规则免费拉出了一批前 10 条都没能写出来的关系。指数微分 ✓。

如果它 < 2 条 → 规则之间不正交也不组合，N×M 退化成 N+M，整个抽象证伪。

**这条规则故意被设计成 "两步 chain"，作为本 arc 验收 §III L1 第二指标的明确触发器。**
