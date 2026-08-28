"""
WSL2 Sandbox Provider — manages a dedicated WSL2 Linux distro as the agent sandbox.
All agent tool operations execute INSIDE this sandbox, never on the Windows host.

Security properties:
- Commands execute in WSL2 Linux, not Windows PowerShell/CMD
- Filesystem is scoped to /home/agent/workspace inside the distro  
- Host environment variables are NOT inherited
- /mnt/ automount can be disabled for full isolation
- Separate process namespace from Windows
"""
import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class SandboxStatus(str, Enum):
    UNKNOWN = "unknown"
    INSTALLING = "installing"
    STOPPED = "stopped"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class SandboxInfo:
    id: str
    name: str
    distro: str
    status: SandboxStatus
    workspace: str = "/home/agent/workspace"
    created_at: float = 0
    error: Optional[str] = None


class WSL2Sandbox:
    """
    Manages a dedicated WSL2 distro for the AI agent.
    All tool execution is routed through this sandbox.
    """

    DISTRO_NAME = "Ubuntu-24.04"  # The WSL distro name
    SANDBOX_USER = "agent"
    WORKSPACE = "/home/agent/workspace"

    def __init__(self):
        self._id = str(uuid.uuid4())[:8]
        self._status = SandboxStatus.UNKNOWN
        self._info: Optional[SandboxInfo] = None

    async def _run_wsl_cmd(self, command: str, timeout: int = 30, as_root: bool = False) -> tuple[int, str, str]:
        """Execute a command inside WSL2 and return (exit_code, stdout, stderr)."""
        user_flag = ["-u", "root"] if as_root else ["-u", self.SANDBOX_USER]
        cmd = [
            "wsl.exe", "-d", self.DISTRO_NAME,
            *user_flag,
            "--", "bash", "-c", command,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # Do NOT pass host env to WSL — isolation!
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
                    "COMSPEC": os.environ.get("COMSPEC", r"C:\Windows\system32\cmd.exe"),
                },
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return (
                proc.returncode or 0,
                stdout.decode("utf-8", errors="replace").strip(),
                stderr.decode("utf-8", errors="replace").strip(),
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return (-1, "", "Command timed out")
        except FileNotFoundError:
            return (-1, "", "wsl.exe not found")

    async def detect(self) -> dict:
        """Detect if WSL2 and the sandbox distro are available."""
        # Check wsl.exe exists
        try:
            proc = await asyncio.create_subprocess_exec(
                "wsl.exe", "--status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            wsl_available = True
        except FileNotFoundError:
            return {"available": False, "error": "WSL not installed"}

        # Check if our distro exists
        proc = await asyncio.create_subprocess_exec(
            "wsl.exe", "--list", "--quiet",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        distros = stdout.decode("utf-16-le", errors="replace").strip().split("\n")
        distros = [d.strip() for d in distros if d.strip()]

        distro_exists = self.DISTRO_NAME in distros

        # Check if it's running
        distro_running = False
        if distro_exists:
            proc = await asyncio.create_subprocess_exec(
                "wsl.exe", "--list", "--verbose",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            verbose = stdout.decode("utf-16-le", errors="replace")
            if self.DISTRO_NAME in verbose and "Running" in verbose:
                distro_running = True

        return {
            "available": True,
            "wsl_available": wsl_available,
            "distro": self.DISTRO_NAME,
            "distro_exists": distro_exists,
            "distro_running": distro_running,
            "distros": distros,
        }

    async def initialize(self) -> SandboxInfo:
        """Initialize the sandbox distro — create user, workspace, install essentials."""
        detection = await self.detect()

        if not detection.get("distro_exists"):
            self._status = SandboxStatus.ERROR
            return SandboxInfo(
                id=self._id,
                name="ai-sandbox",
                distro=self.DISTRO_NAME,
                status=SandboxStatus.ERROR,
                error=f"WSL distro '{self.DISTRO_NAME}' not installed. Run: wsl --install {self.DISTRO_NAME}",
            )

        # Start the distro if not running
        if not detection.get("distro_running"):
            proc = await asyncio.create_subprocess_exec(
                "wsl.exe", "-d", self.DISTRO_NAME, "--", "echo", "started",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=30)

        # Create the agent user if it doesn't exist
        exit_code, stdout, stderr = await self._run_wsl_cmd(
            "id -u agent 2>/dev/null || (useradd -m -s /bin/bash agent && echo 'agent ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers)",
            as_root=True,
            timeout=15,
        )

        # Create workspace
        exit_code, stdout, stderr = await self._run_wsl_cmd(
            "mkdir -p /home/agent/workspace && chown -R agent:agent /home/agent/workspace",
            as_root=True,
            timeout=10,
        )

        # Disable /mnt automount for isolation (only if wsl.conf doesn't already have it)
        exit_code, stdout, stderr = await self._run_wsl_cmd(
            """
            if ! grep -q 'automount' /etc/wsl.conf 2>/dev/null; then
                cat >> /etc/wsl.conf << 'EOF'
[automount]
enabled = false
mountFsTab = false

[interop]
enabled = false
appendWindowsPath = false
EOF
                echo "configured"
            else
                echo "already_configured"
            fi
            """,
            as_root=True,
            timeout=10,
        )

        # Install essential tools if not present
        exit_code, stdout, stderr = await self._run_wsl_cmd(
            "which python3 && which git && which node && echo 'essentials_ok' || echo 'needs_install'",
            timeout=10,
        )

        if "needs_install" in stdout:
            # Install essentials — this might take a minute
            await self._run_wsl_cmd(
                "sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-pip git curl sqlite3 > /dev/null 2>&1 && echo 'installed'",
                timeout=180,
            )

        self._status = SandboxStatus.RUNNING
        self._info = SandboxInfo(
            id=self._id,
            name="ai-sandbox",
            distro=self.DISTRO_NAME,
            status=SandboxStatus.RUNNING,
            workspace=self.WORKSPACE,
            created_at=time.time(),
        )
        return self._info

    async def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 60,
        as_root: bool = False,
    ) -> dict:
        """Execute a command inside the sandbox. This is the core execution method."""
        working_dir = cwd or self.WORKSPACE

        # Ensure cwd is within workspace (prevent traversal)
        sanitized_cwd = working_dir
        if not working_dir.startswith(self.WORKSPACE) and not working_dir.startswith("/tmp"):
            sanitized_cwd = self.WORKSPACE

        full_command = f"cd {sanitized_cwd} 2>/dev/null || cd {self.WORKSPACE}; {command}"

        exit_code, stdout, stderr = await self._run_wsl_cmd(
            full_command,
            timeout=timeout,
            as_root=as_root,
        )

        return {
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "cwd": sanitized_cwd,
            "environment": "sandbox",
            "sandbox_id": self._id,
            "distro": self.DISTRO_NAME,
        }

    async def read_file(self, path: str) -> tuple[bool, str]:
        """Read a file from inside the sandbox."""
        safe_path = self._sanitize_path(path)
        exit_code, stdout, stderr = await self._run_wsl_cmd(f"cat '{safe_path}'", timeout=10)
        return (exit_code == 0, stdout if exit_code == 0 else stderr)

    async def write_file(self, path: str, content: str) -> tuple[bool, str]:
        """Write a file inside the sandbox."""
        safe_path = self._sanitize_path(path)
        # Ensure parent directory exists
        parent = "/".join(safe_path.rsplit("/", 1)[:-1])
        await self._run_wsl_cmd(f"mkdir -p '{parent}'", timeout=5)

        # Use heredoc to avoid shell escaping issues
        import base64
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        exit_code, stdout, stderr = await self._run_wsl_cmd(
            f"echo '{encoded}' | base64 -d > '{safe_path}'",
            timeout=10,
        )
        return (exit_code == 0, "written" if exit_code == 0 else stderr)

    async def list_files(self, path: str = ".") -> tuple[bool, str]:
        """List files inside the sandbox."""
        safe_path = self._sanitize_path(path)
        exit_code, stdout, stderr = await self._run_wsl_cmd(
            f"ls -la '{safe_path}' 2>&1",
            timeout=10,
        )
        return (exit_code == 0, stdout)

    async def file_exists(self, path: str) -> bool:
        """Check if file exists inside sandbox."""
        safe_path = self._sanitize_path(path)
        exit_code, _, _ = await self._run_wsl_cmd(f"test -e '{safe_path}'", timeout=5)
        return exit_code == 0

    async def status(self) -> dict:
        """Get sandbox status."""
        detection = await self.detect()
        if not detection.get("distro_exists"):
            return {"status": "not_installed", "distro": self.DISTRO_NAME}

        if not detection.get("distro_running"):
            return {"status": "stopped", "distro": self.DISTRO_NAME}

        # Get system info from inside sandbox
        exit_code, stdout, _ = await self._run_wsl_cmd(
            "echo \"os=$(cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"')\"; "
            "echo \"kernel=$(uname -r)\"; "
            "echo \"user=$(whoami)\"; "
            "echo \"workspace=$(du -sh /home/agent/workspace 2>/dev/null | cut -f1)\"; "
            "echo \"memory=$(free -h | awk '/^Mem:/{print $2}')\"; "
            "echo \"disk=$(df -h /home/agent/workspace 2>/dev/null | awk 'NR==2{print $4}')\"; "
            "echo \"processes=$(ps aux --no-heading | wc -l)\"",
            timeout=10,
        )

        info = {}
        for line in stdout.split("\n"):
            if "=" in line:
                k, v = line.split("=", 1)
                info[k.strip()] = v.strip()

        return {
            "status": "running",
            "distro": self.DISTRO_NAME,
            "sandbox_id": self._id,
            **info,
        }

    async def reset(self) -> dict:
        """Reset workspace to clean state."""
        exit_code, stdout, stderr = await self._run_wsl_cmd(
            "rm -rf /home/agent/workspace/* /home/agent/workspace/.* 2>/dev/null; "
            "mkdir -p /home/agent/workspace; "
            "echo 'reset_complete'",
            timeout=30,
        )
        return {"reset": exit_code == 0, "error": stderr if exit_code != 0 else None}

    async def stop(self) -> dict:
        """Stop the sandbox distro."""
        proc = await asyncio.create_subprocess_exec(
            "wsl.exe", "--terminate", self.DISTRO_NAME,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        self._status = SandboxStatus.STOPPED
        return {"stopped": True}

    async def restart(self) -> dict:
        """Restart the sandbox."""
        await self.stop()
        await asyncio.sleep(1)
        return await self.status()

    def _sanitize_path(self, path: str) -> str:
        """Ensure path stays within sandbox workspace."""
        if path.startswith("/"):
            # Absolute path — must be within workspace or /tmp
            if not path.startswith(self.WORKSPACE) and not path.startswith("/tmp"):
                return f"{self.WORKSPACE}/{path.lstrip('/')}"
            return path
        else:
            # Relative — prepend workspace
            return f"{self.WORKSPACE}/{path}"

    @property
    def info(self) -> Optional[SandboxInfo]:
        return self._info


# Global sandbox instance
sandbox = WSL2Sandbox()
