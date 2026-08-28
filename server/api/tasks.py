"""
Task API routes — create, list, cancel, retry tasks.
"""
import uuid
import asyncio
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from agent.agent import agent
from database import Database
from events import event_bus, Event, EventType

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class CreateTaskRequest(BaseModel):
    message: str
    title: Optional[str] = None


class TaskResponse(BaseModel):
    id: str
    title: str
    status: str
    created_at: float
    message: Optional[str] = None


@router.post("", response_model=TaskResponse)
async def create_task(request: CreateTaskRequest):
    """Create and start a new task."""
    task_id = str(uuid.uuid4())
    title = request.title or request.message[:100]

    # Start agent in background
    asyncio.create_task(agent.run_task(task_id, request.message, title))

    return TaskResponse(
        id=task_id,
        title=title,
        status="running",
        created_at=time.time(),
        message=request.message,
    )


@router.get("")
async def list_tasks(limit: int = 50, status: Optional[str] = None):
    """List all tasks."""
    if status:
        tasks = await Database.fetch_all(
            "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit),
        )
    else:
        tasks = await Database.fetch_all(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
    return {"tasks": tasks}


@router.get("/{task_id}")
async def get_task(task_id: str):
    """Get a specific task with its events and messages."""
    task = await Database.fetch_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    messages = await Database.fetch_all(
        "SELECT * FROM messages WHERE task_id = ? ORDER BY timestamp",
        (task_id,),
    )
    tool_calls = await Database.fetch_all(
        "SELECT * FROM tool_calls WHERE task_id = ? ORDER BY started_at",
        (task_id,),
    )

    return {
        "task": task,
        "messages": messages,
        "tool_calls": tool_calls,
    }


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task."""
    agent.cancel_task(task_id)
    return {"cancelled": True, "task_id": task_id}


@router.post("/{task_id}/retry")
async def retry_task(task_id: str):
    """Retry a failed task."""
    task = await Database.fetch_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    new_task_id = str(uuid.uuid4())
    asyncio.create_task(agent.run_task(new_task_id, task["description"], task["title"]))

    return {"new_task_id": new_task_id, "original_task_id": task_id}
