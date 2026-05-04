package org.springframework.ai.tool.annotation;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/*
 * Minimal @Tool annotation shim mirroring Spring AI's
 * org.springframework.ai.tool.annotation.Tool. Real Spring AI also
 * declares returnDirect/resultConverter; AgentTest samples don't read
 * those, so they're omitted to keep the shim narrow.
 *
 * RUNTIME retention so a test could reflectively read description() if
 * it ever needs to assert "the tool is described as read-only".
 */
@Target({ElementType.METHOD, ElementType.ANNOTATION_TYPE})
@Retention(RetentionPolicy.RUNTIME)
public @interface Tool {
    String name() default "";
    String description() default "";
}
