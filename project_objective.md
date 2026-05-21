# Project Objective — memory_system_design

> 一句话: **建一个 agent-native 的长期记忆系统, 让卡片之间产生计算性关系, 不只静态 link**。

---

## 1. 问题

现行 agent 工作模式 — 短期靠 context window (stateless), 长期靠 RAG (搭便车在向量数据库上)。两者的共同 limitation:

1. **检索是 pull, 不是 push** — agent 必须自己写 query 去要内容, 容易漏掉它"不知道自己不知道"的相关知识。
2. **存储是静态指向, 不是计算关系** — 卡片之间只有"我 link 到你", 没有"我能从你 derive 出新事实 / 我读你的时候才算 / 我跟你冲突时按这套协议解决"。
3. **越用不一定越强** — 1 万张卡片注入后, 检索 quality 经常退化 (噪声 + 漂移), 没有自演化机制。
4. **粒度由 parser 决定, 不由 goal 决定** — 全字段 dump 出几千张 atom, 多数对当前任务无关。

---

## 2. 目标

一个**原子化的、agent 共用的笔记/记忆系统**, 设计目标:

| # | 承诺 | 关键机制 |
|---|---|---|
| 1 | 按需子集提取不爆 context | typed-link 因果闭包 walk |
| 2 | 指针 over inline (子集告诉 agent 去哪深读) | L1/L2/L3 三级 token 经济 |
| 3 | agent 干完活自动写回 | scratchpad → fast → slow batch consolidation |
| 4 | 越用越强, 1 万张卡注入后检索不退化 | 三层 index + utility prune + namespace boundary |
| 5 | 卡片之间产生**计算性关系** (first-class capability) | sexp/EDN skeleton + 6 capability (见 sys_design_thought §3) |
| 6 | 跨项目的 idle-time collision → 自动 task suggestion | Shower Mode (L10) |
| 7 | 专用 memory agent push, 不是 work agent pull | L9 push 模式 |

---

## 3. 已 ship vs 未 ship

### 已 ship (arc 260520a → arc 260521a, 2026-05-20 → 2026-05-21)

- **kernel 5 components**: cardstore / macro / rules / view / dedup (Python, ~750 LOC, 15/15 tests)
- **65 sources → 3404 atoms ingest** (alpha_second_v1/auto_research_experiment vault)
- **5 rules + 2 macros** as cards (规则即卡片)
- **6 capability demo** 全部跑通: macro 派生 / lazy ref / rules-as-cards / dedup restart / view / 自计算 confidence
- **viz.html**: 3546 nodes / 493 edges, single file, 0 CDN
- **migration path 7 步** from arc 260520a yaml-mixed schema 到统一 sexp/EDN

### 已识别未 ship (L7+ forward)

- consolidation worker (仿 sleep replay)
- 多 agent namespace
- 三层 index (symbol / vector / graph)
- utility prune
- 真 s-expr evaluator (cap6 现是结构匹配)
- transaction model (并发写)

### Han 2026-05-21 新加 (L8 / L9 / L10, 见 `ideas/`)

- **L8 agent-driven selective extraction** — atom 粒度由 agent 按 query goal 抽, 不是 parser 全字段 dump (直接 critique 当前 Phase 2 ingest)
- **L9 Memory Agent push 模式** — 独立 actor 监听 work agent 主动 push 相关 card
- **L10 Shower Mode** — idle-time cross-goal collision worker, 找跨项目 bridge → 写 task suggestion

---

## 4. 成功标准 (sufficiency, 不强求 perfection)

| 阶段 | 标准 |
|---|---|
| L0-L6 shipped ✓ | 6 capability 跑通端到端 demo, 真实数据 (alpha_second vault), 0 外部 CDN viz |
| L7+ migration | consolidation worker 每日跑, retrieval F1 在 10k 卡注入后不退化 (目标 ≥0.75 vs RAG ≈0.40) — 数字未实测, 设计目标 |
| L8-L10 prototype | 各自有最小可验证 demo (一篇 paper × 一个 goal × sub-agent 抽 atom 跟 structural baseline 对比) |
| 生产价值 | agent 在 3dgs / alpha_second / TARS 自己的 reflection 三个 namespace 下都能用, 跨 namespace cross-pollination 可控 |

---

## 5. 不在范围内

- 不做产品 UI (Obsidian / Logseq / Roam / Tana 替代品) — 只做 agent-readable store + 验收用 viz
- 不重写 alpha_second_v1 / 3dgs 项目本体 — wiki/ 是这俩项目的 LTM 层, 不是替代它们
- 不做用户级 visualization optimization — viz.html 是验收工具, 不是 daily-use dashboard
- 不做 multi-tenant SaaS — single-user (han) workspace

---

## 6. 源头

- 触发对话: 2026-05-20 下午 telegram, han 收到 schema 反推 audit 后说"这正是我所需要的" → 锁定 computational relations
- 已 ship arcs: `~/project/work/3dgs/arcs/all/260520a_*` (3dgs) + `~/project/alpha/alpha_second_v1/arcs/all/260521a_*` (alpha_second)
- 集中副本: `~/project/agent/memory_system_design/` (本目录), GitHub: https://github.com/Bisgates/memory_system_design
