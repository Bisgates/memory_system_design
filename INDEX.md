# memory_system_design

> 2026-05-20 至 2026-05-21 关于 agent LTM / 卡片化笔记系统 / computational relations 设计的所有相关产物的 **副本汇总**。
> 原件分散在 `learn_with_agent/` 和两个 alpha/work arc workspace 里, 这里做一份集中索引方便后续做"项目"层级的思考与重构。

---

## 简介

这是从 arc 260520a (3dgs `LLM-Wiki rules engine demo`) 走到 arc 260521a (alpha_second_v1 `wikify auto research vault`) 整个 ~30 小时 / ~$300 预算 / 6 个 sub-agent 协作的思考轨迹的副本。核心承诺: **agent LTM 卡片之间的"计算性关系" (macro 派生 / lazy ref / 规则即卡 / dedup restart 协议 / 视图卡 / 自计算字段) 作 first-class 能力, 不只静态 link**。

---

## 目录

### `grok_html/` (~470KB · 6 文件)
按时间顺序读:

1. **`260520_llm_wiki_lisp_design.html`** (36KB) — *如果 LLM-Wiki 是一个 Lisp 程序: 一份设计稿*. 最早的设计 sketch, lisp 落点首次出现.
2. **`260520_arc_260520a_llm_wiki_rules_engine_demo.html`** (71KB) — *LLM-Wiki 规则引擎最小可运行原型 · 鸟瞰 ↔ 蛙跳*. 第一个跑通的 demo (在 3dgs arc workspace 内).
3. **`260520_brain_memory_for_agent_wiki.html`** (108KB) — *人脑提取短期记忆与长期记忆的机制 → agent LTM 工程映射*. 脑科学 settled vs contested vs retired 区分, 跟 agent LTM 的可借鉴 / 不可借鉴清单.
4. **`260520_arc_260520a_zettelkasten_lisp_redesign.html`** (89KB) — *arc 260520a 深度重构设计稿: Luhmann + Lisp agent LTM*. 12 个工程问题答案 + minimum kernel 5 components + 51 行 pseudo-code (frog §[7]) + migration path 7 步.
5. **`260521_arc_260521a_wikify_summary_by_phase.html`** (80KB) — *arc 260521a wikify alpha_second_v1 vault summary, **按 phase 组织**.* 实际跑完的 5-phase changelog 风, 3404 atoms / 6 capability demo 跑通.
6. **`260521_wikify_kernel_to_full_design_by_layer.html`** (86KB) — *同一份设计, **按 layer / minimum kernel 逐层加复杂度** 教学组织.* 7 layers (L0 atom → L1 typed → L2 rules → L3 macros → L4 views → L5 lazy → L6 dedup), 每层 1 mechanism + 1 tension + 1 capability + H-R3b-4 真数据 trace.

阅读建议:
- **第一次看**: 5 (phase 版) 或 6 (layer 版) 任选一; 看完两个互相印证.
- **想懂 design rationale**: 4 (深度重构设计稿) — 12 工程问题 + Lisp vs Datalog 选型诚实评估.
- **想懂神经/认知背景**: 3 (脑记忆) — 哪些机制能照搬, 哪些"形似神不似".
- **从最早看演化**: 1 → 2 → 4 → 5/6 顺序.

### `arcs/`
- **`260520a_3dgs_llm_wiki_rules_engine_demo/`** (~3.5MB total 含此 arc) — 第一个 arc 完整 workspace (在 3dgs project 下). `output/260520_2102_demo_run/` 是关键 — atoms/rules/derived 三套 yaml schema 的真实 demo run + viz.html.
- **`260521a_alpha_second_wikify_vault_sexp/`** — 第二个 arc, 完整 workspace.
  - `wiki/lib/` — 5 个 module (cardstore / macro / rules / view / dedup), 15/15 tests pass.
  - `wiki/scripts/` — ingest_vault.py / run_rules.py / demo_capabilities.py / build_viz.py / verify_ingest.py.
  - `wiki/cards/atoms/` — **3404 atom 卡跨 65 sources**, 全部 (card :type 'atom ...) sexp 格式.
  - `wiki/cards/rules/` + `wiki/cards/macros/` + `wiki/cards/derived/` — 5 rules + 2 macros + 11 derived, 全部 (card :type ...) 同一 schema.
  - `output/260521_0145_demo_run/` — 6 capability 各自 trace + viz.html (215+493 默认 / 3546 total nodes).
  - `9_summary.html` — arc 协议 done changelog.

### `schema_audits/`
- **`260520a_schema_reverse_engineer.md`** (19KB) — 反推 arc 260520a demo 的 implicit schema. 25 条 query 显化合同 (能答 11 / 部分 5 / 答不上 9), 8-dim 修订版 schema 提议 (能答 ≥22/25).

### `ideas/`
- **`260521_han_design_extensions.md`** — han 2026-05-21 给的 3 个 next-iteration 设计扩展 (L8 / L9 / L10):
  - **L8 agent-driven selective extraction** — atom 粒度由 agent 按 query goal 决定, 不是 parser 全字段 dump (直接 critique 当前 Phase 2 ingest 的 3404 atoms 是"理论最大")
  - **L9 Memory Agent push 模式** — 独立 actor 监听 work agent 主动 push 相关 card, 不是 work agent pull (vs 现 RAG)
  - **L10 Shower Mode** — idle-time cross-goal collision worker, 每日 / 周期跑, 跨 project 找隐藏 bridge → 自动生成 task suggestion 入对应 project

---

## 关键决策摘要 (从所有产物里 distill)

1. **md vs sexp 不是 1:1 比较** — md 是 display 格式, sexp 是数据结构. 卡片该分两层: **body = markdown** (capture friction 低 + 人 eyeball-readable) + **skeleton = sexp/EDN** (typed fields + macro + 程序操作).
2. **Lisp 真正卖点是"规则也是卡 + 派生关系 first-class + 冲突协议跟数据走"** 三件事. 三里有 ≥2 yes 才落 lisp, 否则 yaml+md+ 外部规则引擎更省心.
3. **底层 rule engine 用 Datalog 或 Datomic 比硬上 Clojure 更直接**; Lisp 留在卡片表示 + query 重写 + dedup conflict 协议.
4. **minimum kernel 5 components**: cardstore + macro + rules + view + dedup. 51 行 pseudo-code 端到端走通 read → reason → writeback.
5. **migration incremental 不推倒重做**: 7 步 + 各 step 独立验证. 第一步 typed link + content_snippet 一晚可落.
6. **诚实标 limitation**: cap6 self-compute confidence DSL 是结构匹配非全 sexp eval; m002 lineage slug mismatch; ~90 unknown body labels warn; cap4 README typo (0.969 vs ground truth 0.8358).

---

## 源头位置 (live, 这里只是副本)

- arcs 原件: `/Users/han/project/work/3dgs/arcs/all/260520a_*` + `/Users/han/project/alpha/alpha_second_v1/arcs/all/260521a_*`
- grok HTMLs 原件: `/Users/han/project/learn_with_agent/260520/` + `/Users/han/project/learn_with_agent/260521/`
- schema audit 原件: `/Users/han/project/learn_with_agent/260520/260520a_schema_reverse_engineer.md`

---

## 下一步 candidate (han 还没拍板)

### 短期 (已 ship 系统的 polish)
- **修 README cap4 typo**: arc 260521a 的 `output/260521_0145_demo_run/README.md` 把 0.969 改 0.8358 与 ground truth 对齐.
- **Step 1 migration in-place**: 把 arc 260520a 现 demo 的 wiki/ 加 typed link + content_snippet, 一晚可落.

### L7+ forward (layer 版列的, 旧)
- consolidation worker (sleep replay) / 多 agent namespace / 三层 index for 不退化检索 / utility prune / 真 s-expr eval / transaction model.

### L8 / L9 / L10 (han 2026-05-21 新加的 → 见 `ideas/260521_han_design_extensions.md`)
- **L8 agent-driven selective extraction** — prototype: 一篇 paper × 一个 goal × sub-agent 抽 atom, 跟 Phase 2 全字段 dump 对比 quality/count/cost.
- **L9 Memory Agent push 模式** — 改 work agent 体感, 建议 sandbox 试.
- **L10 Shower Mode cross-goal collision** — 依赖 L8 + L9 + 一个 `goals_active.md`. 最远.

### 前置基建
- **`goals_active.md`** (新建): 汇总 han 14 个项目的当前 goal, 作为 L10 collision worker 的输入. 这是任何 cross-project 能力的最低门槛.
