"""
Tool execution engine — async, concurrent, with cancellation and streaming.
"""
import asyncio
import time
import uuid
import json
from typing import Optional, Callable, Any
from tools.base import Tool, ToolResult, ToolStatus
from tools.registry import registry
from events import event_bus, Event, EventType
from database import Database


class ToolExecution:
    """Represents a single tool execution with state tracking."""

    def __init__(self, tool_name: str, args: dict, task_id: Optional[str] = None):
        self.id = str(uuid.uuid4())
        self.tool_name = tool_name
        self.args = args
        self.task_id = task_id
        self.status = ToolStatus.PENDING
        self.result: Optional[ToolResult] = None
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self._task: Optional[asyncio.Task] = None


class ToolEngine:
    """Manages tool execution with concurrency control, streaming, and telemetry."""

    def __init__(self, max_concurrent: int = 5):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active: dict[str, ToolExecution] = {}
        self._history: list[dict] = []

    async def execute(
        self,
        tool_name: str,
        args: dict,
        task_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> ToolResult:
        """Execute a tool and return the result."""
        tool = registry.get(tool_name)
        if not tool:
            return ToolResult(success=False, error=f"Unknown tool: {tool_name}")

        execution = ToolExecution(tool_name, args, task_id)
        self._active[execution.id] = execution

        # Emit start event
        await event_bus.emit(Event(
            type=EventType.TOOL_STARTED,
            data={"execution_id": execution.id, "tool": tool_name, "args": _sanitize_args(args)},
            task_id=task_id,
        ))

        # Store in database
        await Database.insert("tool_calls", {
            "id": execution.id,
            "task_id": task_id,
            "tool_name": tool_name,
            "input": json.dumps(args, default=str),
            "status": "running",
            "started_at": time.time(),
        })

        tool_timeout = timeout or tool.timeout

        try:
            async with self._semaphore:
                execution.status = ToolStatus.RUNNING
                execution.started_at = time.time()

                result = await asyncio.wait_for(
                    tool.safe_execute(**args),
                    timeout=tool_timeout,
                )

                execution.status = ToolStatus.COMPLETED
                execution.result = result
                execution.completed_at = time.time()

        except asyncio.TimeoutError:
            result = ToolResult(
                success=False,
                error=f"Tool {tool_name} timed out after {tool_timeout}s",
                duration_ms=tool_timeout * 1000,
            )
            execution.status = ToolStatus.TIMEOUT
            execution.result = result
            execution.completed_at = time.time()

        except asyncio.CancelledError:
            result = ToolResult(success=False, error="Tool execution cancelled")
            execution.status = ToolStatus.CANCELLED
            execution.result = result
            execution.completed_at = time.time()

        except Exception as e:
            result = ToolResult(success=False, error=f"{type(e).__name__}: {str(e)}")
            execution.status = ToolStatus.FAILED
            execution.result = result
            execution.completed_at = time.time()

        # Calculate duration
        duration_ms = (execution.completed_at - execution.started_at) * 1000 if execution.started_at and execution.completed_at else 0

        # Emit completion/failure event
        event_type = EventType.TOOL_COMPLETED if result.success else EventType.TOOL_FAILED
        await event_bus.emit(Event(
            type=event_type,
            data={
                "execution_id": execution.id,
                "tool": tool_name,
                "success": result.success,
                "duration_ms": duration_ms,
                "output_preview": _truncate(str(result.output), 500) if result.output else None,
                "error": result.error,
            },
            task_id=task_id,
        ))

        # Update database
        await Database.update("tool_calls", {
            "status": execution.status.value,
            "output": json.dumps(result.to_dict(), default=str),
            "completed_at": time.time(),
            "duration_ms": duration_ms,
            "error": result.error,
        }, "id = ?", (execution.id,))

        # Move to history
        del self._active[execution.id]

        return result

    async def execute_parallel(
        self,
        calls: list[tuple[str, dict]],
        task_id: Optional[str] = None,
    ) -> list[ToolResult]:
        """Execute multiple independent tool calls concurrently."""
        tasks = [
            self.execute(name, args, task_id)
            for name, args in calls
        ]
        return await asyncio.gather(*tasks)

    def cancel(self, execution_id: str) -> bool:
        """Cancel a running tool execution."""
        execution = self._active.get(execution_id)
        if execution and execution._task:
            execution._task.cancel()
            return True
        return False

    def get_active(self) -> list[dict]:
        """Get currently active executions."""
        return [
            {
                "id": e.id,
                "tool": e.tool_name,
                "status": e.status.value,
                "started_at": e.started_at,
                "task_id": e.task_id,
            }
            for e in self._active.values()
        ]


def _sanitize_args(args: dict) -> dict:
    """Sanitize arguments for logging (truncate large values)."""
    sanitized = {}
    for k, v in args.items():
        if isinstance(v, str) and len(v) > 1000:
            sanitized[k] = v[:200] + f"... ({len(v)} chars)"
        elif isinstance(v, bytes):
            sanitized[k] = f"<binary {len(v)} bytes>"
        else:
            sanitized[k] = v
    return sanitized


def _truncate(s: str, max_len: int) -> str:
    if len(s) <= max_len:
        return s
    return s[:max_len] + "..."


# Global engine instance
tool_engine = ToolEngine()
