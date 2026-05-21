---
id: r008_duplicate_introducer
when:
  - {subj: "?A", pred: introduces_doc, obj: "?D"}
  - {subj: "?B", pred: introduces_doc, obj: "?D"}
constraint: "?A != ?B"
then:
  - {subj: "?D", pred: has_duplicate_introducer, obj: "?A"}
---

# r008 · 两个 arc 都声称引入同一个 doc → contradiction-lint

理论上一个 doc 只该有一个 "[NEW]" 出处。两条 introduces_doc 同时存在意味着至少一条标错了 `[NEW]` 应该是 `[UPDATE]`。

这是 condition-system 类规则的最纯版本：不直接修，而是把结构化矛盾派生出来交给用户。
