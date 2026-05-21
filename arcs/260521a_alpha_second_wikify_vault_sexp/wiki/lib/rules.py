"""
RuleEngine — forward-chaining datalog-style rule engine.

Design choices:
- Rules are Cards with :type 'rule, :when [patterns], :then [conclusions].
- Pattern form: [?A pred ?D] — subject/pred/obj each can be a variable (starts with '?')
  or a constant string.
- Matching: we iterate all atom cards in the store and try to unify each pattern
  against (subj, pred, obj). Multiple patterns in :when must all unify with a
  consistent variable binding.
- Derived cards: generated with type='derived', :subj/:pred/:obj filled in,
  :derived_from=rule_id, :parents=[matched atom ids].
- Dedup: natural key is (subj, pred, obj); existing derived card with same triple
  is skipped on re-fire (monotone append-only).
- run_to_fixpoint: repeats run_once until no new cards are added (max_iters guard).
- No aggregation: deliberate, to keep fixpoint convergence guaranteed.
"""

from __future__ import annotations
import hashlib
import datetime
from typing import Any, Optional
from wiki.lib.cardstore import Card, CardStore


# ---------------------------------------------------------------------------
# RuleEngine
# ---------------------------------------------------------------------------

class RuleEngine:
    def __init__(self):
        self._rules: dict[str, Card] = {}

    def register(self, rule_card: Card) -> None:
        self._rules[rule_card.id] = rule_card

    def run_once(self, store: CardStore) -> list[Card]:
        """Fire all rules once; return list of newly added derived cards."""
        new_cards: list[Card] = []
        # Collect existing (subj, pred, obj) natural keys to dedup
        existing_keys = set()
        for c in store.all_cards():
            s = c.kvs.get("subj"); p = c.kvs.get("pred"); o = c.kvs.get("obj")
            if s and p and o:
                existing_keys.add((s, p, o))

        atoms = [c for c in store.all_cards() if c.type in ("atom", "derived")]

        for rule in self._rules.values():
            when_patterns = rule.kvs.get("when", [])
            then_conclusions = rule.kvs.get("then", [])
            if not when_patterns or not then_conclusions:
                continue

            # Find all binding sets that satisfy ALL when patterns
            bindings_list = _match_patterns(when_patterns, atoms)

            for bindings in bindings_list:
                parent_ids = bindings.get("__matched_ids__", [])
                ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
                for conclusion in then_conclusions:
                    if not isinstance(conclusion, list) or len(conclusion) < 3:
                        continue
                    subj = _bind(conclusion[0], bindings)
                    pred = _bind(conclusion[1], bindings)
                    obj  = _bind(conclusion[2], bindings)
                    if subj is None or pred is None or obj is None:
                        continue
                    key = (subj, pred, obj)
                    if key in existing_keys:
                        continue
                    existing_keys.add(key)
                    card_id = "d_" + hashlib.sha1(f"{subj}|{pred}|{obj}".encode()).hexdigest()[:8]
                    c = Card(
                        id=card_id,
                        type="derived",
                        kvs={
                            "subj": subj,
                            "pred": pred,
                            "obj": obj,
                            "derived_from": rule.id,
                            "parents": list(parent_ids),
                            "generated_at": ts,
                        },
                    )
                    store.add(c)
                    new_cards.append(c)
        return new_cards

    def run_to_fixpoint(self, store: CardStore, max_iters: int = 10) -> list[Card]:
        """Repeat run_once until no new cards are generated (fixpoint)."""
        all_new: list[Card] = []
        for _ in range(max_iters):
            batch = self.run_once(store)
            if not batch:
                break
            all_new.extend(batch)
        return all_new


# ---------------------------------------------------------------------------
# Pattern matching (semi-naive forward chaining)
# ---------------------------------------------------------------------------

def _is_var(x: Any) -> bool:
    return isinstance(x, str) and x.startswith("?")


def _bind(template: Any, bindings: dict) -> Optional[str]:
    if _is_var(template):
        return bindings.get(template)
    if isinstance(template, str):
        return template
    return str(template)


def _unify_triple(pattern: list, card: Card, bindings: dict) -> Optional[dict]:
    """
    Try to unify pattern [pat_subj, pat_pred, pat_obj] with card's (subj,pred,obj).
    Returns updated bindings dict if success, None if conflict.
    """
    if len(pattern) < 3:
        return None
    card_triple = [
        card.kvs.get("subj"),
        card.kvs.get("pred"),
        card.kvs.get("obj"),
    ]
    if any(v is None for v in card_triple):
        return None

    new_bindings = dict(bindings)
    for pat_val, card_val in zip(pattern[:3], card_triple):
        if _is_var(pat_val):
            if pat_val in new_bindings:
                if new_bindings[pat_val] != card_val:
                    return None  # conflict
            else:
                new_bindings[pat_val] = card_val
        else:
            if pat_val != card_val:
                return None  # constant mismatch
    return new_bindings


def _match_patterns(patterns: list, atoms: list[Card]) -> list[dict]:
    """
    Find all consistent binding dicts that satisfy ALL patterns.
    Returns list of binding dicts; each dict also has '__matched_ids__' key.
    """
    # Start with one empty binding
    results: list[dict] = [{"__matched_ids__": []}]

    for pattern in patterns:
        if not isinstance(pattern, list):
            continue
        new_results: list[dict] = []
        for bindings in results:
            for atom in atoms:
                unified = _unify_triple(pattern, atom, bindings)
                if unified is not None:
                    updated = dict(unified)
                    updated["__matched_ids__"] = list(bindings.get("__matched_ids__", [])) + [atom.id]
                    new_results.append(updated)
        results = new_results

    return results
