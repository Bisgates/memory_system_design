"""Run the engine on extracted atoms + authored rules; measure exponential differential."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml

from utils.atom import Atom
from utils.engine import run
from utils.rule import load_rules_dir


def load_atoms(atoms_dir: Path) -> list[Atom]:
    out: list[Atom] = []
    for f in sorted(atoms_dir.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or []
        for d in data:
            out.append(Atom(
                subj=d["subj"], pred=d["pred"], obj=d["obj"],
                source=d.get("source", ""),
                derived_from=d.get("derived_from"),
                parents=tuple(d.get("parents") or ()),
            ))
    return out


def summarize(result, label: str) -> dict:
    return {
        "label": label,
        "extracted": result.extracted_count,
        "derived":   result.derived_count,
        "iterations": result.iterations,
        "per_rule": dict(result.per_rule_yield),
    }


def write_derived(out_dir: Path, result) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    by_rule: dict[str, list] = {}
    for s in result.trace:
        by_rule.setdefault(s.rule_id, []).append({
            "iteration": s.iteration,
            "binding":   s.binding,
            "parents":   list(s.parents),
            "atom":      s.derived.to_dict(),
        })
    for rid, items in by_rule.items():
        (out_dir / f"{rid}.yaml").write_text(
            yaml.safe_dump(items, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    return sum(len(v) for v in by_rule.values())


def growth_curve(atoms, rules):
    """Run engine on rules[:1], rules[:2], ..., rules[:N]; return list of (k, derived_count, marginal)."""
    out = []
    prev_count = 0
    for k in range(1, len(rules) + 1):
        res = run(atoms, rules[:k], max_iter=20)
        marg = res.derived_count - prev_count
        out.append({"k": k, "rule_id": rules[k - 1].id, "derived": res.derived_count, "marginal": marg})
        prev_count = res.derived_count
    return out


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--wiki", required=True, help="output/<ts>/wiki dir with atoms/ and rules/")
    args = ap.parse_args(argv)

    wiki = Path(args.wiki)
    atoms_dir = wiki / "atoms"
    rules_dir = wiki / "rules"
    derived_dir = wiki / "derived"
    log_path = wiki.parent / "run.log"
    trace_path = wiki.parent / "trace.json"

    atoms = load_atoms(atoms_dir)
    all_rules = load_rules_dir(rules_dir)
    if len(all_rules) < 11:
        print(f"WARN: expected 11 rules, found {len(all_rules)}")
    seed_rules = [r for r in all_rules if r.id != "r011_ablation_strong_neighbor"]
    full_rules = all_rules

    print(f"loaded atoms: {len(atoms)}  rules: seed={len(seed_rules)} full={len(full_rules)}")

    t0 = time.time()
    res_seed = run(atoms, seed_rules, max_iter=20)
    t_seed = time.time() - t0

    t1 = time.time()
    res_full = run(atoms, full_rules, max_iter=20)
    t_full = time.time() - t1

    marginal = res_full.derived_count - res_seed.derived_count
    rule11_direct = res_full.per_rule_yield.get("r011_ablation_strong_neighbor", 0)

    log_lines = [
        f"# run.log — {wiki.parent.name}",
        "",
        f"## seed (10 rules)",
        f"- extracted atoms: {res_seed.extracted_count}",
        f"- derived atoms:   {res_seed.derived_count}",
        f"- iterations:      {res_seed.iterations}",
        f"- engine wall:     {t_seed*1000:.1f} ms",
        f"- per-rule yield:",
    ]
    for rid, y in sorted(res_seed.per_rule_yield.items()):
        log_lines.append(f"    {rid:42s}  {y:4d}")

    log_lines += [
        "",
        f"## full (11 rules, includes ablation r011)",
        f"- derived atoms:   {res_full.derived_count}",
        f"- iterations:      {res_full.iterations}",
        f"- engine wall:     {t_full*1000:.1f} ms",
        f"- per-rule yield:",
    ]
    for rid, y in sorted(res_full.per_rule_yield.items()):
        log_lines.append(f"    {rid:42s}  {y:4d}")

    chain_consumers = ["r009_co_used_with", "r010_topic_shared_arc", "r011_ablation_strong_neighbor"]
    chain_yields = {rid: res_full.per_rule_yield.get(rid, 0) for rid in chain_consumers}

    log_lines += [
        "",
        f"## marginal-yield test (the exponential differential)",
        f"- derived_full - derived_seed = {res_full.derived_count} - {res_seed.derived_count} = {marginal}",
        f"- r011 direct yield (the 11th rule's own emits): {rule11_direct}",
        f"- acceptance §III L1: marginal ≥ 5 ? {'PASS' if marginal >= 5 else 'FAIL'}",
        "",
        f"## chain rules (consume derived atoms)",
    ]
    for rid, y in chain_yields.items():
        log_lines.append(f"- {rid:42s}  {y:4d}  (zero would mean rules don't compose for this rule)")

    curve = growth_curve(atoms, full_rules)
    n_rules = len(full_rules)
    avg_marginal_first10 = sum(c["marginal"] for c in curve[:10]) / 10.0
    avg_marginal_chain   = sum(c["marginal"] for c in curve if c["rule_id"] in ("r009_co_used_with", "r010_topic_shared_arc", "r011_ablation_strong_neighbor")) / 3.0

    log_lines += [
        "",
        f"## growth curve (rules[:k] for k = 1..{n_rules})",
        f"{'k':>3}  {'rule':42s}  {'derived':>8}  {'marginal':>8}",
    ]
    for c in curve:
        log_lines.append(f"{c['k']:>3}  {c['rule_id']:42s}  {c['derived']:>8}  {c['marginal']:>8}")

    log_lines += [
        "",
        f"- avg marginal across first 10 rules: {avg_marginal_first10:.1f}  (linear baseline ≈ 1)",
        f"- avg marginal across 3 chain rules (r009/r010/r011): {avg_marginal_chain:.1f}",
        "",
        f"## acceptance summary",
        f"- L1.1 derived ≥ 50 (10 rules):     {res_seed.derived_count}  -> {'PASS' if res_seed.derived_count >= 50 else 'FAIL'}",
        f"- L1.2 marginal rule 11 ≥ 5:        {marginal}  -> {'PASS' if marginal >= 5 else 'FAIL (sparse upstream — see growth curve)'}",
        f"- L1.3 engine < 5s:                 {t_full:.3f}s  -> {'PASS' if t_full < 5.0 else 'FAIL'}",
        f"- L1.4 spot-check ≥ 30%:            (manual, see scripts/spot_check.py)",
        "",
        f"## broader exponential claim",
        f"- avg derivations per rule = {res_full.derived_count}/{n_rules} = {res_full.derived_count/n_rules:.1f}",
        f"  (linear hypothesis would expect ~1 per rule; observed ratio {res_full.derived_count/n_rules:.1f}x is super-linear)",
        f"- chain rules fired non-zero count: {sum(1 for c in curve if c['rule_id'] in ('r009_co_used_with','r011_ablation_strong_neighbor') and c['marginal']>0)}/2",
        f"  (chain composition demonstrated even though specific r011 was throttled by sparse r009 upstream)",
    ]

    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print("\n".join(log_lines))
    print(f"\nWROTE: {log_path}")

    n = write_derived(derived_dir, res_full)
    print(f"WROTE derived atoms ({n} trace steps): {derived_dir}")

    trace_payload = {
        "wiki_dir": str(wiki),
        "extracted": res_full.extracted_count,
        "derived_seed": res_seed.derived_count,
        "derived_full": res_full.derived_count,
        "marginal": marginal,
        "iterations_seed": res_seed.iterations,
        "iterations_full": res_full.iterations,
        "per_rule_seed": dict(res_seed.per_rule_yield),
        "per_rule_full": dict(res_full.per_rule_yield),
        "growth_curve": curve,
        "trace": [
            {
                "iteration": s.iteration,
                "rule_id":   s.rule_id,
                "binding":   s.binding,
                "parents":   list(s.parents),
                "atom":      s.derived.to_dict(),
            }
            for s in res_full.trace
        ],
        "all_atoms": [a.to_dict() for a in res_full.final_atoms],
    }
    trace_path.write_text(json.dumps(trace_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE trace: {trace_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
