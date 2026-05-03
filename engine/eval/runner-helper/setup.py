"""One-shot setup for the AgentTest runner-helper.

Downloads JUnit Platform + AssertJ jars from Maven Central into ./lib/
(verifying SHA-1 against the published `.sha1` sidecar) and compiles
TestRunner.java against them. After this script runs once, the validator
and eval harness can invoke the runner via:

    java -cp 'lib/*:.' \
         -Dagenttest.runner.dir=<path-to-this-dir> \
         TestRunner <target.java> <test.java> <test_class_FQN>

Re-run is idempotent: existing jars with the right SHA-1 are skipped.

Why .sha1 and not .sha256? Maven Central reliably ships .sha1 for every
artifact; .sha256 sidecars are inconsistent. HTTPS protects transit;
SHA-1 verification protects against repository corruption / replacement.
For a course project this combination is sufficient.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB_DIR = HERE / "lib"
MAVEN_BASE = "https://repo1.maven.org/maven2"


@dataclass(frozen=True)
class Dep:
    group: str
    artifact: str
    version: str

    @property
    def filename(self) -> str:
        return f"{self.artifact}-{self.version}.jar"

    @property
    def url(self) -> str:
        path = self.group.replace(".", "/")
        return f"{MAVEN_BASE}/{path}/{self.artifact}/{self.version}/{self.filename}"


# JUnit Platform Console Standalone bundles JUnit Platform + Jupiter API
# + Jupiter Engine + Vintage Engine + ASM in one jar. ~6.7 MB.
DEPS: list[Dep] = [
    Dep("org.junit.platform", "junit-platform-console-standalone", "1.10.5"),
    Dep("org.assertj", "assertj-core", "3.25.3"),
]


def fetch(url: str, timeout: int = 120) -> bytes:
    print(f"  GET {url}", flush=True)
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()


def download_with_sha1(dep: Dep, target: Path) -> None:
    expected_sha1 = fetch(dep.url + ".sha1", timeout=30).decode().strip().split()[0]
    if target.exists():
        actual = hashlib.sha1(target.read_bytes()).hexdigest()
        if actual.lower() == expected_sha1.lower():
            print(f"  [skip] {dep.filename} already present and verified")
            return
        print(f"  [warn] {target.name} present but SHA-1 differs; re-downloading")

    payload = fetch(dep.url)
    actual_sha1 = hashlib.sha1(payload).hexdigest()
    if actual_sha1.lower() != expected_sha1.lower():
        raise RuntimeError(
            f"SHA-1 mismatch for {dep.filename}: "
            f"expected {expected_sha1}, got {actual_sha1}"
        )
    target.write_bytes(payload)
    print(f"  [ok] {dep.filename} ({len(payload):,} bytes, sha1 verified)")


def compile_test_runner() -> None:
    print("\nCompiling TestRunner.java...")
    if shutil.which("javac") is None:
        raise RuntimeError("`javac` not on PATH — install JDK 17+ first")
    classpath = str(LIB_DIR / "*")
    cmd = ["javac", "-cp", classpath, "-d", str(HERE), str(HERE / "TestRunner.java")]
    print("  $ " + " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        raise RuntimeError(f"javac exited with status {result.returncode}")
    print("  [ok] TestRunner.class produced")


def main() -> int:
    print(f"Setting up runner-helper at {HERE}")
    LIB_DIR.mkdir(exist_ok=True)

    print("\nDownloading dependencies...")
    for dep in DEPS:
        download_with_sha1(dep, LIB_DIR / dep.filename)

    compile_test_runner()

    print("\nDone.")
    print(
        "\nVerify with:\n"
        f"  cd {HERE}\n"
        "  java -cp 'lib/*:.' -Dagenttest.runner.dir=. TestRunner --help"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
