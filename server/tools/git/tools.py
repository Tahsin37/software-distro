"""
Git tools — operate on git repositories INSIDE the WSL2 sandbox.
"""
from tools.base import Tool, ToolResult, ToolParameter, RiskLevel, Permission
from sandbox.wsl2 import sandbox


class GitInit(Tool):
    name = "git.init"
    description = "Initialize a git repository in the sandbox."
    category = "git"
    risk_level = RiskLevel.LOW
    permissions = [Permission.FILESYSTEM_WRITE]
    parameters = [
        ToolParameter("path", "string", "Directory path (relative to workspace)", required=False, default="."),
    ]

    async def execute(self, path: str = ".") -> ToolResult:
        result = await sandbox.execute(f"cd /home/agent/workspace/{path} && git init 2>&1", timeout=10)
        return ToolResult(success=result["exit_code"] == 0, output=result["stdout"], error=result["stderr"] if result["exit_code"] != 0 else None)


class GitStatus(Tool):
    name = "git.status"
    description = "Show git status."
    category = "git"
    risk_level = RiskLevel.SAFE
    permissions = [Permission.FILESYSTEM_READ]
    parameters = [
        ToolParameter("path", "string", "Repository path", required=False, default="."),
    ]

    async def execute(self, path: str = ".") -> ToolResult:
        result = await sandbox.execute(f"cd /home/agent/workspace/{path} && git status 2>&1", timeout=10)
        return ToolResult(success=result["exit_code"] == 0, output=result["stdout"], error=result["stderr"] if result["exit_code"] != 0 else None)


class GitAdd(Tool):
    name = "git.add"
    description = "Stage files for commit."
    category = "git"
    risk_level = RiskLevel.LOW
    permissions = [Permission.FILESYSTEM_WRITE]
    parameters = [
        ToolParameter("files", "string", "Files to add (use '.' for all)"),
        ToolParameter("path", "string", "Repository path", required=False, default="."),
    ]

    async def execute(self, files: str = ".", path: str = ".") -> ToolResult:
        result = await sandbox.execute(f"cd /home/agent/workspace/{path} && git add {files} 2>&1", timeout=10)
        return ToolResult(success=result["exit_code"] == 0, output=result["stdout"] or "staged", error=result["stderr"] if result["exit_code"] != 0 else None)


class GitCommit(Tool):
    name = "git.commit"
    description = "Create a git commit."
    category = "git"
    risk_level = RiskLevel.LOW
    permissions = [Permission.FILESYSTEM_WRITE]
    parameters = [
        ToolParameter("message", "string", "Commit message"),
        ToolParameter("path", "string", "Repository path", required=False, default="."),
    ]

    async def execute(self, message: str, path: str = ".") -> ToolResult:
        result = await sandbox.execute(
            f"cd /home/agent/workspace/{path} && git -c user.email='agent@sandbox' -c user.name='AI Agent' commit -m '{message}' 2>&1",
            timeout=15,
        )
        return ToolResult(success=result["exit_code"] == 0, output=result["stdout"], error=result["stderr"] if result["exit_code"] != 0 else None)


class GitLog(Tool):
    name = "git.log"
    description = "Show git commit log."
    category = "git"
    risk_level = RiskLevel.SAFE
    permissions = [Permission.FILESYSTEM_READ]
    parameters = [
        ToolParameter("count", "integer", "Number of commits to show", required=False, default=10),
        ToolParameter("path", "string", "Repository path", required=False, default="."),
    ]

    async def execute(self, count: int = 10, path: str = ".") -> ToolResult:
        result = await sandbox.execute(
            f"cd /home/agent/workspace/{path} && git log --oneline -n {count} 2>&1",
            timeout=10,
        )
        return ToolResult(success=result["exit_code"] == 0, output=result["stdout"], error=result["stderr"] if result["exit_code"] != 0 else None)


class GitDiff(Tool):
    name = "git.diff"
    description = "Show git diff."
    category = "git"
    risk_level = RiskLevel.SAFE
    permissions = [Permission.FILESYSTEM_READ]
    parameters = [
        ToolParameter("path", "string", "Repository path", required=False, default="."),
    ]

    async def execute(self, path: str = ".") -> ToolResult:
        result = await sandbox.execute(f"cd /home/agent/workspace/{path} && git diff 2>&1", timeout=10)
        return ToolResult(success=result["exit_code"] == 0, output=result["stdout"] or "(no changes)", error=result["stderr"] if result["exit_code"] != 0 else None)


ALL_GIT_TOOLS = [GitInit(), GitStatus(), GitAdd(), GitCommit(), GitLog(), GitDiff()]
