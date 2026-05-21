# design — 三个数据形状 + 一个不动点

本 arc 用三种数据 + 一种计算把整个 wiki 维护问题 collapse 到 200 行 Python。

## Atom

一条 atom 是一份小型 (subj, pred, obj) 三元组，带 provenance。

```yaml
id: a_<8-hex>          # stable hash of (subj, pred, obj)
subj: <ns>:<id>        # e.g. "arc:260508b", "doc:notes/foo.md", "code:utils/x.py"
pred: <verb>           # e.g. "introduces_doc", "mentions_arc"
obj: <ns>:<id> | str   # symbol reference 或 literal
source: <path>         # extract 出来时的源 markdown；derived 时是 ""
derived_from: null | <rule_id>
parents: []            # 仅 derived 时非空，是 parent atom ids 的列表
```

**ns（namespace）约定**：`arc / doc / code / paper / spec / decision / note / topic / literal`。`arc:` 总是 7-char id，其它 ns 用相对项目根的 path 或 normalized slug。

**dedupe**：(subj, pred, obj) hash 决定 id；同一三元组重复 ingest / 重复 derive 都不重复存。

## Rule

一条 rule 是 markdown 文件，frontmatter 是 pattern，body 是说明。

```yaml
---
id: r003_doc_used_by
when:
  - {subj: "?A", pred: introduces_doc, obj: "?D"}
  - {subj: "?B", pred: mentions_doc,   obj: "?D"}
constraint: "?A != ?B"
then:
  - {subj: "?D", pred: used_by_arc, obj: "?B"}
---
```

**Pattern 语法**（够用就停）：
- `?X` = variable，全 pattern 内共享 binding
- 字面字符串 = 常量
- `when` = conjunction of triples（AND）
- `constraint` = 一个可 eval 的 Python 表达式，bind 后求值；仅 `==` `!=` `<` `>` `<=` `>=` 安全字符
- `then` = 一条或多条 emit 的 triple

**明确不支持**：negation、aggregation、算术、disjunction。够用即停。

## Engine — 不动点

```python
def run(atoms, rules, max_iter=20):
    while True:
        new = set()
        for r in rules:
            for binding in match(r.when, r.constraint, atoms):
                for t in r.then:
                    new.add(instantiate(t, binding, r.id, parents=binding.parents))
        added = new - atoms
        if not added: break
        atoms |= added
    return atoms
```

**O(rules × bindings)** — bindings 由对前两个 trigram 的索引切片得到，不全枚举原子集。

**provenance**：每条 derived atom 的 `derived_from` 是规则 id，`parents` 是 binding 里实际匹配的 atom id 列表。viz 渲染反向链就靠这两个字段。

## 为什么这个形状

1. **atoms 是只追加的事实**：上游 source 改了 → 重抽 → 全量重派生即可，不需要 diff 维护。
2. **rules 是 wiki 的一等 page**：可以 grep、可以 lint、可以版本化、可以单测、可以禁用（直接删那一份 markdown）。
3. **forward chain 让指数浮现**：rule r010 / r011 故意消费其他 rule 的 derived atom，链式触发——这是测"rules × atoms 是否真的乘法效益"的关键。
4. **provenance + dedupe**：撤销一条 bad rule = 删它的 markdown + 重跑；所有由它派生的 atoms 自动消失。

## 不在本 arc 做（明确）

- LLM 写 rules / 抽 atoms
- 接入主 `wiki/` 或 `docs/`
- BM25 / 向量库
- DSL 加 negation / 算术
- web UI / 多用户
- conversation-time 增量维护（本 demo 是 batch 离线）
