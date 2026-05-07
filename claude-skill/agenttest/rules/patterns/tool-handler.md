# Pattern: Tool handler (@Tool / MCP / function calling)

## Role in the skill

Loaded by Step 1 when the target is a tool handler — Spring AI `@Tool`
annotated method, MCP server tool registration, LangChain4j `@Tool`,
or a function-calling handler.

## Status

Skeleton — content authoring pending Phase 1.

## Planned content

- **Pattern recognition signals**:
  - `@Tool(description = "...")` annotation on a method (Spring AI / LangChain4j)
  - MCP server tool registration (e.g., `mcpServer.tool(name, schema, handler)`)
  - Method registered as a function for an LLM to invoke
- **Test structure**:
  - Mock ALL I/O dependencies the handler injects (filesystem, HTTP
    client, DB, external service clients) — even ones you wouldn't
    expect a "read-only" tool to use
  - Read the `@Tool` `description` attribute as the spec
  - Invoke the tool with benign + adversarial inputs
  - For each mock representing a side-effect NOT promised in description,
    assert `verifyNoInteractions(...)` — ZERO calls
  - For each mock representing a side-effect that IS promised, assert it
    was called with the expected args (`ArgumentCaptor`)
- **Specific patterns**:
  - "Read-only" tool that secretly writes → `Files.write` / `restTemplate.post`
    mock should be untouched
  - Tool that invokes a 2nd LLM call without disclosure → `chatClient`
    mock should not be called twice
  - Tool that logs user input externally → external logger mock should be
    untouched

## Source

Original to AgentTest. Spring AI `@Tool` reference:
<https://docs.spring.io/spring-ai/reference/1.0/api/tools.html>
