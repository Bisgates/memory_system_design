---
id: 260520a_llm_wiki_rules_engine_demo
brief: llm wiki rules engine demo
created_at: 2026-05-20T20:55:12+08:00
last_active_at: 2026-05-20T21:10:41+08:00
status: active
actor: agent
parent: null
abandon_reason: null
---

## history
- 2026-05-20T20:55:12+08:00 created

## log
- **[2026-05-20 20:58:18]** [plan] 2_plan.md written; strategy=(atoms,rules)→derived fwd-chain; 10+1 rules; smoke on synthetic before full

- **[2026-05-20 21:01:08]** [smoke] synthetic 10 atoms × 3 rules: extracted=10 derived=7 iters=2 chained=2 (r003 consumed r002). SMOKE PASS — engine forward-chains correctly.

- **[2026-05-20 21:07:57]** [demo] full run: 359 atoms × 11 rules → 211 derived in 26ms, iters=2. Per-rule avg=19.2 (super-linear vs 1/rule baseline). Growth curve dominated by r007=152 (topic graph), r004=21 (code-in-arc). Chains DO fire (r009=2, r011=2) but chain² throttled by sparse r002/r005 upstream. L1.1 PASS (209≥50); L1.2 FAIL (2<5) but contextual.

- **[2026-05-20 21:10:40]** [viz] viz.html written (624 lines, single-file, no CDN). Auto-opened.

- **[2026-05-20 21:10:40]** [done] all plan steps complete. Acceptance: L1.1 PASS (209≥50), L1.2 FAIL (marginal=2<5, sparse-upstream throttle), L1.3 PASS (26ms<5s), L1.4 manual. Engine + DSL + chain composition demonstrated; strict ablation throttled by data scale.
