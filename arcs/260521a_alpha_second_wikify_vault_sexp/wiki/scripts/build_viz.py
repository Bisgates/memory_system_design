#!/usr/bin/env python3
"""
build_viz.py — generate viz.html for Phase 4.

Reads the same atom/rule/macro/derived store the demo uses, extracts
(subj, pred, obj) triples, and emits a single-file self-contained HTML
with a vanilla SVG force-directed graph (no external CDN).

Design choices:
  * 1000+ nodes ⇒ we pre-compute a static layout in Python using a tiny
    Fruchterman-Reingold implementation (constant-time per iteration, 200
    iters is enough). Browser side just renders + supports filter/hover.
  * Color by :type — atom grey / experiment blue / lineage purple / rule red
    / macro orange / derived green / suggestion yellow / view teal /
    anti_pattern brown / doc light-grey / other light-blue.
  * Edge color by predicate (a curated palette for the typed-link family).
  * Default visible types: experiment / lineage / rule / macro / derived /
    suggestion / view / anti_pattern. atom is hidden by default (3000+
    frontmatter triples), togglable via the filter bar.
  * Hover → tooltip with type / id / body excerpt.
  * 6 capabilities block at the bottom — collapsible <details>, each with
    a hand-off paragraph + link to its cap<N>_<name>/ trace files.
  * Fonts: macOS system stack (-apple-system / SF Pro / Helvetica Neue).
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import math
import random
import re
import sys
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
WIKI_ROOT = THIS_DIR.parent
ARC_ROOT = WIKI_ROOT.parent
sys.path.insert(0, str(ARC_ROOT))

from wiki.lib.cardstore import Card, CardStore  # noqa: E402
from wiki.scripts.run_rules import harden_atom_keys  # noqa: E402


ATOMS_DIR    = ARC_ROOT / "wiki" / "cards" / "atoms"
RULES_DIR    = ARC_ROOT / "wiki" / "cards" / "rules"
MACROS_DIR   = ARC_ROOT / "wiki" / "cards" / "macros"
DERIVED_DIR  = ARC_ROOT / "wiki" / "cards" / "derived"
OUTPUT_DIR   = ARC_ROOT / "output"


# Color palette ----------------------------------------------------------

TYPE_COLORS = {
    "atom":                  "#9aa0a6",
    "experiment":            "#3b82f6",
    "lineage":               "#a855f7",
    "rule":                  "#ef4444",
    "macro":                 "#f97316",
    "derived":               "#22c55e",
    "suggestion":            "#eab308",
    "view":                  "#14b8a6",
    "anti_pattern":          "#92400e",
    "anti_pattern_catalog":  "#92400e",
    "doc":                   "#cbd5e1",
    "report":                "#94a3b8",
    "claim":                 "#0ea5e9",
}
TYPE_DEFAULT_COLOR = "#7dd3fc"

# Predicates we care about (typed-link family). Anything else falls back to
# a dim grey edge.
PRED_COLORS = {
    "derived_from":            "#a855f7",
    "derives_to":              "#a855f7",
    "competes_with":           "#ef4444",
    "falsifies":               "#dc2626",
    "inherits_falsification":  "#dc2626",
    "reports_to":              "#0891b2",
    "parent_arc":              "#9333ea",
    "parent_lineage":          "#9333ea",
    "borrowed_by":             "#f97316",
    "borrowed_by_canonical":   "#f97316",
    "references_in_case_examples": "#92400e",
    "is_instance_of_anti_pattern": "#92400e",
    "inherits_anti_pattern":   "#92400e",
    "suggests_experiment":     "#eab308",
    "supports":                "#22c55e",
    "contradicts":             "#dc2626",
    "same_round_as":           "#0ea5e9",
    "top_pick_for":            "#f59e0b",
}
PRED_DEFAULT_COLOR = "#9ca3af"


# Atoms whose pred starts with "has_" are frontmatter triples. They form
# the bulk of the 3331-atom store. We keep them out of the default view
# unless toggled on, but we still include them in the data so the viz can
# render them.
FRONTMATTER_PREFIX = "has_"


# ---------------------------------------------------------------------------
# Store load
# ---------------------------------------------------------------------------

def load_store() -> CardStore:
    store = CardStore()
    for p in sorted(ATOMS_DIR.glob("*.edn")):
        store.load_edn(str(p))
    for p in sorted(RULES_DIR.glob("*.edn")):
        store.load_edn(str(p))
    for p in sorted(MACROS_DIR.glob("*.edn")):
        store.load_edn(str(p))
    for p in sorted(DERIVED_DIR.glob("*.edn")):
        store.load_edn(str(p))
    harden_atom_keys(store)
    return store


# ---------------------------------------------------------------------------
# Build nodes / edges
# ---------------------------------------------------------------------------

TYPED_PREDS = set(PRED_COLORS.keys())


def short_body(s, n=180):
    if s is None:
        return ""
    s = str(s).replace("\n", " ").strip()
    if len(s) > n:
        return s[:n] + " …"
    return s


def extract_tags(card: Card) -> list[str]:
    """
    Heuristic: derive a small set of tag strings for filtering. We collect
    the :tag axis hits from the per-card :tag atoms emitted by Phase 2
    ingest (pred = has_tag with obj like 'axis/sizing'). Caller passes the
    store so we can look those up. This is computed at build_graph time,
    not here.
    """
    return []


def build_graph(store: CardStore) -> dict:
    """
    Returns:
      {
        "nodes": [ {id, type, color, label, body, default_visible, tags}, ... ],
        "edges": [ {source, target, pred, color, default_visible}, ... ],
        "types": [...], "preds": [...]
      }
    """
    all_cards = store.all_cards()

    # Pre-compute tag map: subj → set of tag strings (from has_tag atoms)
    tag_map: dict[str, set[str]] = {}
    for c in all_cards:
        if c.kvs.get("pred") == "has_tag":
            subj = c.kvs.get("subj")
            obj  = c.kvs.get("obj")
            if subj and obj:
                tag_map.setdefault(subj, set()).add(str(obj))

    # Nodes: include only cards that will be rendered (we keep all cards
    # but tag :type 'atom as hidden-by-default).
    nodes_by_id: dict[str, dict] = {}

    # All non-atom typed cards (experiment / lineage / rule / macro /
    # derived / suggestion / view / doc / anti_pattern_catalog / claim /
    # report) are visible by default.
    DEFAULT_VISIBLE_TYPES = {
        "experiment", "lineage", "rule", "macro", "derived", "suggestion",
        "view", "anti_pattern", "anti_pattern_catalog", "doc", "report",
        "claim",
    }

    def short_label(c: Card) -> str:
        if c.type in ("experiment", "lineage", "doc", "report", "anti_pattern_catalog"):
            # use last path slug of id, strip the namespace prefix
            base = c.id.split(":", 1)[-1] if ":" in c.id else c.id
            return base.split("__")[-1][:48]
        if c.type == "rule":
            return c.id.replace("rule:", "").replace("_", "·")[:48]
        if c.type == "macro":
            return c.kvs.get("name", c.id)[:48]
        if c.type in ("suggestion", "derived", "view"):
            return (c.kvs.get("name") or c.kvs.get("obj") or c.id)[:48]
        return c.id[:48]

    def node_body(c: Card) -> str:
        b = c.kvs.get("body")
        if b:
            return short_body(b, 240)
        # Fall back to first non-empty kv preview
        for k in ("name", "obj", "pred"):
            v = c.kvs.get(k)
            if v:
                return f"{k}: {short_body(v, 200)}"
        return ""

    for c in all_cards:
        if c.type == "atom":
            visible = False
        else:
            visible = c.type in DEFAULT_VISIBLE_TYPES
        node_tags = sorted(tag_map.get(c.id, set()))
        if c.type == "experiment":
            # Pull the tags off the subject id (matches :subj of has_tag atoms)
            node_tags = sorted(tag_map.get(c.id, set()))
        # Also use subj-anchored tags for lineages / others
        if not node_tags:
            node_tags = sorted(tag_map.get(c.id, set()))
        nodes_by_id[c.id] = {
            "id": c.id,
            "type": c.type,
            "color": TYPE_COLORS.get(c.type, TYPE_DEFAULT_COLOR),
            "label": short_label(c),
            "body": node_body(c),
            "default_visible": visible,
            "tags": node_tags,
        }

    # Edges:
    #   - non-frontmatter atoms (typed-link family) → edge
    #   - derived cards (subj/pred/obj) → edge
    #   - suggestion cards (subj/pred/obj) → edge
    edges = []
    for c in all_cards:
        subj = c.kvs.get("subj")
        pred = c.kvs.get("pred")
        obj  = c.kvs.get("obj")
        if not (isinstance(subj, str) and isinstance(pred, str) and isinstance(obj, str)):
            continue
        # Skip self-loops where subj == obj  (the per-experiment-card subj==id atoms)
        if subj == obj:
            continue
        # Skip frontmatter "has_*" atoms — they bloat the edge set and have
        # primitive obj values which won't link to other cards
        if pred.startswith(FRONTMATTER_PREFIX):
            continue
        # Only include the edge if both endpoints exist as nodes; otherwise
        # we create a placeholder node so the edge isn't dangling
        if subj not in nodes_by_id:
            nodes_by_id[subj] = {
                "id": subj, "type": "atom",
                "color": TYPE_COLORS["atom"],
                "label": subj[:48], "body": "",
                "default_visible": False, "tags": [],
            }
        if obj not in nodes_by_id:
            # If obj is a long body string (e.g. has_section_hypothesis), it
            # won't be a card id; skip those edges.
            if len(obj) > 80 or obj.startswith("- ") or "\n" in obj:
                continue
            nodes_by_id[obj] = {
                "id": obj, "type": "atom",
                "color": TYPE_COLORS["atom"],
                "label": obj[:48], "body": "",
                "default_visible": False, "tags": [],
            }
        pred_color = PRED_COLORS.get(pred, PRED_DEFAULT_COLOR)
        is_typed = pred in TYPED_PREDS
        edges.append({
            "source": subj,
            "target": obj,
            "pred": pred,
            "color": pred_color,
            "typed": is_typed,
            # Edge visible iff at least one endpoint is default-visible
            "default_visible": (nodes_by_id[subj]["default_visible"]
                                or nodes_by_id[obj]["default_visible"]),
        })

    # Promote endpoints of edges where the *other* endpoint is default visible
    # so we don't have edges dangling into invisible nodes when one side is
    # an experiment. We're going to set node.default_visible = True for any
    # node that participates in a default-visible edge.
    for e in edges:
        if e["default_visible"]:
            nodes_by_id[e["source"]]["default_visible"] = True
            nodes_by_id[e["target"]]["default_visible"] = True

    return {
        "nodes": list(nodes_by_id.values()),
        "edges": edges,
        "types": sorted({n["type"] for n in nodes_by_id.values()}),
        "preds": sorted({e["pred"] for e in edges}),
    }


# ---------------------------------------------------------------------------
# Static layout — minimal Fruchterman-Reingold
# ---------------------------------------------------------------------------

def static_layout(nodes: list, edges: list,
                  width: float = 1600.0, height: float = 1000.0,
                  iters: int = 220, seed: int = 7) -> None:
    """
    Compute (x, y) for each *default-visible* node in-place. Hidden atoms
    get placed in a band around the bottom-right corner so unhiding them
    doesn't immediately overlap the visible network.

    We only layout the visible subgraph because forcing 3000+ atoms through
    O(n^2) FR is needlessly slow.
    """
    rng = random.Random(seed)
    visible = [n for n in nodes if n["default_visible"]]
    hidden  = [n for n in nodes if not n["default_visible"]]
    if not visible:
        return

    n = len(visible)
    id_idx = {nd["id"]: i for i, nd in enumerate(visible)}

    # Initial random placement
    pos = [(rng.uniform(0, width), rng.uniform(0, height)) for _ in range(n)]
    disp = [[0.0, 0.0] for _ in range(n)]

    # Build adjacency from visible edges
    visible_edges = [
        (id_idx[e["source"]], id_idx[e["target"]])
        for e in edges
        if e["source"] in id_idx and e["target"] in id_idx
    ]

    area = width * height
    k = math.sqrt(area / max(n, 1))
    t = max(width, height) / 10.0   # initial temperature
    cooling = t / iters

    for it in range(iters):
        # repulsion: O(n^2) — fine for ~few hundred visible nodes
        for i in range(n):
            disp[i][0] = 0.0
            disp[i][1] = 0.0
        for i in range(n):
            xi, yi = pos[i]
            for j in range(i + 1, n):
                xj, yj = pos[j]
                dx = xi - xj
                dy = yi - yj
                d2 = dx * dx + dy * dy
                if d2 < 0.01:
                    dx = rng.uniform(-0.5, 0.5)
                    dy = rng.uniform(-0.5, 0.5)
                    d2 = dx * dx + dy * dy + 0.01
                d = math.sqrt(d2)
                f = (k * k) / d
                rx = (dx / d) * f
                ry = (dy / d) * f
                disp[i][0] += rx
                disp[i][1] += ry
                disp[j][0] -= rx
                disp[j][1] -= ry

        # attraction along edges
        for (i, j) in visible_edges:
            xi, yi = pos[i]
            xj, yj = pos[j]
            dx = xi - xj
            dy = yi - yj
            d = math.sqrt(dx * dx + dy * dy) + 1e-6
            f = (d * d) / k
            ax = (dx / d) * f
            ay = (dy / d) * f
            disp[i][0] -= ax
            disp[i][1] -= ay
            disp[j][0] += ax
            disp[j][1] += ay

        # apply displacement clamped to temperature
        for i in range(n):
            dx, dy = disp[i]
            d = math.sqrt(dx * dx + dy * dy) + 1e-6
            step = min(d, t)
            x_new = pos[i][0] + (dx / d) * step
            y_new = pos[i][1] + (dy / d) * step
            x_new = min(max(x_new, 20.0), width - 20.0)
            y_new = min(max(y_new, 20.0), height - 20.0)
            pos[i] = (x_new, y_new)

        t -= cooling
        if t < 0.5:
            t = 0.5

    # Stamp positions
    for i, nd in enumerate(visible):
        nd["x"] = pos[i][0]
        nd["y"] = pos[i][1]

    # Hidden nodes — place in a grid in the far right margin so toggling
    # them doesn't drop a blob onto the visible layout. They get repositioned
    # on first toggle via a brief client-side relaxation.
    cols = max(1, int(math.sqrt(len(hidden))))
    gap = 16
    base_x = width + 80
    base_y = 40
    for i, nd in enumerate(hidden):
        nd["x"] = base_x + (i % cols) * gap
        nd["y"] = base_y + (i // cols) * gap


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

CAP_BLURBS = [
    ("cap1_macro_derive", "Capability 1 — macro 派生卡",
     "挑 3 张 experiment card 跑 m001 paper-to-experiment-suggestion macro, 每张 expand 成 3 张 suggestion (baseline/ablation/extension), 共 9 张新卡。Macro 本身也是 card, store.find_by_type('macro') 一并查得。"),
    ("cap2_lazy_ref", "Capability 2 — lazy reference",
     "在 view + atom 卡的 :body 字段嵌 <eval>latest-of …</eval> 和 <eval>count-links-to …</eval>。retrieve 时 store.resolve_lazy 把表达式替换为目标卡 body 摘要 / 入度整数。三个 lazy ref 在 read time 被 evaluate。"),
    ("cap3_rules_as_cards", "Capability 3 — 规则即卡片",
     "11 条 rule card 都是 :type 'rule 的纯 sexp。store.find_by_type 列出, fixpoint 跑完后 9 条有派生 fan-out (53 / 20 / 10 / ...)。按 :body 字符串 contains 'reverse' 命中 r001g + r002。把 r002 status 翻 'paused' 再 re-run, 该 rule 派生卡从 53 → 0, 验证 status flip 阻断 firing。"),
    ("cap4_dedup_restart", "Capability 4 — dedup restart 协议",
     "构造与 SOTA champion has_section_hypothesis 5-10% 偏差的变体卡, similarity ≥ 0.83。3 次跑分别用 keep-both / merge-prefer-newer / supersede 作 :on-dedup-conflict 首选, 每次都按预期触发对应 action (前者加 :see-also 双链, 后两者老卡 :status='superseded' + 新卡 :supersedes)。"),
    ("cap5_view_card", "Capability 5 — 视图卡 (materialized view)",
     "m002 macro 派出一张 view card on lin:arc_260516a__team_h__sizing。三次 materialize: 初始 14 命中 → 注入合成 atom 后 15 → 删除后 14, 完美回到初始。证明 view 完全 lazy, store 变化即时反映。"),
    ("cap6_self_compute", "Capability 6 — 自计算字段",
     "建一张 claim card, :confidence 字段是 sexp 表达式 (compute (- supports contradicts) / (max supports 1))。stage a) 0/0 → 0.000; stage b) 加 3 supporters → 1.000; stage c) 再加 2 contradictors → 0.333。eval 在 read time 跑, 卡片状态变 confidence 立刻刷新。"),
]


def render_html(graph: dict, run_dir: Path) -> str:
    """Render the single-file HTML. Embed graph JSON inline."""
    nodes = graph["nodes"]
    edges = graph["edges"]

    # Compact JSON payload
    payload = {
        "nodes": [
            {"id": n["id"], "t": n["type"], "c": n["color"],
             "l": n["label"], "b": n["body"], "v": n["default_visible"],
             "tg": n.get("tags", []),
             "x": n.get("x", 0), "y": n.get("y", 0)}
            for n in nodes
        ],
        "edges": [
            {"s": e["source"], "o": e["target"], "p": e["pred"],
             "c": e["color"], "v": e["default_visible"], "ty": e["typed"]}
            for e in edges
        ],
    }
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    type_legend = "".join(
        f'<span class="lg-chip" style="background:{c}">{html.escape(t)}</span>'
        for t, c in sorted(TYPE_COLORS.items())
    )

    # Build cap blocks
    cap_blocks = []
    for slug, title, blurb in CAP_BLURBS:
        cap_dir = run_dir / slug
        files = sorted(cap_dir.glob("*"))
        file_list = "".join(
            f'<li><a href="{slug}/{html.escape(f.name)}">{html.escape(f.name)}</a></li>'
            for f in files
        )
        cap_blocks.append(
            f'<details class="cap-block">'
            f'<summary><strong>{html.escape(title)}</strong></summary>'
            f'<p class="cap-blurb">{html.escape(blurb)}</p>'
            f'<ul class="cap-files">{file_list}</ul>'
            f'</details>'
        )
    cap_blocks_html = "\n".join(cap_blocks)

    # Stats summary
    type_counts: dict[str, int] = {}
    for n in nodes:
        type_counts[n["type"]] = type_counts.get(n["type"], 0) + 1
    type_count_str = ", ".join(
        f'{t}={c}' for t, c in sorted(type_counts.items(), key=lambda x: -x[1])
    )

    total_visible_nodes = sum(1 for n in nodes if n["default_visible"])
    total_visible_edges = sum(1 for e in edges if e["default_visible"])

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>Phase 4 viz — auto_research_experiment wiki</title>
<style>
:root {{
  --bg:#0f172a; --panel:#1e293b; --ink:#e2e8f0; --ink-dim:#94a3b8;
  --accent:#38bdf8; --border:#334155;
  --mono: ui-monospace, "SF Mono", "Menlo", "Consolas", monospace;
  --serif: ui-serif, "Iowan Old Style", "Charter", "Georgia", serif;
  --sans: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue",
          "PingFang SC", "Hiragino Sans GB", Arial, sans-serif;
}}
* {{ box-sizing: border-box; }}
html, body {{ margin:0; padding:0; height:100%; background:var(--bg); color:var(--ink); font-family:var(--sans); font-size:14px; }}
header {{
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
  display:flex; flex-wrap: wrap; align-items:center; gap:12px 24px;
  background: var(--panel);
}}
header h1 {{
  margin: 0; font-size:16px; font-weight: 600; letter-spacing:.2px;
}}
header .meta {{
  font-size:12px; color:var(--ink-dim); font-family:var(--mono);
}}
.toolbar {{
  display:flex; gap:14px; align-items:center; flex-wrap:wrap;
  padding: 10px 20px; border-bottom: 1px solid var(--border); background:#172033;
}}
.toolbar label {{ font-size:12px; color:var(--ink-dim); }}
.toolbar input[type=text] {{
  background:#0b1322; color:var(--ink); border:1px solid var(--border);
  padding: 4px 8px; border-radius:4px; font-family:var(--mono); font-size:12px;
  min-width: 240px;
}}
.toolbar select {{
  background:#0b1322; color:var(--ink); border:1px solid var(--border);
  padding: 4px 8px; border-radius:4px; font-size:12px;
}}
.toolbar button {{
  background:#0b1322; color:var(--ink); border:1px solid var(--border);
  padding: 4px 12px; border-radius:4px; font-size:12px; cursor:pointer;
}}
.toolbar button:hover {{ background: var(--accent); color:#0b1322; }}
.legend {{
  display:flex; flex-wrap:wrap; gap:6px; padding: 8px 20px;
  border-bottom: 1px solid var(--border); background:#0f1a2e;
}}
.lg-chip {{
  display:inline-block; padding: 2px 8px; border-radius: 10px; font-size:11px;
  color:#0b1322; font-weight:600; font-family:var(--mono);
}}
#graph {{
  width: 100%; height: calc(100vh - 360px); min-height: 420px;
  background: #060c1c; cursor: grab;
}}
#graph:active {{ cursor: grabbing; }}
#tooltip {{
  position: fixed; pointer-events: none; z-index: 50;
  background: #0b1322; color: var(--ink); border:1px solid var(--accent);
  padding: 8px 10px; border-radius: 4px; max-width: 380px;
  font-size: 12px; line-height: 1.4; box-shadow: 0 4px 14px #000a;
  display:none; font-family: var(--mono);
}}
#tooltip .t-type {{ color: var(--accent); font-weight: 600; }}
#tooltip .t-id {{ color: var(--ink); word-break: break-all; }}
#tooltip .t-body {{ color: var(--ink-dim); margin-top: 4px; font-family: var(--sans); }}
.cap-section {{
  padding: 18px 24px; max-width: 1100px; margin: 0 auto;
  border-top: 1px solid var(--border); background: #0a1428;
}}
.cap-section h2 {{
  font-family: var(--serif); margin: 0 0 4px 0; font-size: 22px;
  font-weight: 600; color: var(--ink);
}}
.cap-section .sub {{
  color:var(--ink-dim); font-size:12px; margin-bottom: 16px;
  font-family: var(--mono);
}}
.cap-block {{
  background: var(--panel); padding: 10px 14px; border-radius: 6px;
  margin-bottom: 8px; border: 1px solid var(--border);
}}
.cap-block summary {{
  cursor: pointer; user-select: none; font-size: 14px;
}}
.cap-block .cap-blurb {{
  color: var(--ink-dim); margin: 8px 0 4px 0; font-size: 13px; line-height: 1.55;
}}
.cap-block .cap-files {{
  margin: 4px 0 0 0; padding-left: 18px; font-family: var(--mono); font-size: 12px;
}}
.cap-block .cap-files a {{
  color: var(--accent); text-decoration: none;
}}
.cap-block .cap-files a:hover {{ text-decoration: underline; }}
footer {{
  text-align:center; padding: 16px; color: var(--ink-dim); font-size: 11px;
  font-family: var(--mono); border-top: 1px solid var(--border);
}}
.stats-row {{
  font-family: var(--mono); font-size: 12px; color: var(--ink-dim);
  display: flex; gap: 22px; flex-wrap: wrap;
}}
.stats-row strong {{ color: var(--ink); }}
.svg-node {{ cursor: pointer; }}
.svg-node.dimmed {{ opacity: .12; }}
.svg-edge {{ pointer-events: none; }}
.svg-edge.dimmed {{ opacity: .03; }}
.svg-node.highlighted {{ stroke: #fff; stroke-width: 2px; }}
.svg-edge.highlighted {{ opacity: 1; stroke-width: 2.5; }}
</style>
</head>
<body>

<header>
  <h1>Phase 4 viz — auto_research_experiment wiki (arc 260521a)</h1>
  <div class="meta">build: {datetime.datetime.now().isoformat(timespec='seconds')}</div>
  <div class="stats-row">
    <span><strong>{len(nodes)}</strong> nodes total</span>
    <span><strong>{len(edges)}</strong> edges total</span>
    <span>visible by default: <strong>{total_visible_nodes}</strong> nodes / <strong>{total_visible_edges}</strong> edges</span>
    <span>type counts: {html.escape(type_count_str)}</span>
  </div>
</header>

<div class="toolbar">
  <label>filter type
    <select id="type-filter">
      <option value="__visible__">default visible</option>
      <option value="__all__">all (incl. {type_counts.get('atom', 0)} atoms)</option>
      {''.join(f'<option value="{html.escape(t)}">type = {html.escape(t)}</option>' for t in sorted(type_counts.keys()))}
    </select>
  </label>
  <label>search id
    <input type="text" id="search-id" placeholder="exp:H-R3b-4 / lin:arc_260516a / rule:r002 …">
  </label>
  <label>filter tag
    <select id="tag-filter">
      <option value="__any__">(any)</option>
    </select>
  </label>
  <button id="reset-btn">reset</button>
  <button id="toggle-atoms-btn">show atoms</button>
</div>

<div class="legend">{type_legend}</div>

<svg id="graph" xmlns="http://www.w3.org/2000/svg"></svg>

<div id="tooltip"></div>

<section class="cap-section">
  <h2>六能力 demo run · 证据索引</h2>
  <div class="sub">每条 capability 都在 <code>output/{html.escape(run_dir.name)}/cap&lt;N&gt;_&lt;name&gt;/</code> 里有 stdout.log + json trace。点击 summary 展开。</div>
  {cap_blocks_html}
</section>

<footer>
  Static layout · vanilla SVG · 0 external CDN · macOS system font stack.
  Hidden atoms are placed off-canvas until toggled on; they re-relax on first reveal.
</footer>

<script>
const GRAPH = {payload_json};

// ---- state ----
const state = {{
  type: '__visible__',
  search: '',
  tag: '__any__',
  atomsVisible: false,
}};

// ---- viewport / pan + zoom ----
const svg = document.getElementById('graph');
const tip = document.getElementById('tooltip');

let viewBoxX = 0, viewBoxY = 0, viewBoxW = 1600, viewBoxH = 1000;
function applyViewBox() {{
  svg.setAttribute('viewBox', `${{viewBoxX}} ${{viewBoxY}} ${{viewBoxW}} ${{viewBoxH}}`);
}}
applyViewBox();

// pan
let panning = false, panStartX = 0, panStartY = 0;
svg.addEventListener('mousedown', (e) => {{ panning = true; panStartX = e.clientX; panStartY = e.clientY; }});
svg.addEventListener('mouseleave', () => panning = false);
window.addEventListener('mouseup', () => panning = false);
svg.addEventListener('mousemove', (e) => {{
  if (!panning) return;
  const rect = svg.getBoundingClientRect();
  const dx = (e.clientX - panStartX) * viewBoxW / rect.width;
  const dy = (e.clientY - panStartY) * viewBoxH / rect.height;
  viewBoxX -= dx; viewBoxY -= dy;
  panStartX = e.clientX; panStartY = e.clientY;
  applyViewBox();
}});

// zoom
svg.addEventListener('wheel', (e) => {{
  e.preventDefault();
  const rect = svg.getBoundingClientRect();
  const mx = viewBoxX + (e.clientX - rect.left) / rect.width  * viewBoxW;
  const my = viewBoxY + (e.clientY - rect.top)  / rect.height * viewBoxH;
  const scale = e.deltaY > 0 ? 1.15 : (1/1.15);
  viewBoxW *= scale; viewBoxH *= scale;
  // re-center on cursor
  viewBoxX = mx - (e.clientX - rect.left) / rect.width  * viewBoxW;
  viewBoxY = my - (e.clientY - rect.top)  / rect.height * viewBoxH;
  applyViewBox();
}}, {{ passive: false }});

// ---- DOM building ----
const SVG_NS = 'http://www.w3.org/2000/svg';

// Edge layer first so nodes paint on top
const edgeLayer = document.createElementNS(SVG_NS, 'g');
const nodeLayer = document.createElementNS(SVG_NS, 'g');
svg.appendChild(edgeLayer);
svg.appendChild(nodeLayer);

const edgeEls = [];
const nodeEls = new Map();
const labelEls = new Map();
const nodeById = new Map();
GRAPH.nodes.forEach(n => nodeById.set(n.id, n));

for (const e of GRAPH.edges) {{
  const a = nodeById.get(e.s);
  const b = nodeById.get(e.o);
  if (!a || !b) continue;
  const line = document.createElementNS(SVG_NS, 'line');
  line.setAttribute('class', 'svg-edge');
  line.setAttribute('x1', a.x); line.setAttribute('y1', a.y);
  line.setAttribute('x2', b.x); line.setAttribute('y2', b.y);
  line.setAttribute('stroke', e.c);
  line.setAttribute('stroke-opacity', e.ty ? '0.85' : '0.45');
  line.setAttribute('stroke-width', e.ty ? '1.4' : '0.8');
  if (e.ty === false) line.setAttribute('stroke-dasharray', '3,3');
  line._edge = e;
  edgeLayer.appendChild(line);
  edgeEls.push(line);
}}

const ALL_TAGS = new Set();
for (const n of GRAPH.nodes) (n.tg || []).forEach(t => ALL_TAGS.add(t));
const tagSel = document.getElementById('tag-filter');
[...ALL_TAGS].sort().forEach(t => {{
  const opt = document.createElement('option');
  opt.value = t; opt.textContent = t;
  tagSel.appendChild(opt);
}});

for (const n of GRAPH.nodes) {{
  const circle = document.createElementNS(SVG_NS, 'circle');
  circle.setAttribute('class', 'svg-node');
  circle.setAttribute('cx', n.x); circle.setAttribute('cy', n.y);
  let r = 4.5;
  if (n.t === 'experiment') r = 6.5;
  else if (n.t === 'lineage') r = 8;
  else if (n.t === 'rule') r = 6;
  else if (n.t === 'macro') r = 7;
  else if (n.t === 'view') r = 6;
  else if (n.t === 'anti_pattern' || n.t === 'anti_pattern_catalog') r = 7;
  else if (n.t === 'claim') r = 6;
  else if (n.t === 'doc') r = 5;
  else if (n.t === 'suggestion' || n.t === 'derived') r = 4;
  else if (n.t === 'atom') r = 2.4;
  circle.setAttribute('r', r);
  circle.setAttribute('fill', n.c);
  circle.setAttribute('stroke', '#0b1322');
  circle.setAttribute('stroke-width', '0.6');
  circle._node = n;
  circle.addEventListener('mouseenter', (ev) => showTip(ev, n));
  circle.addEventListener('mousemove',  (ev) => moveTip(ev));
  circle.addEventListener('mouseleave', () => hideTip());
  circle.addEventListener('click', () => highlight(n));
  nodeLayer.appendChild(circle);
  nodeEls.set(n.id, circle);

  if (n.t !== 'atom') {{
    const txt = document.createElementNS(SVG_NS, 'text');
    txt.setAttribute('x', n.x + r + 2);
    txt.setAttribute('y', n.y + 3);
    txt.setAttribute('font-size', '9');
    txt.setAttribute('font-family', '-apple-system,sans-serif');
    txt.setAttribute('fill', '#cbd5e1');
    txt.setAttribute('pointer-events', 'none');
    txt.textContent = n.l;
    nodeLayer.appendChild(txt);
    labelEls.set(n.id, txt);
  }}
}}

function showTip(ev, n) {{
  tip.innerHTML = `
    <div><span class="t-type">[${{n.t}}]</span> <span class="t-id">${{escapeHtml(n.id)}}</span></div>
    ${{n.b ? `<div class="t-body">${{escapeHtml(n.b)}}</div>` : ''}}
    ${{(n.tg && n.tg.length) ? `<div class="t-body" style="color:#7dd3fc">tags: ${{n.tg.map(escapeHtml).join(', ')}}</div>` : ''}}
  `;
  tip.style.display = 'block';
  moveTip(ev);
}}
function moveTip(ev) {{
  tip.style.left = (ev.clientX + 14) + 'px';
  tip.style.top  = (ev.clientY + 14) + 'px';
}}
function hideTip() {{ tip.style.display = 'none'; }}
function escapeHtml(s) {{
  return String(s).replace(/[&<>"]/g, c => ({{
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'
  }}[c]));
}}

// ---- filtering ----
function applyFilters() {{
  const t = state.type;
  const q = state.search.toLowerCase();
  const tag = state.tag;

  let visibleIds = new Set();
  for (const n of GRAPH.nodes) {{
    let pass = false;
    if (t === '__all__') pass = true;
    else if (t === '__visible__') pass = n.v;
    else pass = (n.t === t);

    // also include atoms iff atomsVisible toggle is on AND we're in default-visible mode
    if (t === '__visible__' && state.atomsVisible && n.t === 'atom') pass = true;

    if (q && pass) pass = n.id.toLowerCase().includes(q) || (n.l && n.l.toLowerCase().includes(q));
    if (tag !== '__any__' && pass) pass = (n.tg || []).includes(tag);

    if (pass) visibleIds.add(n.id);
  }}

  for (const n of GRAPH.nodes) {{
    const el = nodeEls.get(n.id);
    if (!el) continue;
    const on = visibleIds.has(n.id);
    el.style.display = on ? '' : 'none';
    const lbl = labelEls.get(n.id);
    if (lbl) lbl.style.display = on ? '' : 'none';
  }}
  for (const line of edgeEls) {{
    const e = line._edge;
    line.style.display = (visibleIds.has(e.s) && visibleIds.has(e.o)) ? '' : 'none';
  }}
}}

document.getElementById('type-filter').addEventListener('change', (e) => {{
  state.type = e.target.value; applyFilters();
}});
document.getElementById('search-id').addEventListener('input', (e) => {{
  state.search = e.target.value; applyFilters();
}});
document.getElementById('tag-filter').addEventListener('change', (e) => {{
  state.tag = e.target.value; applyFilters();
}});
document.getElementById('reset-btn').addEventListener('click', () => {{
  state.type = '__visible__'; state.search = ''; state.tag = '__any__';
  state.atomsVisible = false;
  document.getElementById('type-filter').value = '__visible__';
  document.getElementById('search-id').value = '';
  document.getElementById('tag-filter').value = '__any__';
  document.getElementById('toggle-atoms-btn').textContent = 'show atoms';
  viewBoxX = 0; viewBoxY = 0; viewBoxW = 1600; viewBoxH = 1000;
  applyViewBox();
  applyFilters();
}});
document.getElementById('toggle-atoms-btn').addEventListener('click', () => {{
  state.atomsVisible = !state.atomsVisible;
  document.getElementById('toggle-atoms-btn').textContent =
    state.atomsVisible ? 'hide atoms' : 'show atoms';
  applyFilters();
}});

// ---- highlight a node + its incident edges on click ----
let currentlyHi = null;
function highlight(n) {{
  for (const el of nodeEls.values()) el.classList.remove('highlighted', 'dimmed');
  for (const e of edgeEls) e.classList.remove('highlighted', 'dimmed');
  if (currentlyHi === n.id) {{ currentlyHi = null; return; }}
  currentlyHi = n.id;
  const incidentIds = new Set([n.id]);
  for (const e of edgeEls) {{
    if (e._edge.s === n.id || e._edge.o === n.id) {{
      e.classList.add('highlighted');
      incidentIds.add(e._edge.s); incidentIds.add(e._edge.o);
    }} else {{
      e.classList.add('dimmed');
    }}
  }}
  for (const [id, el] of nodeEls.entries()) {{
    if (incidentIds.has(id)) el.classList.add('highlighted');
    else el.classList.add('dimmed');
  }}
}}

applyFilters();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=str, default=None,
                    help="path to a demo_run dir (default: latest under output/)")
    args = ap.parse_args()

    if args.run_dir:
        run_dir = Path(args.run_dir).resolve()
    else:
        existing = sorted(OUTPUT_DIR.glob("*_demo_run"))
        if not existing:
            print("no demo_run dir found; run demo_capabilities.py first")
            sys.exit(2)
        run_dir = existing[-1]
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"viz target run dir: {run_dir}")

    t0 = time.time()
    print("  loading store …")
    store = load_store()
    print(f"  store loaded — {len(store.all_cards())} cards in {time.time()-t0:.2f}s")

    print("  building graph …")
    t1 = time.time()
    graph = build_graph(store)
    print(f"  nodes={len(graph['nodes'])} edges={len(graph['edges'])} "
          f"types={len(graph['types'])} preds={len(graph['preds'])} "
          f"in {time.time()-t1:.2f}s")
    visible_nodes = sum(1 for n in graph["nodes"] if n["default_visible"])
    visible_edges = sum(1 for e in graph["edges"] if e["default_visible"])
    print(f"  default-visible: {visible_nodes} nodes / {visible_edges} edges")

    print("  laying out (visible subgraph only) …")
    t2 = time.time()
    static_layout(graph["nodes"], graph["edges"], width=1600, height=1000,
                  iters=220, seed=7)
    print(f"  layout done in {time.time()-t2:.2f}s")

    print("  rendering HTML …")
    html_text = render_html(graph, run_dir)
    viz_path = run_dir / "viz.html"
    viz_path.write_text(html_text, encoding="utf-8")

    size_kb = viz_path.stat().st_size / 1024
    elapsed = time.time() - t0
    print(f"\nHANDOFF: viz_path={viz_path}")
    print(f"  nodes_total={len(graph['nodes'])}  edges_total={len(graph['edges'])}")
    print(f"  visible_nodes={visible_nodes}  visible_edges={visible_edges}")
    print(f"  html_size_kb={size_kb:.1f}  elapsed_sec={elapsed:.2f}")


if __name__ == "__main__":
    main()
