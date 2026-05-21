# Phase 4 — 6 capabilities demo run
_arc 260521a · generated 2026-05-20T17:55:33+00:00 · elapsed 1.33s_

## Headline numbers
- store: **3417** total cards  (atoms 3331, experiments 53, lineages 8, rules 11, macros 2)
- Phase 3 fixpoint pre-baseline: 5 rule families (11 micro-rules) + 2 macros, 99 rule fires + 11 macro expansions in 0.19s

## Capability summaries

### Capability 1 — macro 派生卡
挑 3 张 experiment 卡 (SOTA champion / falsified-plateau-parent / lineage-parent) 过 m001 macro。每张产 3 张 suggestion card (baseline / ablation / extension), 共 **9 张新卡**。store 中 macro 本身也是 card (2 张), 同 :id namespace, `store.find_by_type('macro')` 就能查。证据: `cap1_macro_derive/`.

### Capability 2 — lazy reference
两张含 `<eval>...</eval>` 的卡片 (view + atom) 走 `store.resolve_lazy`. `latest-of` 替换为目标卡 :body, `count-links-to` 替换为入度整数. 共 **3 个 lazy ref 在 read time evaluate**. 证据: `cap2_lazy_ref/before_after.json`.

### Capability 3 — 规则即卡片
`find_by_type('rule')` 一次查出 **11 张 rule card** (7 micro r001a..g + r002 / r003 / r004 / r005). Fixpoint 跑完后 **9** 条 rule 有派生 fan-out. 字符串子查询 (`'reverse' in :body.lower()`) 命中 r001g + r002. 把 r002 状态翻 `paused` 再 re-run, 该 rule 派生卡 -53 → 验证 status flip 确实阻断 firing. 证据: `cap3_rules_as_cards/`.

### Capability 4 — dedup restart 协议
构造与 SOTA champion has_section_hypothesis 5-10% 偏差的变体卡 (similarity = **0.9691** ≥ 0.80). 3 次跑各自指定 `on-dedup-conflict` 列表头部 = `keep-both` / `merge-prefer-newer` / `supersede`. 实际触发 action: **['keep-both', 'merge-prefer-newer', 'supersede']**. 证据: `cap4_dedup_restart/cases.json`.

### Capability 5 — 视图卡 (materialized view)
m002 macro 派一张 view card on `lin:arc_260516a__team_h__sizing`. 三次 materialize: 初始 **14** 命中 → 注入合成 atom 后 **15** → 删除后 **14** (回到初始, 证明 view 完全 lazy 不缓存). 证据: `cap5_view_card/snapshots.json`.

### Capability 6 — 自计算字段
建一张 claim card, :confidence 字段是 sexp 表达式 `(compute (- supports contradicts) / (max supports 1))`. 3 个 snapshot: 0/0 → conf **0.0**; 加 3 supporters → conf **1.0**; 再加 2 contradictors → conf **0.3333**. 证据: `cap6_self_compute/snapshots.json`.

## Viz
`/Users/han/project/alpha/alpha_second_v1/arcs/all/260521a_wikify_auto_research_vault_sexp/output/260521_0145_demo_run/viz.html` — single-file vanilla SVG force-directed graph, 0 external CDN, macOS system font stack. Filter by type / tag / id, hover for body excerpt. 3000+ atoms hidden by default; toggle to reveal.

## Known limitation
- `_eval_confidence` only recognizes the canonical `count-links-to %self :pred 'supports/contradicts` form. A general s-expr evaluator is out of scope for the kernel; the trigger pattern is matched by structural inspection, not parsed.
- viz is **static layout** (one-shot simulation, no on-canvas dragging). 数据 scale 太大没必要做交互.
- Phase 4 不动 atoms/rules/macros 的 .edn 文件; demo 产物只写在 `output/<demo_run>/`.
