# AgentTest — 项目计划

## 1. 项目名称

**AgentTest** —— 面向 Java AI agent 代码的 security-aware 单元测试生成器。

## 2. 目标用户、工作流与业务价值

**用户。** 在 Spring AI / LangChain4j / MCP 这套技术栈上构建 AI agent 产品的
Java 开发者。主要画像是一名独立工程师或一个小型团队,负责一个 multi-tenant
agent 代码库,自己写 JUnit 测试。设计锚定在作者本人维护的一个真实 Spring Boot 多租户
agent 代码库上,但**该代码库不进入交付物、grader 看不到、也不进入 eval 集**;
AgentTest 仅在合成样本上评估(见 § 5)。

**重复性任务。** 给新写或刚改过的 agent 代码写单元测试。其中**最痛**的子集
是 *security-相关* 的测试:抓 prompt 模板组装时的注入漏洞、tool schema 与
实现的不一致、敏感数据漏到 prompt 或日志、multi-tenant 边界违规、retry /
circuit breaker 的误配。这些恰好就是 OWASP Top 10 for LLM Applications、
OWASP LLMSVS、OWASP Top 10 for Agentic AI 列出的风险类别。**通用**的 AI 测试
生成工具(TestSpark、MutGen、ChatUniTest、Diffblue)只优化通用代码上的 line
coverage 和 mutation score,**没有风险分类、没有 Spring AI 特定知识**,所以
系统性地漏掉这一类 bug。

**工作流的起点和终点。** 工作流的起点是开发者把 AgentTest 指向一个实现 agent
逻辑的 Java 类(`MenuMcpServer.java`、`RestaurantPromptAssembler.java` 等)。
终点是开发者 review 完一份生成的 JUnit 5 测试类文件,并决定接受到
`src/test/java/...` 里,或者拒绝。**生成的测试只是建议,不是权威 —— 每条测试
人都要看过才能落地**,既因为 LLM 写的 test 可能锁错不变量,也因为课程作业的
"where a human should stay involved"一节要求这条 control 必须显式存在。

**为什么这个工作流的提升有价值。** Agent 代码相比传统 Java 代码暴露在一类
特殊 bug 上 —— prompt injection、tool 滥用、敏感数据外泄、multi-tenant 边界
失败。这些 bug 又恰好对**传统测试套件不可见**(传统测试测功能正确性,不测
对抗鲁棒性)。把"通用 AI test gen 工具会写的"和"agent 代码实际需要测的"
之间的差距填上,每周给开发者省下几小时手写 risk-specific 测试的时间,降低
OWASP 类 bug 不知不觉上线的概率。

## 3. 问题陈述与 GenAI 适配性

**精确任务。** 给定一个含 AI agent 逻辑的 Java 源文件,输出一个 JUnit 5 测试
类。每个生成的 test method 必须:

1. 命中一个具体的 OWASP risk ID(如 `LLM01_Prompt_Injection`)
2. 引用输入类里具体的行范围或方法
3. 用 JUnit 5 + Mockito 的 assertion **在风险被触发的代码上 fail,在干净
   代码上 pass**
4. 能在标准 Spring Boot Test classpath 下编译通过

**为什么需要 GenAI。**

- OWASP 风险描述是带隐式语义的英文(如 LLM01:*"Prompt Injection occurs
  when user prompts alter the LLM's behavior or output in unintended
  ways…"*)。把这段英文映射到 Spring AI 里某个具体的 prompt 模板组装
  调用点 —— 这需要语言理解,不是关键字匹配,也不是静态分析的 pattern
  规则
- 生成可编译的 JUnit 5 + Mockito 源代码、并且**测试该代码在对抗输入
  下的行为**,毫无疑问是生成任务。assert 必须捕捉的是 LLM 从 OWASP
  风险描述**推断**出的、**应用到这段具体 Java 代码上的**不变量。任何
  template-based 生成器都做不到
- 避开 *tautological assertion*(LLM 写一个"代码做啥就 assert 啥"
  的测试)这个失败模式,需要 LLM 推理 *contract* —— 这段函数在攻击下
  *应该*怎么做 —— 而不是 *implementation*

**为什么更简单的方案不够用。**

- 静态分析器(SpotBugs / SonarQube / SemGrep)能 flag pattern,但不能
  emit 可执行的 JUnit 测试,且它们的规则库不覆盖 OWASP LLM 类别
- Template-based test generator(Auto-Unit-Test-Case-Generator 等)
  写的是 coverage-driven 模板代码,不是 risk-targeted 对抗测试
- 通用 LLM test generator(TestSpark、ChatUniTest、MutGen、Qodo Cover)
  优化通用代码上的 line coverage 和 mutation score。它们的 benchmark
  (HumanEval-Java、LeetCode-Java、Defects4J)**不含 agent 代码、也不含
  OWASP 类 bug**。它们写的 test 在 prompt-injection-vulnerable 的代码
  上是 pass 的,因为代码功能上"work"
- Runtime LLM 红队工具(Garak、Augustus、Spikee、AutoRedTeamer)是探测
  已部署系统;不针对源代码生成 unit test,也不能测尚未部署的代码

这个交集 —— *源代码层面、OWASP-aligned、Java agent 特化、emit JUnit* ——
在 prior art 中是空白的,尽管这一直是 Spring AI / agent 开发社区里被公开
承认的痛点。

**RAG 的使用,需要 justify。** 作业要求"不滥用 RAG / multi-model,除非
确实有助于工作流"。我们用 retrieval 检索 OWASP 风险目录和 agent-pattern
库,理由:(a) OWASP 目录太长,塞不进每个 prompt;(b) agent-pattern 库教
LLM 识别输入中的 Spring AI / LangChain4j / MCP 习惯写法。**这两个 retrieval
源是否真的有用,本身就是评估的一类问题** —— 见 § 5 的 ablation。如果某
个 retrieval 源在 ablation 上没有显著提升 recall,**就从交付里砍掉**。

## 4. 系统设计与 baseline

### 架构

```
Java 源文件 (一个类)
    │
    ▼
[Analyzer]              JavaParser AST → 列出"风险相关的位点":
                        prompt 模板组装、tool 处理器签名、MCP 传输边界、
                        retry/CB 配置、租户边界方法。**无 LLM 调用** ——
                        deterministic
    │
    ▼
[Retriever]             对每个 (位点, 候选 OWASP 风险) 对,检索:
                        - OWASP 目录条目(描述 + 例子)
                        - 1–3 个 agent-pattern 库里相近的样例
                        - (可选) 项目本地上下文(CLAUDE.md)
    │
    ▼
[Generator]             Claude Sonnet 4.6,每个 (位点, 风险) 对一次调用。
                        输出 schema:
                        { risk_id, target_lines, test_method_source,
                          assertion_rationale, refused?: bool }
                        允许 refusal —— 如果该位点针对该风险写不出有
                        意义的 test,显式说不写
    │
    ▼
[Validator]             解析检查(JavaParser)+ 编译检查(in-memory javac)。
                        丢掉:
                        - 编译不过的
                        - 在干净输入上就 fail 的(说明 assertion 错的)
    │
    ▼
[Aggregator]            把活下来的 test method 合并进一个 JUnit 5 类;
                        解决 import;输出单个 .java 文件
    │
    │  通过 FastAPI :8000 + SSE 提供进度事件
    │  主交付面:CLI(grader 和 eval harness 使用)
    │  Bonus 交付面:Claude Code skill(可选,交互式)
    ▼
JUnit 5 源代码写到用户指定路径
```

### 各阶段

1. **Analyzer。** 纯 Java AST 分析。用 deterministic 规则识别 risk-relevant
   位点(如:一个接 `String` 参数并构造 `PromptTemplate` 的方法,是 LLM01
   prompt-assembly 的候选位点)。输出 `RiskSite` 记录 list,含文件路径、
   行范围、候选 OWASP 风险 ID。**这个阶段无 LLM 调用** —— 让 per-class
   成本低、analyzer deterministic、可缓存

2. **Retriever。** 对每个 `RiskSite`,检索:
   - 候选风险的 OWASP 目录条目(从 `configs/owasp.yaml` —— 我们覆盖的
     ~10 个风险的 curated YAML,每条含描述、Java 模式样例、test 模式样例)
   - 从 curated agent-pattern 库(`configs/patterns/{spring-ai,
     langchain4j, mcp}/...`)里基于 embedding 相似度检索 top 1–3 个
   - (可选) 项目 CLAUDE.md / CONTRIBUTING.md —— 仅当用户传 `--project-root`
     才取

3. **Generator。** 每个 (位点, 风险) 对,一次 Claude Sonnet 4.6 调用,
   prompt 是结构化的:
   - System: 角色定义 + JUnit 5 + Mockito 约定
   - User: OWASP 风险描述、agent-pattern 样例、目标位点的源码、要 assert
     的不变量
   - Output: 结构化 JSON,含 `risk_id`、`target_lines`、`test_method_source`、
     `assertion_rationale`、可选 `refused`

   模型被硬性要求:**要么 emit 一个能在风险变体上 fail 的测试,要么 refuse**。
   Refusal 是 first-class 输出,不是 fallback

4. **Validator。** 用 JavaParser 解析生成的 `test_method_source`;非合法
   Java 直接丢。用 stub classpath in-memory 编译;不过的丢。在干净输入类
   上跑这个方法;在干净输入上 fail 的丢(说明 assertion 写错了,而不是
   代码真有问题)

5. **Aggregator。** 把活下来的 method 合并进一个稳定命名的类
   (`<TargetClass>SecurityGenTest.java`),解决 import,头部注释列出覆盖
   的 OWASP 风险 ID

### 用户看到什么、做什么

**主交付面(grader-facing):一个 CLI。**
`python -m agenttest.cli generate path/to/Foo.java [--out FooSecurityGenTest.java]`
读 Java 源,在 pipeline 跑的同时把进度行(`analyzing → retrieving →
generating → validating`)流到 stdout,最后落一个 JUnit 5 测试类文件。
README 带 grader 把一个注入风险的样例端到端跑一遍。**CLI 才是作业评估
的对象。**

**Bonus 交付面(计划在 S5 推进,scope 允许时才做):Claude Code skill。**
`/agenttest analyze Foo.java` 会包同一个 FastAPI 引擎,把 SSE 进度事件渲染
到 Claude Code 终端。这是开发体验加成;**grader 不需要安装 Claude Code
就能评估这个项目** —— CLI 才是交付物。

### 课程概念怎么落地

作业要求至少两个;本设计自然命中四个。

**1. Multi-step orchestration(Week 5)。** 五段 pipeline:
`analyzer → retriever → generator → validator → aggregator`。每段都有
typed input/output 契约;通过 Protocol 而非共享状态拼装。这种拆分正是
§ 5 ablation 矩阵能跑得起来的前提 —— 每行只换或丢一段。

**2. Retrieval-Augmented Generation(Week 4)。** 两个 retrieval 源:
OWASP 风险目录(~10 风险,每条 ~200 token)和 agent-pattern 库(~30 个
pattern,每条 ~150 token)。两者都是 YAML,索引用
`sentence-transformers/all-MiniLM-L6-v2`(本地,首次 ~80 MB 下载,
无需额外 API key)。每个风险位点,从 pattern 库检索 top-3 + 匹配的
OWASP 条目,塞进 generator prompt。**RAG(对照"把整目录硬塞进每个
prompt")是否真的有用,通过 ablation 实证检验** —— 见 § 5。

**3. Structured outputs(Week 2–3)。** Generator 不返回自由文本。它返
回符合
`{ risk_id, target_lines, test_method_source, assertion_rationale, refused?: bool }`
schema 的 JSON。这让 refusal 成为 first-class 输出(而不是 parser 要去
检测的自由文本)、让 validator 单独校验 `test_method_source`、让 eval
harness 有确定的字段去抓 OWASP risk ID。

**4. Governance and deployment controls(Week 6)。** 计划里就内建:显式
human-in-the-loop(每条 test 都是 advisory,绝不自动合并)、强制 OWASP
引用(无引用的 method 丢)、Validator gate(编译不过 / 在干净代码上
fail 的 test 在用户看到前丢)、Refusal as output(没识别到风险位点时
emit 空 test 类 + 注释)。完整 controls 清单见 § 7。

### Baseline

**Baseline = 单 prompt 的 Claude Sonnet 4.6。** 同一个 FastAPI app 里
sibling 端点 `POST /generate/baseline`。同样的 Java 类输入,单 prompt:

> *"You are a security-focused Java test engineer. Given the following
> Java class implementing AI-agent logic, generate JUnit 5 + Mockito
> tests targeting common OWASP risks for LLM agents. Output one Java
> test class file."*

无 analyzer、无 retrieval、无 per-risk 循环、无 validator。Eval harness
对同一批 test case 调两个端点(`/generate` 和 `/generate/baseline`)。
这个 baseline 之所以**公平**:它就是开发者**只用 Claude**会做的事 ——
同样的 model、同样的 input、同样的 output 格式期望。

## 5. 评估计划

### Ground truth:合成注入

每个干净 Java 样本,定义一组 **risk injection** —— deterministic 的代码
编辑,引入一个已知的 OWASP 类 bug:

- LLM01(Prompt Injection):去掉 prompt 模板里的输入消毒;把 raw user
  input 直接拼到模板字符串里
- LLM02(Sensitive Information Disclosure):在可能含敏感数据的路径上
  注入 `log.info(request)`
- LLM06(Excessive Agency):让 tool 的 description 声明只读,但 implementation
  写数据
- Agentic-AI(多租户):删掉 privileged tool 调用前的 tenant ID 校验
- Resilience 相关:把 Resilience4j retry 配成对 transient error 类无限
  retry

每个 (干净样本, injection) 对,在**有 bug 的版本**上跑 AgentTest。生成
的 test 类编译并运行在:

- **有 bug 版本** —— 至少一条生成的 test 应当 fail(true positive:抓到
  注入的 risk)
- **干净版本** —— 没有生成的 test 应当 fail(true negative:无 false
  positive)

这是**完全客观**的。**主指标不依赖 model-as-judge**。

### Test set 构成

~20 个手动 curate 的干净 Java 代码样本,分布:

- Spring AI prompt 组装器和 `PromptTemplate` 消费方(~6)
- LangChain4j tool 定义和 tool handler(~4)
- MCP server tool 注册和 request handler(~4)
- 多租户 agent 代码(tenant-scoped tool 调用)(~3)
- Resilience 相关:retry / circuit breaker config 调用点(~3)

每个干净样本定义 1–3 个 risk injection → **共 ~30–50 个 test case**。
若样本合成跟不上,允许 Week 6 检查点先落到区间下界(~15 样本 / ~30 case)。

样本从真实 OSS pattern 合成(Spring AI 例子、LangChain4j 文档、MCP spec
例子)—— 不含任何专有代码。

### 指标

**主指标(客观):**

- **Recall@class**(catch 率):每对 injection 中,至少有一条生成的 test
  在 buggy 版本上 fail 的比例
- **Precision**(false-positive 率):生成的 test 中,在 clean 版本上
  错误 fail 的比例 —— 应接近 0
- **Per-OWASP-risk 拆分**:按风险类别(LLM01、LLM02、LLM06...)分别
  统计 recall 和 precision

**次要指标:**

- **Compilation rate**:生成的 test method 中能编译的比例
- **Refusal correctness**:无风险时,系统是否正确 refuse 而不是编一个
  test 出来
- **Latency**:每个 Java 类的秒数(目标 ≤ 60s)
- **Cost**:每个 Java 类的 $(目标 ≤ $0.10)

### Ablation 矩阵

| 配置 | Recall@class | Precision | Cost / class |
|---|---|---|---|
| Baseline(单 prompt,无 retrieval,无 analyzer) | | | |
| 仅 Analyzer(无 retrieval,generator 直接拿 raw 位点) | | | |
| Analyzer + OWASP 目录检索 | | | |
| Analyzer + Agent-pattern 检索 | | | |
| 全套(Analyzer + 两路 retrieval + validator) | | | |

每行在完整 test set 上跑一遍。**某层在 ablation 上若没有显著提升,该层
从交付里砍掉**(ASSIGNMENT.md:*"Do not use RAG, agents, or multiple
models unless they actually help"*)。

### 成功阈值

AgentTest 在 test set 上达到以下条件即视为成功:

- Recall@class ≥ 60%(抓住多数注入 risk)
- Precision ≥ 80%(干净代码上 false positive 少)
- 在 recall 上比单 prompt baseline 有可测的明显优势(≥ 15 个百分点)
- 每个 Java 类 60 秒、$0.10 以内

如果交付时未达,README 报告**实际达到了什么、哪些类别欠佳、可能的原因
假设**。诚实的负向结果是作业明确要求的输出之一:*"what worked, what
failed, where a human should stay involved."*

## 6. 输入示例与失败模式

### 输入示例

1. **`RestaurantPromptAssembler.assemble(String userQuery)`** ——
   一个 Spring AI prompt 构造器,把 `userQuery` 插到一个多租户 system
   prompt 模板里。**预期风险**:LLM01 Prompt Injection。预期 test:
   构造含模板 breakout 内容的 `userQuery`,assert 组装出的 prompt 不
   含 breakout

2. **`MenuMcpServer.searchMenu(SearchRequest req)`** —— 一个 MCP tool
   handler,tool description 说是"只读菜单搜索",但 implementation
   会增加 per-tenant 浏览计数(写)。**预期风险**:LLM06 Excessive
   Agency / Tool Description Mismatch。预期 test:assert 实际可观测
   的副作用与 tool description 一致

3. **`AgentLogger.logRequest(AgentRequest req)`** —— 调
   `req.toString()` 写日志。**预期风险**:`req` 含 header / 用户数据
   时的 LLM02 Sensitive Information Disclosure。预期 test:喂含 sentinel
   PII 字段的 request,assert 日志不含

4. **`OrderTool.execute(String tenantId, OrderArgs args)`** —— 不校验
   `tenantId` 和当前会话的 tenant 一致的 privileged tool。**预期风险**:
   多租户边界违规(OWASP Agentic-AI 类别)。预期 test:用错配的
   tenant 调用,assert 拒绝

### 预期的失败模式

1. **Hallucinated assertion** —— 生成的 test assert 一个连干净代码都
   不满足的不变量。*Mitigation*:validator 丢掉在 clean 版本上 fail
   的 test

2. **Tautological assertion** —— assert 代码当前的实现行为(等于把 bug
   锁死)。*Mitigation*:prompt 显式要求 test 命中**named OWASP risk**,
   以风险描述作为 contract reference。**风险描述是 oracle,不是 implementation**

3. **OWASP 误分类** —— analyzer 把一个位点标成 X 类风险,实际是 Y 类。
   *Mitigation*:per-risk recall 拆分能暴露这种偏差;analyzer 每个位
   点 emit 多个候选风险,generator 选最契合的

4. **Compilation 失败** —— 生成的代码用了不存在的 import / 符号。
   *Mitigation*:validator 编译检查在 aggregation 前丢掉

5. **Pattern library 过期** —— Spring AI / LangChain4j / MCP 演进很
   快,缓存的 pattern 可能过时。*Mitigation*:pattern 库放
   `configs/patterns/...`,version-controlled,可 diff review,加日期戳

6. **Over-suggestion** —— emit 一堆质量低的 test 而不是少量强 test。
   *Mitigation*:每对 (风险位点, OWASP 风险) 硬性 cap 一条;validator
   把多余的丢掉

## 7. 风险与治理

**系统可能在哪里失败。**

- OWASP 风险 → Java 模式的映射是新的,可能不完整
- 合成注入 eval 可能高估真实世界 recall(可控 bug 比真 bug 容易抓)
- Python 生态里的 Java AST 解析不如 Java 自身成熟 —— 兜底:开个 Java
  小工具子进程 emit AST 成 JSON,或者用 `javalang`(纯 Python parser,
  精度差些)
- Spring AI / LangChain4j / MCP 都在快速变,pattern 库会 drift

**系统不该被信任的地方。**

- 不能替代人对 agent 代码的安全 review
- 不覆盖目录外的 OWASP 风险(系统对未识别的位点类型会 refuse)
- 不适用 Java 以外的语言
- 不适用非 agent 的 Java 代码(系统没有适用的 pattern)

**控制措施。**

- **始终 human-in-the-loop。** 每个生成的 test 类都是 *advisory*;
  README 和 CLI 输出每次跑都明示(用 skill 时 skill UI 也会)。
  **任何生成的 test 都不会自动合并进项目**
- **强制 OWASP 引用。** 每条 emitted test method 引用具体的 OWASP risk
  ID。无引用的 test 丢掉
- **Validator gate。** 编译不过 / 在干净输入上 fail 的 test 不会到达
  用户
- **Refusal 是 first-class 输出。** 没识别到风险位点时,emit 空 test
  类 + 说明性注释 —— **绝不**编风险来填位
- **Pattern 库是 version-controlled config。** OWASP 目录和 agent-pattern
  库放 `engine/configs/`,可 diff review

**数据、隐私、成本。**

- *隐私*:AgentTest **不收集、不写日志、不持久化**任何用户数据。但
  提交的 Java 源**会传给 Anthropic** 做 Sonnet 调用。README 明示
  这一点,让用专有代码的用户在跑工具之前就能自己判断。pattern 库
  RAG 走本地 sentence-transformers 嵌入,**不引入第二个 provider**
- *API key*:README 列出 grader 唯一需要在 `.env` 配的 key ——
  `ANTHROPIC_API_KEY`(生成必需)。无需其他 provider 的 key
- *成本*:每类生成 ~$0.05–0.10;**完整 ablation 一轮 ≤ ~$20**(5 行
  ablation × ~50 个 case × ~$0.05–0.10/调用,synthesizer 的 system
  prompt 走 prompt cache)。在个人预算内;每次跑都跟踪,需要时可压缩
- *Reproducibility*:`cd engine && pip install -e ".[dev]" && pytest` 跑
  unit test;`python -m agenttest.cli generate <file.java>` 端到端跑
  一个例子。README 一步步带 grader 走

## 8. Sprint 计划

课程时间是 Week 4–8;本计划用 S1–S5 编号。

| S | Week | 目标 |
|---|------|------|
| **S1** | 4 | 骨架:pyproject + agents 接线(rename 之后已就位)、analyzer 含 1 条风险位点规则(prompt assembly)、retriever stub、generator stub。端到端 pipeline 跑过 1 个例子,emit 一个 dummy JUnit method |
| **S2** | 5 | LLM01 的真实 generator prompt。OWASP 目录 YAML 含 4–5 个风险。Validator(parse + compile)。5 个手工 case。第一组 recall 数字 |
| **S3** | 6 | **课程 Week-6 检查点。** Spring AI 的 agent-pattern retrieval(对 worked-example 代码库杠杆最大)。Baseline 端点上线。Test set 扩到 ~15 个 case。第一组 baseline-vs-AgentTest 对比数字 |
| **S4** | 7 | Test set 到 30–50 个 case。完整 ablation 矩阵。最弱风险类别的二轮调优。CLI 打磨。**README 初稿**(clone → 一个例子跑通)。预录 demo 视频拍掉 |
| **S5** | 8 | README 终稿。Lightning presentation 幻灯片。最终 eval run、最终数字。(可选)Claude Code skill 打磨作为 bonus 交付面 —— 仅当 CLI + README 已经 grader-ready 才做 |

**课程 Week-6 检查点**预期:端到端 pipeline 在 ≥ 15 个 case 上跑通、
覆盖 ≥ 3 个 OWASP 风险、baseline 端点上线、初版 recall/precision 数字
(即使 ablation 还没全做完)。Week 6 的目的是**有可信的初版测量**,
不是每个维度都赢。

**Lightning demo & artifact snapshot。** 2–3 分钟的幻灯片里夹一段
**预录 ~30 秒视频**:CLI 跑一个 prompt-injection 样例 → 展示生成的
test 类 → 同一条 test 在 buggy 版本上 fail、在 clean 版本上 pass。
README 把这段镜像成 sample-input / sample-output 块。ASSIGNMENT.md
对 lightning 不强制要求 live demo;预录视频是兜底,如果时间允许 CLI
跑一遍也够短可以现场试。

## 9. Pair request

N/A —— 个人项目。
