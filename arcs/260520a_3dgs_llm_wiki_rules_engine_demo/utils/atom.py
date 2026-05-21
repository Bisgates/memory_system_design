"""Atom: a (subj, pred, obj) triple with provenance."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional


def _atom_id(subj: str, pred: str, obj: str) -> str:
    h = hashlib.sha1(f"{subj}|{pred}|{obj}".encode("utf-8")).hexdigest()[:8]
    return f"a_{h}"


@dataclass(frozen=True)
class Atom:
    subj: str
    pred: str
    obj: str
    source: str = ""
    derived_from: Optional[str] = None
    parents: tuple = field(default_factory=tuple)

    @property
    def id(self) -> str:
        return _atom_id(self.subj, self.pred, self.obj)

    @property
    def key(self) -> tuple:
        return (self.subj, self.pred, self.obj)

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "subj": self.subj,
            "pred": self.pred,
            "obj": self.obj,
            "source": self.source,
            "derived_from": self.derived_from,
            "parents": list(self.parents),
        }
        return d


class AtomStore:
    """Dedup-by-key set of atoms with (subj, pred) → atoms index."""

    def __init__(self) -> None:
        self._by_key: dict[tuple, Atom] = {}
        self._by_sp: dict[tuple, list[Atom]] = {}
        self._by_po: dict[tuple, list[Atom]] = {}

    def __len__(self) -> int:
        return len(self._by_key)

    def __iter__(self):
        return iter(self._by_key.values())

    def __contains__(self, atom: Atom) -> bool:
        return atom.key in self._by_key

    def add(self, atom: Atom) -> bool:
        if atom.key in self._by_key:
            return False
        self._by_key[atom.key] = atom
        self._by_sp.setdefault((atom.subj, atom.pred), []).append(atom)
        self._by_po.setdefault((atom.pred, atom.obj), []).append(atom)
        return True

    def by_pred(self, pred: str) -> list[Atom]:
        return [a for a in self._by_key.values() if a.pred == pred]

    def by_subj_pred(self, subj: str, pred: str) -> list[Atom]:
        return list(self._by_sp.get((subj, pred), ()))

    def by_pred_obj(self, pred: str, obj: str) -> list[Atom]:
        return list(self._by_po.get((pred, obj), ()))

    def get(self, atom_id: str) -> Optional[Atom]:
        for a in self._by_key.values():
            if a.id == atom_id:
                return a
        return None

    def all_atoms(self) -> list[Atom]:
        return list(self._by_key.values())
