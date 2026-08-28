"""
System inspection tools — reports SANDBOX system info, NOT host info.
"""
from tools.base import Tool, ToolResult, ToolParameter, RiskLevel, Permission
from sandbox.wsl2 import sandbox


class SystemInfo(Tool):
    name = "system.info"
    description = "Get system information about the sandbox environment."
    category = "system"
    risk_level = RiskLevel.SAFE
    permissions = [Permission.SYSTEM_READ]
    parameters = []

    async def execute(self) -> ToolResult:
        result = await sandbox.execute(
            'echo "os=$(cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d \'"\')"; '
            'echo "kernel=$(uname -r)"; '
            'echo "arch=$(uname -m)"; '
            'echo "user=$(whoami)"; '
            'echo "hostname=$(hostname)"; '
            'echo "shell=$(echo $SHELL)"; '
            'echo "python=$(python3 --version 2>/dev/null || echo not_installed)"; '
            'echo "node=$(node --version 2>/dev/null || echo not_installed)"; '
            'echo "git=$(git --version 2>/dev/null || echo not_installed)"',
            timeout=10,
        )
        info = {}
        for line in result["stdout"].split("\n"):
            if "=" in line:
                k, v = line.split("=", 1)
                info[k.strip()] = v.strip()
        info["environment"] = "sandbox"
        info["host_access"] = "DENIED"
        return ToolResult(success=True, output=info)


class SystemMemory(Tool):
    name = "system.memory"
    description = "Get memory usage inside the sandbox."
    category = "system"
    risk_level = RiskLevel.SAFE
    permissions = [Permission.SYSTEM_READ]
    parameters = []

    async def execute(self) -> ToolResult:
        result = await sandbox.execute("free -h 2>&1", timeout=5)
        return ToolResult(success=True, output={"memory": result["stdout"], "environment": "sandbox"})


class SystemDisk(Tool):
    name = "system.disk"
    description = "Get disk usage inside the sandbox workspace."
    category = "system"
    risk_level = RiskLevel.SAFE
    permissions = [Permission.SYSTEM_READ]
    parameters = []

    async def execute(self) -> ToolResult:
        result = await sandbox.execute(
            "df -h /home/agent/workspace 2>&1; echo '---'; du -sh /home/agent/workspace 2>&1",
            timeout=10,
        )
        return ToolResult(success=True, output={"disk": result["stdout"], "environment": "sandbox"})


class SystemProcesses(Tool):
    name = "system.processes"
    description = "List processes running in the sandbox."
    category = "system"
    risk_level = RiskLevel.SAFE
    permissions = [Permission.SYSTEM_READ]
    parameters = []

    async def execute(self) -> ToolResult:
        result = await sandbox.execute("ps aux 2>&1 | head -30", timeout=5)
        return ToolResult(success=True, output={"processes": result["stdout"], "environment": "sandbox"})


ALL_SYSTEM_TOOLS = [SystemInfo(), SystemMemory(), SystemDisk(), SystemProcesses()]
