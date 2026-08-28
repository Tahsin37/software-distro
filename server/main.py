"""
Main FastAPI server — entry point for the AI Computer Platform backend.
Registers routes, WebSocket, event bus, tool registration, sandbox init, and database init.
"""
import asyncio
import json
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from events import event_bus, Event, EventType
from tools.registry import registry
from sandbox.wsl2 import sandbox

# Import tool modules
from tools.filesystem.tools import ALL_FS_TOOLS
from tools.terminal.tools import ALL_TERMINAL_TOOLS
from tools.process.tools import ALL_PROCESS_TOOLS
from tools.git.tools import ALL_GIT_TOOLS
from tools.system.tools import ALL_SYSTEM_TOOLS

# Import API routers
from api.tasks import router as tasks_router
from api.tools import router as tools_router
from api.settings import router as settings_router


def register_all_tools():
    """Register all available tools."""
    all_tools = ALL_FS_TOOLS + ALL_TERMINAL_TOOLS + ALL_PROCESS_TOOLS + ALL_GIT_TOOLS + ALL_SYSTEM_TOOLS
    for tool in all_tools:
        registry.register(tool)

    print(f"[Tools] Registered {registry.tool_count} tools in {len(registry.get_categories())} categories")
    for cat in registry.get_categories():
        tools = registry.list_by_category(cat)
        print(f"  [{cat}] {len(tools)} tools: {', '.join(t['name'] for t in tools)}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    # Startup
    print(f"[Platform] Starting AI Computer Platform")
    print(f"[Platform] Database: {settings.database_path}")
    print(f"[Platform] Host access policy: ALL DENIED")

    settings.ensure_directories()
    await init_db()
    register_all_tools()

    # Initialize sandbox
    print(f"[Sandbox] Detecting sandbox environment...")
    detection = await sandbox.detect()
    if detection.get("distro_exists"):
        print(f"[Sandbox] WSL2 distro '{sandbox.DISTRO_NAME}' found")
        info = await sandbox.initialize()
        if info.error:
            print(f"[Sandbox] WARNING: {info.error}")
        else:
            print(f"[Sandbox] Initialized: {info.name} ({info.distro}) — workspace: {info.workspace}")
    else:
        print(f"[Sandbox] WARNING: WSL2 distro '{sandbox.DISTRO_NAME}' not installed.")
        print(f"[Sandbox] Run: wsl --install {sandbox.DISTRO_NAME}")

    print(f"[Platform] Server ready at http://{settings.host}:{settings.port}")

    yield

    # Shutdown
    print("[Platform] Shutting down...")


app = FastAPI(
    title="AI Computer Platform",
    description="Local autonomous AI computer platform with WSL2 sandbox isolation",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(tasks_router)
app.include_router(tools_router)
app.include_router(settings_router)


@app.get("/api/health")
async def health():
    """Health check — reports sandbox info, never host info."""
    sandbox_status = await sandbox.status()
    return {
        "status": "ok",
        "version": "0.2.0",
        "tools": registry.tool_count,
        "categories": registry.get_categories(),
        "sandbox": {
            "status": sandbox_status.get("status", "unknown"),
            "distro": sandbox_status.get("distro"),
        },
        "host_access": "DENIED",
        "timestamp": time.time(),
    }


@app.get("/api/events/history")
async def event_history(event_type: str = None, limit: int = 100):
    """Get event history."""
    return {"events": event_bus.get_history(event_type, limit)}


@app.websocket("/api/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time events."""
    await ws.accept()
    event_bus.add_ws_connection(ws)
    print(f"[WS] Client connected")

    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type")
                if msg_type == "ping":
                    await ws.send_text(json.dumps({"type": "pong", "timestamp": time.time()}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        print(f"[WS] Client disconnected")
    finally:
        event_bus.remove_ws_connection(ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        reload_dirs=[str(settings.project_root / "server")],
    )
