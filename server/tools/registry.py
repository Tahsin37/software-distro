"""
Tool registry — discovers, registers, and provides tools to the agent and API.
"""
import importlib
import pkgutil
from typing import Optional
from tools.base import Tool, RiskLevel


class ToolRegistry:
    """Central registry for all tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._categories: dict[str, list[str]] = {}

    def register(self, tool: Tool):
        """Register a tool instance."""
        self._tools[tool.name] = tool
        category = tool.category
        if category not in self._categories:
            self._categories[category] = []
        if tool.name not in self._categories[category]:
            self._categories[category].append(tool.name)

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_all(self) -> list[dict]:
        """List all registered tools with metadata."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "risk_level": t.risk_level.value,
                "version": t.version,
                "parameters": t.get_input_schema(),
            }
            for t in self._tools.values()
        ]

    def list_by_category(self, category: str) -> list[dict]:
        """List tools in a specific category."""
        names = self._categories.get(category, [])
        return [
            {
                "name": self._tools[n].name,
                "description": self._tools[n].description,
                "parameters": self._tools[n].get_input_schema(),
            }
            for n in names
            if n in self._tools
        ]

    def get_categories(self) -> list[str]:
        """Get all tool categories."""
        return list(self._categories.keys())

    def get_openai_tools(self, categories: Optional[list[str]] = None, max_risk: Optional[RiskLevel] = None) -> list[dict]:
        """Get tools in OpenAI function calling format, optionally filtered."""
        tools = list(self._tools.values())

        if categories:
            tools = [t for t in tools if t.category in categories]

        if max_risk:
            risk_order = [RiskLevel.SAFE, RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]
            max_idx = risk_order.index(max_risk)
            tools = [t for t in tools if risk_order.index(t.risk_level) <= max_idx]

        return [t.to_openai_tool() for t in tools]

    @property
    def tool_count(self) -> int:
        return len(self._tools)


# Global registry instance
registry = ToolRegistry()
