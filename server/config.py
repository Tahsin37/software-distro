"""
Configuration management for the AI Computer Platform.
Uses pydantic-settings for environment variable support.

SECURITY NOTE: This config is for the CONTROL PLANE only.
Agent tools never access these settings directly — they use the sandbox.
"""
from pathlib import Path
from enum import Enum
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class NetworkPolicy(str, Enum):
    OFFLINE = "offline"
    ALLOWLIST = "allowlist"
    RESTRICTED = "restricted"
    NORMAL = "normal"


class RiskLevel(str, Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PermissionPolicy(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = True

    # Paths (control plane only — NOT exposed to agent)
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent)
    database_path: Path = Field(default_factory=lambda: Path(__file__).parent / "data" / "platform.db")

    # LLM (default to Ollama)
    llm_provider: str = "ollama"
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:7b"
    llm_temperature: float = 0.1
    llm_context_size: int = 8192
    llm_max_output: int = 4096
    llm_timeout: int = 120

    # Sandbox
    sandbox_provider: str = "wsl2"
    sandbox_distro: str = "Ubuntu-24.04"
    network_policy: NetworkPolicy = NetworkPolicy.NORMAL
    max_process_count: int = 50
    max_file_size_mb: int = 100
    max_disk_usage_mb: int = 5000
    command_timeout: int = 300
    max_concurrent_tools: int = 5

    # Host Access Policy — ALL DENY by default
    host_filesystem_policy: PermissionPolicy = PermissionPolicy.DENY
    host_terminal_policy: PermissionPolicy = PermissionPolicy.DENY
    host_process_policy: PermissionPolicy = PermissionPolicy.DENY
    host_registry_policy: PermissionPolicy = PermissionPolicy.DENY
    host_environment_policy: PermissionPolicy = PermissionPolicy.DENY
    host_hardware_policy: PermissionPolicy = PermissionPolicy.DENY

    # Sandbox permissions (what the agent CAN do inside sandbox)
    sandbox_filesystem_policy: PermissionPolicy = PermissionPolicy.ALLOW
    sandbox_terminal_policy: PermissionPolicy = PermissionPolicy.ALLOW
    sandbox_browser_policy: PermissionPolicy = PermissionPolicy.ALLOW
    sandbox_network_policy: PermissionPolicy = PermissionPolicy.ALLOW
    sandbox_process_policy: PermissionPolicy = PermissionPolicy.ALLOW

    # Agent
    max_agent_steps: int = 100
    max_retries: int = 3
    verification_enabled: bool = True

    model_config = {"env_prefix": "ACP_", "env_file": ".env"}

    def ensure_directories(self):
        """Create required directories if they don't exist."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
