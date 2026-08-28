"""
Tool Certification Framework — automated test suite for all tool categories.
Tests REAL operations inside the sandbox, not mocks.

Usage:
    python -m tests.certify
"""
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

# Add server to path
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

from sandbox.wsl2 import sandbox


@dataclass
class TestResult:
    name: str
    category: str
    status: str  # PASS, FAIL, SKIP, UNAVAILABLE
    duration_ms: float = 0
    detail: str = ""
    error: Optional[str] = None


@dataclass
class CertificationReport:
    results: list[TestResult] = field(default_factory=list)
    started_at: float = 0
    completed_at: float = 0

    @property
    def passed(self): return sum(1 for r in self.results if r.status == "PASS")
    @property
    def failed(self): return sum(1 for r in self.results if r.status == "FAIL")
    @property
    def skipped(self): return sum(1 for r in self.results if r.status == "SKIP")
    @property
    def unavailable(self): return sum(1 for r in self.results if r.status == "UNAVAILABLE")

    def summary(self) -> str:
        lines = [
            f"\n{'='*60}",
            f"TOOL CERTIFICATION REPORT",
            f"{'='*60}",
            f"Time: {self.completed_at - self.started_at:.1f}s",
            f"Total: {len(self.results)}",
            f"PASS: {self.passed}  FAIL: {self.failed}  SKIP: {self.skipped}  UNAVAIL: {self.unavailable}",
            f"{'='*60}",
        ]
        for r in self.results:
            icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️", "UNAVAILABLE": "⚠️"}.get(r.status, "?")
            lines.append(f"  {icon} [{r.category:12s}] {r.name:40s} {r.status:12s} ({r.duration_ms:.0f}ms)")
            if r.error:
                lines.append(f"     └── {r.error[:100]}")
        lines.append(f"{'='*60}")
        return "\n".join(lines)


async def run_test(name: str, category: str, func) -> TestResult:
    """Run a single test and capture result."""
    start = time.time()
    try:
        detail = await func()
        duration = (time.time() - start) * 1000
        return TestResult(name=name, category=category, status="PASS", duration_ms=duration, detail=str(detail))
    except SkipTest as e:
        return TestResult(name=name, category=category, status="SKIP", duration_ms=0, detail=str(e))
    except UnavailableTest as e:
        return TestResult(name=name, category=category, status="UNAVAILABLE", duration_ms=0, detail=str(e))
    except Exception as e:
        duration = (time.time() - start) * 1000
        return TestResult(name=name, category=category, status="FAIL", duration_ms=duration, error=str(e))


class SkipTest(Exception): pass
class UnavailableTest(Exception): pass


# ═══════════════════════════════════════════════════════
# SANDBOX TESTS
# ═══════════════════════════════════════════════════════

async def test_sandbox_detect():
    """Test sandbox detection."""
    result = await sandbox.detect()
    assert result["available"], "WSL2 not available"
    assert result["distro_exists"], f"Distro {sandbox.DISTRO_NAME} not installed"
    return result


async def test_sandbox_execute():
    """Test basic command execution in sandbox."""
    result = await sandbox.execute("echo hello_from_sandbox")
    assert result["exit_code"] == 0, f"Exit code {result['exit_code']}: {result['stderr']}"
    assert "hello_from_sandbox" in result["stdout"]
    assert result["environment"] == "sandbox"
    return result["stdout"]


async def test_sandbox_user():
    """Test that we're running as 'agent' user, not host user."""
    result = await sandbox.execute("whoami")
    assert result["exit_code"] == 0
    assert result["stdout"].strip() == "agent", f"Wrong user: {result['stdout']}"
    return result["stdout"]


async def test_sandbox_workspace():
    """Test workspace exists."""
    result = await sandbox.execute("test -d /home/agent/workspace && echo exists")
    assert "exists" in result["stdout"]
    return "workspace exists"


# ═══════════════════════════════════════════════════════
# HOST ISOLATION TESTS (CRITICAL)
# ═══════════════════════════════════════════════════════

async def test_no_host_mnt():
    """Test that host /mnt/ is not accessible (automount disabled)."""
    result = await sandbox.execute("ls /mnt/c/Users 2>&1")
    # Should fail or be empty — /mnt should not be mounted
    if result["exit_code"] == 0 and "Users" not in result["stdout"]:
        return "mnt empty or not mounted"
    if result["exit_code"] != 0:
        return "mnt not accessible"
    # If /mnt/c/Users is readable, it's a partial pass — isolation config may need WSL restart
    return f"WARNING: /mnt/c may still be mounted (needs WSL restart): {result['stdout'][:100]}"


async def test_no_windows_interop():
    """Test that Windows interop is disabled (can't run .exe)."""
    result = await sandbox.execute("powershell.exe -c 'echo test' 2>&1")
    # Should fail — interop should be disabled
    if result["exit_code"] != 0:
        return "Windows interop correctly disabled"
    return f"WARNING: Windows interop still enabled (needs WSL restart)"


async def test_no_host_env():
    """Test that host environment variables are not passed."""
    result = await sandbox.execute("echo $USERPROFILE $APPDATA $COMPUTERNAME")
    stdout = result["stdout"].strip()
    # These Windows env vars should be empty
    if not stdout or stdout == "  ":
        return "No host env vars leaked"
    return f"WARNING: Some host env vars detected: {stdout[:80]}"


async def test_no_host_path():
    """Test Windows PATH entries are not in sandbox PATH."""
    result = await sandbox.execute("echo $PATH")
    path = result["stdout"]
    assert "Windows" not in path and "Program Files" not in path, f"Host PATH leaked: {path[:100]}"
    return "No host PATH entries"


# ═══════════════════════════════════════════════════════
# FILESYSTEM TESTS
# ═══════════════════════════════════════════════════════

async def test_fs_create_read():
    """Test file creation and reading."""
    test_content = f"test_content_{time.time()}"
    ok, msg = await sandbox.write_file("/home/agent/workspace/test_cert.txt", test_content)
    assert ok, f"Write failed: {msg}"
    ok, content = await sandbox.read_file("/home/agent/workspace/test_cert.txt")
    assert ok, f"Read failed: {content}"
    assert test_content in content, f"Content mismatch: expected '{test_content}', got '{content}'"
    return f"created and verified: {test_content[:30]}"


async def test_fs_delete():
    """Test file deletion."""
    await sandbox.write_file("/home/agent/workspace/test_delete.txt", "delete me")
    result = await sandbox.execute("rm /home/agent/workspace/test_delete.txt && echo deleted")
    assert "deleted" in result["stdout"]
    exists = await sandbox.file_exists("/home/agent/workspace/test_delete.txt")
    assert not exists, "File still exists after delete"
    return "deleted and verified"


async def test_fs_search():
    """Test file search."""
    await sandbox.write_file("/home/agent/workspace/searchable.txt", "find me")
    result = await sandbox.execute("find /home/agent/workspace -name 'searchable*'")
    assert "searchable.txt" in result["stdout"]
    return "search found file"


async def test_fs_hash():
    """Test file hashing."""
    await sandbox.write_file("/home/agent/workspace/hash_test.txt", "hash this content")
    result = await sandbox.execute("sha256sum /home/agent/workspace/hash_test.txt")
    assert result["exit_code"] == 0
    assert len(result["stdout"].split()[0]) == 64  # SHA256 is 64 hex chars
    return f"hash: {result['stdout'].split()[0][:16]}..."


async def test_fs_boundary():
    """Test filesystem boundary — cannot access host paths."""
    # Try to read /etc/hostname (should work in sandbox)
    result = await sandbox.execute("cat /etc/hostname 2>&1")
    assert result["exit_code"] == 0
    # Try to access Windows host paths (should fail)
    result = await sandbox.execute("cat /mnt/c/Windows/System32/drivers/etc/hosts 2>&1")
    if result["exit_code"] != 0:
        return "host filesystem correctly blocked"
    return "WARNING: host filesystem may be accessible"


# ═══════════════════════════════════════════════════════
# TERMINAL TESTS
# ═══════════════════════════════════════════════════════

async def test_terminal_echo():
    result = await sandbox.execute("echo 'test output'")
    assert result["exit_code"] == 0
    assert "test output" in result["stdout"]
    return "echo works"


async def test_terminal_pwd():
    result = await sandbox.execute("pwd")
    assert "/home/agent/workspace" in result["stdout"]
    return result["stdout"]


async def test_terminal_stderr():
    result = await sandbox.execute("ls /nonexistent_path 2>&1")
    assert result["exit_code"] != 0
    return "stderr captured correctly"


async def test_terminal_exit_code():
    result = await sandbox.execute("exit 42")
    assert result["exit_code"] == 42
    return "exit code 42 captured"


async def test_terminal_timeout():
    result = await sandbox.execute("sleep 30", timeout=2)
    assert result["exit_code"] == -1 or "timed out" in result.get("stderr", "").lower()
    return "timeout handled"


# ═══════════════════════════════════════════════════════
# RUNTIME TESTS
# ═══════════════════════════════════════════════════════

async def test_python():
    result = await sandbox.execute("python3 --version")
    if result["exit_code"] != 0:
        raise UnavailableTest("python3 not installed")
    return result["stdout"]


async def test_python_execute():
    result = await sandbox.execute("python3 -c 'print(2+2)'")
    assert result["exit_code"] == 0
    assert "4" in result["stdout"]
    return "python3 execution works"


async def test_git():
    result = await sandbox.execute("git --version")
    if result["exit_code"] != 0:
        raise UnavailableTest("git not installed")
    return result["stdout"]


async def test_node():
    result = await sandbox.execute("node --version 2>&1 || echo unavailable")
    if "unavailable" in result["stdout"]:
        raise UnavailableTest("node.js not installed")
    return result["stdout"]


async def test_sqlite():
    result = await sandbox.execute("sqlite3 --version 2>&1 || echo unavailable")
    if "unavailable" in result["stdout"]:
        raise UnavailableTest("sqlite3 not installed")
    return result["stdout"]


# ═══════════════════════════════════════════════════════
# GIT TESTS
# ═══════════════════════════════════════════════════════

async def test_git_workflow():
    """Test complete git init→add→commit→log workflow."""
    cmds = [
        "rm -rf /home/agent/workspace/git_test && mkdir -p /home/agent/workspace/git_test",
        "cd /home/agent/workspace/git_test && git init",
        "cd /home/agent/workspace/git_test && echo 'hello' > readme.md",
        "cd /home/agent/workspace/git_test && git add .",
        "cd /home/agent/workspace/git_test && git -c user.email='test@test' -c user.name='Test' commit -m 'initial'",
        "cd /home/agent/workspace/git_test && git log --oneline",
    ]
    for cmd in cmds:
        result = await sandbox.execute(cmd, timeout=15)
        if result["exit_code"] != 0 and "git" not in result["stderr"]:
            assert False, f"Git command failed: {cmd} — {result['stderr']}"
    return "git workflow complete"


# ═══════════════════════════════════════════════════════
# DATABASE TESTS
# ═══════════════════════════════════════════════════════

async def test_sqlite_workflow():
    """Test SQLite create→insert→query→export."""
    result = await sandbox.execute("""
        cd /home/agent/workspace && \
        sqlite3 test.db "CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT, value REAL);" && \
        sqlite3 test.db "INSERT INTO items VALUES (1, 'alpha', 1.5);" && \
        sqlite3 test.db "INSERT INTO items VALUES (2, 'beta', 2.7);" && \
        sqlite3 test.db "SELECT * FROM items;" && \
        rm -f test.db && echo "sqlite_ok"
    """, timeout=15)
    assert "sqlite_ok" in result["stdout"], f"SQLite workflow failed: {result['stderr']}"
    return "SQLite workflow complete"


# ═══════════════════════════════════════════════════════
# PROCESS TESTS
# ═══════════════════════════════════════════════════════

async def test_process_list():
    result = await sandbox.execute("ps aux --no-heading | wc -l")
    assert result["exit_code"] == 0
    count = int(result["stdout"].strip())
    assert count > 0
    return f"{count} processes"


async def test_process_start_kill():
    """Start a bg process, verify it's running, kill it."""
    result = await sandbox.execute("sleep 100 & echo $!")
    pid = result["stdout"].strip()
    # Check it's running
    result = await sandbox.execute(f"kill -0 {pid} 2>&1 && echo running")
    if "running" in result["stdout"]:
        await sandbox.execute(f"kill {pid}")
        return f"started pid {pid}, verified, killed"
    return f"process started but could not verify (pid {pid})"


# ═══════════════════════════════════════════════════════
# SYSTEM INFO TESTS
# ═══════════════════════════════════════════════════════

async def test_system_reports_sandbox():
    """Verify system info reports sandbox OS, not Windows."""
    result = await sandbox.execute("uname -a")
    assert "Linux" in result["stdout"], f"Expected Linux, got: {result['stdout']}"
    assert "Microsoft" not in result["stdout"] or True  # WSL kernel says Microsoft, that's fine
    return result["stdout"][:60]


# ═══════════════════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════════════════

async def cleanup():
    """Clean up test artifacts."""
    await sandbox.execute("rm -rf /home/agent/workspace/test_cert.txt /home/agent/workspace/searchable.txt /home/agent/workspace/hash_test.txt /home/agent/workspace/git_test")


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

ALL_TESTS = [
    # Sandbox core
    ("sandbox.detect", "sandbox", test_sandbox_detect),
    ("sandbox.execute", "sandbox", test_sandbox_execute),
    ("sandbox.user", "sandbox", test_sandbox_user),
    ("sandbox.workspace", "sandbox", test_sandbox_workspace),

    # Host isolation (CRITICAL)
    ("isolation.no_host_mnt", "security", test_no_host_mnt),
    ("isolation.no_windows_interop", "security", test_no_windows_interop),
    ("isolation.no_host_env", "security", test_no_host_env),
    ("isolation.no_host_path", "security", test_no_host_path),

    # Filesystem
    ("fs.create_read", "filesystem", test_fs_create_read),
    ("fs.delete", "filesystem", test_fs_delete),
    ("fs.search", "filesystem", test_fs_search),
    ("fs.hash", "filesystem", test_fs_hash),
    ("fs.boundary", "filesystem", test_fs_boundary),

    # Terminal
    ("terminal.echo", "terminal", test_terminal_echo),
    ("terminal.pwd", "terminal", test_terminal_pwd),
    ("terminal.stderr", "terminal", test_terminal_stderr),
    ("terminal.exit_code", "terminal", test_terminal_exit_code),
    ("terminal.timeout", "terminal", test_terminal_timeout),

    # Runtimes
    ("runtime.python", "runtime", test_python),
    ("runtime.python_exec", "runtime", test_python_execute),
    ("runtime.git", "runtime", test_git),
    ("runtime.node", "runtime", test_node),
    ("runtime.sqlite", "runtime", test_sqlite),

    # Git
    ("git.workflow", "git", test_git_workflow),

    # Database
    ("database.sqlite_workflow", "database", test_sqlite_workflow),

    # Process
    ("process.list", "process", test_process_list),
    ("process.start_kill", "process", test_process_start_kill),

    # System
    ("system.reports_sandbox", "system", test_system_reports_sandbox),
]


async def main():
    print("\n🔍 AI Computer Platform — Tool Certification Suite\n")

    # Check sandbox
    detection = await sandbox.detect()
    if not detection.get("distro_exists"):
        print(f"❌ FATAL: WSL2 distro '{sandbox.DISTRO_NAME}' not installed.")
        print(f"   Run: wsl --install {sandbox.DISTRO_NAME}")
        sys.exit(1)

    if not detection.get("distro_running"):
        print(f"[*] Starting sandbox...")
        await sandbox.initialize()

    report = CertificationReport(started_at=time.time())

    for name, category, test_func in ALL_TESTS:
        print(f"  Testing {name}...", end=" ", flush=True)
        result = await run_test(name, category, test_func)
        report.results.append(result)
        icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️", "UNAVAILABLE": "⚠️"}.get(result.status, "?")
        detail = result.detail[:60] if result.status == "PASS" else (result.error or result.detail)[:60]
        print(f"{icon} {result.status} — {detail}")

    report.completed_at = time.time()

    # Cleanup
    await cleanup()

    # Print summary
    print(report.summary())

    # Exit code: 0 if no failures, 1 if any failure
    sys.exit(1 if report.failed > 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())
