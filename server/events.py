"""
Event bus for real-time communication between components.
Supports WebSocket broadcast and event history.
"""
import asyncio
import json
import time
from typing import Any, Callable, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


class EventType(str, Enum):
    # Task events
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"

    # Tool events
    TOOL_STARTED = "tool.started"
    TOOL_OUTPUT = "tool.output"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"

    # Agent events
    AGENT_STATE_CHANGED = "agent.state_changed"
    AGENT_THINKING = "agent.thinking"
    AGENT_MESSAGE = "agent.message"

    # Sandbox events
    SANDBOX_STARTED = "sandbox.started"
    SANDBOX_STOPPED = "sandbox.stopped"
    SANDBOX_RESET = "sandbox.reset"

    # System events
    SCREEN_UPDATED = "screen.updated"
    FILE_CHANGED = "file.changed"
    PROCESS_STARTED = "process.started"
    PROCESS_EXITED = "process.exited"
    BROWSER_CHANGED = "browser.changed"
    VERIFICATION_STARTED = "verification.started"
    VERIFICATION_COMPLETED = "verification.completed"
    LOG = "log"
    ERROR = "error"


@dataclass
class Event:
    type: EventType
    data: dict = field(default_factory=dict)
    task_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "data": self.data,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class EventBus:
    """Central event bus for the platform."""

    def __init__(self, max_history: int = 1000):
        self._subscribers: dict[str, list[Callable]] = {}
        self._global_subscribers: list[Callable] = []
        self._history: list[Event] = []
        self._max_history = max_history
        self._ws_connections: list = []

    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def subscribe_all(self, callback: Callable):
        """Subscribe to all events."""
        self._global_subscribers.append(callback)

    def add_ws_connection(self, ws):
        """Register a WebSocket connection for broadcast."""
        self._ws_connections.append(ws)

    def remove_ws_connection(self, ws):
        """Unregister a WebSocket connection."""
        if ws in self._ws_connections:
            self._ws_connections.remove(ws)

    async def emit(self, event: Event):
        """Emit an event to all subscribers and WebSocket connections."""
        # Store in history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # Notify specific subscribers
        event_type = event.type.value if isinstance(event.type, EventType) else event.type
        for callback in self._subscribers.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                print(f"Event subscriber error: {e}")

        # Notify global subscribers
        for callback in self._global_subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                print(f"Global subscriber error: {e}")

        # Broadcast to WebSocket connections
        message = event.to_json()
        dead_connections = []
        for ws in self._ws_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead_connections.append(ws)

        # Cleanup dead connections
        for ws in dead_connections:
            self.remove_ws_connection(ws)

    def get_history(self, event_type: Optional[str] = None, limit: int = 100) -> list[dict]:
        """Get event history, optionally filtered by type."""
        events = self._history
        if event_type:
            events = [e for e in events if (e.type.value if isinstance(e.type, EventType) else e.type) == event_type]
        return [e.to_dict() for e in events[-limit:]]


# Global event bus instance
event_bus = EventBus()
