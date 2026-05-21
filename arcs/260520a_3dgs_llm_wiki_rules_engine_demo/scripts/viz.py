"""Render a single-page HTML report from trace.json + run.log."""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


STYLE = """
:root {
  --paper:        #fbf6e9;
  --paper-2:      #f3ebd6;
  --ink:          #1f1a14;
  --ink-soft:     #3b332a;
  --ink-faint:    #6b6052;
  --rule:         #b8a583;
  --rule-soft:    #d8c9a2;
  --accent:       #8c2f1c;
  --accent-2:     #2c5340;
  --gold:         #a37c2a;
  --code-bg:      #efe6ce;
  --code-fg:      #1a140d;
}
* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: -apple-system, "Iowan Old Style", "Charter", "Cormorant Garamond", "Playfair Display", Georgia, "Times New Roman", serif;
  font-size: 17px; line-height: 1.65;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
}
body { padding-bottom: 6em; }
.mono, code, pre {
  font-family: ui-monospace, "SF Mono", Menlo, Monaco, "Cascadia Mono", Consolas, "Liberation Mono", "Courier New", monospace;
}
main { max-width: 960px; margin: 0 auto; padding: 48px 32px 0; }

.masthead {
  text-align: center;
  border-top: 4px double var(--rule);
  border-bottom: 1px solid var(--rule);
  padding: 28px 0 20px;
  margin-bottom: 36px;
}
.masthead .kicker {
  font-variant: small-caps; letter-spacing: 0.28em;
  font-size: 12px; color: var(--accent);
}
.masthead h1 {
  font-size: 36px; line-height: 1.18; margin: 12px 0 8px;
  font-weight: 500;
}
.masthead .deck {
  font-style: italic; color: var(--ink-soft);
  font-size: 17px; max-width: 640px; margin: 0 auto;
}

.chapter-rule { text-align: center; margin: 48px 0 18px; color: var(--accent); font-variant: small-caps; letter-spacing: 0.3em; }
.chapter-rule .roman { display: inline-block; font-size: 19px; font-style: italic; padding: 0 14px; border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); line-height: 2; }
.chapter-title { text-align: center; font-size: 23px; font-style: italic; font-weight: 500; margin: 0 0 22px; color: var(--ink); }

.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(165px, 1fr));
  gap: 16px;
  margin: 22px 0;
}
.metric {
  background: var(--paper-2); border: 1px solid var(--rule-soft);
  padding: 16px 18px;
}
.metric .num { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-weight: 600; font-size: 1.85rem; line-height: 1; color: var(--ink); }
.metric .lbl { color: var(--ink-faint); font-size: 0.7rem; letter-spacing: 0.08em; text-transform: uppercase; margin-top: 8px; }
.metric .delta { font-size: 0.78rem; margin-top: 6px; color: var(--accent-2); }
.metric.fail .delta { color: var(--accent); }

.callout {
  background: var(--paper-2); border-left: 3px solid var(--accent);
  padding: 14px 18px; margin: 22px 0;
}
.callout.calm { border-left-color: var(--accent-2); }
.callout .ctitle { font-variant: small-caps; letter-spacing: 0.12em; color: var(--accent); font-size: 12px; margin-bottom: 6px; }
.callout.calm .ctitle { color: var(--accent-2); }

table { width: 100%; border-collapse: collapse; margin: 18px 0; font-size: 14.5px; }
th, td { border-top: 1px solid var(--rule-soft); border-bottom: 1px solid var(--rule-soft); padding: 7px 10px; text-align: left; vertical-align: top; }
th { font-variant: small-caps; letter-spacing: 0.08em; color: var(--accent); border-bottom: 1px solid var(--rule); }
table.compact th, table.compact td { padding: 4px 8px; font-size: 13.5px; }
td.num { font-family: ui-monospace, "SF Mono", Menlo, monospace; text-align: right; }

code { font-size: 0.88em; background: var(--code-bg); color: var(--code-fg); padding: 1px 5px; border-radius: 2px; }
pre { background: var(--code-bg); color: var(--code-fg); border-left: 3px solid var(--gold); padding: 12px 16px; overflow-x: auto; font-size: 12.5px; line-height: 1.55; margin: 18px 0; }
pre code { background: transparent; padding: 0; }

.bar-row { display: grid; grid-template-columns: 220px 1fr 60px; align-items: center; gap: 10px; margin: 3px 0; font-size: 13.5px; }
.bar-row .nm { font-family: ui-monospace, Menlo, monospace; color: var(--ink-soft); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bar-row .bar { background: var(--paper-2); border: 1px solid var(--rule-soft); height: 14px; position: relative; }
.bar-row .bar > i { display: block; height: 100%; background: var(--accent); opacity: 0.85; }
.bar-row .bar.chain > i { background: var(--accent-2); }
.bar-row .v { font-family: ui-monospace, Menlo, monospace; text-align: right; }

.legend { font-size: 12.5px; color: var(--ink-faint); margin: 8px 0 18px; }
.legend .sw { display: inline-block; width: 12px; height: 10px; vertical-align: middle; margin: 0 4px 0 12px; }
.legend .sw.acc { background: var(--accent); }
.legend .sw.acc2 { background: var(--accent-2); }

svg.curve { background: var(--paper-2); border: 1px solid var(--rule-soft); padding: 12px; margin: 16px 0; }

details.deriv { background: var(--paper-2); border: 1px solid var(--rule-soft); padding: 6px 12px; margin: 6px 0; font-size: 13.5px; }
details.deriv > summary { cursor: pointer; color: var(--ink-soft); }
details.deriv > summary code { font-size: 0.95em; }
details.deriv .parents { margin-top: 8px; padding-left: 12px; border-left: 2px solid var(--rule-soft); }
.tag { display: inline-block; background: var(--paper); border: 1px solid var(--rule-soft); padding: 0 6px; border-radius: 2px; font-family: ui-monospace, Menlo, monospace; font-size: 11.5px; color: var(--ink-soft); margin-right: 4px; }
.tag.rule { background: var(--code-bg); color: var(--accent); }
.tag.derived { background: rgba(44,83,64,0.08); color: var(--accent-2); }

footer.colophon {
  max-width: 960px; margin: 56px auto 0; padding: 18px 32px 0;
  border-top: 1px solid var(--rule);
  display: flex; justify-content: space-between;
  font-family: ui-monospace, Menlo, monospace; font-size: 12px; letter-spacing: 0.06em;
  color: var(--ink-faint); text-transform: uppercase;
}

@media (max-width: 720px) {
  main { padding: 28px 14px 0; }
  .bar-row { grid-template-columns: 1fr 1fr 50px; }
  .bar-row .nm { font-size: 11.5px; }
}
"""


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def render_growth_svg(curve: list[dict], width: int = 760, height: int = 240) -> str:
    n = len(curve)
    if n == 0:
        return ""
    pad = 36
    inner_w = width - 2 * pad
    inner_h = height - 2 * pad
    max_d = max(c["derived"] for c in curve) or 1
    pts = []
    bars = []
    for i, c in enumerate(curve):
        x = pad + inner_w * (i / max(1, n - 1))
        y = height - pad - inner_h * (c["derived"] / max_d)
        pts.append(f"{x:.1f},{y:.1f}")
        bx = x - 6
        by = height - pad - inner_h * (c["marginal"] / max_d)
        bw = 12
        bh = height - pad - by
        chain = c["rule_id"] in ("r009_co_used_with", "r010_topic_shared_arc", "r011_ablation_strong_neighbor")
        fill = "#2c5340" if chain else "#8c2f1c"
        bars.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw}" height="{bh:.1f}" fill="{fill}" opacity="0.35"/>')

    polyline = " ".join(pts)
    dots = []
    labels = []
    for i, c in enumerate(curve):
        x = pad + inner_w * (i / max(1, n - 1))
        y = height - pad - inner_h * (c["derived"] / max_d)
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#8c2f1c"/>')
        labels.append(f'<text x="{x:.1f}" y="{height-pad+14}" text-anchor="middle" font-size="10" font-family="ui-monospace,Menlo,monospace" fill="#6b6052">{c["k"]}</text>')

    # y-axis ticks (4 ticks)
    yticks = []
    for tk in range(5):
        v = max_d * tk / 4
        y = height - pad - inner_h * (tk / 4)
        yticks.append(f'<line x1="{pad-4}" x2="{pad}" y1="{y:.1f}" y2="{y:.1f}" stroke="#6b6052"/>')
        yticks.append(f'<text x="{pad-6}" y="{y+3:.1f}" text-anchor="end" font-size="10" font-family="ui-monospace,Menlo,monospace" fill="#6b6052">{v:.0f}</text>')

    return f"""
<svg class="curve" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect x="{pad}" y="{pad}" width="{inner_w}" height="{inner_h}" fill="none" stroke="#d8c9a2"/>
  {"".join(yticks)}
  {"".join(bars)}
  <polyline points="{polyline}" fill="none" stroke="#8c2f1c" stroke-width="1.8"/>
  {"".join(dots)}
  {"".join(labels)}
  <text x="{width/2:.1f}" y="{height-4}" text-anchor="middle" font-size="11" font-family="ui-monospace,Menlo,monospace" fill="#6b6052">rule k (1..{n})</text>
  <text x="14" y="{height/2:.1f}" text-anchor="middle" font-size="11" font-family="ui-monospace,Menlo,monospace" fill="#6b6052" transform="rotate(-90 14 {height/2:.1f})">derived (cumulative)</text>
</svg>
"""


def render_yield_bars(per_rule: dict[str, int], chain_set: set[str]) -> str:
    items = sorted(per_rule.items(), key=lambda kv: -kv[1])
    if not items:
        return ""
    mx = max(v for _, v in items) or 1
    rows = []
    for rid, v in items:
        pct = (v / mx) * 100
        chain_cls = " chain" if rid in chain_set else ""
        rows.append(
            f'<div class="bar-row">'
            f'<div class="nm">{esc(rid)}</div>'
            f'<div class="bar{chain_cls}"><i style="width:{pct:.1f}%"></i></div>'
            f'<div class="v">{v}</div>'
            f'</div>'
        )
    return "".join(rows)


def render_atoms_summary(atoms: list[dict]) -> str:
    by_pred: dict[str, int] = {}
    by_ns_subj: dict[str, int] = {}
    derived_n = 0
    for a in atoms:
        by_pred[a["pred"]] = by_pred.get(a["pred"], 0) + 1
        ns = a["subj"].split(":", 1)[0]
        by_ns_subj[ns] = by_ns_subj.get(ns, 0) + 1
        if a.get("derived_from"):
            derived_n += 1
    rows1 = []
    for p, n in sorted(by_pred.items(), key=lambda kv: -kv[1]):
        rows1.append(f"<tr><td><code>{esc(p)}</code></td><td class='num'>{n}</td></tr>")
    rows2 = []
    for ns, n in sorted(by_ns_subj.items(), key=lambda kv: -kv[1]):
        rows2.append(f"<tr><td><code>{esc(ns)}</code></td><td class='num'>{n}</td></tr>")
    return f"""
<div style="display:grid; grid-template-columns:1fr 1fr; gap:18px;">
  <div>
    <h3 style="font-size:13px; font-variant:small-caps; letter-spacing:0.1em; color:var(--ink-faint); margin:6px 0 4px;">By predicate</h3>
    <table class="compact"><tbody>{"".join(rows1)}</tbody></table>
  </div>
  <div>
    <h3 style="font-size:13px; font-variant:small-caps; letter-spacing:0.1em; color:var(--ink-faint); margin:6px 0 4px;">By subj namespace</h3>
    <table class="compact"><tbody>{"".join(rows2)}</tbody></table>
  </div>
</div>
<p style="font-size:13px; color:var(--ink-faint); margin-top:8px;">
  Total atoms: <code>{len(atoms)}</code> (derived: <code>{derived_n}</code>, extracted: <code>{len(atoms)-derived_n}</code>)
</p>
"""


def render_trace(trace: list[dict], atoms_by_id: dict[str, dict], cap: int = 30, prefer_chain: bool = True) -> str:
    chain_ids = {"r009_co_used_with", "r010_topic_shared_arc", "r011_ablation_strong_neighbor"}
    if prefer_chain:
        chain_first = [t for t in trace if t["rule_id"] in chain_ids]
        rest = [t for t in trace if t["rule_id"] not in chain_ids]
        ordered = chain_first + rest
    else:
        ordered = trace
    items = []
    for t in ordered[:cap]:
        rid = t["rule_id"]
        a = t["atom"]
        parents = []
        for pid in t.get("parents", []):
            pa = atoms_by_id.get(pid)
            if pa:
                parents.append(f'<div><span class="tag">{esc(pid)}</span> <code>{esc(pa["subj"])}</code> · <code>{esc(pa["pred"])}</code> · <code>{esc(pa["obj"])}</code> <span class="tag {"derived" if pa.get("derived_from") else ""}">{esc(pa.get("derived_from") or "extracted")}</span></div>')
            else:
                parents.append(f'<div><span class="tag">{esc(pid)}</span> <em>(parent not in store)</em></div>')
        items.append(f"""
<details class="deriv">
  <summary>
    <span class="tag rule">{esc(rid)}</span>
    <span class="tag">iter {t["iteration"]}</span>
    <code>{esc(a["subj"])}</code> · <code>{esc(a["pred"])}</code> · <code>{esc(a["obj"])}</code>
  </summary>
  <div class="parents">
    <div style="font-size:11.5px; color:var(--ink-faint); margin-bottom:4px;">binding: {esc(json.dumps(t["binding"], ensure_ascii=False))}</div>
    {"".join(parents)}
  </div>
</details>
""")
    return "".join(items)


def render_acceptance(payload: dict) -> str:
    extracted = payload["extracted"]
    derived = payload["derived_full"]
    marginal = payload["marginal"]
    n_rules = len(payload["per_rule_full"])
    avg_per_rule = derived / n_rules
    metrics_html = []

    def card(num, label, pass_: bool | None, baseline: str = ""):
        cls = "" if pass_ is None else ("" if pass_ else " fail")
        verdict = "" if pass_ is None else (f'<div class="delta">{"PASS" if pass_ else "FAIL"}</div>')
        base_html = f'<div style="font-size:0.72rem;color:var(--ink-faint);margin-top:6px">{esc(baseline)}</div>' if baseline else ""
        return f'<div class="metric{cls}"><div class="num">{esc(num)}</div><div class="lbl">{esc(label)}</div>{verdict}{base_html}</div>'

    metrics_html.append(card(str(derived), "Derived atoms", derived >= 50, f"target ≥ 50"))
    metrics_html.append(card(str(marginal), "Marginal rule 11", marginal >= 5, "target ≥ 5"))
    metrics_html.append(card(f"{avg_per_rule:.1f}", "Avg per rule", avg_per_rule >= 2.0, "linear baseline ≈ 1"))
    metrics_html.append(card(str(extracted), "Extracted atoms", None, "from 30 sources"))
    return '<div class="metrics">' + "".join(metrics_html) + "</div>"


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--run-log", required=True)
    ap.add_argument("--rules-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    payload = json.loads(Path(args.trace).read_text(encoding="utf-8"))
    run_log = Path(args.run_log).read_text(encoding="utf-8")

    atoms_by_id = {a["id"]: a for a in payload["all_atoms"]}
    chain_set = {"r009_co_used_with", "r010_topic_shared_arc", "r011_ablation_strong_neighbor"}

    growth_svg = render_growth_svg(payload["growth_curve"])
    yield_bars = render_yield_bars(payload["per_rule_full"], chain_set)
    atoms_summary = render_atoms_summary(payload["all_atoms"])
    trace_html = render_trace(payload["trace"], atoms_by_id, cap=24)
    acceptance_html = render_acceptance(payload)

    rules_dir = Path(args.rules_dir)
    rule_rows = []
    for rule_path in sorted(rules_dir.glob("r*.md")):
        text = rule_path.read_text(encoding="utf-8")
        rid = rule_path.stem
        first_doc_line = ""
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("# ") and not line.startswith("# r"):
                first_doc_line = line[2:]
                break
            if line.startswith("# r"):
                first_doc_line = line[2:]
                break
        chain_mark = ' <span class="tag derived">CHAIN</span>' if rid in chain_set else ""
        y = payload["per_rule_full"].get(rid, 0)
        rule_rows.append(
            f"<tr>"
            f"<td><code>{esc(rid)}</code>{chain_mark}</td>"
            f"<td>{esc(first_doc_line)}</td>"
            f"<td class='num'>{y}</td>"
            f"</tr>"
        )

    out_html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>LLM-Wiki Rules Engine · arc 260520a</title>
<style>{STYLE}</style>
</head>
<body>
<main>

  <header class="masthead">
    <div class="kicker">arc 260520a · demo report · 2026-05-20</div>
    <h1>LLM-Wiki 规则引擎最小可运行原型</h1>
    <div class="deck">用明确规则让 wiki 价值跨越线性增长 — 359 atoms · 11 rules · 211 derivations · 26ms</div>
  </header>

  <section>
    <div class="chapter-rule"><span class="roman">I · 结论速读</span></div>
    {acceptance_html}
    <div class="callout">
      <div class="ctitle">一句话结论</div>
      <p>引擎跑通；avg 19.2 derivations/rule（远超线性基线 1）；chain 规则真的链式触发（r009、r011 都非零）。
      但严格 L1.2（r011 边际 ≥ 5）<strong>没过</strong> — 因为 chain² 上游被 r002 (5) 和 r009 (2) 卡死。
      在 30 sources 这个数据规模上，<em>chain 是可工作但脆弱的</em>；总体的"rules × atoms"乘法效益由 join-dense rule（r007=152）扛起。</p>
    </div>
  </section>

  <section>
    <div class="chapter-rule"><span class="roman">II · 增长曲线</span></div>
    <h2 class="chapter-title">rules[:k] 每加一条，cumulative 与 marginal 各长多少</h2>
    {growth_svg}
    <div class="legend">
      <span class="sw acc"></span>非链式规则 (extracted-only joins)
      <span class="sw acc2"></span>链式规则 (consumes derived atoms — r009/r010/r011)
    </div>
    <p style="font-size:14.5px; color:var(--ink-soft);">线条 = cumulative derived；柱 = 每条规则的 marginal 增量（柱高同尺度）。
      r004 (+21) 和 r007 (+152) 是两个"join-dense"节点；r009/r010/r011 是 chain rules，
      在 30 sources 上 marginal ≤ 2。</p>
  </section>

  <section>
    <div class="chapter-rule"><span class="roman">III · 每条规则产量</span></div>
    {yield_bars}
    <div class="legend">
      <span class="sw acc"></span>extracted-only joins
      <span class="sw acc2"></span>chain rules (consume derived atoms)
    </div>
  </section>

  <section>
    <div class="chapter-rule"><span class="roman">IV · 规则目录</span></div>
    <table>
      <thead><tr><th>id</th><th>说明（rule 自带 markdown 标题）</th><th>yield</th></tr></thead>
      <tbody>{"".join(rule_rows)}</tbody>
    </table>
  </section>

  <section>
    <div class="chapter-rule"><span class="roman">V · Atom 仓库</span></div>
    {atoms_summary}
  </section>

  <section>
    <div class="chapter-rule"><span class="roman">VI · 派生样本</span></div>
    <p style="color:var(--ink-soft); font-size:14.5px;">每条 derived atom 展开后显示 binding 与所有 parent atoms（带 atom id 反向链）。chain 规则的派生优先展示——它们的 parent 自带 <code class="tag derived">r0XX</code> 标记，代表是上一条规则派生的。</p>
    {trace_html}
  </section>

  <section>
    <div class="chapter-rule"><span class="roman">VII · 完整 run.log</span></div>
    <pre>{esc(run_log)}</pre>
  </section>

  <section>
    <div class="chapter-rule"><span class="roman">VIII · 解读与下一步</span></div>
    <h2 class="chapter-title">这个原型证伪了什么、留下了什么</h2>
    <div class="callout calm">
      <div class="ctitle">证实的部分</div>
      <ul>
        <li><strong>规则即数据</strong>：11 份 markdown rule 各自独立 lint / version / 删除，引擎机械吃完。</li>
        <li><strong>forward chaining 真触发</strong>：r009 消费 r002 的 used_by_arc，r011 消费 r009 的 co_used_with 和 r007 的 shares_topic_with，trace 里有完整 parent 反向链。</li>
        <li><strong>总体超线性</strong>：avg 19.2 derivations/rule。若 30 sources × 11 rules 是线性，期望 ~11 derivations，实测 211。</li>
        <li><strong>provenance 完整</strong>：每条 derived atom 都带 <code>derived_from</code> + <code>parents</code>，撤回一条规则 = 删 markdown + 重跑 = 它派生的全部消失。</li>
      </ul>
    </div>
    <div class="callout">
      <div class="ctitle">证伪 / 限制的部分</div>
      <ul>
        <li><strong>严格 L1.2 没过</strong>：r011 chain² 边际 = 2 < 5。原因不是引擎，是数据规模 + 链路设计 — r002 只产 5，r009 只产 2，r011 继承了上游稀疏。</li>
        <li><strong>r008 = 0</strong>：项目里没有重复 introduces_doc — 这其实是项目质量好；contradiction-lint 在没真矛盾的数据集上必然为 0。</li>
        <li><strong>r010 = 0</strong>：contributes_to 输出 6 条，但没有两条共享 topic — 30 sources 太稀疏。</li>
        <li><strong>"指数"二字得谨慎</strong>：在小数据集上真正放大效应的是 dense join (r007=152)，不是 chaining；要把 chain 放大到 dense，需要 (a) 50+ arcs，(b) chain rule 上游选 high-cardinality predicate。</li>
      </ul>
    </div>
    <div class="callout calm">
      <div class="ctitle">下一步建议</div>
      <ul>
        <li><strong>加 source 数</strong>：把所有 13 个 arc + 全部 docs 都吃进来（当前跳过了 5 个 arc 因为没有 9_summary）。</li>
        <li><strong>设计 dense-chain rule</strong>：让 chain² 的上游是 r007 (152) 而不是 r009 (2)；例如 shares_topic_with + introduced_by → topic_neighbor_introduced_by。</li>
        <li><strong>引入 LLM 作 extract layer</strong>：deterministic regex 抽出来的 atoms 偏 path-shaped；LLM 能抽 claim-shaped (e.g. "Difix3D shows pseudo-views help PSNR")，rule 的覆盖面立刻拉宽。</li>
        <li><strong>把 wiki 接进 3dgs 主 docs/</strong>：当前是 sandbox demo；下一个 arc 把 atoms/rules 物化到 <code>docs/wiki/</code>，让真实任务流过引擎。</li>
      </ul>
    </div>
  </section>

</main>

<footer class="colophon">
  <span>arc 260520a · demo report</span>
  <span>2026-05-20</span>
</footer>
</body>
</html>
"""
    Path(args.out).write_text(out_html, encoding="utf-8")
    print(f"WROTE: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
