"""
HARDENED Terminal tools — execute commands INSIDE the WSL2 sandbox, never on Windows host.
All commands run as the 'agent' user inside the sandbox Linux environment.
Host PowerShell/CMD is NEVER exposed to the AI agent.
"""
import asyncio
import os
import time
from typing import Optional
from tools.base import Tool, ToolResult, ToolParameter, RiskLevel, Permission
from sandbox.wsl2 import sandbox


class TerminalExecute(Tool):
    name = "terminal.execute"
    description = "Execute a shell command inside the sandbox Linux environment. Returns stdout, stderr, and exit code."
    category = "terminal"
    risk_level = RiskLevel.MEDIUM
    permissions = [Permission.PROCESS_CREATE]
    timeout = 300
    parameters = [
        ToolParameter("command", "string", "The bash command to execute inside the sandbox"),
        ToolParameter("cwd", "string", "Working directory inside sandbox (default: /home/agent/workspace)", required=False, default=None),
        ToolParameter("timeout", "integer", "Timeout in seconds", required=False, default=60),
    ]

    async def execute(self, command: str, cwd: str = None, timeout: int = 60) -> ToolResult:
        start = time.time()

        result = await sandbox.execute(
            command=command,
            cwd=cwd,
            timeout=timeout,
        )

        duration = time.time() - start
        exit_code = result["exit_code"]
        stdout = result["stdout"]
        stderr = result["stderr"]

        # Truncate very large outputs
        max_output = 50000
        if len(stdout) > max_output:
            stdout = stdout[:max_output] + f"\n... (truncated, {len(stdout)} total chars)"
        if len(stderr) > max_output:
            stderr = stderr[:max_output] + f"\n... (truncated, {len(stderr)} total chars)"

        output = {
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "duration_seconds": round(duration, 2),
            "timed_out": exit_code == -1 and "timed out" in stderr.lower(),
            "cwd": result.get("cwd", "/home/agent/workspace"),
            "environment": "sandbox",
            "sandbox_id": result.get("sandbox_id"),
        }

        if exit_code == -1:
            return ToolResult(success=False, output=output, error=stderr or "Command failed")

        return ToolResult(
            success=exit_code == 0,
            output=output,
            error=stderr if exit_code != 0 and stderr else None,
        )


class TerminalBash(Tool):
    name = "terminal.bash"
    description = "Execute a bash command inside the sandbox. Alias for terminal.execute."
    category = "terminal"
    risk_level = RiskLevel.MEDIUM
    permissions = [Permission.PROCESS_CREATE]
    timeout = 300
    parameters = [
        ToolParameter("command", "string", "Bash command to execute in the sandbox"),
        ToolParameter("cwd", "string", "Working directory", required=False, default=None),
        ToolParameter("timeout", "integer", "Timeout in seconds", required=False, default=60),
    ]

    async def execute(self, command: str, cwd: str = None, timeout: int = 60) -> ToolResult:
        executor = TerminalExecute()
        return await executor.execute(command=command, cwd=cwd, timeout=timeout)


# NOTE: PowerShell and CMD tools are DELIBERATELY REMOVED.
# The agent operates inside a Linux sandbox and should never execute
# host Windows commands. This is a security requirement.

ALL_TERMINAL_TOOLS = [
    TerminalExecute(),
    TerminalBash(),
]
