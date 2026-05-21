"""Rule: a (when AND ... [constraint]) → then pattern, parsed from markdown."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

_VAR_RE = re.compile(r"^\?[A-Za-z][A-Za-z0-9_]*$")


def is_var(x: Any) -> bool:
    return isinstance(x, str) and bool(_VAR_RE.match(x))


@dataclass
class Pattern:
    subj: str
    pred: str
    obj: str

    @classmethod
    def from_dict(cls, d: dict) -> "Pattern":
        return cls(subj=str(d["subj"]), pred=str(d["pred"]), obj=str(d["obj"]))

    def vars(self) -> list[str]:
        return [v for v in (self.subj, self.pred, self.obj) if is_var(v)]


_SAFE_CONSTRAINT_RE = re.compile(r"^[\s\?A-Za-z0-9_:.\-/<>=!\"']+$")


@dataclass
class Rule:
    id: str
    when: list[Pattern]
    then: list[Pattern]
    constraint: Optional[str] = None
    source_path: str = ""
    body_md: str = ""

    @classmethod
    def from_markdown(cls, path: str | Path) -> "Rule":
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        if not text.startswith("---"):
            raise ValueError(f"{p}: missing frontmatter")
        _, fm, body = text.split("---", 2)
        meta = yaml.safe_load(fm)
        rule_id = str(meta["id"])
        when = [Pattern.from_dict(x) for x in meta["when"]]
        then = [Pattern.from_dict(x) for x in meta["then"]]
        constraint = meta.get("constraint")
        if constraint is not None:
            constraint = str(constraint)
            if not _SAFE_CONSTRAINT_RE.match(constraint):
                raise ValueError(f"{p}: unsafe constraint chars: {constraint!r}")
        return cls(
            id=rule_id,
            when=when,
            then=then,
            constraint=constraint,
            source_path=str(p),
            body_md=body.strip(),
        )

    def all_vars(self) -> list[str]:
        seen: list[str] = []
        for pat in self.when + self.then:
            for v in pat.vars():
                if v not in seen:
                    seen.append(v)
        return seen


def load_rules_dir(dir_path: str | Path) -> list[Rule]:
    d = Path(dir_path)
    rules: list[Rule] = []
    for p in sorted(d.glob("r*.md")):
        rules.append(Rule.from_markdown(p))
    return rules


def eval_constraint(expr: str, binding: dict[str, str]) -> bool:
    """Evaluate a safe constraint expression after substituting bindings.

    Allowed: comparison ops on string literals (we render every binding
    as a quoted string before eval). Nothing else.
    """
    rendered = expr
    for var, val in binding.items():
        rendered = rendered.replace(var, repr(val))
    if not re.fullmatch(r"[\s\"'A-Za-z0-9_:.\-/<>=!()]+", rendered):
        raise ValueError(f"refusing to eval constraint after sub: {rendered!r}")
    return bool(eval(rendered, {"__builtins__": {}}, {}))
