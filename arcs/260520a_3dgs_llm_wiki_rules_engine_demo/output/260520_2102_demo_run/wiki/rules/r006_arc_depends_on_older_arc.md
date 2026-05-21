---
id: r006_arc_depends_on_older_arc
when:
  - {subj: "?A", pred: mentions_arc, obj: "?B"}
constraint: "?A > ?B"
then:
  - {subj: "?A", pred: depends_on, obj: "?B"}
---

# r006 · 新 arc 提到老 arc → 新 arc 依赖老 arc

arc id 是 `YYMMDDx`，字典序就是时间序，所以 `?A > ?B` 等价于 "A 比 B 晚"。

只有"晚 arc 提到早 arc"的引用才被视为依赖；反向引用不构成依赖（早 arc 不可能预先依赖后来的 arc）。

输出被 r011 链式消费。
