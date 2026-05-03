/*
 * AgentTest runner-helper.
 *
 * Single-file JUnit 5 test runner used by both the validator (run-on-clean
 * gate) and the eval harness (recall measurement on injected variants).
 *
 * Usage:
 *   java -cp 'lib/*:.' TestRunner <target.java> <test.java> <test_class_FQN>
 *
 * Behavior:
 *   - Compiles target + test + bundled Spring AI shim sources via
 *     javax.tools.JavaCompiler in one task.
 *   - Loads the test class with a fresh URLClassLoader.
 *   - Invokes JUnit Platform Launcher and waits for the run to finish.
 *
 * Output (single token on first line, optional details after):
 *   PASS                       — all selected tests passed (exit 0)
 *   FAIL\n<failures>           — at least one selected test failed (exit 1)
 *   COMPILE_FAIL\n<diagnostics> — compilation didn't succeed (exit 2)
 *   ERROR\n<reason>            — internal error (exit 3)
 *
 * The validator interprets PASS as "test is well-formed on the clean
 * variant"; FAIL there means the test asserts a false invariant and gets
 * dropped. The eval harness flips the polarity: PASS on the buggy variant
 * means the risk wasn't caught (recall miss); FAIL means it was caught.
 *
 * Note: the system property `agenttest.runner.dir` controls where the
 * Spring AI shim sources are looked up (defaults to the current working
 * directory). The Python validator sets this to the runner-helper dir.
 */

import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.StandardLocation;
import javax.tools.ToolProvider;

import java.io.File;
import java.io.PrintWriter;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import org.junit.platform.engine.discovery.DiscoverySelectors;
import org.junit.platform.launcher.Launcher;
import org.junit.platform.launcher.LauncherDiscoveryRequest;
import org.junit.platform.launcher.LauncherSession;
import org.junit.platform.launcher.core.LauncherDiscoveryRequestBuilder;
import org.junit.platform.launcher.core.LauncherFactory;
import org.junit.platform.launcher.listeners.SummaryGeneratingListener;
import org.junit.platform.launcher.listeners.TestExecutionSummary;

public class TestRunner {

    public static void main(String[] args) throws Exception {
        if (args.length != 3) {
            System.out.println("ERROR");
            System.out.println("Usage: TestRunner <target.java> <test.java> <test_class_FQN>");
            System.exit(3);
        }
        Path targetSrc = Path.of(args[0]).toAbsolutePath();
        Path testSrc = Path.of(args[1]).toAbsolutePath();
        String testFqn = args[2];

        if (!Files.isRegularFile(targetSrc)) {
            errorOut("target source not found: " + targetSrc);
        }
        if (!Files.isRegularFile(testSrc)) {
            errorOut("test source not found: " + testSrc);
        }

        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) {
            errorOut("no JavaCompiler available — TestRunner must be run on a JDK, not a JRE");
        }

        Path classOut = Files.createTempDirectory("agenttest-runner-classes-");

        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        try (StandardJavaFileManager fm = compiler.getStandardFileManager(diagnostics, null, null)) {
            fm.setLocation(StandardLocation.CLASS_OUTPUT, List.of(classOut.toFile()));

            String runnerDir = System.getProperty("agenttest.runner.dir", ".");
            File stubsRoot = new File(runnerDir, "stubs");
            List<File> shimSources = listJavaFilesRecursively(stubsRoot);

            List<File> sources = new ArrayList<>();
            sources.add(targetSrc.toFile());
            sources.add(testSrc.toFile());
            sources.addAll(shimSources);

            Iterable<? extends JavaFileObject> compUnits = fm.getJavaFileObjectsFromFiles(sources);
            JavaCompiler.CompilationTask task = compiler.getTask(null, fm, diagnostics, null, null, compUnits);
            boolean ok = task.call();
            if (!ok) {
                System.out.println("COMPILE_FAIL");
                for (Diagnostic<? extends JavaFileObject> d : diagnostics.getDiagnostics()) {
                    System.out.println(d);
                }
                System.exit(2);
            }
        }

        URL[] urls = new URL[]{ classOut.toUri().toURL() };
        try (URLClassLoader cl = new URLClassLoader(urls, TestRunner.class.getClassLoader())) {
            Class<?> testClass;
            try {
                testClass = cl.loadClass(testFqn);
            } catch (ClassNotFoundException e) {
                errorOut("test class " + testFqn + " not found after compile: " + e.getMessage());
                return; // unreachable; errorOut exits
            }

            LauncherDiscoveryRequest request = LauncherDiscoveryRequestBuilder.request()
                .selectors(DiscoverySelectors.selectClass(testClass))
                .build();

            SummaryGeneratingListener listener = new SummaryGeneratingListener();
            try (LauncherSession session = LauncherFactory.openSession()) {
                Launcher launcher = session.getLauncher();
                launcher.registerTestExecutionListeners(listener);
                launcher.execute(request);
            }

            TestExecutionSummary summary = listener.getSummary();
            if (summary.getTotalFailureCount() > 0) {
                System.out.println("FAIL");
                PrintWriter pw = new PrintWriter(System.out);
                summary.printFailuresTo(pw);
                pw.flush();
                System.exit(1);
            } else if (summary.getTestsFoundCount() == 0) {
                errorOut("no tests discovered in " + testFqn);
            } else {
                System.out.println("PASS");
                System.exit(0);
            }
        }
    }

    private static List<File> listJavaFilesRecursively(File root) {
        List<File> out = new ArrayList<>();
        if (root == null || !root.exists()) return out;
        if (root.isFile()) {
            if (root.getName().endsWith(".java")) out.add(root);
            return out;
        }
        File[] children = root.listFiles();
        if (children != null) {
            for (File c : children) out.addAll(listJavaFilesRecursively(c));
        }
        return out;
    }

    private static void errorOut(String msg) {
        System.out.println("ERROR");
        System.out.println(msg);
        System.exit(3);
    }
}
