# Han 的设计扩展 — 2026-05-21 早上

> 在 msg 1156 (layer 教学版 grok) 之后, han 通过 telegram 给的 3 个设计扩展。
> 这 3 条都不在已 ship 的 arc 260520a / 260521a 里, 是 next-iteration 的设计目标。

---

## 1. 原子拆解必须 agent 做, 不能纯 parser

### Han 原话 (paraphrase)
> 对一个 content, 原子该如何拆 — 这步绝对是 agent 做的, 不可能用程序自己解决。比如一篇 paper, 按照设定的"我需要获取什么", 可能只用存 3 张原子 card 就够了; 但是直接程序跑可能跑出 1000 张 card, 因为信息确实相当多。

### 核心机制
**atom 粒度不是数据结构问题, 是认知问题。** 同一份 paper, 在不同 query goal 下应该抽出**完全不同**的 atom 集合:
- goal = "找类似 sizing 策略的 candidate" → 抽 3 张: rule snippet / NAV 结果 / falsification verdict
- goal = "建一个完整 sizing taxonomy" → 抽 30 张: 每个 sub-decision (anchor 选择 / sizing 公式 / regime gate / ...) 一张
- goal = "复现这个实验" → 抽 50 张: 含所有 code path + parameter + dependency

纯 parser 永远在抽 schema-level 全字段 = 总是抽到"理论最大 atom 数", 多数 atom 对当前 task 无关 = retrieval 时噪声大。

agent 知道 query goal, 能做 selective extraction: "对这个 goal 而言, 这 paper 里值得记的 atom 是这 3 个"。

### 对当前系统的 critique (诚实)
**arc 260521a 的 Phase 2 ingest 用的就是 han 说的"程序自己跑"** — `ingest_vault.py` 是 structural parser, 把 65 个 .md 的 frontmatter 全字段拆成 (subj pred obj) 三元组, 产 **3404 atoms**。
- 优势: 0.13s 跑完, 0 LLM cost, 重跑 idempotent
- 劣势: 完全没有 query 意识, 抽出来的 3404 atoms 是"理论最大", 真要用的可能就 30-50 个

**当前系统的合理位置**: Phase 2 输出是 **raw atom dump (corpus baseline)**, 不是 "for agent use 的 production atoms"。production atoms 应该由 memory agent 在跑 task 时 on-demand 从 raw dump (或直接从原 md) selectively 抽。

### 工程落地建议
- **新增 layer L8**: agent-driven selective extraction
  - input: (paper_path, current_task_goal, existing_atoms_for_this_goal)
  - output: list of new atoms to add for this task
  - 实现: 给 sub-agent 一个 prompt template, 让它读 paper + goal + 已存 atoms, 输出 "为此 goal 应该新加这 N 张 atom" 的 sexp list
- **保留 Phase 2 structural parser 作为 fallback / baseline**: 当 query goal 未知或为 "give me everything" 时, structural dump 是 ground floor。
- **edge**: 同一 paper 在多个 goal 下会被 agent 多次访问 → 抽出多套 atoms, 共享一个 (paper, has_excerpt_for_goal_X) 索引

### 风险 / 边界
- agent extraction 不可避免引入 stochasticity (同一 paper 第二次抽可能不同 N 张)
- 需要 dedup vs already-extracted-for-this-goal atoms (用 layer L6 的 dedup restart)
- LLM cost: ~每 paper $0.02-0.10 (sonnet) × 数万 paper = 数百到数千美元一次, 不能频繁全 rebuild

---

## 2. 专用 Memory Agent (push 而非 pull)

### Han 原话 (paraphrase)
> 有一个 agent 就是负责记忆梳理以及记忆提取的。别的 agent 干活的时候他会搜寻记忆, 直接发给对应的 agent。这个和 work_agent 主动提取不是一个逻辑 — 这个记忆对于 work_agent 来说是"自己挑出来的"。

### 核心机制
**Memory Agent 是独立 actor, 不是 work agent 的 sub-routine。** 现行 RAG 模式是 pull (work agent 自己写 retrieval query)。Han 的设想是 push (memory agent 监听 work agent 活动, 实时找相关 memory, 主动发过去)。

差别比喻:
- pull (RAG): "我搜书架找有用的书"
- push (memory agent): "助理看见我在做什么, 抽屉里翻出三本相关的书放我桌上"

work agent 体感: memory 是"出现"在它的 context 里的, 不是它"找来"的 — 这降低 work agent 的 cognitive overhead (work agent 不需要知道 memory 在哪 / 怎么 query / 用什么关键词), 它只专注 task。

### 对当前系统的 critique
**arc 260521a 完全没有 memory agent** — 6 cap demo 是脚本驱动的, 不是 actor 驱动。subset extraction (cap5) 是 work agent 显式 materialize view, 不是 memory agent 主动 surface。

### 工程落地建议
- **新增 layer L9**: Memory Agent 作为独立 sub-agent
  - 输入: work agent 当前 turn 的 message (从 jsonl 流读取)
  - 输出: 推送给 work agent 的 memory packet (typically 3-7 张 cards + 它们的 typed link 邻居)
  - 触发: work agent 每发出一个新 user message / 调一个工具, memory agent 决定是否 push
  - push 通道: memory packet 作为 system-reminder 注入 work agent 下一个 turn 的 context (类似 TARS 现 MEMORY 注入机制)
- **关键设计**: memory agent 不能太多嘴 (push 过频污染 work agent context), 也不能太沉默 (该提醒没提醒)。需要 **relevance threshold** + **diminishing returns** (同一 thread 内已 push 过的 atom 不重复 push, 除非有 new information)
- **work agent 体感**: 跟你 TARS 现 MEMORY auto-load 机制类似, 但 memory packet 是动态的、每 turn 重算的

### 风险 / 边界
- 双 agent 协调 latency: memory agent 决策慢会拖累 work agent
- push 错的代价: 噪声进 work agent context, 浪费 token, 误导 reasoning
- multi-tenant: 多 work agent 同时跑时一个 memory agent 服务谁? 一对一还是 pool?

---

## 3. Shower 模式 (idle-time cross-goal collision)

### Han 原话 (paraphrase)
> 类似 shower (指代人类洗澡时迸发灵感) — memory agent 知道自己有 N 个 goal, 已经存在的信息很可能发生碰撞, 产生新的想法, 这要存到对应的 task 内。比如 memory 系统知道我们此刻正在同时进行 3 个大项目, 进一步的 14 个小项目, 每个项目都有 goal。它在梳理 P12 记忆时会突然"想到"这个点可能帮助 P15, 它会给 P15 记一个 task: "试试这个"。

### 核心机制
**Memory Agent 在 idle 时跑 cross-goal collision pass**: 不是被动响应 work agent, 而是**主动扫**当前所有 active goal 池, 在已存 atoms 里找 "可能 unlock 另一个 goal 的隐藏连接"。

类比:
- 人在 shower / 散步 / 入睡 — 当下没在解任何具体问题, 但脑子在 background 跑 cross-domain 联想
- DMN (default mode network) 神经科学已经在做这块研究 (跟 layer 7+ "sleep replay" 高度相关)

实操机制:
- input: list of active goals (P1...P14 各自的 goal_text + 已有 atom 集合)
- output: 对每个 P_i 的 task list 追加一条 `(suggestion :for-goal P_i :from-collision (P_j ∩ P_i atoms) :body "试试 ...")`
- 触发: 周期性 idle pass (e.g. 每天凌晨 / 每个 work agent session 结束后)
- 算法: 找 atom pairs (a_x, a_y) 满足 (a) a_x 属于 P_i corpus / a_y 属于 P_j corpus / (b) a_x 与 a_y 有 high semantic similarity 但没显式 link / (c) bridging assertion (a_x → a_y) 对 P_i goal 有价值

### 对当前系统的 critique
**完全没做, 是 net-new capability**。arc 260520a / 260521a 都是单 goal 内的卡片操作 (rules engine 跑 derived, macro 派生 suggestion), 没有 cross-goal collision detection。

### 工程落地建议
- **新增 layer L10**: Shower Mode (cross-goal collision worker)
- 实现:
  - daily cron / Stop hook 触发 memory agent 跑 collision pass
  - 算法步骤:
    1. enumerate active goals from `/Users/han/project/agent/memory_system_design/goals_active.md` (新建 — 维护 active goal list 是前提)
    2. 对每对 (P_i, P_j), compute atom embedding overlap / structural bridge candidates
    3. 用 LLM call 验证 candidate bridges 是否真的 actionable (避免 spurious cosine similarity)
    4. 把通过验证的 bridge 写成 task card append 到 P_j (或两边都加)
  - push 给 han: 一份每日 "shower insights" digest, 让 han 决定哪些 task 真正 enqueue
- **前置依赖**: 项目/goal 状态本身要 first-class 进 wiki — 现在 han 的 14 个项目状态散在各 arc workspace, 没有统一 active-goals 视图。需要先加一层 "project / goal card", 把 goal 也当一种 card type 存进 store。

### 风险 / 边界
- spurious collision (cosine 相似但语义无关) → 噪声 task 多, 浪费 han 决策 budget
- collision 频率: 每日跑还是每周? 每日烦但新鲜, 每周累但筛过
- 边界 across project 越多越好, 但 namespace 隔离 (你 3 个量化项目 / 1 个 3dgs / 1 个 life) 不能彻底打通, 不然敏感信息会跨项目泄

---

## 与已 ship 系统的关系

| Layer | 状态 | 添加内容 |
|---|---|---|
| L0-L6 | ✓ shipped (arc 260521a) | cardstore / typed link / rules / macros / views / lazy ref / dedup restart |
| L7+ forward (旧) | 描述未实现 | consolidation worker, 三层 index, 多 agent namespace, transaction model, 真 sexp eval |
| **L8 (新)** | **设计中** | **agent-driven selective extraction** (代替 / 补充 structural ingest) |
| **L9 (新)** | **设计中** | **Memory Agent push 模式 (vs RAG pull)** |
| **L10 (新)** | **设计中** | **Shower Mode cross-goal collision** |

**重要观察**: L8 / L9 / L10 三层共同点是**引入 "agent as actor" 进 memory system**, 而 L0-L6 是 pure data structure + 命令式调用。这是从 "wiki 库" 到 "wiki 系统" 的质变。

---

## 下一步建议

1. **先建 goals_active.md** (前置: shower mode 必须知道有哪些 active goal). 把 han 14 个项目的 goal 状态汇总.
2. **prototype L8** (agent selective extraction): 拿 arc 260516a 一篇 paper, 给一个明确 goal (e.g. "找 sizing strategy candidates"), 让 sub-agent 抽 atom, 跟 Phase 2 structural parser 输出对比 — 看 quality / count / cost 差异。
3. **prototype L9** 比较 risky (改 work agent 体感), 建议在 sandbox 试: 复制现 wikify 工作流, 加 memory agent 中间层, observe work agent context 污染情况。
4. **L10 最远** — 依赖 L8 + L9 + goals_active.md 都到位才能跑。
