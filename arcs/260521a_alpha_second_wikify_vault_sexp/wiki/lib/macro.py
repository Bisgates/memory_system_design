"""
MacroEngine — macro registration and expansion for the sexp wiki.

Design choices:
- A macro is a Card with :type 'macro, :name sym, :params [list], :body [card-templates].
- Body is a list of template dicts. Each template is a dict of key→value where
  values may contain '?var-name' placeholder strings.
- expand() substitutes ?vars from args_dict, generates new Card instances
  with auto-assigned ids and :parents set to [source_card_id, macro_card_id].
- Homoiconic: macro body is stored as plain Python data (parsed from sexp card kvs),
  so the same sexp parser from cardstore is reused.
- Not a full Lisp evaluator — we only do literal substitution of ?var tokens.
  Nested list substitution is also handled recursively.
"""

from __future__ import annotations
import hashlib
import datetime
from typing import Any, Optional
from wiki.lib.cardstore import Card


class MacroEngine:
    def __init__(self):
        self._macros: dict[str, Card] = {}  # name → macro Card

    def register(self, macro_card: Card) -> None:
        """Register a macro Card. Keyed by :name field in kvs."""
        name = macro_card.kvs.get("name")
        if name is None:
            raise ValueError(f"macro card {macro_card.id!r} missing :name field")
        self._macros[str(name)] = macro_card

    def expand(self, macro_name: str, args_dict: dict[str, Any], source_card_id: str) -> list[Card]:
        """
        Expand macro_name with args_dict substituted for ?params.
        Returns list of new Cards, each with :parents = [source_card_id, macro_card.id].
        """
        macro = self._macros.get(macro_name)
        if macro is None:
            raise KeyError(f"Macro {macro_name!r} not registered")

        params = macro.kvs.get("params", [])
        body_templates = macro.kvs.get("body", [])

        # Build substitution map: ?param-name → value
        bindings = {}
        if isinstance(params, list):
            for p in params:
                p_key = str(p).lstrip("?")
                if p_key in args_dict:
                    bindings[f"?{p_key}"] = args_dict[p_key]
        # Also accept direct ?key keys in args_dict
        for k, v in args_dict.items():
            if k.startswith("?"):
                bindings[k] = v
            else:
                bindings[f"?{k}"] = v

        new_cards = []
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for template in (body_templates if isinstance(body_templates, list) else []):
            if not isinstance(template, dict):
                continue
            # Substitute bindings into all values
            resolved_kvs = _subst_dict(template, bindings)
            # Generate id from content hash
            content_sig = f"{macro_name}|{source_card_id}|{sorted(resolved_kvs.items())}|{ts}"
            card_id = "m_" + hashlib.sha1(content_sig.encode()).hexdigest()[:8]
            card_type = resolved_kvs.pop("type", "derived")
            resolved_kvs["parents"] = [source_card_id, macro.id]
            resolved_kvs["derived_from"] = macro.id
            resolved_kvs["generated_at"] = ts
            new_cards.append(Card(id=card_id, type=str(card_type), kvs=resolved_kvs))

        return new_cards


# ---------------------------------------------------------------------------
# Substitution helpers
# ---------------------------------------------------------------------------

def _subst_val(val: Any, bindings: dict[str, Any]) -> Any:
    """Recursively substitute ?var placeholders in val."""
    if isinstance(val, str):
        # Check exact match first
        if val in bindings:
            return bindings[val]
        # Inline substitution (e.g. "experiment for ?paper-id")
        result = val
        for placeholder, replacement in bindings.items():
            result = result.replace(placeholder, str(replacement))
        return result
    if isinstance(val, list):
        return [_subst_val(item, bindings) for item in val]
    if isinstance(val, dict):
        return _subst_dict(val, bindings)
    return val


def _subst_dict(d: dict, bindings: dict[str, Any]) -> dict:
    return {k: _subst_val(v, bindings) for k, v in d.items()}
