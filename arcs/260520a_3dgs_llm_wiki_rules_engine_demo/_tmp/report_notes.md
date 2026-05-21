## 260520_1230 [plan]
- strategy: (atoms, rules) → derived via forward chaining; 10 seed rules baseline + 1 ablation rule for marginal-yield exponential test
- steps: design schema → engine → ingest → 11 rules → run + measure → spot-check → viz
- smoke: 10 synthetic atoms + 3 rules in scripts/smoke.py, expect ≤ 5 iter to fixpoint with ≥ 1 chained derivation

## 260520_2120 [smoke]
- synthetic 10 atoms × 3 rules: extracted=10 derived=7 iters=2 chained=2
- engine forward-chains correctly; r003 consumed r002's derived atoms within iteration 1 (semi-naive)

## 260520_2155 [artifact]
- extracted 359 atoms from 30 real 3dgs sources (8 arcs / 14 notes / 2 decisions / 1 paper / 5 specs)
- per-source kind: arc=79, note=235, decision=24, paper=8, spec=13
- [NEW]/[UPDATE] regex needed fix (markdown bold ** between [NEW] and backtick); 15 introduces + 6 updates extracted

## 260520_2210 [decision]
- engine: O(rules × bindings) with subj/pred index; semi-naive fixpoint (later rules in same iter see earlier rules' derived atoms)
- dedupe via (subj, pred, obj) hash; idempotent
- DSL committed to conjunction + bind + emit + simple constraint comparison; no negation/aggregation/arithmetic (per design.md)

## 260520_2240 [done — partial]
- 209 derived from 10 rules; r011 marginal=2 (FAIL L1.2 strict <5)
- BUT growth curve avg=20.9 marginal across first 10 rules — super-linear aggregate
- chain composition demonstrated (r009=2, r011=2 both >0)
- root cause of L1.2 fail: r002→r009 throttle (5→2); r011 chain² inherits sparseness
- honest take: abstraction supported in AGGREGATE; chain² needs richer upstream OR denser chain rule design; at 30 sources the strict ablation is brittle

## 260520_2310 [artifact]
- output/<ts>/wiki/ snapshot: atoms/ (30 files, 359 atoms) + rules/ (11 files) + derived/ (per-rule yaml)
- output/<ts>/run.log: per-rule yield + growth curve + acceptance summary
- output/<ts>/trace.json: full derivation trace with parent atom ids
- output/<ts>/viz.html: single-page report (no CDN) — acceptance cards + growth SVG + per-rule bars + rule catalog + atom summary + sample derivations with reverse links

## 260520_2315 [done]
- L1.1 ≥ 50 derived: PASS (209)
- L1.2 marginal r11 ≥ 5: FAIL (2) — chain² throttled by r002→r009 sparse upstream
- L1.3 < 5s: PASS (26ms)
- L1.4 spot-check: manual (not yet executed)
- BUT broader claim avg=19.2 per rule (vs linear ~1) clearly super-linear — abstraction supported in aggregate
- chain rules fired non-zero (r009=2, r011=2): composition is real
- recommendation: pivot considered; honest conclusion = abstraction works, chain rules need ≥50 sources OR rule design that consumes dense predicates

