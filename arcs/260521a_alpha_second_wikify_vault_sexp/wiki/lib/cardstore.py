"""
CardStore — unified card store for the sexp/EDN wiki.

Design choices:
- Card is a dataclass with id, type (atom|rule|macro|view|derived), and open kvs dict.
- Storage is in-memory dict; persistence via dump_edn/load_edn.
- EDN format: one card per line as (card <id> :type <type> :key val ...).
  We write a minimal sexp parser (~80 lines) by hand — no third-party edn lib needed.
  Fallback: if a YAML round-trip is requested, we support PyYAML, but default is sexp.
- Versioning: every update appends (timestamp, prev_kvs) to card.history list.
- Linking: find_links_to / find_links_from scan atom kvs for :subj/:obj fields.
"""

from __future__ import annotations
import re
import datetime
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Card dataclass
# ---------------------------------------------------------------------------

@dataclass
class Card:
    id: str
    type: str  # atom | rule | macro | view | derived
    kvs: dict = field(default_factory=dict)
    history: list = field(default_factory=list)  # list of (ts, prev_kvs)

    def get(self, key, default=None):
        return self.kvs.get(key, default)

    def __repr__(self):
        return f"Card(id={self.id!r}, type={self.type!r}, kvs={self.kvs!r})"


# ---------------------------------------------------------------------------
# CardStore
# ---------------------------------------------------------------------------

class CardStore:
    def __init__(self):
        self._store: dict[str, Card] = {}

    # --- CRUD ---------------------------------------------------------------

    def add(self, card: Card) -> None:
        if card.id in self._store:
            raise ValueError(f"Card {card.id!r} already exists; use update()")
        self._store[card.id] = card

    def get(self, id: str) -> Optional[Card]:
        return self._store.get(id)

    def delete(self, id: str) -> None:
        self._store.pop(id, None)

    def update(self, id: str, **kvs) -> Card:
        card = self._store[id]
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        card.history.append((ts, dict(card.kvs)))
        card.kvs.update(kvs)
        return card

    def all_cards(self) -> list[Card]:
        return list(self._store.values())

    # --- Query helpers -------------------------------------------------------

    def query(self, predicate_fn: Callable[[Card], bool]) -> list[Card]:
        return [c for c in self._store.values() if predicate_fn(c)]

    def find_by_type(self, type_str: str) -> list[Card]:
        return self.query(lambda c: c.type == type_str)

    def find_links_to(self, target_id: str, link_pred: Optional[str] = None) -> list[Card]:
        """Find cards whose kvs :obj == target_id (optionally filtered by :pred)."""
        results = []
        for c in self._store.values():
            if c.kvs.get("obj") == target_id:
                if link_pred is None or c.kvs.get("pred") == link_pred:
                    results.append(c)
        return results

    def find_links_from(self, source_id: str, link_pred: Optional[str] = None) -> list[Card]:
        """Find cards whose kvs :subj == source_id (optionally filtered by :pred)."""
        results = []
        for c in self._store.values():
            if c.kvs.get("subj") == source_id:
                if link_pred is None or c.kvs.get("pred") == link_pred:
                    results.append(c)
        return results

    def resolve_lazy(self, card: Card) -> Card:
        """
        Replace <eval>...</eval> expressions in card kvs :body with evaluated results.
        Supports: latest-of <card-id>, count-links-to <card-id>.
        Returns a *new* Card with resolved values (original untouched).
        """
        import copy
        resolved = copy.deepcopy(card)
        body = resolved.kvs.get("body", "")
        if not isinstance(body, str):
            return resolved

        def replacer(m):
            expr = m.group(1).strip()
            parts = expr.split()
            if parts[0] == "latest-of" and len(parts) == 2:
                ref = self.get(parts[1])
                if ref:
                    return str(ref.kvs.get("body", f"[no body on {parts[1]}]"))
                return f"[not found: {parts[1]}]"
            if parts[0] == "count-links-to" and len(parts) == 2:
                count = len(self.find_links_to(parts[1]))
                return str(count)
            return m.group(0)  # unknown expr, leave as-is

        resolved.kvs["body"] = re.sub(r"<eval>(.*?)</eval>", replacer, body)
        return resolved

    # --- EDN serialization ---------------------------------------------------

    def dump_edn(self, path: str) -> None:
        lines = []
        for card in self._store.values():
            parts = [f"(card {_edn_str(card.id)} :type {_edn_str(card.type)}"]
            for k, v in card.kvs.items():
                parts.append(f"  :{k} {_edn_val(v)}")
            if card.history:
                parts.append(f"  :_history {_edn_val(card.history)}")
            lines.append("\n".join(parts) + ")")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(lines) + "\n")

    def load_edn(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        tokens = tokenize(text)
        pos = [0]
        while pos[0] < len(tokens):
            form = parse_form(tokens, pos)
            if form is None:
                break
            if isinstance(form, list) and len(form) >= 2 and form[0] == "card":
                card = _form_to_card(form)
                self._store[card.id] = card


# ---------------------------------------------------------------------------
# Minimal sexp/EDN tokenizer + parser  (~80 lines)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r'"(?:[^"\\]|\\.)*"'      # string literal
    r"|[()]"                   # parens
    r"|:[\w\-]+"              # :keyword
    r"|true|false|nil"        # literals
    r"|[\-+]?\d+\.\d*"       # float
    r"|[\-+]?\d+"             # int
    r"|[^\s()\",:;]+"         # symbol / bare token
)


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def parse_form(tokens: list[str], pos: list[int]):
    """Parse one form from tokens[pos[0]]; advance pos[0]. Returns Python value."""
    if pos[0] >= len(tokens):
        return None
    tok = tokens[pos[0]]
    pos[0] += 1

    if tok == "(":
        items = []
        while pos[0] < len(tokens) and tokens[pos[0]] != ")":
            item = parse_form(tokens, pos)
            if item is not None:
                items.append(item)
        if pos[0] < len(tokens):
            pos[0] += 1  # consume ")"
        return items
    elif tok == ")":
        return None
    elif tok.startswith('"'):
        return tok[1:-1].replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
    elif tok == "true":
        return True
    elif tok == "false":
        return False
    elif tok == "nil":
        return None
    elif tok.startswith(":"):
        return tok  # keyword kept as ":keyword"
    else:
        # try int, float, else symbol
        try:
            return int(tok)
        except ValueError:
            pass
        try:
            return float(tok)
        except ValueError:
            pass
        return tok  # symbol


def _form_to_card(form: list) -> Card:
    """Convert (card id :type t :k v ...) form to Card."""
    assert form[0] == "card", form[0]
    card_id = str(form[1])
    kvs = {}
    history = []
    i = 2
    while i < len(form) - 1:
        key = form[i]
        val = form[i + 1]
        i += 2
        if not isinstance(key, str) or not key.startswith(":"):
            continue
        field_name = key[1:]  # strip ":"
        if field_name == "_history":
            history = val if isinstance(val, list) else []
        elif field_name == "type":
            pass  # handled below
        else:
            kvs[field_name] = val
    card_type = kvs.pop("type", "atom")  # :type may land in kvs
    # re-scan for :type at top level
    i = 2
    while i < len(form) - 1:
        if form[i] == ":type":
            card_type = str(form[i + 1])
            break
        i += 2
    card = Card(id=card_id, type=card_type, kvs=kvs, history=history)
    return card


# ---------------------------------------------------------------------------
# EDN value serializers
# ---------------------------------------------------------------------------

def _edn_str(s: str) -> str:
    escaped = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _edn_val(v: Any) -> str:
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return str(v)
    if isinstance(v, str):
        return _edn_str(v)
    if isinstance(v, list):
        inner = " ".join(_edn_val(x) for x in v)
        return f"({inner})"
    if isinstance(v, tuple):
        inner = " ".join(_edn_val(x) for x in v)
        return f"({inner})"
    if isinstance(v, dict):
        pairs = " ".join(f":{k} {_edn_val(val)}" for k, val in v.items())
        return f"({pairs})"
    return _edn_str(str(v))
