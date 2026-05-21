"""
View — materialized view cards and lazy reference resolution.

Design choices:
- A view card has :type 'view and :query field containing a filter spec dict.
- materialize(view_card, store) evaluates :query at read-time, returning matching cards.
- Query DSL (minimal): dict with optional keys:
    :filter_type  → match card.type
    :filter_pred  → match card.kvs['pred']
    :filter_subj  → match card.kvs['subj']
    :filter_obj   → match card.kvs['obj']
    :filter_fn_name → named filter function (registered with register_filter)
  All specified keys must match (AND semantics). '?_' is wildcard (matches anything).
- Lazy reference in :body: <eval>expr</eval> inline expressions.
  Delegation to CardStore.resolve_lazy() which handles latest-of and count-links-to.
- Views are not cached; they are re-evaluated on each materialize() call.
  This is intentional for a kernel — caching/incremental maintenance is Phase 3+.
"""

from __future__ import annotations
from typing import Callable, Optional
from wiki.lib.cardstore import Card, CardStore


# Registry for named filter functions (extensible)
_named_filters: dict[str, Callable[[Card], bool]] = {}


def register_filter(name: str, fn: Callable[[Card], bool]) -> None:
    """Register a named filter for use in view queries."""
    _named_filters[name] = fn


def _matches_query(card: Card, query: dict) -> bool:
    """Return True if card matches all constraints in query dict."""
    WILDCARD = "?_"

    def _check(field_val: Optional[str], constraint: str) -> bool:
        if constraint == WILDCARD:
            return True
        return field_val == constraint

    if "filter_type" in query:
        if not _check(card.type, query["filter_type"]):
            return False

    if "filter_pred" in query:
        if not _check(card.kvs.get("pred"), query["filter_pred"]):
            return False

    if "filter_subj" in query:
        if not _check(card.kvs.get("subj"), query["filter_subj"]):
            return False

    if "filter_obj" in query:
        if not _check(card.kvs.get("obj"), query["filter_obj"]):
            return False

    if "filter_fn_name" in query:
        fn = _named_filters.get(query["filter_fn_name"])
        if fn and not fn(card):
            return False

    return True


def materialize(view_card: Card, store: CardStore) -> list[Card]:
    """
    Evaluate view_card's :query against store.
    Returns list of matching cards (re-evaluated at call time).
    """
    query = view_card.kvs.get("query", {})
    if not isinstance(query, dict):
        # If query is a string (sexp stored as string), treat as empty → all cards
        return store.all_cards()
    return [c for c in store.all_cards() if _matches_query(c, query)]


def resolve_lazy(card: Card, store: CardStore) -> Card:
    """
    Resolve <eval>...</eval> inline expressions in card's :body.
    Delegates to CardStore.resolve_lazy().
    """
    return store.resolve_lazy(card)
