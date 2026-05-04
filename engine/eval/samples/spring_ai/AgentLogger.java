package com.example.spring;

import java.util.logging.Logger;

/**
 * Agent-side request logger. Receives an inbound AgentRequest carrying
 * potentially-sensitive fields (auth header, email, SSN) and writes a
 * single INFO-level log line for observability.
 *
 * The clean implementation routes the request through redactPii(...)
 * before string-concatenation into the log message, so the canonical
 * LLM02 sentinels (`Bearer SENTINEL_TOKEN`, `sentinel@example.com`,
 * `999-99-9999`) never appear verbatim in the captured log output.
 *
 * The llm02_drop_redaction injection rewrites the redactPii(req) call
 * to a bare `req` reference; Java's implicit toString in string
 * concatenation then leaks every field unredacted. The failure mode
 * is observable via java.util.logging.Handler#publish capturing the
 * raw sentinel substring.
 *
 * AgentRequest is intentionally a mutable bean (no-arg ctor + setters
 * + explicit toString) — that matches the shape the LLM02 OWASP
 * exemplar test demonstrates, so Sonnet can copy the pattern. The
 * sibling RequestAuditTrail sample uses a Java record for variety.
 */
public class AgentLogger {

    public static class AgentRequest {
        private String authHeader;
        private String email;
        private String ssn;

        public String getAuthHeader() { return authHeader; }
        public void setAuthHeader(String authHeader) { this.authHeader = authHeader; }

        public String getEmail() { return email; }
        public void setEmail(String email) { this.email = email; }

        public String getSsn() { return ssn; }
        public void setSsn(String ssn) { this.ssn = ssn; }

        @Override
        public String toString() {
            return "AgentRequest{authHeader=" + authHeader
                + ", email=" + email
                + ", ssn=" + ssn + "}";
        }
    }

    private static final Logger logger = Logger.getLogger(AgentLogger.class.getName());

    public void logRequest(AgentRequest req) {
        // Clean: route through redactPii so the auth/email/SSN sentinels
        // never appear verbatim in the captured log. The LLM02 injection
        // strips the redactPii call.
        logger.info("Handling agent request: " + redactPii(req));
    }

    private static String redactPii(AgentRequest req) {
        // Covers the canonical LLM02 sentinels enumerated in the OWASP
        // catalog's invariant_to_assert. Per docs/plan/architecture.md
        // S2 retrospective: sample defenses MUST cover every sentinel
        // the OWASP entry lists, otherwise generated tests appear to
        // catch the injection but actually catch a sample-coverage gap.
        String raw = String.valueOf(req);
        return raw.replaceAll("(?i)Bearer\\s+\\S+", "Bearer ***")
                  .replaceAll("[\\w.+-]+@[\\w.-]+\\.[\\w]+", "***@***")
                  .replaceAll("\\d{3}-\\d{2}-\\d{4}", "***-**-****");
    }
}
