---
id: r004_code_developed_in_arc
when:
  - {subj: "?A", pred: mentions_code, obj: "?C"}
  - {subj: "?A", pred: has_type,      obj: "type:arc"}
then:
  - {subj: "?C", pred: developed_in_arc, obj: "?A"}
---

# r004 · arc 提到某个 code 路径 → 那段 code 算"在该 arc 里被开发"

关键限制：subj 必须是 arc（用 has_type 联合 join 限制），否则 note 里提到 code 也会触发。

输出被 r011 (ablation) 链式消费。
