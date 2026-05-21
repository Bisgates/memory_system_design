---
id: 260521a_wikify_auto_research_vault_sexp
brief: wikify auto research vault sexp
created_at: 2026-05-21T01:13:07+08:00
last_active_at: 2026-05-21T02:13:53+08:00
status: done
actor: agent
parent: null
abandon_reason: null
---

## history
- 2026-05-21T01:13:07+08:00 created
- 2026-05-21T02:13:53+08:00 active -> done

## log
- **[2026-05-21 01:22:08]** kernel build: cardstore.py complete — Card dataclass + CardStore CRUD/query/links/versioning/EDN roundtrip, sexp parser 106 lines, 6/6 tests pass

- **[2026-05-21 01:22:15]** kernel build: macro.py complete — MacroEngine register/expand, ?var substitution, parents chain, 3/3 tests pass

- **[2026-05-21 01:22:15]** kernel build: rules.py complete — RuleEngine forward chaining, pattern matching, dedup by triple, run_to_fixpoint, 2/2 tests pass

- **[2026-05-21 01:22:15]** kernel build: view.py complete — materialize with filter DSL + wildcard, resolve_lazy <eval> expressions, 2/2 tests pass

- **[2026-05-21 01:22:16]** kernel build: dedup.py complete — similarity (text+structural), find_near_dupes, restart protocol keep-both/supersede, 2/2 tests pass

- **[2026-05-21 01:22:16]** kernel build: smoke_test.py end-to-end PASSED — 8 atoms, 5 derived, 1 rule, 1 macro, 1 view, 16 total cards, EDN roundtrip verified, 15/15 unit tests pass

- **[2026-05-21 01:29:49]** Phase 2 ingest script: wiki/scripts/ingest_vault.py written (~430 lines), structural parser (PyYAML frontmatter + regex H2 sections + double-link extractor), namespace prefixes exp:/lin:/arc:/report:/doc:/ap:

- **[2026-05-21 01:29:57]** Phase 2 ingest run: 65 sources (53 experiments + 8 lineages + 1 report + 1 anti-pattern catalog + 1 VAULT_DESIGN + 1 README) → 3404 unique atoms in 65 .edn files; 104 frontmatter typed links + 169 body typed links; 70 unique tag values; 0.13s elapsed; 90 warnings (unknown body link labels kept but flagged)

- **[2026-05-21 01:29:57]** Phase 2 query verification: 5 sample queries all pass — Q1 53 experiments / Q2 21 atoms tagged axis/blacklist / Q3 1 falsifies link extracted / Q4 SOTA champion has 58 outgoing atoms across 30+ predicates / Q5 20 unique exp+lin subjects tagged status/falsified; ID hash stable across reruns

- **[2026-05-21 01:40:00]** Phase 3 rule cards on disk — r001 canonicalize_body_links (7 micro-rules r001a..r001g: borrowed_by / descendants / base_for / team_a_top_picks / inherits_failure_mode×2 / same_round_as) at wiki/cards/rules/r001_canonicalize_body_links.edn

- **[2026-05-21 01:40:00]** Phase 3 rule cards on disk — r002 derived_from_reverse (?A derived_from ?B ⇒ ?B derives_to ?A) at wiki/cards/rules/r002_derived_from_reverse.edn

- **[2026-05-21 01:40:00]** Phase 3 rule cards on disk — r003 competes_with_symmetry (closure, dedup by triple prevents ping-pong) at wiki/cards/rules/r003_competes_with_symmetry.edn

- **[2026-05-21 01:40:00]** Phase 3 rule cards on disk — r004 falsifies_cluster (transitive: A falsifies B & B falsifies C ⇒ A inherits_falsification C) at wiki/cards/rules/r004_falsifies_cluster.edn

- **[2026-05-21 01:40:00]** Phase 3 rule cards on disk — r005 anti_pattern_inheritance (ap references_in_case_examples exp ⇒ exp is_instance_of_anti_pattern ap) at wiki/cards/rules/r005_anti_pattern_inheritance.edn

- **[2026-05-21 01:40:00]** Phase 3 macro cards on disk — m001 paper-to-experiment-suggestion (1 source → 3 suggestion cards: baseline / ablation / extension) at wiki/cards/macros/m001_paper_to_experiment_suggestion.edn

- **[2026-05-21 01:40:00]** Phase 3 macro cards on disk — m002 lineage-to-comparison-view (1 lineage → 1 view card with lazy parent_lineage query) at wiki/cards/macros/m002_lineage_to_comparison_view.edn

- **[2026-05-21 01:41:02]** Phase 3 run_rules.py end-to-end PASSED — 3404 atoms loaded → 99 rule-derived cards in 2 effective iterations (94+5) to fixpoint, 0.10s; per-rule fires: r001a=2 r001b=2 r001c=3 r001d=6 r001e=2 r001f=1 r001g=0 r002=53 r003=20 r004=0 r005=10; macro dispatch: m001 × 3 experiments → 9 suggestion cards, m002 × 2 lineages → 2 view cards (materialize 14+7 atoms via lazy parent_lineage query); dedup invariant holds (0 dup triples), re-fire idempotent (0 new on second pass); 11 derived .edn files at wiki/cards/derived/; full log at output/phase3_rules.log

- **[2026-05-21 01:50:00]** Phase 4 cap1 macro-derive demo end-to-end PASSED — 3 hand-picked experiments (SOTA champion H-R3b-4 / falsified B-R10-2 / lineage-parent H-R2-2) × m001 paper-to-experiment-suggestion → 9 fresh suggestion cards (baseline+ablation+extension per source); macro itself queryable as :type 'macro card (store.find_by_type('macro') = 2); trace at output/260521_0145_demo_run/cap1_macro_derive/

- **[2026-05-21 01:50:00]** Phase 4 cap2 lazy-reference demo PASSED — built two ephemeral cards (view + atom) carrying <eval>latest-of …</eval> and <eval>count-links-to …</eval> markers; store.resolve_lazy substituted (champion in-degree 14, parent H-R2-2 in-degree 11, latest-of body excerpts inlined); 3 lazy expressions resolved at read time; before/after trace at output/260521_0145_demo_run/cap2_lazy_ref/before_after.json

- **[2026-05-21 01:50:00]** Phase 4 cap3 rules-as-cards demo PASSED — store.find_by_type('rule') = 11 cards; fixpoint produces 99 derived spread across 9 rules; substring query ":body contains 'reverse'" hits 2 rules (r001g + r002); flipping r002.status='paused' then re-running fixpoint drops total derived from 99 → 46 (Δ=53 = exactly r002's prior fan-out) — confirming status='paused' really gates firing

- **[2026-05-21 01:50:00]** Phase 4 cap4 dedup-restart demo PASSED — built a 5-10% variant of champion has_section_hypothesis (similarity 0.969 ≥ 0.80); 3 sub-store runs each with on-dedup-conflict head = keep-both / merge-prefer-newer / supersede; all 3 actions fired as expected — keep-both adds :see-also bidirectional, merge-prefer-newer + supersede flip original status to 'superseded' and set :superseded-by / :supersedes; per-case before/after at output/260521_0145_demo_run/cap4_dedup_restart/cases.json

- **[2026-05-21 01:50:00]** Phase 4 cap5 view-card demo PASSED — m002 expand on lin:arc_260516a__team_h__sizing yields a view card; materialize cycle: initial=14 atoms → inject synthetic parent_lineage atom → 15 → delete synthetic → 14 (returns to baseline); proves view is lazy, no caching layer, store mutation reflected immediately at read time

- **[2026-05-21 01:50:00]** Phase 4 cap6 self-compute confidence demo PASSED — built claim card with :confidence sexp expr (compute (- supports contradicts) / (max supports 1)); 3-stage progression: (a) 0 supp / 0 contra → 0.000; (b) +3 supports → 1.000; (c) +2 contradicts → 0.333; per-stage trace at output/260521_0145_demo_run/cap6_self_compute/snapshots.json

- **[2026-05-21 01:54:00]** Phase 4 viz.html built — single-file 678 KB, 0 external CDN, macOS system font stack, vanilla SVG force-directed (Fruchterman-Reingold static layout, 220 iters, ~1.6s); 3546 nodes / 493 edges total, 215 visible-by-default / 3331 atoms hidden behind toggle; filter by type+tag+id, click to highlight incident edges, hover for body excerpt; 6-capability collapsible evidence index at the bottom; lives at output/260521_0145_demo_run/viz.html

- **[2026-05-21 01:54:00]** Phase 4 hand-off — output/260521_0145_demo_run/README.md + summary.json written; demo_capabilities.py + build_viz.py idempotent via --run-dir; total wall time ~3.0s (demo 1.3s + viz 1.7s); 6/6 capabilities have stdout.log + json trace; ready for Phase 5 grok summary
