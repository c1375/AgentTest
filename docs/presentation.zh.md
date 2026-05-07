# AgentTest — Lightning Presentation 讲稿文档

> 本文档按照 [`docs/ASSIGNMENT.md`](ASSIGNMENT.md) § Lightning
> Presentation 的四块要求详细讲述本项目，作为期末展示的讲稿/排练
> 底稿。展示约束（来自 ASSIGNMENT，逐字摘录）：
>
> - 时长 **2–3 分钟**
> - **必须用 slides 辅助**
> - **不需要 live demo**（artifact snapshot 用截图 / 短录屏 / sample
>   output 即可）
> - 必须覆盖四块：**Context, user, and problem** → **Solution and
>   design** → **Evaluation and results** → **Artifact snapshot**

权威数据来源：
- 设计 rationale：[`docs/project_plan.md`](project_plan.md)
- N=3 完整结果：[`experiments/realworld-results.md`](../experiments/realworld-results.md)
- 入口文件：[`claude-skill/agenttest/SKILL.md`](../claude-skill/agenttest/SKILL.md)

---

## 一、Context, user, and problem

### 1.1 用户是谁

一个在 **Spring AI / LangChain4j / MCP** 技术栈上做 AI agent 产品的
**Java 开发者**。主 persona 是单个工程师或一个小团队，自己拥有 agent
代码库、自己写 JUnit 测试。

### 1.2 我们在改善什么工作流

为新写的或修改的 agent 代码写单元测试。痛点子集是 **agent 特定的测试**
—— 通用 Java 测试生成器看不懂的不变量：

- **Prompt injection**（LLM01 / ASI01）：模板组装中用户输入或上一轮
  LLM 响应循环回下一轮 prompt，未 sanitize
- **Excessive agency**（LLM06 / ASI02 / ASI04 / ASI05 / ASI08）：
  无界 LLM 控制迭代、tool 描述↔实现漂移、MCP tool-definition poisoning、
  cascading sub-agent failures
- **Sensitive-data disclosure**（LLM02）：敏感数据泄漏到 prompt 或日志

### 1.3 为什么这个问题重要

agent 代码暴露在传统 Java 代码不会遇到的一类 bug 中。这些 bug 还
**不成比例地不可见**于：

1. **传统测试套件** —— 它们测功能正确性，不测对抗鲁棒性或 agent 模式
   合规性
2. **vanilla LLM 测试生成器** —— 我们的 N=3 evaluation 显示 vanilla
   Claude Code 在三个真实 `spring-ai-examples` 文件上写出的测试
   **抓出 0 个 OWASP 风险**，全是 behavior-match 测试

闭合这个差距，开发者每周省下数小时手写时间，并降低 agent-class bug
漏出概率。

### 1.4 在 prior art 中的定位

| 类别 | 代表 | 它做什么 | 它不做什么 |
|---|---|---|---|
| 通用 LLM 测试生成器 | TestSpark, ChatUniTest, Diffblue, Qodo Cover | 优化 line coverage + mutation score on 通用代码 | benchmark（HumanEval-Java, Defects4J）**不含 agent 代码**也不含 OWASP 类 bug |
| OWASP audit skills | `agamm/claude-code-owasp`, `AgriciDaniel/claude-cybersecurity` | 跨语言 OWASP 最佳实践审查 / 多 agent 安全 review | **做 review，不做测试生成** |
| 静态分析器 | SpotBugs, SonarQube, SemGrep | 模式检测 | 不能 emit JUnit 测试，规则库不覆盖 OWASP LLM 类别 |

**交叉点**——*source-level + OWASP-aligned + Java-agent-specific +
JUnit-emitting*——在 prior art 里是空的。这就是 AgentTest 的位置。

### 1.5 为什么这个任务必须用 GenAI

ASSIGNMENT 明确要求每个项目说清"why GenAI is useful for this task"。
三个具体原因——静态分析、模板生成、通用 LLM 测试生成器都不行：

1. **OWASP 风险描述是英文语义语境**。把 *"Prompt Injection occurs
   when user prompts alter the LLM's behavior or output in unintended
   ways…"* 这种句子映射到具体某个 Spring AI prompt-template 组装调用
   点，需要语言理解——不是关键词匹配，不是 AST pattern 规则。
2. **生成在对抗输入下测行为的 JUnit 5 + Mockito 源代码是明确的生成
   任务**。断言要捕捉 LLM **从 OWASP 风险描述推理出来**、应用到**具体**
   这一段 Java 代码的不变量。
3. **避免 tautological assertion 失败模式需要 contract 推理**。一个
   断言"代码做了它做的"的测试抓不到 bug（bug 就是当前行为）。把
   "函数在攻击下应该怎样"和"实现当前怎样"区分开——这正是 GenAI 擅长
   的判断。

静态分析器（SpotBugs, SemGrep）能标 pattern 但不能 emit JUnit。
模板生成器产出覆盖率样板，不是 risk-targeted 对抗测试。通用 LLM 测试
生成器优化 benchmark（HumanEval-Java, Defects4J）的 line coverage——
这些 benchmark 没有 agent 代码也没有 OWASP 类 bug。

---

## 二、Solution and design

### 2.1 我们做了什么（一句话）

一个 Claude Code skill，安装到 `~/.claude/skills/agenttest/`。用户在
任何 Maven Java 项目中输入 `/agenttest <file>`，skill 读文件 → 分类
agent 模式 → 加载对应 OWASP 风险 + Java 规则 → 规划 Given-When-Then
测试用例 → 询问确认 → 生成 JUnit 5 + Mockito 测试类 → 跑
`mvn test-compile` 验证 → 打印源码供用户**审阅后再写盘**。

**做 LLM 工作的是用户已有的 Claude Code session 本身**——没有独立
engine、没有 `ANTHROPIC_API_KEY`、没有第二个 LLM 服务。skill 就是
加载到一个已经在那里的 session 上的 markdown rules。价值增量是
**OWASP grounding + agent-pattern recognition + invariant-test
discipline**，不是一个更花哨的 LLM 调用。

### 2.2 架构（12 个模块化 markdown 文件）

```
SKILL.md（7 步 orchestrator，~150 行）
  ├── rules/general/          —— cross-language test discipline
  │   ├── attack-payload-assertions.md
  │   └── existing-test-awareness.md
  ├── rules/owasp/            —— LLM01 / LLM02 / LLM06 invariants + payloads
  │   ├── llm01-prompt-injection.md
  │   ├── llm02-sensitive-disclosure.md
  │   └── llm06-excessive-agency.md
  ├── rules/patterns/         —— agent 模式分类
  │   ├── chain-workflow.md
  │   ├── iterative-agent.md
  │   ├── tool-handler.md
  │   └── log-handler.md
  ├── rules/java/             —— JUnit 5 + Mockito + AssertJ + ChatClient mocking
  │   ├── junit-template.md
  │   └── chatclient-mocking.md
  └── rules/post-generation/  —— mvn 验证
      └── verify.md
```

**关键工程选择**：rules **按需加载**——Step 1 模式分类决定加载哪几
个 OWASP + pattern 文件，不是一次性灌完。`SKILL.md` 本体保持精简。

### 2.3 7 步工作流

| Step | 动作 | refusal license |
|---|---|---|
| 1 | Read 目标 + 分类 agent 模式（chain workflow / iterative-agent / tool-handler / log-handler） | 不匹配 → refuse "no agent pattern detected" |
| 2 | 加载匹配的 OWASP 风险规则 + general 规则 | — |
| 3 | 输出 Given-When-Then 测试用例表（**先写表，后写代码**） | 无法形成 OWASP 相关测试 → refuse |
| 4 | `AskUserQuestion` 询问用户确认 | 用户拒绝 → 停 |
| 5 | 读 Java rules → 生成 `<TargetClass>AgentGenTest` | 只能引用目标源里可见的符号，不能凭空发明 inner class |
| 6 | `mvn test-compile`（最多重试 5 次）+ `mvn test -Dtest=…` | retries 用尽 → 交付 source 但**警示**未编译通过 |
| 7 | 打印测试源 + 用例表 + 验证报告 | **绝不**未经用户确认就写到 `src/test/java/` |

### 2.4 关键 GenAI 设计选择

1. **Skill-native，不是 engine wrapper**。S4 中期 review 把架构从
   FastAPI engine pipeline pivot 到 markdown rules tree。三个原因：
   - 匹配 Claude Code skill 设计哲学（prompt-time augmentation）
   - 不给 grader 第二把 API key（用户已有 Claude Code 订阅覆盖 LLM 调用）
   - 跑在用户**真实** Spring AI Maven classpath 上（不是 stub jars）

2. **OWASP 锚定的 risk taxonomy**。不发明 risk category。每个生成的测
   试方法的 javadoc 引用具体 OWASP risk ID（LLM01, LLM06 等）+ Agentic
   2026 ASI mapping（ASI01–ASI08）。Agentic 2026 的 10 个 ASI 风险中
   **6 个**被 Java 单元测试覆盖（ASI03/06 多租户+记忆毒化超出范围；
   ASI09/10 不是单测能测的）。

3. **Attack-payload assertions 作为技术贡献**。测试注入 canonical OWASP
   payloads（`}}`, `<|im_start|>`, `[INST]`, `Ignore previous` 等），
   断言 payload 字符**不**在被捕获的 LLM 输入 / 日志输出 / 工具副作用
   中存活——比 "invariant tests" 这一抽象框架更**锐**，也不和通用 Java
   测试 skill 重叠。

4. **Human stays in the loop**。SKILL.md Step 7 显式：
   > "do NOT write to `src/test/java/` without explicit user confirmation"

   所有生成测试都是 **advisory**；没匹配 agent 模式就 refuse（**不编造**）。
   这同时满足 ASSIGNMENT "where a human should stay involved" 的要求和
   工程常识（LLM 写错不变量的测试比没测试更糟，会把坏行为锁住）。

5. **Locked baseline = vanilla Claude Code session**。同一个 Claude Code
   build，相同工具访问（Read, Grep, Bash），唯一差异是是否注入 skill
   grounding。**无工具不对称**——这让差异是干净的"框架 vs 无框架"对比，
   不是"有工具 vs 没工具"。

### 2.5 课程概念覆盖

ASSIGNMENT 要求至少两个；本项目设计自然落到三个：

- **Multi-step orchestration（Week 5）**：7-step SKILL.md 工作流 +
  多个 refusal license 点，每步有类型化期望
- **Structured outputs（Weeks 2–3）**：Step 7 打印测试源 + Given-When-Then
  用例表 + 验证报告（V_buggy/V_clean PASS/FAIL）——结构化视图，不是
  一坨文本
- **Governance / deployment controls（Week 6）**：显式 human-in-the-loop，
  generated test never auto-merge

*RAG（Week 4）有意未用*：pre-pivot engine 确实有 RAG over OWASP catalog
+ agent-pattern library；skill-native 用 12 个按需加载的 markdown 文件
替代——简单、不需要 embedding service、不需要第二把 key。

---

## 三、Evaluation and results

### 3.1 对照什么（baseline）

**Locked baseline = vanilla Claude Code session + 锁定 prompt**。
2026-05-06 用 Claude Code v2.x 捕获，三个样本逐字相同：

> 帮我给 ChainWorkflow.java 写一个测试

同一个 Claude Code build，skill 已安装但 `/agenttest` **不调用**。这是
**公平**的对比——这就是单独用 Claude Code 的开发者会得到的输出。三份
vanilla 输出已逐字提交在
[`experiments/{chainworkflow,orchestratorworkers,evaluatoroptimizer}/test_vanilla.java`](../experiments/)。

### 3.2 测试集——3 个真实 OSS 文件

来自 [`spring-projects/spring-ai-examples`](https://github.com/spring-projects/spring-ai-examples)
@ commit `2a6088db3d18d5fa6fc208b12adf1172d22f77fd`：

| Sample | Pattern | 真实上游 OWASP 风险 |
|---|---|---|
| `ChainWorkflow.java` | chain workflow | Line 121 `String.format("{%s}\n {%s}", prompt, response)` 把用户输入 + LLM 响应循环回下一步 prompt，无 sanitize（**LLM01 直接 + 间接**） |
| `OrchestratorWorkers.java` | iterative-agent (fan-out) | Line 189 stream over LLM 控制的 `tasks` list，**无上界**（LLM06/ASI08）；输入流入 prompt 无 sanitize（LLM01 + ASI07） |
| `EvaluatorOptimizer.java` | iterative-agent (recursion) | Lines 212–235 **无界递归**（只有 `evaluation == PASS` 才退出 → LLM06/ASI08）；evaluator `feedback` 流入下一轮 `context` 无 sanitize（LLM01 间接 / ASI04） |

**真实 OSS 文件 + 真实 bug**——无合成注入。S2/S3 engine 时代的
"self-validation problem"（自己写 bug 自己测）在结构上**不存在**：
bug 不是我们写的。

### 3.3 用什么 rubric

```
V_buggy = 上游代码原样（真实 OWASP 风险存在）
V_clean = 手工修复（sanitize() helper + bounded loop where applicable）

A = skill 模式输出（/agenttest invocation）
B = vanilla 模式输出（locked baseline prompt）

A 或 B 投到 V_buggy → mvn test → 期望 FAIL  （catch / recall）
A 或 B 投到 V_clean → mvn test → 期望 PASS  （precision）
```

**Catch 准则**（机械的，**无 LLM-as-judge**）：
- `mvn test` exit ≠ 0
- AND 失败信息匹配 regex
  `(?i)(sanitize|injection|template.?breakout|system\s*:|prompt.?inject)`

**Precision 准则**：每个测试在 V_clean 上都 PASS。

### 3.4 结果——N=3 final headline

| Sample | Pattern | skill catches | skill precision | vanilla catches | vanilla precision |
|---|---|---|---|---|---|
| ChainWorkflow | chain workflow | **4 / 4** ✓ † | 5 / 5 ✓ | 0 / 5 ✗ | 5 / 5 ✓ |
| OrchestratorWorkers | iterative-agent (fan-out) | **4 / 4** ✓ | 4 / 4 ✓ | 0 / 7 ✗ | 7 / 7 ✓ |
| EvaluatorOptimizer | iterative-agent (recursion) | **4 / 4** ✓ | 4 / 4 ✓ | 0 / 7 ✗ | 7 / 7 ✓ |
| **TOTAL** | 3 patterns | **12 catches** | **13 / 13 PASS** | **0 catches** | **19 / 19 PASS** |

† ChainWorkflow skill 输出 = 4 attack-payload 测试 + 1 sanity 测试
（恒 PASS）；catch 分母只数 attack-payload 测试，precision 数全 5 个。

**12-0 catch differential，两边 precision 都没坏**——vanilla 也不
false-positive on V_clean。差距是 **framing**，不是技术能力：vanilla
写 behavior-match 测试（断言"代码现在做什么"），skill 写 OWASP attack-
payload 锚定的 invariant 测试（断言"无论代码当前状态如何，什么应该成立"）。

### 3.5 Cross-cutting findings（精简自 [`experiments/realworld-results.md`](../experiments/realworld-results.md)）

1. **vanilla 有技术功夫，缺的是 framing**。三份 vanilla 输出都用了
   正确的 Spring AI 1.0 fluent-API mocks（`ChatClientRequestSpec`,
   `CallResponseSpec`, `PromptUserSpec`）、正确的
   `ArgumentCaptor.getAllValues()`、正确的 `verify(times(N))`。差异
   **纯粹**是 behavior-match vs invariant——**不是知识，是 framing**。
2. **Indirect-injection 覆盖在三个模式间一致**。skill 抓住了每个模式
   特有的间接注入面（响应循环 / task 字段流入 / feedback 上下文）——
   同一个 OWASP 风险，三种不同表面形状。
3. **V_clean scope 必须匹配 catch scope（方法学教训）**。第一版 V_clean
   只修了 headline LLM06，导致 LLM01 测试 precision = 0/4。第二版补全
   `sanitize()` 后达到 4/4。教训是：V_clean 必须是 skill 标记出的
   **每一个** OWASP 风险的全面修复，不能只修 headline——真实工程师
   读 skill 输出也会这样修。
4. **Skill 规则 throw-vs-truncate 一致性 gap（future work）**。
   `iterative-agent.md` Invariant 1（bounded recursion）显式接受
   `assertThatThrownBy` 的 throwing 修复；Invariant 2（LLM fan-out
   cap）用裸 `verify(atMost(...))`，没 try/catch——意味着一个 throw
   的 V_clean 会让测试 error。我们在 OrchestratorWorkers V_clean 用
   truncate 绕过。throw 和 truncate 都是合理的工程修复，规则应该
   两个都接受。

### 3.6 限制（坦承——这块直接在 slides 上讲）

- **N=3 是 existence proof，不是 benchmark**。要做普遍性声明
  ("skill > vanilla on all Java AI code") 需要 N=15+ 跨更多模式 + 框架。
  Week-7 deliverable 范围之外。
- **样本是 self-selected**。我们选 iterative-agent 变体正是因为 skill
  对它们有未验证的规则。`tool-handler`、`log-handler`、MCP server 模式
  在 N=3 中**未端到端验证**——它们是有规则但没跑过的。
- **V_clean scope 必须匹配 catch scope**（方法学教训）。第一版 V_clean
  只修了 LLM06，导致 LLM01 测试 precision = 0/4。第二版补全
  `sanitize()` 后 4/4。这是 V_clean 缺陷，不是 skill 缺陷。
- **Maven only**——shells out to `mvn test-compile` / `mvn test`。
  Gradle / Bazel 不支持。
- **Java only**——无 Kotlin / Scala。
- **Spring AI 1.0 fluent API only**——`chatclient-mocking.md` 编码的是
  `ChatClient.prompt().user(...).call()` 这种 shape。LangChain4j 和
  raw MCP clients 用的 API 不一样。

### 3.7 我们明确**没**做什么（以及为什么）

主动声明，避免被 grader 误判为遗漏：

- **没安排 live demo**。ASSIGNMENT 明说不需要；2–3 分钟窗口里用
  sample-output snapshot 风险更低。
- **没做 N=15+ benchmark**。N=3 作为 Week-7 deliverable 的 existence
  proof 量级足够；benchmark 级评估是 future work。
- **没端到端验证 tool-handler / log-handler**。skill 里有这些规则，
  但 N=3 eval 没覆盖——评估时 `spring-ai-examples` 没有合适的
  log-handler 目标。
- **没用 RAG**。pre-pivot engine 有过；skill-native 用 12 个按需加载
  的 markdown 文件替代——简单、不需要 embedding service、不需要第二
  把 key。Week-4 RAG 概念有意未用。
- **catch 准则不用 model-as-judge**。catch 是机械的：`mvn test`
  exit + 失败信息上的 grep regex。没有任何 LLM 给测试打分。这是
  有意的方法学选择，避免循环评估。
- **deliverable 里没有 engine / FastAPI server**。S4 pivot 删了
  engine（commit `99df6e0`）。git history 仍可考古；不是 shipped
  artifact 的一部分。

---

## 四、Artifact snapshot

ASSIGNMENT 明确说**不需要 live demo**——一张截图 / 一段短录屏 /
一份 sample output 即可证明项目能跑。我们用并排代码对比作为最强
artifact——**同一个 ChainWorkflow.java、同一个 ArgumentCaptor.getAllValues()
配方，相反的 framing**。

### 4.1 `/agenttest` 产出（chain pattern, LLM01 direct）

```java
@Test
void chain_userInputContainsTemplateBreakout_noStepLeaksPayload() {
    // Given
    ArgumentCaptor<String> promptCaptor = ArgumentCaptor.forClass(String.class);
    when(chatClient.prompt(promptCaptor.capture())).thenReturn(promptSpec);
    when(promptSpec.call()).thenReturn(responseSpec);
    when(responseSpec.content()).thenReturn("benign step output");

    // When
    target.chain(PAYLOAD_TEMPLATE_BREAKOUT);

    // Then
    List<String> capturedPrompts = promptCaptor.getAllValues();
    assertThat(capturedPrompts).isNotEmpty();
    for (String captured : capturedPrompts) {
        assertThat(captured)
                .as("LLM01: rendered prompt must not leak template-breakout payload")
                .doesNotContain("}}")
                .doesNotContain("Ignore previous")
                .doesNotContain("system:");
    }
}
```

### 4.2 `/agenttest` 产出（iterative-agent, LLM06/ASI08 fan-out）

```java
@Test
void process_orchestratorReturns1000Tasks_workerCountIsCappedAtReasonableBound() {
    // Given: 一个失控/恶意 LLM 生成 1000 个子任务
    List<Task> hugeTaskList = IntStream.range(0, 1000)
            .mapToObj(i -> new Task("type-" + i, "do thing " + i))
            .toList();
    when(callResponseSpec.entity(OrchestratorResponse.class))
            .thenReturn(new OrchestratorResponse("massive plan", hugeTaskList));
    when(callResponseSpec.content()).thenReturn("worker output");

    // When
    new OrchestratorWorkers(chatClient).process("trivial task");

    // Then: 总 prompt() 调用必须有上界（1 orchestrator + 至多 ~20 workers）
    verify(chatClient, atMost(REASONABLE_WORKER_CAP + 1)).prompt();
}
```

### 4.3 vanilla Claude 产出（**同一个** ChainWorkflow.java）

```java
@Test
void chainFeedsPreviousResponseIntoNextStep() {
    when(callResponseSpec.content()).thenReturn("first-out", "second-out");
    String[] prompts = { "PROMPT_A", "PROMPT_B" };

    new ChainWorkflow(chatClient, prompts).chain("USER_INPUT");

    ArgumentCaptor<String> inputs = ArgumentCaptor.forClass(String.class);
    verify(chatClient, times(2)).prompt(inputs.capture());
    List<String> calls = inputs.getAllValues();

    assertThat(calls.get(0)).isEqualTo("{PROMPT_A}\n {USER_INPUT}");
    assertThat(calls.get(1)).isEqualTo("{PROMPT_B}\n {first-out}");
}
```

### 4.4 关键洞察——展示讲稿用这一句

> 两边同一个 `ArgumentCaptor.getAllValues()` 配方；framing 完全相反。
> vanilla 把测试**锁死在当前字面 format string**——这意味着它在 buggy
> 上游代码上 PASS，在 V_clean 上也 PASS：**它两边都不抓 LLM01 漏洞**。
> skill 断言**没有任何 OWASP attack payload 在被捕获的 prompt 中存活**
> ——它在 buggy 上 FAIL，在 V_clean 上 PASS。

### 4.5 完整 artifacts（slides 上加一行 reference）

- [`experiments/chainworkflow/`](../experiments/chainworkflow/) ——
  test_skill.java, test_vanilla.java, V_clean baseline, smoke-result.md
- [`experiments/orchestratorworkers/`](../experiments/orchestratorworkers/)
- [`experiments/evaluatoroptimizer/`](../experiments/evaluatoroptimizer/)
- [`experiments/realworld-results.md`](../experiments/realworld-results.md) ——
  完整 N=3 数据 + methodology + 4 个 cross-cutting findings

---

## 五、Slide 大纲（针对 2–3 分钟讲稿）

| # | Slide | 时长 | 内容 | 讲稿要点（口语化） |
|---|---|---|---|---|
| 1 | **标题** | 5s | "AgentTest — JUnit tests for AI agent code, OWASP-grounded" | "AgentTest 是一个 Claude Code skill，给 Java AI agent 代码生成 JUnit 测试" |
| 2 | **Context** | 30–40s | 用户 / 工作流 / 痛点（一张图：Java agent 代码 → 传统测试看不见 OWASP 类 bug） | "用户是 Spring AI 开发者，痛点是 agent 特定的测试不变量——prompt injection、excessive agency、敏感数据泄漏——传统测试套件看不见，通用 LLM 测试生成器也看不见。我们的 evaluation 显示 vanilla Claude Code 在三个真实文件上抓 0 个 OWASP 风险" |
| 3 | **Solution** | 30–40s | 7-step skill orchestrator + 12 个 markdown rules（架构图）+ 设计三要点 | "做了一个 Claude Code skill——`/agenttest <file>` 触发 7 步流程，按需加载 12 个模块化 markdown rule。三个关键设计：skill-native 不是 engine wrapper、OWASP 锚定的 risk taxonomy、用 attack payload 做断言而不是 behavior-match" |
| 4 | **Evaluation** | 40–50s | 方法（V_buggy/V_clean + 机械 catch criterion）+ 12-0 结果表 | "对照是同一个 Claude Code session，差异只是 skill grounding。3 个真实 OSS 文件，V_buggy 跑期望 FAIL = catch，V_clean 跑期望 PASS = precision。结果是 **12 个 catch vs 0 个 catch**，两边 precision 都没坏。差距是 **framing，不是技术能力**" |
| 5 | **Artifact** | 20–30s | 一张并排对比图：skill 测试 vs vanilla 测试同一个文件 | "这是同一个 ChainWorkflow.java 的两份测试——同一个 ArgumentCaptor 配方，相反的 framing。vanilla 把测试锁死在当前格式串；skill 断言 OWASP payload 不存活" |
| 6 | **Limits + Wrap** | 10–15s | N=3 是 existence proof / Maven only / Spring AI 1.0 only / human-in-the-loop | "N=3 是 existence proof 不是 benchmark；Maven + Java + Spring AI 1.0 限定；所有测试都是 advisory，绝不 auto-merge" |

**预计总时长**：≈ 2 分 30 秒（在 2–3 分钟窗内）。

---

## 六、关键数字记忆卡片（排练时强记）

| 数字 | 含义 |
|---|---|
| **12 / 0** | skill catches vs vanilla catches（最关键 headline） |
| **13/13 + 19/19** | 两边 precision 都满分（无 false positive on V_clean） |
| **N=3** | 三个真实 OSS 文件，三个不同 agent 模式 |
| **commit 2a6088d** | spring-ai-examples 的 pinned commit |
| **7 步** | SKILL.md orchestrator 步数 |
| **12** | 模块化 markdown rule 文件总数 |
| **$0** | grader 的边际成本（用 Claude Code 订阅，无第二把 API key） |

---

## 七、排练自查清单

- [ ] **3 分钟内**能讲完四块（在浴室对镜子或对计时器跑两遍）
- [ ] slides 上有 12-0 那张表（headline 视觉锚点）
- [ ] slides 上有 skill vs vanilla 并排代码图（artifact snapshot）
- [ ] 讲稿里**点出 "framing not knowledge"** 这句关键洞察
- [ ] 讲稿里**坦承 N=3 限制**（不假装是 benchmark）
- [ ] 讲稿里提到 **human-in-the-loop / advisory**（ASSIGNMENT 要求）
- [ ] **不**安排 live demo（ASSIGNMENT 说不需要，且降低风险）
- [ ] slides 末尾留一行 reference URL：
      `github.com/c1375/AgentTest`

---

## 八、可能被问到的问题（Q&A 准备）

| 提问 | 一句话回答 |
|---|---|
| 为什么 N=3 就够？ | N=3 是 **existence proof**——证明 framing differential 在不同 agent 模式间存在；要做普遍性声明需要 N=15+，但 Week-7 deliverable 范围之外 |
| 为什么不直接测 vanilla 是否懂 OWASP？ | 我们就是这么测的——**locked prompt** 是 vanilla 自然会得到的输出，差异只来自 skill grounding。不是 vanilla "不懂" OWASP，是它默认写 behavior-match 测试 |
| 万一 skill 自己写错不变量呢？ | 这就是 V_clean 检查存在的原因——precision 准则要求测试在 V_clean 上 PASS。N=3 评估里两边 precision 都没坏。**而且最终人类必须 review** |
| 为什么从 engine pivot 到 skill？ | 三个原因：匹配 Claude Code skill 设计哲学、grader 不需要第二把 API key、跑在用户**真实** Spring AI Maven classpath 上而不是 stub jars |
| 你们是不是抄了 clear-solutions/unit-tests-skills？ | 我们用了相似的 multi-file `rules/` 树**结构**——但所有规则**内容**是新写的（clear-solutions 没 LICENSE 文件，所以我们没 fork 它的 prose） |
| 为什么不用 RAG？ | pre-pivot engine 用过；skill-native 用 12 个按需加载的 markdown 文件替代——简单，不需要 embedding service，不需要第二把 key。Week-4 RAG 概念有意未用 |

---

## 九、文档来源

| 信息 | 文件 |
|---|---|
| 课程要求（binding） | [`docs/ASSIGNMENT.md`](ASSIGNMENT.md) |
| 设计 rationale + 整个 sprint 历史 | [`docs/project_plan.md`](project_plan.md) / [`.zh.md`](project_plan.zh.md) |
| 用户面（README） | [`README.md`](../README.md) |
| skill 入口 | [`claude-skill/agenttest/SKILL.md`](../claude-skill/agenttest/SKILL.md) |
| N=3 完整结果 | [`experiments/realworld-results.md`](../experiments/realworld-results.md) |
| 每个样本的 raw artifacts | [`experiments/{chainworkflow,orchestratorworkers,evaluatoroptimizer}/`](../experiments/) |
| 本文档英文版 | [`docs/presentation.md`](presentation.md) |
