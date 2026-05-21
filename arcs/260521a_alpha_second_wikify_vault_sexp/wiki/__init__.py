"""
wiki — sexp/EDN card store kernel for the auto_research_experiment vault.

Public API:
  Card, CardStore   — core data model + store (cardstore.py)
  MacroEngine       — macro registration + expansion (macro.py)
  RuleEngine        — forward-chaining datalog rules (rules.py)
  materialize       — evaluate view cards against store (view.py)
  resolve_lazy      — resolve <eval>...</eval> inline expressions (view.py)
  similarity        — card similarity score [0,1] (dedup.py)
  find_near_dupes   — find near-duplicate cards in store (dedup.py)
  resolve_conflict  — run restart protocol for dedup conflicts (dedup.py)
"""

from wiki.lib.cardstore import Card, CardStore
from wiki.lib.macro import MacroEngine
from wiki.lib.rules import RuleEngine
from wiki.lib.view import materialize, resolve_lazy
from wiki.lib.dedup import similarity, find_near_dupes, resolve_conflict

__all__ = [
    "Card", "CardStore",
    "MacroEngine",
    "RuleEngine",
    "materialize", "resolve_lazy",
    "similarity", "find_near_dupes", "resolve_conflict",
]
