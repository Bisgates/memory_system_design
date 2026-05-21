# System Design Thought — memory_system_design

> 设计哲学 + 关键决策 + 工程 trade-off 的浓缩。
> 完整 narrative 看 `grok_html/`, 这里是 distilled commitments。

---

## 1. 第一性原理: card 不是 document, 是 program

传统笔记 (md / Obsidian / Roam) 把卡片当 *display artifact* (人眼读). 我们把卡片当 *data structure with computational closure* (机器读 + 派生 + eval).

具体到分层:
- **body = markdown** (capture friction 低 + 人 eyeball-readable) — 70-90% 内容
- **skeleton = sexp/EDN** (typed fields + macro + 程序操作) — 10-30% 结构

`(card <id> :type 'atom|rule|macro|view|derived :key val ...)` 形, atom 和 rule 和 macro **共享一个 store + namespace + versioning + query 引擎 + dedup**.

---

## 2. 为什么 Lisp/sexp 不是装饰

**lisp 的真正卖点是三件事, 不是语法**:

1. **规则也是卡** (homoiconic) — agent 可以查 / 编辑 / 派生规则跟查数据同接口
2. **派生关系 first-class** — macro 展开是 data transform, 不是 app code
3. **冲突协议跟数据走** — restart 选项在卡里, dedup engine 不需要 hardcode

**三件事里 ≥2 yes 才落 Lisp, 否则 yaml+md+ 外部 rule engine 更省心**。

**底层 rule engine 用 Datalog/Datomic 比硬上 Clojure 更直接** — Lisp 留在 card representation + query 重写 + dedup conflict 协议。装饰用就别用。

---

## 3. 6 个 computational relation capabilities

每条都在 arc 260521a demo 跑通 + 留 trace:

| # | Capability | 机制 | demo 证据 |
|---|---|---|---|
| 1 | macro 派生卡 | `(card :type 'macro ...)` 展开生成 new card cluster | 3 input × m001 → 9 suggestions |
| 2 | lazy reference | body 含 `<eval>...</eval>`, retrieve 时 resolve | `count-links-to H-R3b-4` 得 14 |
| 3 | 规则即卡片 | `(card :type 'rule ...)`, 跟 atom 同 store | `r002 paused → derived 99→46 (Δ=53)` |
| 4 | dedup restart 协议 | 新卡自带 `:on-dedup-conflict [keep-both / merge-prefer-newer / supersede]` | sim 0.8358, 3 actions 各 fire |
| 5 | 视图卡 | `(card :type 'view :query ...)` materialize 时 reflects current store | `materialize 14→15→14` 随数据动 |
| 6 | 自计算字段 | `:confidence (compute ...)` retrieve 时 eval | `0 → 1.0 → 0.333` 随 supporter/contradictor |

⚠️ cap6 现实现是结构匹配 (pattern match `count-links-to %self :pred ...`), 不是全 sexp eval. 标 limitation.

---

## 4. minimum kernel (5 components, ship 优先级)

| # | Module | LOC | 角色 |
|---|---|---|---|
| K1 | `cardstore.py` | 273 | sexp parser + Card dataclass + CardStore (add/get/query/find_links_*/versioning/dump_edn/load_edn) |
| K2 | `macro.py` | 103 | `(card :type 'macro)` 注册 + 展开, `?var-name` 占位替换, parents 自动挂 |
| K3 | `rules.py` | 167 | Datalog-style forward chaining, multi-pattern when, dedup by (subj pred obj) natural key, fixpoint |
| K4 | `view.py` | 84 | `(card :type 'view)` materialize + lazy ref resolve_lazy (`<eval>` 替换) |
| K5 | `dedup.py` | 144 | similarity (text + structural), find_near_dupes, restart 协议 |

51 行 pseudo-code 端到端走通 read → reason → writeback (见 grok layer 教学版 frog [7]).

---

## 5. Layer 演化纪律

每层只加 1 个 mechanism, 每层有 1 条 "前一层撑不住" 的 tension justification:

| Layer | Add | Tension solved |
|---|---|---|
| L0 | Card + (subj pred obj) | (没存事实) |
| L1 | typed predicate vocabulary | "只能查值, 不能按 link 类型 walk" |
| L2 | rules-as-cards + forward chaining | "每条 derived_from 反向 derives_to 都要手写" |
| L3 | macros-as-cards | "rule 只能 derive 边, 不能 derive 节点簇" |
| L4 | view cards | "派生卡是冻结的, store 变它不变" |
| L5 | lazy `<eval>` field-level | "view 是整张卡的 query, 字段级 lazy 没解" |
| L6 | dedup restart 协议 | "增长不可逆, 累积污染" |
| L7+ | (未 ship) | consolidation worker / 多 ns / 三层 index / utility prune / 真 sexp eval / transaction |
| **L8** | **agent-driven selective extraction** | "parser 全字段 dump = 理论最大 atom, 噪声大" |
| **L9** | **Memory Agent push** | "RAG pull 漏掉 agent 不知道自己不知道的" |
| **L10** | **Shower Mode cross-goal collision** | "单 goal 内自演化, 跨 goal 灵感不发生" |

---

## 6. 工程 trade-off 决策

### 6.1 选 sexp/EDN 不选 yaml — 为什么

- yaml 能装 typed field 不能装 macro body / restart 协议 / lazy expression
- yaml 缺嵌套 list-of-list 的统一表达 (sexp 天然有)
- yaml 的 anchor (`*`/`&`) 不是 first-class macro
- json 一样的问题 + 加 boilerplate

### 6.2 选 Python stdlib 实现 — 为什么不上 Datomic / Cyc / Datalog 现成库

- 65 sources × 3404 atoms 的规模, stdlib + 手撸 80 行 sexp parser 足够
- 上 Datomic 引入 JVM 依赖 + 学习成本; Cyc 是知识库不是引擎
- 下一阶段 (>100k atoms) 再切真 Datalog (PyDatalog / Souffle), 现 RuleEngine API 已经长 Datalog 样, 切换成本低

### 6.3 hash8 stable id — 不上 uuid 不上 sequence

- id = sha256(subj|pred|str(obj))[:8] → 重跑 ingest **idempotent**, 二次跑不会 id 漂移
- 让 atom 自然 dedup by (subj pred obj) 三元组
- 8 字符碰撞概率在 10^9 atoms 后才显著 (远超 alpha_second 全 history 量级)

### 6.4 65 文件 ingest 用 structural parser 不用 LLM

- 0.13s 跑完 vs LLM ~$2-5
- frontmatter 已经 schema-rich, 不需要 LLM 抽取
- **但**: 这是 baseline / corpus dump, 不是 production atom. Han L8 critique 对的 — production 该 agent goal-aware extract.

### 6.5 一卡片一 .edn 文件 (atom + rule + macro + derived 都是)

- 方便 git diff (跑前后 rule 改了哪条一眼可见)
- 重跑 idempotent (hash stable + 覆盖式 write)
- 缺点: 文件数多 (65 atom files + 5 rule + 2 macro + 11 derived = 83+ files) → filesystem 操作多. >10k 卡时需切单文件多卡 batch.

---

## 7. Anti-pattern 警示 (别犯)

| ❌ Anti-pattern | ✓ Correct |
|---|---|
| 把 body 也 sexp 化 (cargo cult lisp) | body = md, skeleton = sexp |
| 用 sexp 重写 Obsidian (装饰用 lisp) | 只在三件事 (规则即卡 / 派生 first-class / restart 协议) ≥2 yes 才上 |
| consolidation 跟 sleep replay 字面对照 (借 ripple/circadian 衬底) | 借 batch-consolidation 的**功能**, 不照搬生物机制 |
| reconsolidation 每次 read 都允许 mutate (生物里靠分子守门) | 软件里用 versioning + scratchpad, 不开 per-read writability |
| engram distributed coding (LLM embedding 已经覆盖) | 别再造一遍 distributed representation |
| 自计算 confidence 在 production 用 (读 N 次得 N 个不同值, debug 噩梦) | 周期性 batch 重算 + 缓存; demo 可以, daily 不行 |
| view 永不 cache (大规模时 latency 爆) | 小规模 OK 不 cache, >10k cards 时 add memo |
| 一个 LLM call per ingest (run-cost 不可控) | structural parser 做 baseline, LLM 只在 L8 goal-aware extract 时调 |
| **mock 数据替代真实数据 demo** | demo 必须用真 H-R3b-4 / 真 B-R10-2 等实际 atoms |
| **隐瞒 limitation 把 demo 当 production-ready** | cap6 现实是结构匹配, ground-truth typo 等 fix 都显式写 .uncertain |

---

## 8. 学术诚实

### 8.1 来源

- Luhmann Zettelkasten — atomicity / unique ID / link-not-tag / emergence / own-words 6 原则; 严格遵守 3 条, 修正 2 条, 1 条不适用 (emergent hierarchy 改 derived view)
- McCarthy Lisp (1960) — sexp + homoiconic
- Datalog / Datomic — forward chaining rules + entity-attribute-value
- Common Lisp condition/restart system — 启发 dedup restart 协议
- 脑认知 (Tonegawa / Tulving / Anderson / Squire / Nadel / Eichenbaum / Renoult-Rugg) — sleep replay / pattern separation / encoding specificity / rational forgetting — 借机制不照搬衬底, 见 `grok_html/260520_brain_memory_for_agent_wiki.html`

### 8.2 已知 limitations / contested

- L7+ "10k 卡 retrieval F1 ≥0.75" 是设计目标, 未实测
- m002 lineage slug mismatch (frontmatter slug ≠ filename slug, m002 手挑 top-2)
- ~90 unknown body link labels ingest 时 warn 留, 未全 canonicalize
- axis list 字段在 RuleEngine 跑时 in-memory hardening (kernel 没改)
- cap4 README typo 0.969 vs ground truth (cases.json) **0.8358**, 现以 ground truth 为准
- 单租户 / 单线程 append-only store, 多 agent 并发 write 未做 transaction

---

## 9. 决策 leaderboard (top 10)

1. **body = md, skeleton = sexp** (避免 cargo cult lisp)
2. **三件事阈值** 决定上不上 lisp (规则即卡 + 派生 first-class + restart 协议, ≥2 yes)
3. **底层 rule engine 用 Datalog** 思路, Lisp 留在卡片表示
4. **minimum kernel 5 components** + 51 行 pseudo-code 走通
5. **incremental migration 7 步**, 不推倒重做
6. **hash8 stable id** + idempotent ingest
7. **structural parser baseline + L8 agent goal-aware extract** (互补不替代)
8. **一卡一 .edn** (git-friendly, <10k 规模)
9. **诚实标 limitations** 用 `.uncertain` / 显式 flag, 别当 settled 卖
10. **真实数据 demo** (H-R3b-4 / B-R10-2), 不用 toy/mock

---

## 10. 跟相关项目的边界

| Project | 关系 |
|---|---|
| Obsidian / Logseq / Roam / Tana | 启发了 typed link 词表, 但 they are read 端产品, no compute 端 — 这是质变 |
| Cyc | 跟知识 ontology 出发点同, 但 Cyc 顶层 ontology 已死; 我们走 bottom-up emergent |
| Mem.ai / Heptabase | 用户向产品, 不是 agent-native |
| TARS auto-memory (~/.tars/memories/) | 同一类机制的简化版 — MEMORY.md (durable) + HOT.md (task-state) + UPS hook auto-inject, 是 L9 push 模式的 prototype |
| 3dgs project | 提供 arc 260520a workspace (yaml 时代 demo) |
| alpha_second_v1 | 提供 arc 260521a workspace + auto_research_experiment vault 作 ingest 真实语料 |

---

更细节看:
- 设计稿: `grok_html/260520_arc_260520a_zettelkasten_lisp_redesign.html` (12 工程问题答完)
- phase 实施: `grok_html/260521_arc_260521a_wikify_summary_by_phase.html`
- layer 演化: `grok_html/260521_wikify_kernel_to_full_design_by_layer.html`
- L8/L9/L10: `ideas/260521_han_design_extensions.md`
