package com.example.spring;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.logging.Logger;

/**
 * Audit trail for agent tool invocations. For each invocation, writes
 * one INFO-level log line recording the tool name and a SHA-256 hash
 * of the user-supplied arguments JSON. The hash is non-reversible, so
 * sensitive content embedded in the args (auth headers, emails, SSNs)
 * never appears verbatim in the audit log.
 *
 * The llm02_drop_redaction injection rewrites the sha256(inv.argsJson())
 * call to a bare `inv.argsJson()` reference, leaking the raw payload
 * — a realistic regression where someone "simplifies" the audit
 * pipeline without realizing the hash was load-bearing for privacy.
 *
 * ToolInvocation is a Java record (immutable) — variety vs. the sibling
 * AgentLogger sample which uses a mutable bean to match its OWASP
 * exemplar's shape. Both are valid agent-side patterns; covering both
 * gives the generator exposure to the two flavors of input DTO it
 * will see in real Spring AI / LangChain4j code.
 */
public class RequestAuditTrail {

    public record ToolInvocation(String tool, String argsJson) { }

    private static final Logger logger = Logger.getLogger(RequestAuditTrail.class.getName());

    public void recordInvocation(ToolInvocation inv) {
        // Clean: hash the argsJson so any sentinel embedded in it is
        // irrecoverable from the audit log. The LLM02 injection drops
        // the sha256 call.
        logger.info("audit: tool=" + inv.tool() + " argsHash=" + sha256(inv.argsJson()));
    }

    private static String sha256(String input) {
        // SHA-256 hex digest. The output never contains substrings of
        // the input, so any LLM02 sentinel inside `input` is provably
        // absent from the captured log when this helper is in place.
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(input.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(hash.length * 2);
            for (byte b : hash) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException("SHA-256 not available", e);
        }
    }
}
