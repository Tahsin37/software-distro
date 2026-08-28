"""
Base types for the tool system.
Every tool implements ToolDefinition and returns ToolResult.
"""
import time
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class RiskLevel(str, Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class Permission(str, Enum):
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    PROCESS_CREATE = "process.create"
    PROCESS_KILL = "process.kill"
    NETWORK_ACCESS = "network.access"
    BROWSER_ACCESS = "browser.access"
    SYSTEM_READ = "system.read"
    SYSTEM_WRITE = "system.write"
    SCREEN_CAPTURE = "screen.capture"
    INPUT_CONTROL = "input.control"
    HOST_ACCESS = "host.access"


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }

    def to_llm_string(self) -> str:
        """Format result for LLM consumption - concise and useful."""
        if self.success:
            if isinstance(self.output, str):
                return self.output
            return json.dumps(self.output, indent=2, default=str)
        else:
            return f"Error: {self.error}"


@dataclass
class ToolParameter:
    """Schema for a single tool parameter."""
    name: str
    type: str  # string, integer, number, boolean, array, object
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[list] = None

    def to_schema(self) -> dict:
        schema: dict = {"type": self.type, "description": self.description}
        if self.enum:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        return schema


class Tool(ABC):
    """Base class for all tools."""

    name: str
    description: str
    category: str
    parameters: list[ToolParameter]
    risk_level: RiskLevel = RiskLevel.SAFE
    permissions: list[Permission] = []
    version: str = "1.0.0"
    timeout: int = 60  # seconds

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with the given arguments."""
        ...

    def get_input_schema(self) -> dict:
        """Generate JSON Schema for tool input."""
        properties = {}
        required = []
        for param in self.parameters:
            properties[param.name] = param.to_schema()
            if param.required:
                required.append(param.name)
        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    def to_openai_tool(self) -> dict:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_input_schema(),
            },
        }

    def validate_input(self, kwargs: dict) -> Optional[str]:
        """Basic input validation. Returns error message or None."""
        for param in self.parameters:
            if param.required and param.name not in kwargs:
                return f"Missing required parameter: {param.name}"
            if param.name in kwargs and param.enum:
                if kwargs[param.name] not in param.enum:
                    return f"Invalid value for {param.name}: {kwargs[param.name]}. Must be one of: {param.enum}"
        return None

    async def safe_execute(self, **kwargs) -> ToolResult:
        """Execute with validation, timing, and error handling."""
        # Validate input
        error = self.validate_input(kwargs)
        if error:
            return ToolResult(success=False, error=error)

        # Apply defaults
        for param in self.parameters:
            if param.name not in kwargs and param.default is not None:
                kwargs[param.name] = param.default

        start = time.time()
        try:
            result = await self.execute(**kwargs)
            result.duration_ms = (time.time() - start) * 1000
            return result
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"Tool {self.name} timed out after {self.timeout}s",
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"{type(e).__name__}: {str(e)}",
                duration_ms=(time.time() - start) * 1000,
            )


import asyncio
