# 260520a Schema 反向工程审计

> 目标 demo: `/Users/han/project/learn_with_agent/260520/260520a_llm_wiki_rules_engine_demo.html`
> 审计问题: demo 在隐性合同里支持哪些 query, 用了哪些 dimension, 哪些 dimension 因为 query 没浮出来而被压缩, narrative 修辞跟 schema 在哪儿混线。

---

## Thesis

demo 的 atomic schema **不是"原文的最小事实形状"**, 而是"**graph join + forward chaining 这两件计算能跑起来的最小语法承诺**"。`(subj, pred, obj)` 三元组是 *engine-first* 的, 不是 *content-first* 的 —— dimension 几乎全在回答"这条事实能不能跟另一条 join", 而 atom 自己声称的"事实"维度 (when / where / why / how confident / for whom) 几乎全部缺席。Demo body 里写出来的 "id / subj / pred / obj / source / derived\_from / parents" 七字段在表面上像 schema, 但其中只有 3 个是真 dimension (subj / pred / obj), 另外 4 个是 **graph 追责工具**, 不是事实的描述维度。Demo 里"事实"= "RDF 边", 这个 reduction 是隐性的, 也是它最强的赌注 —— 把所有原本是文档 / 段落 / 上下文的东西, 压成只能产生 join key 的 token。

---

## §1. demo 隐含支持的 query (20 条) — 显化合同

| # | query (中文) | demo 能答? | 证据 / 解释 |
|---|---|---|---|
| Q1 | 这份 doc 是哪个 arc 引入的? | √ | `r001_introduces_reverse` 反向出 `doc → introduced_by → arc`。第三章 r002 frontmatter 直接用 `introduces_doc`。 |
| Q2 | 这个 arc 引入了哪些 doc? | √ | extract 阶段直接产出 `(arc:260508b, introduces_doc, doc:...)` atom (frog §II Out[3])。 |
| Q3 | 这个 doc 被哪些 arc 复用 (= 引入后被别的 arc 提到)? | √ | r002 派生 `used_by_arc`。frog §III r002.md。 |
| Q4 | 两个 doc 是不是被同一个 arc 同时复用? | √ | r009 派生 `co_used_with`。frog §V。 |
| Q5 | 两个 doc 是不是共享 topic? | √ | r007 派生 `shares_topic_with` (bird §VI yield 152)。 |
| Q6 | 哪两个 doc 既被同一 arc 复用又共享 topic (= "强邻居")? | √ | r011 派生 `strong_neighbor`。frog §V Out[11]。 |
| Q7 | 有没有两个 arc 都声称引入同一份 doc (= 重复 introducer 矛盾)? | √ | r008 `duplicate_introducer` 专门为此而设, 即使输出 0 也算答了 (bird §VI callout "0 不是 bug, 是体检报告")。 |
| Q8 | 一个 arc 依赖哪些更老的 arc? | √ | `r006_arc_depends_on_older_arc` (frog §VI run.log)。 |
| Q9 | 一个 arc 提到 (mentions) 了哪些 doc / code / arc? | √ | extract 阶段产 `mentions_doc / mentions_code / refs_arc` (从 r002.md / r003.md 的 when slot 反推)。 |
| Q10 | 一个 atom 是从哪条规则、哪几条父 atom 派生出来的 (lineage / 追责)? | √ | `derived_from` + `parents` 字段, 第二章承重柱段; frog §V Out[11] 直接展示。 |
| Q11 | 一个 topic 下面有哪些 arc 在贡献? | √ | `r005_arc_contributes_topic`。 |
| Q12 | 这份 doc 处理的是哪个 topic? | ~ | extract 产出 `has_topic`, 但 demo **从没说 topic 是怎么抽出来的** —— 看 r007 的 when 在用, 看 r010 在用, 但 regex 规则没暴露。Topic 抽取是个黑箱。 |
| Q13 | 这份 doc 在说什么 (semantic content / 摘要)? | × | atom 只有 `(subj, pred, obj)`, **没有自由文本字段**。`has_title` 是唯一带自然语言的, 也只是 title 字符串。 |
| Q14 | 这条 fact 是什么时候被记下来的 / 来自原文的哪一行? | ~ | `source` 字段是文件路径, **粒度到文件**, 没有 line number / offset。 |
| Q15 | 这条 fact 有多确定 / agent 抽错没? | × | 没有 confidence / strength / extraction\_method 字段。extract 是 deterministic regex, 这是隐性 dignity, 不是显性字段。 |
| Q16 | 两条 atom 是不是互相矛盾 (除了 duplicate introducer 之外的语义冲突)? | × | demo 只把"两个 arc 都 introduces 同一 doc"当矛盾。语义矛盾 (e.g. "A 说 X 是好方法" vs "B 说 X 失败了") 没有 dimension 承载。 |
| Q17 | 这份 doc 是哪种类型的 doc (note / spec / decision / paper)? | ~ | 隐藏在 namespace 前缀里 (`doc:notes/...` vs `doc:SPECS/...`), demo 在 bird §II callout 提了一句"命名空间约定", 但**没有显式 `has_type` for doc**, 只有 `(arc, has_type, type:arc)` 这一条 (frog §II Out[3])。所以"找所有 spec 类型的 doc"要靠 obj 字符串 hack。 |
| Q18 | 这条规则跑了多少次 / 它的 yield 高不高? | √ | per-rule yield 表 (bird §VI / frog §VI run.log) 直接列出 r001..r011 的产量。这其实是 **rule 的 meta-dimension**, 不是 atom 的。 |
| Q19 | 一份新 source 加进来后, 哪些既有 atom / rule 受影响? | ~ | 理论上 fixpoint 重跑能算, 但 demo 没暴露 incremental delta 视图; 现实就是"全量 rerun"。 |
| Q20 | 同一个 fact 在两份 source 里被独立提到, 算几条 atom? | × (但 dedupe 模糊) | `id = sha1(subj|pred|obj)[:8]`, dedupe by key —— 所以**只算 1 条**, 第二个 source 的 provenance 被丢掉。frog §II "dedupe-by-content"。这是个有意识的损失但 demo 没承认它。 |
| Q21 | 一个 entity (arc/doc/topic) 总共关联多少条 atom / 在 graph 里有多 central? | × | 没有 degree / pagerank dimension, 也没有显式 aggregator —— 第三章明说 "没有聚合"。 |
| Q22 | 这个 arc 的状态是什么 (active / done / abandoned)? | × | extract 看的是 9\_summary.md 的内容, 但 atom schema 里没有 `has_status`。`Status: DONE ✅` 那行只是 prose, 没进 atom 集 (frog §I head 输出里能看到这行被 head 但没 extract)。 |
| Q23 | 哪些 fact 是 LLM 主观抽的, 哪些是 deterministic regex 抽的? | × | `derived_from: null` 表示 extracted (frog §II), 但 demo 强调 extract = 纯 regex, 所以二分变成 "regex extracted vs rule derived"。**LLM-extracted 这种第三类不存在** —— 这是 demo 的隐性约束, 不是 schema 的弹性。 |
| Q24 | 同一条 fact 重抽多次 / 在不同语境下出现, 强度会不会累积? | × | dedupe 后只有 1 条, 没有 `evidence_count` / `support_strength`。 |
| Q25 | 这份原 markdown 里**哪些段落**没有被任何规则消费 / 抽干净? | × | 没有 "coverage" dimension。原文里的 prose 段落 (e.g. 9\_summary 的 TL;DR 内容) 完全没进 atom store, 但 demo 没显示这个 leak。 |

**小计**: 25 条 query 里 demo 能稳健答上 11 条 (Q1-Q11, Q18), 部分答 5 条 (Q12, Q14, Q17, Q19), 答不上 9 条 (Q13, Q15, Q16, Q20, Q21, Q22, Q23, Q24, Q25)。**能答的都是 graph 形态的 query, 答不上的都是 "content / confidence / coverage / status" 类 query**。这个倾斜本身是 schema 的最大特征。

---

## §2. demo 实际用的 dimension (atomic schema 解析)

从 frog §II 的 dataclass + Out[3] yaml + bird §II 的字段表反推。

### Dimension 表 (按显隐分层)

| dim | 显式? | 来源证据 | 取值空间 | 正交性 / 重叠 |
|---|---|---|---|---|
| **D1. subj** | 显式 | dataclass `subj: str` (frog §II); `arc:260508b` (frog §II Out[3]) | `ns:id` 字符串; ns ∈ {arc, doc, code, topic, type} | 跟 D3 共享同一命名空间 —— subj 和 obj 是**同一类型对象**在不同 slot, 不正交 (一个 entity 同时是别人的 subj 和别的 obj)。 |
| **D2. pred** | 显式 | dataclass `pred: str`; 词汇表 = {has\_type, has\_title, has\_topic, introduces\_doc, updates\_doc, mentions\_doc, mentions\_code, refs\_arc, ...} | 固定词汇表 (closed vocabulary), 大小约 10-15 个 (从 r001..r011 when/then 推) | 跟 namespace **强耦合** —— `introduces_doc` 只对 doc namespace 的 obj 有效, `mentions_code` 只对 code; bird §II callout 明说"pattern matching 不用 schema 也能正确分轨"—— 即 pred 隐含 obj 的类型, 这不正交。 |
| **D3. obj** | 显式 | 同 D1 | 同 D1 | 同 D1, 跟 subj 不正交。 |
| **D4. id** | 显式但派生 | `sha1(subj\|pred\|obj)[:8]` (frog §II utils/atom.py) | 8-hex string | 完全从 D1+D2+D3 派生, **不是独立 dimension**, 是 cache key。 |
| **D5. source** | 显式 | dataclass `source: str = ""` | 文件路径 (e.g. `arcs/all/260508b_l2_lidar_merge_metric/9_summary.md`) | 跟 D6 互斥 —— 派生 atom 的 source = "" (frog §IV engine.py 的 `source=""`)。这是 **provenance 的一半**, 但只在 extracted atom 上有意义。 |
| **D6. derived\_from** | 显式 | `derived_from: Optional[str]` | rule\_id (e.g. `r002_doc_used_by_arc`) 或 None | 跟 D5 互斥, 也跟 D7 共生。**这是 demo 把 atom 切成"原始 vs 派生"两类的硬开关**, 但它表达的是 **"who made this"**, 不是 **"what is this"**。 |
| **D7. parents** | 显式 | `parents: tuple = ()` | (atom\_id, atom\_id, ...) | 派生 atom 才非空。bird §II "asymptotic check"段说去掉就失去 viz 反向链。跟 D6 共同构成 lineage; 跟 D1/D2/D3 完全独立。 |

### 频率与位置 (concrete refs)

- D1/D2/D3 在 demo 里的出现密度: **每个 atom 必有**。引擎 join (`_match_all` frog §IV) 100% 依赖这三轴。
- D4 (id) 在 bird §II 第一份 yaml 例子里出现 (`id: a_a26feb5c`), 在 frog §II Out[3] 也出现。但**没有任何规则的 when/then 引用 id 字段** —— id 是工程产物, 不是语义维度。
- D5 (source) 在 extracted atom 上 100% 填, 派生 atom 上 100% 空 (frog §IV engine.py line `source=""`)。
- D6/D7 在 extracted atom 上 100% null/空, 派生 atom 上 100% 填。
- 没有任何规则在 when 子句里用 D5/D6/D7 做 join —— **provenance 字段是"读 graph 时用"的, 不是"算 graph 时用"的**。这是个有意思的不对称: 它们是 dimension 在 schema 上, 不是 dimension 在 query 语义上。

### 隐式 dimension (没写进 dataclass 但被 demo 默认存在)

| dim | 怎么藏的 |
|---|---|
| **D8. namespace** | 藏在 `subj`/`obj` 的字符串前缀里 (`arc:` / `doc:` / `code:` / `topic:` / `type:`)。bird §II callout 提了一次, 但**没有显式字段**。结果是 namespace 既是 entity-type 又是 join 分轨工具, 一个字段承担两职。 |
| **D9. directionality** | 藏在 pred 词汇表里 —— `introduces_doc` 是 arc→doc, `mentions_code` 是 ?→code; r001 反向出 `doc → introduced_by → arc`, 用一条规则把方向"翻"过来。**direction 没被建模成 dimension**, 而是被编码进 pred 名字, 所以"introduces vs introduced\_by"是两个 pred, 不是一个 pred + direction 标志。 |
| **D10. extraction\_method** | 藏在 D6 的二值 (null = regex extracted, 否则 rule derived)。**第三类 (LLM extracted) 不存在**, 这个二分是 closed-world 假设。 |

---

## §3. 缺失但 query 需要的 dimension

把 §1 里被标 × / ~ 的 query 反推:

| 缺的 dim | 哪些 query 因此卡 | 真盲点还是 demo 故意 park? |
|---|---|---|
| **content / payload** (atom 携带的自然语言片段) | Q13 (this doc 在说啥)、Q25 (哪些段落没抽干净) | **故意 park**。bird §II 第一句"如果 wiki 里所有事实都长一个样, 最少要带几个字段? 推到 0 个全是自由文本就回到 RAG"—— demo 明说不要 content 字段。但这意味着 LLM-wiki **没法回答语义类 query**, 必须配 RAG 才完整。demo 没承认这件事。 |
| **confidence / strength / evidence\_count** | Q15 (多确定), Q24 (重复出现要不要累积) | **盲点**。demo 因为 extract = deterministic regex 所以默认 confidence = 1, dedupe 不累积。一旦 LLM 加入 extract 链路 (将来必然要做, frog §VII 自己也说"下一轮如果让 LLM 写 rule"), 这个 dimension 就立即需要。 |
| **temporal / timestamp** | Q14 (何时记下来), Q19 (incremental delta) | **盲点**。source 是 file path 但 file 的 mtime / commit 信息没进 atom。fixpoint 是 stateless 全量重跑, 没有 "before/after rule X was added" 的 dimension。 |
| **status / lifecycle** | Q22 (这 arc done 还是 active) | **盲点**。9\_summary.md 第一行 `**Status: DONE ✅**` 在 frog §I head 输出里清清楚楚, 但没有 `has_status` pred —— extract regex 没覆盖。这条信息本来应该是 first-class dimension。 |
| **semantic conflict** (非 schematic 的) | Q16 (语义矛盾) | **盲点**。demo 只识别 schematic 矛盾 (r008 duplicate\_introducer)。"A 文说 X 方法 work, B 文说不 work" 这种 LLM-detectable 冲突没有 dimension 承载。 |
| **doc type / entity sub-type** | Q17 (这是 note 还是 spec) | **半故意 park**。bird §II callout 把它压进 namespace 前缀, 但实际产 atom 时只对 arc 加了 `has_type`, 对 doc 没加。可以 fix —— 不是真盲点, 是 demo 的 extract regex 没补完。 |
| **aggregation / centrality** | Q21 (entity 在 graph 里多 central) | **故意 park**。bird §III callout "放弃聚合"明说为了 fixpoint 收敛性放弃 aggregation。但用户问 "哪个 topic 最热"是合理 query, demo 只能靠 r007 yield 152 这种侧面信号回答, 不直接。 |
| **provenance multiplicity** (同一 fact 多 source) | Q20 (重复 fact 算几条) | **盲点伪装成 feature**。frog §II 说 "dedupe-by-content", 但**第二个 source 的信息整个丢掉**。如果将来要做"这条结论由 5 份独立 source 支持, 比那条只有 1 份 source 的更可信", 现在的 schema 完全不支持。 |
| **coverage** (原文哪些段落没被抽到) | Q25 (哪些段落漏抽) | **盲点**。没有任何机制告诉你 9\_summary.md 的 TL;DR 段 (那段讲 Spearman ρ = 1.0000 的) 完全没进 atom store —— 因为 regex 只抓 `[NEW]/[UPDATE]/mentions` 模式, prose 部分 silently dropped。这是个 silent failure。 |

**汇总**: 9 个缺失 dim 里 3 个是 demo 主动 park (content / aggregation / extraction 单态), 6 个是真盲点 (confidence / temporal / status / semantic-conflict / provenance-multiplicity / coverage)。主动 park 的 3 个是为了让"fixpoint 收敛 + 规则可单测"这套保证成立, 这个交易是诚实的; 6 个盲点是 demo 没意识到 / 没承认。

---

## §4. narrative 结构跟 schema 混线的地方

demo 是 HTML 文章, 有 H1/H2/段落/codeblock。修辞结构在 3 处被冒充成 dimension:

### 例 1: bird §V "kernel\_v3 四招都掉出来了" 的 4×2 matrix

bird §V 给了张表把 "kernel\_v3 的四招" 跟 "rule engine 里的对应物" 配对 (macros / multimethod / condition-restart / lazy streams ↔ 规则即 markdown / 多轴 predicate / derived atom 表达矛盾 / forward chaining 共享黑板)。这张表**读起来像 4 个 dimension**, 实际上是 4 个 narrative analogy。它告诉你"作者认为这件事重要", 不告诉你 atom schema 里多了 4 个字段。**任何尝试用这 4 招做 query 的人都会扑空** —— atom 里没有 "is\_macro\_like / has\_multimethod\_axis" 字段。这是 narrative collapse 被错位 promote 成 schema 的最典型例子。

### 例 2: "extracted-only join" vs "chain rule" 的二分 (bird §V matrix, frog §V)

bird/frog 都把规则切成两类 (extracted-only / chain), 切得非常显眼。但这个二分**不是 atom 的 dimension, 是 rule 的 meta-dimension** —— 它描述"这条规则的 when 里有没有派生 pred", 不描述"这个 atom 是什么"。读者很容易把它误解成 "atom 有两类"。实际上 atom 只有 extracted / derived 二分 (D6/D10), rule 的 chain depth 是另一个轴, 两轴正交但 demo 没把它们摆开。

### 例 3: bird §II 的"承重柱"修辞

bird §II 说 "`source` 和 `derived_from`/`parents` 这一组字段不是装饰。它是**整个抽象的承重柱**"。这种修辞强度让 reader 觉得这 3 个字段是 dimension 的核心, 但**这 3 个字段在引擎的 join 里完全没用** —— `_match_all` 只看 subj/pred/obj。修辞强度跟语义 centrality 错位: 承重柱在调试 / 可解释性上, 不在 query / join 上。

### 例 4 (轻一点): "atom 是 markdown 切成三元组" 的标题 (frog §II)

frog §II 标题 "原子：把 markdown 切成三元组" 给人的感觉是 "atom = markdown 的语义切片"。但 atom 里**没有 markdown 上下文信息**, 没有"这条 fact 来自哪个 H2 下面的哪段"。"切" 这个动词的语义被章节修辞放大了。

---

## §5. 如果照 §1 重新设计 schema (修订版)

按 §1 列的 25 条 query 倒推, 给一个 5-8 dim 的修订表。每条标 source query + fitness test。

| dim | source query | fitness test (atom 单独拎出来能否答这条 query?) |
|---|---|---|
| **R1. subj / pred / obj** (保留, 不变) | Q1-Q11 (所有 graph 类) | 给一条 atom `(arc:X, introduces_doc, doc:Y)`, 不看 store 也能回答 "X 引入了 Y"。√ |
| **R2. namespace\_subj, namespace\_obj** (从 ns:id 拆出来, 升格为字段) | Q17 (找所有 spec 类型 doc), Q12 (topic 抽取黑箱) | 给一条 atom 能直接判断 subj 是 arc 还是 doc, 不靠字符串前缀 hack。√ |
| **R3. content\_snippet** (原文片段, 限长 ≤ 200 字符) | Q13 (this doc 在说啥), Q25 (coverage) | 给一条 atom 能 quote 原文里支撑它的句子。**RAG 的能力被显式拉进 schema**, 不再外挂。√ |
| **R4. source\_locator** (file + line\_range, 取代 D5 的 file path) | Q14 (何时何处记下), Q25 (coverage —— 没被抽到的 line 一目了然) | 给一条 atom 能跳到原文具体行。√ |
| **R5. extraction\_method + confidence** (regex / llm / hand, 0..1 浮点) | Q15 (多确定), Q23 (谁抽的) | 给一条 atom 能说 "这是 regex 抽的, 1.0 confidence" 或 "LLM 抽的, 0.7 confidence"。√ |
| **R6. lineage** (derived\_from + parents, 保留) | Q10 (lineage 追责) | 不变。√ |
| **R7. status / temporal** (created\_at, valid\_until 可空, status 枚举) | Q19 (incremental), Q22 (arc 的 status), Q24 (重复 fact 强化) | 给一条 atom 能说 "2026-05-08 抽到, 来源 arc 当时 status=DONE"。√ |
| **R8. evidence\_count + supporting\_sources** (多源汇总) | Q20 (重复 fact 算几条), Q24 (强化) | 同一 (subj, pred, obj) 重抽时 evidence\_count++, supporting\_sources 累积。**dedupe 不再丢信息**。√ |

**8 个 dim 的特性对比**:

| 性质 | 原 demo schema | 修订 schema |
|---|---|---|
| fixpoint 收敛 | 保证 | 仍保证 (R7/R8 是 monotone, 不影响) |
| pattern matching 单元 | (subj, pred, obj) | 同 (其它 dim 是 ride-along) |
| LLM 可参与 extract | 没建模 | R5 显式承载 |
| RAG 类 query | 必须外挂 | R3 内建 |
| coverage 可见 | 不可见 | R4 让漏抽 silently 可被 audit |
| 提交一条新 atom 的成本 | 极低 | 中 (要填 R3-R5, R7-R8 是默认值) |

**取舍**: 修订版加 5 个 dim, atom 从 7 字段变 12 字段, **存储成本约 2x**, 但能答的 query 从 11/25 涨到 ≥ 22/25。剩下 Q21 (aggregation/centrality) 仍然不能直接答 —— 因为这是 query-time 的 aggregator, 不是 atom 的 dim, 应该靠 view layer 加。

---

## §6. 一句话收

demo 隐性押注 "atom = graph join 单元", 把 dimension 全部押在 join 形状上, 把 content / confidence / coverage / status 这 4 类 dim 整组缺席。这个押注对它声称要做的 query (graph 类) 是 well-fitted 的, 但对 LLM-wiki 实际会被问的 query (semantic / lifecycle / 可信度) 是 under-fitted 的。修订版 8-dim 是 minimum delta 让两类 query 都站得住的形状。
