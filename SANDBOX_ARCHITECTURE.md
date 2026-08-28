# Sandbox Architecture

## Decision: WSL2-based Linux Sandbox

### Available Technologies (Detected)

| Technology | Available | Strength | Decision |
|---|---|---|---|
| WSL2 | ✅ Yes (v2.5.9, kernel 6.6.87) | Strong — full Linux kernel, separate filesystem, process namespace | **SELECTED** |
| Hyper-V | ✅ Present | Full VM — strongest, but heavy for this use case | Available as future option |
| Docker Desktop | ❌ CLI not in PATH | Container isolation | Unavailable |
| Windows Sandbox | ❓ Requires elevation to check | Disposable Windows VM | Cannot verify |
| VirtualBox/VMware | ❌ Not installed | Full VM | Unavailable |

### Architecture

```
WINDOWS HOST (protected — never exposed to agent)
       │
       │ Control plane only
       ▼
┌─────────────────────────────────────────────┐
│  FastAPI Backend (Windows)                   │
│  ├── API Server                              │
│  ├── WebSocket Events                        │
│  ├── LLM Manager (API keys encrypted)        │
│  ├── Tool Engine                             │
│  └── Sandbox Manager                         │
│         │                                    │
│         │ wsl.exe -d Ubuntu-24.04            │
│         │ (process boundary)                 │
│         ▼                                    │
│  ┌───────────────────────────────────┐       │
│  │  WSL2 SANDBOX (Ubuntu 24.04)      │       │
│  │  ├── User: agent                  │       │
│  │  ├── Workspace: /home/agent/work  │       │
│  │  ├── bash terminal                │       │
│  │  ├── python3                      │       │
│  │  ├── git                          │       │
│  │  ├── sqlite3                      │       │
│  │  ├── curl/wget                    │       │
│  │  ├── node.js (if installed)       │       │
│  │  └── Playwright (if installed)    │       │
│  │                                   │       │
│  │  /mnt automount: DISABLED         │       │
│  │  Windows interop: DISABLED        │       │
│  │  Windows PATH append: DISABLED    │       │
│  └───────────────────────────────────┘       │
│                                              │
├─────────────────────────────────────────────┤
│  React Frontend (localhost:5173)             │
│  └── Connects to backend via WebSocket       │
└─────────────────────────────────────────────┘
```

### Security Properties

| Property | Enforcement |
|---|---|
| Host filesystem access | DENIED — /mnt automount disabled in wsl.conf |
| Windows .exe execution | DENIED — interop disabled in wsl.conf |
| Host PATH visibility | DENIED — appendWindowsPath=false in wsl.conf |
| Host environment variables | DENIED — not passed to WSL commands |
| Host process visibility | DENIED — WSL2 has separate PID namespace |
| Agent user isolation | agent user created in sandbox, not root |
| Workspace scoping | All tool paths resolved to /home/agent/workspace/ |

### Lifecycle Operations

| Operation | Implementation |
|---|---|
| detect | Check `wsl --list` for distro |
| create | `wsl --install Ubuntu-24.04` |
| initialize | Create user, workspace, install essentials, configure wsl.conf |
| start | `wsl -d Ubuntu-24.04 -- echo started` |
| stop | `wsl --terminate Ubuntu-24.04` |
| reset | `rm -rf /home/agent/workspace/*` |
| status | Run system info commands inside sandbox |
| restart | terminate → start |

### Host Access Policy

Default: **ALL DENIED**

```json
{
  "host_filesystem": "DENY",
  "host_terminal": "DENY",
  "host_powershell": "DENY",
  "host_process_inspection": "DENY",
  "host_registry": "DENY",
  "host_environment": "DENY",
  "host_hardware_telemetry": "DENY",
  "host_browser": "DENY",
  "host_applications": "DENY"
}
```

### Limitations

1. WSL2 shares the Linux kernel with other WSL distros (not a full VM boundary)
2. WSL restart required for wsl.conf changes to take effect
3. WSL2 memory is shared with host (no hard memory limit by default)
4. Network is bridged — sandbox can access the internet
5. GUI apps require WSLg (available on this system)

### Future Improvements

1. Docker-based sandbox (when Docker available) for better disposability
2. Hyper-V VM for strongest isolation
3. Per-sandbox resource limits via WSL2 `.wslconfig`
4. Network policy enforcement at sandbox level
