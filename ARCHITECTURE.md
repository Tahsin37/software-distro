# Architecture — Autonomous AI Computer Platform

## Overview

A local-first autonomous AI computer platform where a local LLM operates a sandbox computer through real tools. The AI can perform ordinary software-based computer work: creating files, running programs, browsing the web, manipulating documents, debugging code, and more.

## Environment

- **OS**: Windows 11 Pro x64
- **RAM**: 16GB
- **GPU**: Intel UHD 630 (integrated)
- **Node.js**: v22.19.0
- **Python**: 3.13.1
- **Git**: 2.52.0
- **Browser**: Chrome
- **Docker**: Not available
- **FFmpeg**: Not available

## Stack

| Layer | Technology | Rationale |
|---|---|---|
| Backend API | Python 3.13 + FastAPI | Async, WebSocket native, excellent ecosystem for automation |
| Frontend | React 19 + TypeScript + Vite + Tailwind CSS | Fast DX, premium UI, type safety |
| Component Library | shadcn/ui (Radix primitives) | Zero-dependency, customizable, developer-focused |
| State Management | Zustand | Lightweight, TypeScript-native |
| Database | SQLite via aiosqlite | Zero config, local-first, migration-ready |
| Real-time | WebSocket (FastAPI native) | Bidirectional, low latency |
| Browser Automation | Playwright (Python) | Headful Chrome, robust automation |
| Desktop Automation | pyautogui + win32api + mss | Screen capture, mouse/keyboard, window management |
| Process Management | psutil | Cross-platform process inspection/control |
| Image Processing | Pillow | Already installed, comprehensive |
| LLM | Provider abstraction | Ollama, OpenAI-compatible, local HTTP |

## Sandbox Strategy

Docker is not available. The sandbox uses **process-level isolation with filesystem boundaries**:

1. **Filesystem boundary**: All tool operations confined to `sandbox_root/` directory
2. **Process monitoring**: psutil tracks spawned processes, enforces limits
3. **Network policy**: Application-layer enforcement (allowlist/blocklist)
4. **Resource limits**: Configurable CPU time, memory, disk quotas
5. **Abstraction layer**: `SandboxProvider` interface designed for future Docker/Hyper-V providers

This is **soft isolation** — it relies on application-level enforcement, not OS containers. The architecture ensures that adding Docker later requires only a new provider implementation, not a rewrite.

## Data Flow

```
User (Browser)
    │
    ▼
React Frontend ◄──WebSocket──► FastAPI Backend
    │                              │
    │                              ├── Agent Runtime
    │                              │   ├── Planner
    │                              │   ├── Executor
    │                              │   ├── Observer
    │                              │   ├── Verifier
    │                              │   └── Recovery
    │                              │
    │                              ├── LLM Layer
    │                              │   ├── OllamaProvider
    │                              │   ├── OpenAICompatProvider
    │                              │   └── LocalHTTPProvider
    │                              │
    │                              ├── Tool Runtime
    │                              │   ├── Registry
    │                              │   ├── Engine (async, concurrent)
    │                              │   └── 30+ tool categories
    │                              │
    │                              ├── Sandbox Manager
    │                              │   └── ProcessSandbox
    │                              │
    │                              └── SQLite Database
    │
    ▼
Sandbox Root (filesystem boundary)
```

## Security Model

- **Filesystem**: Tools operate only within `sandbox_root/`. Path traversal blocked.
- **Process**: Spawned processes tracked. Orphan cleanup on shutdown.
- **Network**: Configurable policy (offline/allowlist/restricted/normal).
- **Permissions**: Every tool has a risk level (SAFE/LOW/MEDIUM/HIGH).
- **Audit**: All tool calls logged with arguments, duration, results.
- **External content**: Treated as untrusted. Never elevated to system instructions.
- **Host protection**: No tool can access host filesystem outside sandbox boundary.
