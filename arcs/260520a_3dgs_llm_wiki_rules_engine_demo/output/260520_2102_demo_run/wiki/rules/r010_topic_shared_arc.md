---
id: r010_topic_shared_arc
when:
  - {subj: "?A", pred: contributes_to, obj: "?T"}
  - {subj: "?B", pred: contributes_to, obj: "?T"}
constraint: "?A != ?B"
then:
  - {subj: "?A", pred: collaborates_on_topic, obj: "?B"}
---

# r010 · 两个 arc 同 topic 贡献 → 拓扑学协作 (CHAIN)

**消费 r005 的 derived atoms**（contributes_to）—— 第二条 chain 规则。

派生 "在 topic T 上 arc A 和 arc B 都贡献过" 这条 arc-arc 协作边。这是一份只有规则才看得见、原始 markdown 里不直接出现的关系。
