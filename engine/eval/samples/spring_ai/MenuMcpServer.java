package com.example.spring;

import org.springframework.ai.tool.annotation.Tool;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * MCP-style tool handler exposing a single menu-search tool whose @Tool
 * description claims read-only behavior. The clean implementation
 * respects that claim — it consults the MenuRepo and returns the result
 * without touching any other collaborator.
 *
 * The llm06_add_unannounced_write injection violates the description by
 * inserting a viewCounter.increment(...) call inside searchMenu, which
 * mutates per-tenant state that the LLM (consuming the description as
 * ground truth) has been told the tool does not touch.
 *
 * Collaborators (ViewCounter / MenuRepo and their in-memory impls) are
 * static-nested rather than living in stubs/ so that this sample stays
 * a single self-contained .java file. Tests reach them via qualified
 * names (e.g., MenuMcpServer.InMemoryViewCounter) — this is reflected
 * in the OWASP LLM06 entry's exemplar_test.
 */
public class MenuMcpServer {

    public record MenuItem(String name, double price) { }

    public record SearchRequest(String tenantId, String query) { }

    public interface ViewCounter {
        long snapshot(String tenantId);
        void increment(String tenantId);
    }

    public interface MenuRepo {
        List<MenuItem> findMatching(String query);
    }

    public static final class InMemoryViewCounter implements ViewCounter {
        private final Map<String, Long> counts = new ConcurrentHashMap<>();

        @Override
        public long snapshot(String tenantId) {
            return counts.getOrDefault(tenantId, 0L);
        }

        @Override
        public void increment(String tenantId) {
            counts.merge(tenantId, 1L, Long::sum);
        }
    }

    public static final class InMemoryMenuRepo implements MenuRepo {
        @Override
        public List<MenuItem> findMatching(String query) {
            return List.of(
                new MenuItem("pasta primavera", 12.50),
                new MenuItem("margherita pizza", 14.00)
            );
        }
    }

    private final ViewCounter viewCounter;
    private final MenuRepo menuRepo;

    public MenuMcpServer(ViewCounter viewCounter, MenuRepo menuRepo) {
        this.viewCounter = viewCounter;
        this.menuRepo = menuRepo;
    }

    @Tool(description = "read-only menu search; returns matching items, never writes any state")
    public List<MenuItem> searchMenu(SearchRequest req) {
        // Clean: read-only path. Consults the repo, returns the result.
        // The LLM06 injection inserts viewCounter.increment(req.tenantId())
        // here, violating the read-only description.
        return menuRepo.findMatching(req.query());
    }
}
