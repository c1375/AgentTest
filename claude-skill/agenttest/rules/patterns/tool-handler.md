# Pattern: Tool handler (@Tool / MCP / function calling)

Loaded by `SKILL.md` Step 1 when the target is a tool handler — a
method the LLM can invoke (Spring AI `@Tool`, LangChain4j `@Tool`,
MCP server tool registration, or generic function-calling handler).

## Pattern recognition signals

You're looking at a tool handler if **any** of:

- Method has `@Tool(description = "...")` annotation (Spring AI / LangChain4j)
- Method registered via `mcpServer.tool(name, schema, handler)` or
  similar MCP API (Spring AI MCP SDK exposes `@Tool` for MCP server too)
- Method registered as an OpenAI / Anthropic function-call tool
  (`FunctionCallback`, `ToolCallback`, etc.)
- Class implements a Tool / Function interface from any agent framework

## OWASP risks

Primary: **LLM06 / ASI02 (Tool Misuse) + ASI04 (Supply Chain) +
ASI05 (Code Execution)**.

For invariants + canonical test patterns, see
`rules/owasp/llm06-excessive-agency.md`. That file has 5 sub-sections
covering:

1. Description ↔ implementation conformance
2. Tool argument validation
3. Tool output sanitization before re-prompting
4. Bounded loop termination
5. MCP tool definition poisoning

This file (`tool-handler.md`) provides the **pattern recognition** and
the test-wiring specifics.

## Test class skeleton for tool handlers

```java
@ExtendWith(MockitoExtension.class)
class WeatherToolAgentGenTest {

    // Mock every I/O dependency — for "read-only" tools, all writes
    // must be verifyNoInteractions.
    //
    // IMPORTANT: java.nio.file.Files is final + static-only and cannot
    // be @Mock'd directly with plain Mockito. If the tool wraps file
    // ops behind a service interface (recommended), mock that service.
    // If it calls Files.* directly, use Mockito's mockStatic:
    //   try (MockedStatic<Files> filesStatic = mockStatic(Files.class)) {
    //       filesStatic.when(() -> Files.write(any(), any(byte[].class)))
    //                  .thenThrow(new AssertionError("unexpected write"));
    //       target.readUser("user-123");
    //       filesStatic.verifyNoInteractions();
    //   }
    @Mock private RestTemplate httpClient;       // any external HTTP
    @Mock private FileService fileService;       // wrap Files.* behind a service
    @Mock private EntityManager entityManager;   // any DB
    @Mock private JmsTemplate jmsTemplate;       // any messaging

    private WeatherTool target;

    @BeforeEach
    void setup() {
        target = new WeatherTool(httpClient);
        // (or @InjectMocks if straightforward DI)
    }

    @Test
    void getWeather_invokedWithCity_callsExpectedReadApiOnly() {
        // Description says "Get weather for city" → only HTTP GET allowed

        // Wire the expected read API
        when(httpClient.getForObject(anyString(), eq(WeatherDto.class)))
            .thenReturn(new WeatherDto(72, "sunny"));

        // When
        target.getWeather("San Francisco");

        // Then: verify the read call happened with proper arg
        verify(httpClient).getForObject(contains("San Francisco"), eq(WeatherDto.class));

        // CRUCIAL: verify NO write-side-effects happened
        verify(httpClient, never()).postForObject(any(), any(), any());
        verify(httpClient, never()).put(any(), any());
        verify(httpClient, never()).delete(any());
        verifyNoInteractions(fileService);
        verifyNoInteractions(entityManager);
        verifyNoInteractions(jmsTemplate);
    }

    // Plus: tool argument validation tests (see llm06 sub-section 2)
    // Plus: tool output sanitization tests (see llm06 sub-section 3)
    // Plus: MCP poisoning tests if MCP-registered (see llm06 sub-section 5)
}
```

## Reading the @Tool description

The `description` attribute is natural-language. To map it to expected
side-effects, look for these keywords (per `llm06-excessive-agency.md`
side-effect blacklist):

| Description keyword | Allowed side-effects |
|---|---|
| `read`, `get`, `list`, `search`, `view`, `find`, `query` | Reads only — no writes / sends / deletes |
| `write`, `create`, `add`, `insert`, `save`, `store` | The corresponding write category — but NOT others |
| `update`, `modify`, `change`, `edit` | Updates only — not deletes |
| `delete`, `remove`, `drop` | Deletes only |
| `send`, `email`, `notify`, `publish` | Outbound messaging only |
| `execute`, `run`, `invoke`, `call` | Process/RPC — most dangerous, requires extra scrutiny |

If the description is ambiguous (e.g., "manage user" — read or write or
both?), the test should refuse rather than guess.

## Java targets in spring-ai-examples

| File | Tool kind | Test focus |
|---|---|---|
| `model-context-protocol/dynamic-tool-update/server/MathTools.java` | MCP server tools (math ops) | sub-section 1 + 2 + 5 |
| `model-context-protocol/dynamic-tool-update/server/WeatherService.java` | MCP server tool (HTTP GET) | sub-section 1 + 2 |
| `model-context-protocol/filesystem/` | MCP filesystem tool — high LLM06 risk surface | sub-section 1 + 2 |
| `advisors/tool-argument-augmenter-demo/` | Tool with arg augmentation | sub-section 2 (arg validation) |

## Source

Original to AgentTest. Spring AI Tools API:
<https://docs.spring.io/spring-ai/reference/1.0/api/tools.html>
