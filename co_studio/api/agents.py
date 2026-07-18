"""REST endpoints for agent CRUD, lifecycle, QR, and diagnostics."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .. import config, creator, diagnostics, identity, logs, registry
from ..registry import AgentMeta
from ..supervisor import SUPERVISOR

router = APIRouter(prefix="/agents", tags=["agents"])


class CreateAgentBody(BaseModel):
    """POST /api/agents payload."""

    name: str = Field(min_length=1, max_length=80)
    model: str = "co/gemini-2.5-flash"
    toolkits: list[str] = ["utility"]
    trust: str = "open"


def summarize(meta: AgentMeta) -> dict[str, object]:
    """AgentSummary per the API contract."""
    return {
        "slug": meta.slug,
        "name": meta.name,
        "address": meta.address,
        "port": meta.port,
        "model": meta.model,
        "toolkits": meta.toolkits,
        "trust": meta.trust,
        "state": SUPERVISOR.state_of(meta.slug),
        "created_at": meta.created_at,
    }


def detail(meta: AgentMeta) -> dict[str, object]:
    """AgentDetail per the API contract (summary + paths + runtime signals)."""
    agent_dir = registry.agent_dir(meta.slug)
    endpoints, relay = logs.parse_runtime_signals(agent_dir / config.STDOUT_LOG_NAME)
    return {
        **summarize(meta),
        "script_path": str(agent_dir / "agent.py"),
        "co_dir": str(agent_dir / ".co"),
        "endpoints_announced": endpoints,
        "relay_ok": relay,
        "last_error": SUPERVISOR.last_error_of(meta.slug),
    }


def _get_meta(slug: str) -> AgentMeta:
    """Load meta or raise 404."""
    meta = registry.load(slug)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"no agent named '{slug}'")
    return meta


@router.get("")
def list_agents() -> dict[str, object]:
    """GET /api/agents."""
    return {"agents": [summarize(meta) for meta in registry.load_all()]}


@router.post("")
def create_agent(body: CreateAgentBody) -> dict[str, object]:
    """Create identity + QR-ready agent directory; does NOT start the process."""
    try:
        meta = creator.create(body.name, body.model, body.toolkits, body.trust)
    except ValueError as exc:  # unknown toolkit or trust level
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:  # port range exhausted
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return detail(meta)


@router.get("/{slug}")
def get_agent(slug: str) -> dict[str, object]:
    """GET /api/agents/{slug}."""
    return detail(_get_meta(slug))


class RenameBody(BaseModel):
    """POST /api/agents/{slug}/rename payload."""

    name: str = Field(min_length=1, max_length=80)


@router.post("/{slug}/rename")
def rename_agent(slug: str, body: RenameBody) -> dict[str, object]:
    """Rename an agent: update meta.json AND re-render agent.py so the name it advertises
    matches (keeps its slug, identity, port, and folder). Restart to apply to a live process."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name must not be blank")
    with registry.locked():
        meta = _get_meta(slug)
        meta.name = name
        registry.save(meta)
        agent_dir = registry.agent_dir(slug)
        (agent_dir / "agent.py").write_text(
            creator.render(name, meta.model, meta.port, meta.toolkits, meta.trust)
        )
    return summarize(meta)


@router.post("/{slug}/start")
async def start_agent(slug: str) -> dict[str, str]:
    """Spawn the agent process."""
    return {"state": await SUPERVISOR.start(_get_meta(slug))}


@router.post("/{slug}/stop")
async def stop_agent(slug: str) -> dict[str, str]:
    """Terminate the agent process group."""
    _get_meta(slug)
    return {"state": await SUPERVISOR.stop(slug)}


@router.post("/{slug}/restart")
async def restart_agent(slug: str) -> dict[str, str]:
    """Stop then start the agent."""
    return {"state": await SUPERVISOR.restart(_get_meta(slug))}


@router.delete("/{slug}", status_code=204)
async def delete_agent(slug: str) -> Response:
    """Stop the agent and permanently delete its directory (identity, keys, logs)."""
    _get_meta(slug)
    await SUPERVISOR.stop(slug)
    SUPERVISOR.forget(slug)
    with registry.locked():
        registry.delete(slug)
    return Response(status_code=204)


@router.get("/{slug}/qr.svg")
def agent_qr(slug: str) -> Response:
    """SVG QR of the bare 0x address for the iOS scan-to-add flow."""
    meta = _get_meta(slug)
    return Response(content=identity.qr_svg(meta.address), media_type="image/svg+xml")


@router.get("/{slug}/diagnostics")
def agent_diagnostics(slug: str) -> PlainTextResponse:
    """The Copy-for-Claude markdown bundle."""
    return PlainTextResponse(diagnostics.build(_get_meta(slug)), media_type="text/markdown")
