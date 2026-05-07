# AgentTest — 项目计划

> **S4 重写（2026-05-07）**：本文档在 Sprint 4 engine→skill 转型后重写。
> 转型前版本（FastAPI engine + analyzer/retriever/generator/validator
> 流水线 + 合成注入 eval）保留在 git 历史 commit `99df6e0` 之前。§ 8
> 归档了架构演进。本文档与 [`docs/ASSIGNMENT.md`](ASSIGNMENT.md) 冲突时
> 以 ASSIGNMENT 为准。

## 1. 项目名称

**AgentTest** —— 一个 Claude Code skill，为 Java AI agent 代码（Spring
AI / LangChain4j / MCP）生成 JUnit 5 测试，锚定在 OWASP LLM Top 10 的
canonical 攻击载荷上。

skill 针对三类 OWASP / Agentic-2026 风险——这些风险是上游 Spring AI /
LangChain4j / MCP Java 样本里**真实存在**的：

1. **LLM01 / ASI01** —— 直接 prompt 注入（template-breakout 字符、
   conversation-turn 标记、instruction-shape 短语）以及通过响应回流、
   tool 输出、evaluator 反馈的间接注入。
2. **LLM06 / ASI02 / ASI04 / ASI05 / ASI08** —— excessive agency
   （LLM 控制的迭代无界、tool 描述与实现漂移、MCP tool 定义投毒、级联
   sub-agent 失败）。
3. **LLM02** —— 敏感数据泄漏到 prompt 或日志中。
   *（在 N=3 评估中暂未覆盖 —— `spring-ai-examples` 没有干净的
   log-handler 目标。）*

OWASP 是**评估的 ground truth**：catch 准则是机械的（`mvn test` 退出码
+ 在断言消息上 grep 正则），**不用 model-as-judge**。skill 对早期框架
里"agent 模式正确性"和"可靠性"两类的覆盖也走同一棵规则树，但**不计入
头条指标**。

## 2. 目标用户、工作流与业务价值

**用户。** 在 Spring AI / LangChain4j / MCP 这套技术栈上构建 AI agent
产品的 Java 开发者。主要画像是一名独立工程师或一个小型团队，负责一个
多租户 agent 代码库，自己写 JUnit 测试。设计最初锚定在作者维护的一个
真实 Spring Boot 多租户 agent 代码库上；该代码库**不进入交付物，grader
看不到，也不进入 eval 集**。AgentTest 在 `spring-ai-examples` 的三个
真实 OSS 文件上评估（§ 5）。

**重复性任务。** 给新写或刚改过的 agent 代码写单元测试。其中**最痛**
的子集是 *agent 特定* 的测试 —— 通用 Java 测试生成器看不懂的不变量：

- **安全性**（OWASP-anchored）：prompt 模板组装时的注入漏洞、敏感数据
  漏到 prompt 或日志、多租户边界违规、tool 描述与实现的偏离
  （excessive agency）。
- **Agent 模式正确性**：tool schema 与实现的契约一致性、prompt 模板跨
  refactor 的稳定性、RAG context 不变量（只有检索到的 context 进
  prompt）。
- **可靠性**：retry / circuit-breaker 误配、瞬态故障下的幂等性。

其中**安全性**这一项与 OWASP Top 10 for LLM Applications、OWASP LLMSVS、
OWASP Top 10 for Agentic AI 2026 对齐 —— 也是我们做**客观评测**用的那
一类（§ 5），因为真实 OSS 代码已经展示这些风险（不需要合成注入）。
通用 AI 测试生成工具（TestSpark、ChatUniTest、Diffblue 等）只优化通用
代码上的 line coverage 和 mutation score，**没有 agent 分类法、没有
Spring AI / LangChain4j / MCP 知识**，所以系统性地漏掉这一类 bug。

**工作流的起点和终点。** 工作流的起点是开发者在 Claude Code 里对一个
实现 agent 逻辑的 Java 类（`ChainWorkflow.java`、`OrchestratorWorkers.java`、
`MathTools.java` 等）输入 `/agenttest <java-file>`。终点是开发者 review
完一份生成的 JUnit 5 测试类，并决定接受到 `src/test/java/...` 或者
拒绝。**生成的测试只是建议，不是权威 —— 每条测试人都要看过才能落地**，
既因为 LLM 写的 test 可能锁错不变量（见 § 5 cross-cutting findings），
也因为课程作业的 "where a human should stay involved" 要求这条 control
必须显式存在。

**为什么这个工作流的提升有价值。** Agent 代码相比传统 Java 代码暴露
在一类特殊 bug 上 —— prompt injection、tool 契约漂移、敏感数据外泄、
多租户边界失败、瞬态故障下的 retry / 幂等性破坏。这些 bug 又恰好对
**传统测试套件不可见**（传统测试测功能正确性，不测对抗鲁棒性、也不测
agent 模式契约）。把"通用 AI test gen 工具会写的"和"agent 代码实际
需要测的"之间的差距填上，每周给开发者省下几小时手写这一类测试的时间，
降低 agent 类 bug —— 安全、正确性或可靠性 —— 漏到生产的概率。

## 3. 问题陈述与 GenAI 适配

**精确的任务。** 给定一个含 AI agent 逻辑的 Java 源文件，输出一个
JUnit 5 测试类。每条生成的测试方法必须：

1. 针对一个具体的 OWASP 风险（如 LLM01、LLM06）
2. 引用输入类中的调用点或方法作为目标
3. 产生 JUnit 5 + Mockito + AssertJ 断言：**当代码实现了该风险时
   FAIL，代码干净时 PASS**（V_buggy/V_clean 方法论 —— § 5）
4. 能在标准 Maven `spring-boot-starter-test` classpath 下编译通过

**为什么用 GenAI。**

- OWASP 风险描述是英文，含隐式语义上下文（如 LLM01：*"Prompt Injection
  occurs when user prompts alter the LLM's behavior or output in
  unintended ways…"*）。把这映射到一个 Spring AI prompt 模板组装调用
  点需要语言理解 —— 不是关键词匹配、不是静态分析规则。
- 生成可编译的 JUnit 5 + Mockito 源码，**测试代码在对抗输入下的行为**
  是不折不扣的 generation。断言要捕获的不变量是 LLM *从* OWASP 风险
  描述 *推断* 出来的，针对 *具体* Java 代码。
- 避免**循环断言**失败模式（LLM 写"代码做了什么就断言什么"）需要分别
  推理 *契约*（函数在攻击下 *应该* 怎样）和 *实现*。

**为什么简单方案不够。**

- **静态分析器**（SpotBugs / SonarQube / SemGrep）能标模式但不能输出
  可执行 JUnit 测试，规则库也不覆盖 OWASP LLM 类别。
- **基于模板的测试生成器**输出的是 coverage-driven 样板代码，不是
  风险针对的对抗测试。
- **通用 LLM 测试生成器**（TestSpark、ChatUniTest、Qodo Cover）优化
  的是通用代码上的 line coverage 和 mutation score。它们的评估基准
  （HumanEval-Java、Defects4J）不含 agent 代码、也不含 OWASP 类 bug。
  它们写的测试在 prompt-injection 漏洞代码上会 PASS，因为那段代码
  功能上"works" —— § 5 N=3 证据：vanilla Claude 在三个样本上都暴露
  了这个失败模式。
- **运行时 LLM 红队工具**（Garak、Spikee、AutoRedTeamer）测的是已部署
  的系统，不针对源码生成单元测试。

交集 —— *源码级、OWASP 对齐、Java agent 特定、JUnit 输出* —— 是先前
工作里的空白。

**为什么走 Claude Code skill（skill-native）而不是独立 engine。**
S4 架构转型是核心设计决策。skill-native 路径胜过 engine 路径有三个
理由：

1. **Skill 设计哲学契合。** Claude Code skill 是 prompt-time
   增强 —— markdown 规则加载到用户已有会话。独立 engine 调 Anthropic
   违反这个 convention，还要给用户加一把第二个 API key。
2. **没有第二个 LLM 调用成本。** 用户的 Claude Code 订阅已经包含
   LLM 调用。独立 engine 让花费翻倍。
3. **真实 classpath 对齐。** 用 stub Spring AI jar 验证的 engine 测的
   是用户从来不存在的世界。skill 在用户真实的 mvn classpath 上跑
   `mvn test`。

skill 的价值在于 **OWASP 锚定 + agent 模式识别 + invariant test 纪律**，
打包成 12 个按需加载的 markdown 规则文件。不是更花哨的 LLM 调用。

## 4. 系统设计与 baseline

### 架构

```
用户在 Claude Code:  /agenttest src/main/java/com/example/Foo.java
                              │
                              ▼
                      [SKILL.md, 7 步编排]
                              │
       Step 1: 读目标 + 分类 agent pattern
              ├── chain workflow / prompt assembler  → 加载 rules/patterns/chain-workflow.md
              ├── iterative agent (变长 LLM 循环)   → 加载 rules/patterns/iterative-agent.md
              ├── tool handler / MCP server          → 加载 rules/patterns/tool-handler.md
              └── log handler                        → 加载 rules/patterns/log-handler.md
              （都不匹配则 refuse）
                              │
       Step 2: 加载匹配的 OWASP 规则
              ├── chain / iterative → rules/owasp/llm01-prompt-injection.md
              ├── iterative / tool   → rules/owasp/llm06-excessive-agency.md（5 sub-section）
              └── log handler        → rules/owasp/llm02-sensitive-disclosure.md
                              │
       Step 3: 读通用纪律规则
              ├── rules/general/attack-payload-assertions.md
              └── rules/general/existing-test-awareness.md
                              │
       Step 4: 规划测试用例（Given/When/Then 表）
                              │
       Step 5: 通过 AskUserQuestion 让用户确认
                              │
       Step 6: 读 Java 规则 → 生成测试类
              ├── rules/java/junit-template.md
              └── rules/java/chatclient-mocking.md（Spring AI fluent API）
                              │
       Step 7: 验证（rules/post-generation/verify.md）
              ├── mvn test-compile（最多 5 次重试）
              └── mvn test -Dtest=<TargetClass>AgentGenTest
                              │
                              ▼
              JUnit 5 源码打印；用户 review 后再决定是否
              写到 src/test/java/（advisory，绝不自动 merge）
```

总共 12 个 markdown 文件。SKILL.md 约 150 行；规则文件每个约 50–250 行，
按 Step 1 分类结果按需加载。

### 阶段（skill 工作流 vs. engine 工作流）

| 阶段 | engine 时期（S1-S3，已删） | skill 时期（S4，当前） |
|---|---|---|
| 模式识别 | Python AST 分析器（`javalang`） | Claude 通过 Step 1 规则读取 + 分类 |
| 风险目录 | YAML（`engine/configs/owasp.yaml`） | Markdown（`rules/owasp/*.md`） |
| 生成 | Sonnet 4.6 经 Anthropic API | Claude Code 会话（用户订阅） |
| 编译关 | `javac` in-memory + JavaParser | 用户工程里的 `mvn test-compile` |
| 运行关 | 自定义 runner + stub classpath | 真实 Maven classpath 上的 `mvn test` |
| Refusal | 结构化 JSON `refused: bool` | SKILL.md 的 "no agent pattern → refuse" |

### 用户看到 / 做什么

**单一界面：在 Claude Code 里 `/agenttest <java-file>`。** 没有独立
CLI、没有 FastAPI 服务、没有 API key。skill 在用户已有 Claude Code
会话里运行。

README 带 grader 走完安装（`bin\install-skill.ps1`）、调用、一个端到
端示例 + 样本输出。

### 课程概念怎么落地

作业要求至少两个；设计自然落到三个 skill-native 架构对得上的：

**1. 多步编排（Week 5）。** SKILL.md 的 7 步工作流，多个步骤有显式
refuse 条款。每步有类型化期望；如果 `mvn test-compile` 重试后仍失败，
skill 不能越过 Step 6。

**2. 结构化输出（Week 2-3）。** Step 7 打印测试源码 + Given-When-Then
用例表 + 期望 OWASP 风险 ID 列 + 验证报告（每方法在 V_buggy 和 V_clean
上的 PASS/FAIL）。用户看到结构化视图，不是大段文本。

**3. 治理 / 部署 control（Week 6）。** 显式 human-in-the-loop ——
**skill 不会**没经用户确认就写到 `src/test/java/`。每条测试都是
advisory。完整 control 列表见 § 7。

*RAG（Week 4）有意没用。* 转型前 engine 在 OWASP 目录 + agent-pattern
库上做了 RAG。skill 用按 Step 1 分类按需加载约 12 个 markdown 规则
文件替代了它 —— 更简单、没 embedding 服务、没第二个 key。转型理由
见下面 § 8。

### Baseline

**Baseline = 装了 skill 但不调用 `/agenttest` 的 vanilla Claude Code
会话。** 同一个 Claude Code 构建版本。用户原文输入一句 prompt：

> 帮我给 `<File>.java` 写一个测试

这是**公平**的 —— 因为这就是开发者单用 Claude Code 会写的方式。同样
模型、同样 fluent API 访问（Mockito、AssertJ、Spring AI 类型）、同样
的 Java 工具链。**只有 OWASP 锚定 / 攻击载荷断言纪律不一样**。
**没有工具不对称。**

锁定的 baseline prompt 在 2026-05-06 用 Claude Code v2.x 录的。三个
vanilla 输出原文 commit 在
[`experiments/{chainworkflow,orchestratorworkers,evaluatoroptimizer}/test_vanilla.java`](../experiments/)。

## 5. 评估方案与结果

### 方法论

对每个 (sample, mode) 其中 `mode ∈ {vanilla, skill}`：

```
V_buggy  = 上游代码原样（含真实 OWASP 风险）
V_clean  = 手修版本（sanitize() helper + 适用时的有界循环）

A = WITH skill 的 Claude Code 输出（/agenttest 调用）
B = WITHOUT skill 的输出（锁定 baseline prompt）

把 A 或 B 落进 V_buggy → mvn test → 期望 FAIL（catch / recall）
把 A 或 B 落进 V_clean → mvn test → 期望 PASS（precision）
```

**Catch 准则**：(测试集, V_buggy) pair 算 "catch" 当且仅当 `mvn test`
非零退出 AND 失败消息匹配
`(?i)(sanitize|injection|template.?breakout|system\s*:|prompt.?inject)`。
允许人工 spot-check **删除**误 catch，但**不允许新增**。

**Precision 准则**：测试集每条测试在 V_clean 上 PASS。

### 测试集组成

[`spring-projects/spring-ai-examples`](https://github.com/spring-projects/spring-ai-examples)
@ commit `2a6088db3d18d5fa6fc208b12adf1172d22f77fd` 中的三个真实 Java
文件：

| 样本 | Pattern | 真实 OWASP 风险 |
|---|---|---|
| `agentic-patterns/chain-workflow/.../ChainWorkflow.java` | chain workflow | 第 121 行 `String.format("{%s}\n {%s}", prompt, response)` 把用户输入 + LLM 响应循环进下一步 prompt 不做 sanitize（LLM01 直接 + 间接） |
| `agentic-patterns/orchestrator-workers/.../OrchestratorWorkers.java` | iterative-agent (fan-out) | 第 189 行 `tasks` 列表无上限被 LLM 控制（LLM06 / ASI08）；`taskDescription` + `task.type/description` 不 sanitize 流入 prompt（LLM01 + ASI07） |
| `agentic-patterns/evaluator-optimizer/.../EvaluatorOptimizer.java` | iterative-agent (递归) | 第 212–235 行无上限递归循环（只有 PASS 才退出 —— LLM06 / ASI08）；evaluator `feedback` 流入下一轮 `context` 不 sanitize（LLM01 indirect / ASI04） |

这三个都是真实 OSS 文件，含真实 bug —— 不需要合成注入。前文 engine
eval（§ 8）那个 self-validation 问题在结构上不存在：bug 不是我们写的。

### 结果（N=3 最终头条）

| 样本 | skill catches | skill precision | vanilla catches | vanilla precision |
|---|---|---|---|---|
| ChainWorkflow | **4 / 4** ✓ † | 5 / 5 ✓ | 0 / 5 ✗ | 5 / 5 ✓ |
| OrchestratorWorkers | **4 / 4** ✓ | 4 / 4 ✓ | 0 / 7 ✗ | 7 / 7 ✓ |
| EvaluatorOptimizer | **4 / 4** ✓ | 4 / 4 ✓ | 0 / 7 ✗ | 7 / 7 ✓ |
| **合计** | **12 catches** | 13 / 13 PASS | **0 catches** | 19 / 19 PASS |

† ChainWorkflow 的 skill 输出有 4 个攻击载荷测试 + 1 个 sanity 测试
（设计上始终 PASS）；catch 分母只算攻击载荷测试。precision 算全部 5 个。

**12-0 catch 差距。** 双方 precision 都干净 —— 谁都不在 V_clean 上误报。

### Cross-cutting 发现（完整版：[`experiments/realworld-results.md`](../experiments/realworld-results.md)）

**Finding 1 —— vanilla 技术能力够，缺的是 framing。**
三次 vanilla 输出都用对了 Spring AI 1.0 fluent API mock
（`ChatClient.ChatClientRequestSpec`、`CallResponseSpec`、
`PromptUserSpec`）、用对了 `ArgumentCaptor.getAllValues()`、用对了
`verify(times(N))` 调用次数模式。但每条 vanilla 测试都是 *behavior-match*
（"代码做了什么"），不是 *invariant*（"代码无论当下状态如何 *应该*
做什么"）。差距纯粹是 framing —— **同工具，反方向**。

**Finding 2 —— 间接注入覆盖跨 pattern 一致。** 三个 skill 输出都抓到
了对应 pattern 的间接注入面：
- ChainWorkflow：LLM 响应 → 下一步 prompt
- OrchestratorWorkers：orchestrator 的 `task` 字段 → worker prompt
- EvaluatorOptimizer：evaluator 反馈 → 下一轮 context

skill 的 `rules/owasp/llm01-prompt-injection.md` 把这条记为 agent
代码里杠杆最高的攻击面。N=3 的证据说明 skill 教 Claude 跨不同 pattern
形态（响应循环、扇出、递归）识别同一个面。

**Finding 3 —— V_clean 范围必须配齐 catch 范围（方法论教训）。**
两个 stretch 样本的第一版 V_clean 只修了 bounded-loop OWASP 风险
（`LLM06`），理由是这是"stretch 特有的"风险。但 skill 也抓到了两个
样本的 LLM01 prompt-injection 变种 —— 所以 V_clean v1 在 4 个 skill
测试上 precision = 0/4。V_clean v2（已 commit）补上了对输入和 LLM
输出字段的全面 `sanitize()`。教训：V_clean 必须是对 skill 标识的
**所有** OWASP 风险的全面修复，不只是头条风险。不全的 V_clean 是
V_clean 缺陷，不是 skill 缺陷。

**Finding 4 —— skill 规则一致性 gap（未来工作）。**
`rules/patterns/iterative-agent.md` Invariant 1（有界递归）显式接受
通过 `assertThatThrownBy` 抛异常的修法。Invariant 2（LLM 决定的扇出
封顶）只用裸 `verify(atMost(...))` 不接异常 —— 意味着抛异常的 V_clean
会让测试 ERROR。我们绕开了：在 `OrchestratorWorkers_fixed.java` 用
truncate。skill 规则应该接受任一种修法；这条进了未来工作清单。

### 局限 / 项目在哪里崩

- **N=3 是存在性证明，不是 benchmark。** 普遍主张（"skill 在所有
  Java AI 代码上 > vanilla"）需要 N=15+ 跨更多 pattern + 框架。
  超出 Week-7 交付物的范围。
- **样本是自选的。** 我们挑 iterative-agent 子类型恰恰因为 skill 对
  它们的规则没端到端验过。`tool-handler`、`log-handler`、MCP server
  pattern **未在** Phase 2 端到端验证。
- **仅支持 Maven。** skill 依赖 `mvn test-compile` 和 `mvn test`。
  Gradle、Bazel 或非 Maven 工程在 skill 验证步之外。
- **仅支持 Java。** 不支持 Kotlin、Scala 或其他 JVM 语言。
- **仅 Spring AI 1.0 fluent API。** chatclient-mocking 规则编码了
  Spring AI 特定的 `ChatClient.prompt().user(...).call()` 形态。
  LangChain4j 和裸 MCP 客户端 API 不同；规则主要覆盖 Spring AI。
- **Catch 准则正则要人工 spot-check 误报**（N=3 中无误报）。允许删
  误 catch，但不允许新增。

## 6. 示例输入与发现

### 示例 1 —— `ChainWorkflow.java`（Phase 2 anchor）

**真实上游 OWASP 风险**：第 121 行
`String input = String.format("{%s}\n {%s}", prompt, response);`
之后 `response = chatClient.prompt(input).call().content();`。
用户输入直接进 step 0 的 prompt；LLM 响应循环进 step 1 的 prompt；
两个面都不 sanitize。

**期望风险**：LLM01 Prompt Injection（直接 + 通过响应循环的间接）。

**Skill 输出**（5 条测试，节选）：4 条攻击载荷测试断言 `}}` /
`<|im_start|>` / `[INST]` / `Ignore above` 的载荷字符不在链式调用中
任何捕获到的 prompt 里幸存；1 条 sanity 测试断言 chain 进行 4 次 LLM
调用（每个 `DEFAULT_SYSTEM_PROMPTS` 条目一次）。V_buggy 上 4/4 catch；
V_clean 上 5/5 PASS。

**Vanilla 输出**（5 条测试）：全是 behavior-match。测试 #3 用了同样
的 `ArgumentCaptor.getAllValues()` recipe，但断言的是 *字面当前格式*
`"{PROMPT_A}\n {USER_INPUT}"` —— 这意味着把 buggy 行为锁进了测试。
0/5 catch。

### 示例 2 —— `OrchestratorWorkers.java`（Phase 2 stretch）

**真实上游 OWASP 风险**：第 189 行
`orchestratorResponse.tasks().stream().map(...)` 在 LLM 控制的
`tasks` 列表上迭代无上限 —— 一个被投毒的或 runaway 的 orchestrator
响应能 spawn 任意数量 worker LLM 调用。加上 `taskDescription` 和
`task.type/description` 直接进 prompt 参数。

**期望风险**：LLM06 / ASI08（cascading failures）、LLM01 / ASI07
（agent 间通信）。

**Skill 输出**（4 条测试）：通过用户 task 的 template-breakout、通过
orchestrator 输出 Task 字段的 `<|im_start|>` 标记、通过 Task 字段的
Llama `[INST]` 标记、**mock LLM 输出 1000 个 task → 断言 worker 数被
封顶**。V_buggy 上 4/4 catch；V_clean 上 4/4 PASS。

**Vanilla 输出**（7 条测试）：全是 behavior-match。没有 mock 1000-task
响应；没有注入 template-breakout 载荷。0/7 catch。

### 示例 3 —— `EvaluatorOptimizer.java`（Phase 2 stretch）

**真实上游 OWASP 风险**：第 212–235 行是无界递归 `loop()`，唯一退出
是 `evaluation == PASS`。永不返回 PASS 的 evaluator 会触发
`StackOverflowError`。Evaluator `feedback` 直接进下一轮 `context`。

**期望风险**：LLM06 / ASI08（有界递归）、LLM01 indirect / ASI04
（被投毒的反馈再注入到 generator context）。

**Skill 输出**（4 条测试）：通过用户 task 的 template-breakout、通过
用户 task 的 OpenAI 标记、**evaluator 返回带投毒反馈的 NEEDS_IMPROVEMENT
→ 断言第二轮 context 不漏标记**、**evaluator 永不返回 PASS → 断言
调用在有限 LLM 调用次数内终止**。V_buggy 上 4/4 catch；V_clean 上
4/4 PASS。

**Vanilla 输出**（7 条测试）：全是 behavior-match。测试断言具体的
3 轮迭代序列，不是有界终止。0/7 catch。

### 预期的失败模式

转型前 engine eval（§ 8）显式列了六种失败模式（hallucinated assertion、
tautological assertion、OWASP 错分类、编译失败、pattern 库过期、
over-suggestion）。skill 时期的对应物：

| 失败模式 | skill 工作流的 mitigation |
|---|---|
| Hallucinated assertion | 在 V_buggy + V_clean 上跑 mvn test —— V_clean 跑能抓到在干净代码上也 fail 的断言 |
| Tautological assertion | rules/general/attack-payload-assertions.md 强制要求测试断言载荷不幸存，不是字面格式相等 |
| Pattern 误分类 | SKILL.md Step 1 不匹配则 refuse；不会 fallback 到通用模式 |
| 编译失败 | SKILL.md Step 6 重试 `mvn test-compile` 最多 5 次，把无法修复的失败诚实暴露 |
| Pattern 库过期 | 12 个 markdown 文件 version control；带日期戳（规则注明 "verified 2026-05-07"） |
| Over-suggestion | SKILL.md Step 4 让用户在生成前确认测试用例 |

## 7. 风险与治理

**系统在哪可能失败。**

- OWASP 风险 → Java pattern 映射是新东西，可能在覆盖的 4 种 pattern /
  3 种风险类之外不完整。
- N=3 结果是 N=3 —— framing 差距可能不能推广到所有 Java AI agent 代码。
- Spring AI / LangChain4j / MCP 都演化得快；
  `rules/java/chatclient-mocking.md` 规则编码 Spring AI 1.0 特定的
  fluent API，2.x 出来时需要更新。
- 仅 Maven 验证。

**系统不该被信任的地方。**

- 不是替代人工 agent 代码安全审查。
- 不覆盖 curated 类别外的 OWASP 风险（skill 在不识别的目标上 refuse）。
- 不支持 Java 之外的语言。
- 不适用于非 agent Java 代码（skill 没有合适的 pattern 可以 apply）。

**Control（人在哪个环节介入）。**

- **永远 human-in-the-loop。** 每个生成的测试类都是 advisory；SKILL.md
  Step 7 显式说"未经用户显式确认不写到 `src/test/java/`"。**没有任何
  生成的测试会自动 merge 进项目。**
- **强制 OWASP 引用。** 每条生成的测试方法 javadoc 引用一个具体 OWASP
  风险 ID。没有引用的测试 review 时被 drop。
- **两阶段验证。** SKILL.md Step 6 跑 `mvn test-compile`（catch
  无法编译的输出）AND `mvn test -Dtest=<…>AgentGenTest`（catch 在
  用户实际代码上没注入也 fail 的断言）。失败被报告，不被隐藏。
- **Refusal 是一等输出。** Step 1 不识别 agent pattern 时 SKILL.md
  说："no agent pattern detected; AgentTest does not apply." 不编造。
- **Pattern 库是 version control 的 markdown。** 全部 12 个规则文件
  在 `claude-skill/agenttest/rules/`，可 diff review。

**数据、隐私、成本。**

- *隐私*：AgentTest **不**收集、记录或持久化任何用户数据。Java 源码
  被 Claude Code 读，和用户自己 session 读任何文件一样。**没有第二个
  LLM provider 调用。**
- *API key*：**不需要。** skill-native 架构意味着用户已有的 Claude
  Code 订阅覆盖所有 LLM 调用。README 显式说明这一点。
- *成本*：边际 $0 —— 用用户的 Claude Code 订阅。
- *复现*：`git clone` → `bin\install-skill.ps1` → 在任何 Maven Java
  工程的 Claude Code 里 `/agenttest <file>`。README 带 grader 走完
  端到端示例。

## 8. Sprint 历史（S1–S5，Week 4–8）

| S | Week | 发生了什么 |
|---|------|------------|
| **S1** | 4 | 仓库 skeleton：pyproject + agents wiring，1 条 risk-site 规则的 analyzer，retriever stub，generator stub。端到端 FastAPI engine 流水线在 1 个示例上跑通，输出一条 dummy JUnit 方法。 |
| **S2** | 5 | 真正的 LLM01 generator prompt。带 4 个风险的 OWASP 目录 YAML。Validator（parse + compile + clean-input check）。5 个手工测试用例。第一组 recall 数据（4/6 = 66.7%）。 |
| **S3** | 6 | **课程 Week-6 检查点。** Agent-pattern retrieval 加上。Baseline endpoint 上线。测试集扩到 6 个。头条：pipeline 4/6 = baseline 4/6 —— 同 recall，**不同失败模式**（pipeline 在 validator gate drop；baseline 出错不变量测试）。 |
| **S4** | 7 | **Sprint 中段架构 review 把 engine 转型为 skill-native。** Engine 删除（commit `99df6e0`）。Skill scaffold + 12 模块化规则编写。Phase 2 真实评估在 `ChainWorkflow.java`（anchor）+ `OrchestratorWorkers.java` + `EvaluatorOptimizer.java`（stretch）上 —— N=3 最终头条 12-0。README + project_plan 重写。 |
| **S5** | 8 | （计划中）lightning 答辩 slides。README 最终版。Demo clip。（可选 polish：log-handler 验证、MCP 目标验证。） |

### S4 转型理由（节选自 sprint-4.md § "Why pivot"）

S1–S3 建了一条复杂的 engine 流水线，假设"skill = 外部服务的 wrapper"。
S4 sprint 中段 review 暴露了四个问题：

1. **Self-validation 问题。** S2/S3 写样本时知道要注入什么 bug，然后
   测同样样本的 catch。封闭循环，可信度弱。
2. **Validator gate 的 classpath 是 fixture-specific 的。** 真正的
   Spring AI 用户用 mvn 编译针对真实 Spring AI jar —— 我们 stub-only
   的 validator 测的是用户从来不存在的世界。
3. **产品界面不清。** 一个 FastAPI 服务不是面向用户的。
4. **Skill 设计哲学不匹配。** Claude Code skill 是 prompt-time 增强，
   不是外部 LLM 服务。架构 "skill → CLI → engine → Anthropic API"
   违反 skill convention，还要给 grader 加第二把 API key。

S4 排他地转向 skill-native。Engine（约 5000 行 Python + 200 行 Java +
合成 eval 工具）在 commit `99df6e0` 删除。方法论的严格性靠机械的
clean-vs-buggy `mvn test` PASS / FAIL 在真实 OSS 代码上保证 —— 没有
人工评估，没有 model-as-judge。

转型前 engine 代码可以从 git 历史在 `99df6e0` 之前的任何 commit 恢复
（如 `git show 4359ac7:engine/...`）。S2/S3/S4 的 sprint 计划文档
（gitignore 于 `docs/plan/`）保留了详细的阶段追踪、锁定决策和
转型前 artifact 处置说明，需要考古时本地参考。

## 9. Pair request

N/A —— 个人项目。
