---
id: r009_co_used_with
when:
  - {subj: "?D", pred: used_by_arc, obj: "?B"}
  - {subj: "?E", pred: used_by_arc, obj: "?B"}
constraint: "?D != ?E"
then:
  - {subj: "?D", pred: co_used_with, obj: "?E"}
---

# r009 · 同被一个 arc 复用的两个 doc → 互为复用邻居 (CHAIN)

**消费 r002 的 derived atoms**（used_by_arc）—— 第一条 chain 规则。

如果 r009 在 baseline 跑里贡献了非零数字，说明 forward chaining 真的发生了。如果它是 0，说明 r002 的 yield 集中在"同一 arc 只复用一个 doc"，rules 没有组合 — 需要重新设计。

被 r011 (ablation) 链式消费。
