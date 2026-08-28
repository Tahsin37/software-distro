"""
Tool API routes — list tools, execute tools directly.
"""
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any
from tools.registry import registry
from tools.engine import tool_engine

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ExecuteToolRequest(BaseModel):
    args: dict = {}
    task_id: Optional[str] = None


@router.get("")
async def list_tools(category: Optional[str] = None):
    """List all registered tools."""
    if category:
        tools = registry.list_by_category(category)
    else:
        tools = registry.list_all()
    return {
        "tools": tools,
        "categories": registry.get_categories(),
        "total": len(tools),
    }


@router.get("/categories")
async def list_categories():
    """List tool categories."""
    return {"categories": registry.get_categories()}


@router.post("/{tool_name}/execute")
async def execute_tool(tool_name: str, request: ExecuteToolRequest):
    """Execute a specific tool."""
    tool = registry.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

    result = await tool_engine.execute(tool_name, request.args, request.task_id)
    return result.to_dict()


@router.get("/active")
async def get_active():
    """Get currently executing tools."""
    return {"active": tool_engine.get_active()}
