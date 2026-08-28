"""
Settings API — provider configuration, host access policy, sandbox management.
API keys are NEVER returned in API responses. Only masked versions shown.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from llm.manager import llm_manager, PROVIDER_PRESETS
from sandbox.wsl2 import sandbox
from secret_store import secret_store

router = APIRouter(prefix="/api/settings", tags=["settings"])


class LLMSettingsUpdate(BaseModel):
    provider: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    context_size: Optional[int] = None
    max_output: Optional[int] = None
    timeout: Optional[int] = None
    api_key: Optional[str] = None  # Only used for updates, never returned


class HostAccessPolicy(BaseModel):
    filesystem: str = "DENY"
    terminal: str = "DENY"
    powershell: str = "DENY"
    process_inspection: str = "DENY"
    registry: str = "DENY"
    environment: str = "DENY"
    hardware_telemetry: str = "DENY"
    browser: str = "DENY"
    applications: str = "DENY"


# ── LLM Settings ──

@router.get("/llm")
async def get_llm_settings():
    """Get LLM config. API key is NEVER included — only masked version."""
    return llm_manager.get_config_safe()


@router.put("/llm")
async def update_llm_settings(update: LLMSettingsUpdate):
    """Update LLM config. API key stored encrypted, never returned."""
    kwargs = {k: v for k, v in update.model_dump().items() if v is not None}
    return llm_manager.update_config(**kwargs)


@router.post("/llm/test")
async def test_llm():
    """Test LLM provider connection."""
    return await llm_manager.test()


@router.get("/llm/models")
async def list_models():
    """List available models from the provider."""
    try:
        models = await llm_manager.list_models()
        return {"models": models}
    except Exception as e:
        return {"models": [], "error": str(e)}


@router.post("/llm/preset/{preset_name}")
async def apply_preset(preset_name: str):
    """Apply a provider preset (ollama, openrouter, openai, custom)."""
    try:
        config = llm_manager.apply_preset(preset_name)
        return {"applied": preset_name, "config": config}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/llm/presets")
async def get_presets():
    """Get available provider presets."""
    return {"presets": llm_manager.get_presets()}


# ── API Key Management ──

@router.post("/llm/api-key")
async def set_api_key(data: dict):
    """Set API key for a provider. Stored encrypted, never returned."""
    provider = data.get("provider", llm_manager.config.provider)
    api_key = data.get("api_key", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="API key required")
    secret_store.set(f"llm_api_key_{provider}", api_key)
    # Force provider recreation
    llm_manager.update_config()
    return {"stored": True, "provider": provider, "masked": secret_store.mask(api_key)}


@router.delete("/llm/api-key/{provider}")
async def delete_api_key(provider: str):
    """Delete stored API key for a provider."""
    secret_store.delete(f"llm_api_key_{provider}")
    return {"deleted": True, "provider": provider}


@router.get("/llm/api-key-status")
async def api_key_status():
    """Check which providers have API keys stored."""
    statuses = {}
    for name in PROVIDER_PRESETS:
        key = f"llm_api_key_{name}"
        statuses[name] = {
            "has_key": secret_store.has(key),
            "masked": secret_store.mask(secret_store.get(key, "")) if secret_store.has(key) else None,
        }
    return {"providers": statuses}


# ── Host Access Policy ──

@router.get("/host-policy")
async def get_host_policy():
    """Get host access policy. Default: ALL DENIED."""
    return HostAccessPolicy().model_dump()


# ── Sandbox Management ──

@router.get("/sandbox")
async def get_sandbox_status():
    """Get sandbox status and system info (SANDBOX info, never host info)."""
    return await sandbox.status()


@router.post("/sandbox/detect")
async def detect_sandbox():
    """Detect sandbox capabilities."""
    return await sandbox.detect()


@router.post("/sandbox/initialize")
async def initialize_sandbox():
    """Initialize the sandbox environment."""
    info = await sandbox.initialize()
    return {
        "id": info.id,
        "name": info.name,
        "distro": info.distro,
        "status": info.status.value,
        "workspace": info.workspace,
        "error": info.error,
    }


@router.post("/sandbox/reset")
async def reset_sandbox():
    """Reset sandbox workspace to clean state."""
    return await sandbox.reset()


@router.post("/sandbox/stop")
async def stop_sandbox():
    """Stop the sandbox."""
    return await sandbox.stop()


@router.post("/sandbox/restart")
async def restart_sandbox():
    """Restart the sandbox."""
    return await sandbox.restart()
