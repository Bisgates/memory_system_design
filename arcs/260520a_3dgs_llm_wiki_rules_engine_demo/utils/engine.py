"""Forward-chaining engine — apply rules to atoms until fixpoint."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator

from utils.atom import Atom, AtomStore
from utils.rule import Pattern, Rule, eval_constraint, is_var


@dataclass
class DerivationStep:
    iteration: int
    rule_id: str
    binding: dict[str, str]
    parents: tuple
    derived: Atom


@dataclass
class RunResult:
    final_atoms: list[Atom]
    extracted_count: int
    derived_count: int
    iterations: int
    trace: list[DerivationStep] = field(default_factory=list)
    per_rule_yield: dict[str, int] = field(default_factory=dict)


def _match_one(pat: Pattern, store: AtomStore, binding: dict[str, str]) -> Iterator[tuple[dict[str, str], Atom]]:
    """Yield (extended_binding, matched_atom) for each atom matching pat under binding."""
    subj_q = binding.get(pat.subj, pat.subj) if is_var(pat.subj) else pat.subj
    pred_q = binding.get(pat.pred, pat.pred) if is_var(pat.pred) else pat.pred
    obj_q  = binding.get(pat.obj,  pat.obj)  if is_var(pat.obj)  else pat.obj

    if not is_var(pred_q):
        candidates: Iterable[Atom] = store.by_pred(pred_q)
    else:
        candidates = store
    for a in candidates:
        if not is_var(subj_q) and a.subj != subj_q:
            continue
        if not is_var(pred_q) and a.pred != pred_q:
            continue
        if not is_var(obj_q)  and a.obj  != obj_q:
            continue
        b = dict(binding)
        ok = True
        for slot, val in ((pat.subj, a.subj), (pat.pred, a.pred), (pat.obj, a.obj)):
            if is_var(slot):
                if slot in b and b[slot] != val:
                    ok = False
                    break
                b[slot] = val
        if ok:
            yield b, a


def _match_all(when: list[Pattern], constraint: str | None, store: AtomStore) -> Iterator[tuple[dict[str, str], tuple[Atom, ...]]]:
    """Yield (binding, matched_atoms_tuple) for every binding satisfying the full conjunction."""

    def step(i: int, binding: dict[str, str], parents: tuple[Atom, ...]):
        if i == len(when):
            if constraint and not eval_constraint(constraint, binding):
                return
            yield binding, parents
            return
        for b2, a in _match_one(when[i], store, binding):
            yield from step(i + 1, b2, parents + (a,))

    yield from step(0, {}, ())


def _instantiate(pat: Pattern, binding: dict[str, str]) -> tuple[str, str, str] | None:
    def resolve(x: str) -> str | None:
        if is_var(x):
            return binding.get(x)
        return x
    subj = resolve(pat.subj)
    pred = resolve(pat.pred)
    obj  = resolve(pat.obj)
    if subj is None or pred is None or obj is None:
        return None
    return (subj, pred, obj)


def run(
    initial: Iterable[Atom],
    rules: list[Rule],
    *,
    max_iter: int = 20,
) -> RunResult:
    store = AtomStore()
    extracted = 0
    for a in initial:
        if store.add(a):
            extracted += 1

    trace: list[DerivationStep] = []
    per_rule: dict[str, int] = {r.id: 0 for r in rules}
    iteration = 0
    while iteration < max_iter:
        iteration += 1
        added_this_round = 0
        for rule in rules:
            for binding, parents in _match_all(rule.when, rule.constraint, store):
                for tpat in rule.then:
                    triple = _instantiate(tpat, binding)
                    if triple is None:
                        continue
                    subj, pred, obj = triple
                    new = Atom(
                        subj=subj, pred=pred, obj=obj,
                        source="",
                        derived_from=rule.id,
                        parents=tuple(p.id for p in parents),
                    )
                    if store.add(new):
                        per_rule[rule.id] = per_rule.get(rule.id, 0) + 1
                        added_this_round += 1
                        trace.append(DerivationStep(
                            iteration=iteration,
                            rule_id=rule.id,
                            binding=dict(binding),
                            parents=tuple(p.id for p in parents),
                            derived=new,
                        ))
        if added_this_round == 0:
            break

    derived = len(store) - extracted
    return RunResult(
        final_atoms=store.all_atoms(),
        extracted_count=extracted,
        derived_count=derived,
        iterations=iteration,
        trace=trace,
        per_rule_yield=per_rule,
    )
