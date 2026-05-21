---
id: r001_introduces_reverse
when:
  - {subj: "?A", pred: introduces_doc, obj: "?D"}
then:
  - {subj: "?D", pred: introduced_by, obj: "?A"}
---

# r001 · introduces_doc → introduced_by

每条 "arc 引入 doc" 都派生反向边，让 doc 一侧也能直接答 "我是被哪个 arc 引入的"。

预期 yield = #(introduces_doc) ≈ 15。
