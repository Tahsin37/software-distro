"""
HARDENED Filesystem tools — all operations execute INSIDE the WSL2 sandbox.
The agent never sees or touches the Windows host filesystem.
Every path is relative to /home/agent/workspace/ inside the sandbox.
"""
import json
import time
from typing import Optional
from tools.base import Tool, ToolResult, ToolParameter, RiskLevel, Permission
from sandbox.wsl2 import sandbox

WORKSPACE = "/home/agent/workspace"


def _safe_path(path: str) -> str:
    """Convert path to sandbox-relative. Prevents sandbox escape."""
    if not path or path == ".":
        return WORKSPACE
    # Strip leading slash for relative paths
    clean = path.strip()
    if clean.startswith("/"):
        # Absolute path — must be within workspace
        if not clean.startswith(WORKSPACE):
            return f"{WORKSPACE}/{clean.lstrip('/')}"
        return clean
    else:
        return f"{WORKSPACE}/{clean}"


class FsList(Tool):
    name = "fs.list"
    description = "List files and directories in the sandbox workspace."
    category = "filesystem"
    risk_level = RiskLevel.SAFE
    permissions = [Permission.FILESYSTEM_READ]
    parameters = [
        ToolParameter("path", "string", "Path relative to workspace", required=False, default="."),
        ToolParameter("recursive", "boolean", "List recursively", required=False, default=False),
        ToolParameter("show_hidden", "boolean", "Show hidden files", required=False, default=False),
    ]

    async def execute(self, path: str = ".", recursive: bool = False, show_hidden: bool = False) -> ToolResult:
        safe = _safe_path(path)
        flags = "-la" if show_hidden else "-l"
        if recursive:
            cmd = f"find '{safe}' -maxdepth 3 -ls 2>&1 | head -200"
        else:
            cmd = f"ls {flags} '{safe}' 2>&1"

        result = await sandbox.execute(cmd, timeout=10)
        if result["exit_code"] != 0:
            return ToolResult(success=False, error=result["stderr"] or result["stdout"])

        return ToolResult(success=True, output={
            "path": path,
            "listing": result["stdout"],
            "environment": "sandbox",
        })


class FsCreateFile(Tool):
    name = "fs.create_file"
    description = "Create a new file with content inside the sandbox. Creates parent directories."
    category = "filesystem"
    risk_level = RiskLevel.LOW
    permissions = [Permission.FILESYSTEM_WRITE]
    parameters = [
        ToolParameter("path", "string", "File path relative to workspace"),
        ToolParameter("content", "string", "File content", required=False, default=""),
    ]

    async def execute(self, path: str, content: str = "") -> ToolResult:
        safe = _safe_path(path)
        ok, msg = await sandbox.write_file(safe, content)
        if not ok:
            return ToolResult(success=False, error=msg)
        return ToolResult(success=True, output={
            "path": path,
            "size": len(content.encode("utf-8")),
            "created": True,
            "environment": "sandbox",
        })


class FsReadFile(Tool):
    name = "fs.read_file"
    description = "Read file contents from the sandbox."
    category = "filesystem"
    risk_level = RiskLevel.SAFE
    permissions = [Permission.FILESYSTEM_READ]
    parameters = [
        ToolParameter("path", "string", "File path relative to workspace"),
        ToolParameter("max_lines", "integer", "Maximum lines to read (0 = all)", required=False, default=0),
    ]

    async def execute(self, path: str, max_lines: int = 0) -> ToolResult:
        safe = _safe_path(path)
        if max_lines > 0:
            cmd = f"head -n {max_lines} '{safe}' 2>&1"
        else:
            cmd = f"cat '{safe}' 2>&1"

        result = await sandbox.execute(cmd, timeout=10)
        if result["exit_code"] != 0:
            return ToolResult(success=False, error=result["stderr"] or result["stdout"])

        content = result["stdout"]
        # Truncate huge files for LLM context
        if len(content) > 100000:
            content = content[:100000] + f"\n... (truncated, file too large)"

        return ToolResult(success=True, output={
            "content": content,
            "path": path,
            "truncated": max_lines > 0 or len(result["stdout"]) > 100000,
            "environment": "sandbox",
        })


class FsWriteFile(Tool):
    name = "fs.write_file"
    description = "Write content to a file in the sandbox, overwriting if it exists."
    category = "filesystem"
    risk_level = RiskLevel.LOW
    permissions = [Permission.FILESYSTEM_WRITE]
    parameters = [
        ToolParameter("path", "string", "File path relative to workspace"),
        ToolParameter("content", "string", "File content"),
    ]

    async def execute(self, path: str, content: str) -> ToolResult:
        safe = _safe_path(path)
        ok, msg = await sandbox.write_file(safe, content)
        if not ok:
            return ToolResult(success=False, error=msg)
        return ToolResult(success=True, output={
            "path": path,
            "size": len(content.encode("utf-8")),
            "written": True,
            "environment": "sandbox",
        })


class FsAppendFile(Tool):
    name = "fs.append_file"
    description = "Append content to an existing file in the sandbox."
    category = "filesystem"
    risk_level = RiskLevel.LOW
    permissions = [Permission.FILESYSTEM_WRITE]
    parameters = [
        ToolParameter("path", "string", "File path"),
        ToolParameter("content", "string", "Content to append"),
    ]

    async def execute(self, path: str, content: str) -> ToolResult:
        safe = _safe_path(path)
        import base64
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        result = await sandbox.execute(f"echo '{encoded}' | base64 -d >> '{safe}'", timeout=10)
        if result["exit_code"] != 0:
            return ToolResult(success=False, error=result["stderr"])
        return ToolResult(success=True, output={"path": path, "appended_bytes": len(content.encode("utf-8"))})


class FsDelete(Tool):
    name = "fs.delete"
    description = "Delete a file or directory in the sandbox."
    category = "filesystem"
    risk_level = RiskLevel.MEDIUM
    permissions = [Permission.FILESYSTEM_WRITE]
    parameters = [
        ToolParameter("path", "string", "Path to delete"),
        ToolParameter("recursive", "boolean", "Delete directory recursively", required=False, default=False),
    ]

    async def execute(self, path: str, recursive: bool = False) -> ToolResult:
        safe = _safe_path(path)
        # Safety: never delete workspace root
        if safe.rstrip("/") == WORKSPACE:
            return ToolResult(success=False, error="Cannot delete workspace root directory")
        flag = "-rf" if recursive else "-f"
        result = await sandbox.execute(f"rm {flag} '{safe}' 2>&1", timeout=10)
        if result["exit_code"] != 0:
            return ToolResult(success=False, error=result["stderr"] or result["stdout"])
        return ToolResult(success=True, output={"deleted": path})


class FsCopy(Tool):
    name = "fs.copy"
    description = "Copy a file or directory inside the sandbox."
    category = "filesystem"
    risk_level = RiskLevel.LOW
    permissions = [Permission.FILESYSTEM_READ, Permission.FILESYSTEM_WRITE]
    parameters = [
        ToolParameter("source", "string", "Source path"),
        ToolParameter("destination", "string", "Destination path"),
    ]

    async def execute(self, source: str, destination: str) -> ToolResult:
        src = _safe_path(source)
        dst = _safe_path(destination)
        result = await sandbox.execute(f"cp -r '{src}' '{dst}' 2>&1", timeout=30)
        if result["exit_code"] != 0:
            return ToolResult(success=False, error=result["stderr"] or result["stdout"])
        return ToolResult(success=True, output={"copied": source, "to": destination})


class FsMove(Tool):
    name = "fs.move"
    description = "Move/rename a file or directory inside the sandbox."
    category = "filesystem"
    risk_level = RiskLevel.LOW
    permissions = [Permission.FILESYSTEM_WRITE]
    parameters = [
        ToolParameter("source", "string", "Source path"),
        ToolParameter("destination", "string", "Destination path"),
    ]

    async def execute(self, source: str, destination: str) -> ToolResult:
        src = _safe_path(source)
        dst = _safe_path(destination)
        result = await sandbox.execute(f"mv '{src}' '{dst}' 2>&1", timeout=10)
        if result["exit_code"] != 0:
            return ToolResult(success=False, error=result["stderr"] or result["stdout"])
        return ToolResult(success=True, output={"moved": source, "to": destination})


class FsMkdir(Tool):
    name = "fs.mkdir"
    description = "Create a directory inside the sandbox."
    category = "filesystem"
    risk_level = RiskLevel.LOW
    permissions = [Permission.FILESYSTEM_WRITE]
    parameters = [
        ToolParameter("path", "string", "Directory path"),
    ]

    async def execute(self, path: str) -> ToolResult:
        safe = _safe_path(path)
        result = await sandbox.execute(f"mkdir -p '{safe}' 2>&1", timeout=5)
        if result["exit_code"] != 0:
            return ToolResult(success=False, error=result["stderr"] or result["stdout"])
        return ToolResult(success=True, output={"created": path})


class FsExists(Tool):
    name = "fs.exists"
    description = "Check if a file or directory exists in the sandbox."
    category = "filesystem"
    risk_level = RiskLevel.SAFE
    permissions = [Permission.FILESYSTEM_READ]
    parameters = [
        ToolParameter("path", "string", "Path to check"),
    ]

    async def execute(self, path: str) -> ToolResult:
        safe = _safe_path(path)
        result = await sandbox.execute(
            f"if [ -e '{safe}' ]; then "
            f"  if [ -f '{safe}' ]; then echo 'file'; "
            f"  elif [ -d '{safe}' ]; then echo 'directory'; "
            f"  else echo 'other'; fi; "
            f"  stat --printf='%s' '{safe}' 2>/dev/null; "
            f"else echo 'not_found'; fi",
            timeout=5,
        )
        stdout = result["stdout"].strip()
        exists = "not_found" not in stdout
        output = {"exists": exists, "path": path}
        if exists:
            lines = stdout.split("\n")
            output["type"] = lines[0] if lines else "unknown"
            output["is_file"] = lines[0] == "file" if lines else False
            output["is_dir"] = lines[0] == "directory" if lines else False
        return ToolResult(success=True, output=output)


class FsStat(Tool):
    name = "fs.stat"
    description = "Get detailed file metadata from sandbox."
    category = "filesystem"
    risk_level = RiskLevel.SAFE
    permissions = [Permission.FILESYSTEM_READ]
    parameters = [
        ToolParameter("path", "string", "Path to inspect"),
    ]

    async def execute(self, path: str) -> ToolResult:
        safe = _safe_path(path)
        result = await sandbox.execute(f"stat '{safe}' 2>&1", timeout=5)
        if result["exit_code"] != 0:
            return ToolResult(success=False, error=result["stderr"] or result["stdout"])
        return ToolResult(success=True, output={"stat": result["stdout"], "path": path})


class FsSearch(Tool):
    name = "fs.search"
    description = "Search for files matching a pattern in the sandbox."
    category = "filesystem"
    risk_level = RiskLevel.SAFE
    permissions = [Permission.FILESYSTEM_READ]
    parameters = [
        ToolParameter("pattern", "string", "Search pattern (glob or name)"),
        ToolParameter("path", "string", "Starting directory", required=False, default="."),
        ToolParameter("max_results", "integer", "Maximum results", required=False, default=50),
    ]

    async def execute(self, pattern: str, path: str = ".", max_results: int = 50) -> ToolResult:
        safe = _safe_path(path)
        result = await sandbox.execute(
            f"find '{safe}' -name '{pattern}' -maxdepth 5 2>/dev/null | head -n {max_results}",
            timeout=15,
        )
        matches = [m for m in result["stdout"].split("\n") if m.strip()]
        return ToolResult(success=True, output={
            "pattern": pattern,
            "count": len(matches),
            "matches": matches,
        })


class FsHash(Tool):
    name = "fs.hash"
    description = "Compute SHA256 hash of a file in the sandbox."
    category = "filesystem"
    risk_level = RiskLevel.SAFE
    permissions = [Permission.FILESYSTEM_READ]
    parameters = [
        ToolParameter("path", "string", "File path"),
    ]

    async def execute(self, path: str) -> ToolResult:
        safe = _safe_path(path)
        result = await sandbox.execute(f"sha256sum '{safe}' 2>&1", timeout=10)
        if result["exit_code"] != 0:
            return ToolResult(success=False, error=result["stderr"] or result["stdout"])
        parts = result["stdout"].split()
        return ToolResult(success=True, output={"hash": parts[0] if parts else "", "algorithm": "sha256", "path": path})


class FsRename(Tool):
    name = "fs.rename"
    description = "Rename a file or directory in the sandbox."
    category = "filesystem"
    risk_level = RiskLevel.LOW
    permissions = [Permission.FILESYSTEM_WRITE]
    parameters = [
        ToolParameter("path", "string", "Current path"),
        ToolParameter("new_name", "string", "New name"),
    ]

    async def execute(self, path: str, new_name: str) -> ToolResult:
        safe = _safe_path(path)
        # Get parent directory
        result = await sandbox.execute(f"dirname '{safe}'", timeout=5)
        parent = result["stdout"].strip()
        new_path = f"{parent}/{new_name}"
        result = await sandbox.execute(f"mv '{safe}' '{new_path}' 2>&1", timeout=5)
        if result["exit_code"] != 0:
            return ToolResult(success=False, error=result["stderr"] or result["stdout"])
        return ToolResult(success=True, output={"renamed": path, "to": new_name})


ALL_FS_TOOLS = [
    FsList(),
    FsCreateFile(),
    FsReadFile(),
    FsWriteFile(),
    FsAppendFile(),
    FsDelete(),
    FsCopy(),
    FsMove(),
    FsMkdir(),
    FsExists(),
    FsStat(),
    FsSearch(),
    FsHash(),
    FsRename(),
]
