# Objective — arc 260521a · Wikify auto_research_experiment vault to sexp/EDN

## 来源
- 2026-05-21 ~00:30 han 通过 telegram 锁定方向: 计算性关系 (computational relations) 作 first-class 能力, 卡片不只静态 link
- 上游产物:
  - arc 260520a (3dgs) — Luhmann-Wiki rules engine demo (atoms + rules + derived 三套 yaml 分裂)
  - `/Users/han/project/learn_with_agent/260520/arc_260520a_zettelkasten_lisp_redesign.html` — 设计稿 (统一 sexp/EDN, 12 工程问题, kernel 5 components, migration 7 步)
  - `/Users/han/project/learn_with_agent/260520/260520a_schema_reverse_engineer.md` — schema 反推 audit (8-dim 修订版)
  - `/Users/han/project/learn_with_agent/260520/brain_memory_for_agent_wiki.html` — STM/LTM 机制 → agent LTM 工程映射

## 一句话
把 alpha_second_v1/auto_research_experiment Obsidian vault 完整 wikify 到统一 sexp/EDN card store, 把 vault 内已有的 typed link (derived_from / competes_with / falsifies / reports_to / parent_arc / parent_lineage) + tag axis 当 computational relations 的初始 schema, **跑通并 demo 6 个能力**: macro 派生卡 · lazy reference · 规则即卡片 · dedup restart 协议 · 视图卡 · 自计算字段。

## Why alpha_second_v1
- vault 已经是高度结构化的实验候选 md, frontmatter 字段 + 6 种 typed link + 7 套分层 tag axis (#axis/sizing 等), 跨 arc 复用
- vault 内 ~hundreds 个 .md candidate 是真实数据 (arc 260516a team a-h 全部产出), 不是 toy
- vault 本身的设计目标就是 "给未来 agent 看 lineage" (VAULT_DESIGN.md §1.1), wikify 后直接 dogfood

## 接受标准 (sufficiency, 不强求 perfection)
1. **card store**: `wiki/cards/*.edn` 统一格式, atom · rule · macro · derived · view 全部以 `(card ...)` 表示, 共享 :id namespace
2. **parser/serializer**: Python `wiki/lib/cardstore.py` 能读写 .edn, 跑 query, 跨 atom/rule/macro 平 namespace 查找
3. **vault ingest**: `wiki/scripts/ingest_vault.py` 把 auto_research_experiment 的 `experiments/` + `lineages/` + frontmatter + double-link 抽成 atom 卡 (一份 paper md → 多张 atom 表达 (subj pred obj) 三元组)
4. **rules + macros 至少 5 套**:
   - rule: derived_from 反向边 (类比 arc 260520a 的 r001)
   - rule: competes_with 对称化
   - rule: falsifies 链推断 anti-pattern cluster
   - macro: from-paper-derive-experiment-suggestion (例 1)
   - macro: from-lineage-derive-comparison-view (例 5 视图卡)
5. **6 能力 demo run 跑通**, 各产出至少一条具体可看的证据:
   - macro 派生: 选一张 candidate paper 卡, macro-expand 出 ≥3 张新建议卡
   - lazy ref: 视图卡 body 是 query, retrieve 时 evaluate
   - 规则即卡: 上面 3 条 rule 全部以 (card :type 'rule ...) 存在 wiki 同一目录
   - dedup restart: 故意制造一对 80%+ 相似 atom, 走 restart 协议
   - 视图卡: `(view :type 'view ...)` 注册查询, read 时 materialize
   - 自计算字段: `:confidence (compute ...)` 在 ≥1 张 claim 卡上 demo
6. **demo run 产物**: `output/<YYMMDD_HHMM>_demo_run/` 含 cards/ + rules.log + derived/ + viz.html (图谱)
7. **/grok 总结 HTML**: dual-tab + simple, 完工 outbox @attachment 推 telegram

## 预算
- 总 $300 (han 给的). 主 token sink 是 vault ingest (sonnet medium 跑 LLM 抽取) + rule firing + grok 总结 sub-agent
- 模型: heavy lifting 用 sonnet 4.6 (memory: "费 token 的 task 交给 sonnet medium 做"); orchestration + final grok 可用 opus
- 软性 stop: 单 sub-agent 超过预期 token (e.g. >50M for ingest) 主动 reassess

## 不要做
- 不要重写 alpha_second_v1 本体, 这个 arc 只输出 wiki/ 子树 + arc 内 output/
- 不要碰 arc 260520a 那套 3dgs wiki, 那是独立项目
- 不要做产品 UI (Obsidian/Logseq 替代品), 只做 agent-readable store + 一个验收用的 viz.html
- 不要 settle 在 "Obsidian-style 双链"; 必须 6 能力都跑出来才算完, computational relations 是这次的 unique selling point

## 中途坑可脱离原设计 (han 授权)
- Datalog vs Lisp 落点: 设计稿推荐底层 rule engine 用 Datalog/Datomic, Lisp 用在 card representation。中途如发现 Python 直接 eval sexp 已经够用 (像 arc 260520a 那样), 不必硬上 Datomic
- Card namespace 设计: 如 :type 'rule 的卡跟 :type 'atom 在 query 引擎里实操有 friction, 允许临时分子目录但 schema 不分

## 完工 hand-off
- HTML: outbox @attachment 推 telegram (han 睡觉中, 不打扰)
- arc status → done
- 9_summary.html in arc 根目录
