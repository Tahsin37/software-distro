"""
Process management tools — inspect and control processes INSIDE the WSL2 sandbox.
Never exposes host Windows processes.
"""
from tools.base import Tool, ToolResult, ToolParameter, RiskLevel, Permission
from sandbox.wsl2 import sandbox


class ProcessList(Tool):
    name = "process.list"
    description = "List running processes inside the sandbox."
    category = "process"
    risk_level = RiskLevel.SAFE
    permissions = [Permission.SYSTEM_READ]
    parameters = [
        ToolParameter("filter", "string", "Filter by process name", required=False, default=None),
    ]

    async def execute(self, filter: str = None) -> ToolResult:
        cmd = "ps aux --no-heading"
        if filter:
            cmd += f" | grep -i '{filter}' | grep -v grep"
        result = await sandbox.execute(cmd, timeout=10)
        return ToolResult(success=True, output={
            "processes": result["stdout"],
            "environment": "sandbox",
        })


class ProcessKill(Tool):
    name = "process.kill"
    description = "Kill a process by PID inside the sandbox."
    category = "process"
    risk_level = RiskLevel.MEDIUM
    permissions = [Permission.PROCESS_KILL]
    parameters = [
        ToolParameter("pid", "integer", "Process ID to kill"),
        ToolParameter("signal", "string", "Signal to send (TERM, KILL, INT)", required=False, default="TERM"),
    ]

    async def execute(self, pid: int, signal: str = "TERM") -> ToolResult:
        result = await sandbox.execute(f"kill -{signal} {pid} 2>&1", timeout=5)
        return ToolResult(
            success=result["exit_code"] == 0,
            output={"killed": pid, "signal": signal},
            error=result["stderr"] if result["exit_code"] != 0 else None,
        )


class ProcessStart(Tool):
    name = "process.start"
    description = "Start a background process inside the sandbox."
    category = "process"
    risk_level = RiskLevel.MEDIUM
    permissions = [Permission.PROCESS_CREATE]
    parameters = [
        ToolParameter("command", "string", "Command to run in background"),
    ]

    async def execute(self, command: str) -> ToolResult:
        result = await sandbox.execute(
            f"nohup {command} > /tmp/proc_$$.log 2>&1 & echo $!",
            timeout=10,
        )
        pid = result["stdout"].strip()
        return ToolResult(success=True, output={
            "pid": pid,
            "command": command,
            "environment": "sandbox",
        })


ALL_PROCESS_TOOLS = [ProcessList(), ProcessKill(), ProcessStart()]
