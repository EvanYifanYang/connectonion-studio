"""Create a new agent: slug, port, identity, key copy, rendered agent.py, meta.json."""

from __future__ import annotations

import datetime
import re
import shutil
import string

from . import config, identity, ports, registry
from .registry import AgentMeta
from .toolkits import HINTS, validate


DEFAULT_MODEL = "co/gemini-3.5-flash"


def slugify(name: str) -> str:
    """Lowercase, hyphenated, filesystem-safe slug ("Kitchen Sink!" → "kitchen-sink")."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "agent"


def _unique_slug(name: str) -> str:
    """First free slug derived from the name (kitchen-sink, kitchen-sink-2, ...)."""
    base = slugify(name)
    candidate, counter = base, 2
    while registry.agent_dir(candidate).exists():
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def _system_prompt(name: str, toolkits: list[str]) -> str:
    """Compose the agent's system prompt from its toolkit selection."""
    abilities = "; ".join(HINTS[t] for t in toolkits) or "plain conversation"
    return (
        f"You are {name}, a test agent created in ConnectOnion Studio to exercise the "
        f"ConnectOnion iOS client. You can help with: {abilities}. "
        "Use whichever tool fits the request. Keep replies short and friendly."
    )


TRUST_LEVELS = ("open", "careful", "strict")
PRESETS = ("custom", "co-ai")
DEFAULT_CO_AI_INVITE_CODE = "developer"
_INVITE_CODE_RE = re.compile(r"[A-Za-z0-9_-]{4,64}")


def validate_trust(trust: str) -> str:
    """Ensure the requested trust level is one host() understands."""
    if trust not in TRUST_LEVELS:
        raise ValueError(f"unknown trust level: {trust!r} (expected one of {', '.join(TRUST_LEVELS)})")
    return trust


def validate_preset(preset: str) -> str:
    """Ensure the requested Studio template is supported."""
    if preset not in PRESETS:
        raise ValueError(f"unknown preset: {preset!r} (expected one of {', '.join(PRESETS)})")
    return preset


def validate_invite_code(invite_code: str | None) -> str:
    """Return a policy-safe co-ai invite code."""
    code = (invite_code or DEFAULT_CO_AI_INVITE_CODE).strip()
    if not _INVITE_CODE_RE.fullmatch(code):
        raise ValueError("invite code must be 4-64 letters, numbers, hyphens, or underscores")
    return code


def _co_ai_trust_policy(invite_code: str) -> str:
    """Deny-by-default policy for a full coding agent."""
    return (
        "---\n"
        "allow: [whitelisted, contact]\n"
        "deny: [blocked]\n"
        "onboard:\n"
        f"  invite_code: [{invite_code}]\n"
        "default: deny\n"
        "---\n"
        "Only clients admitted with the configured invite code may use this coding agent."
    )


def render(
    name: str,
    model: str,
    port: int,
    toolkits: list[str],
    trust: str,
    *,
    preset: str = "custom",
    invite_code: str | None = None,
) -> str:
    """Render agent.py from the template (the get_ips patch is inlined by the template itself)."""
    preset = validate_preset(preset)
    if preset == "co-ai":
        code = validate_invite_code(invite_code)
        template = string.Template(config.CO_AI_TEMPLATE_PATH.read_text())
        return template.substitute(
            DOC_NAME=" ".join(name.split()).replace("\\", "").replace('"', "'"),
            NAME_LITERAL=repr(name),
            MODEL_LITERAL=repr(model),
            PORT=str(port),
            TRUST_POLICY_LITERAL=repr(_co_ai_trust_policy(code)),
        )

    template = string.Template(config.TEMPLATE_PATH.read_text())
    return template.substitute(
        # DOC_NAME lands RAW inside a """...""" docstring, so collapse whitespace and
        # strip backslashes / double-quotes: no `"""` or escape can form to break out.
        DOC_NAME=" ".join(name.split()).replace("\\", "").replace('"', "'"),
        NAME_LITERAL=repr(name),
        MODEL_LITERAL=repr(model),
        PORT=str(port),
        TOOLKITS_LITERAL=repr(list(toolkits)),
        SYSTEM_PROMPT_LITERAL=repr(_system_prompt(name, toolkits)),
        TRUST_LITERAL=repr(trust),
    )


def create(
    name: str,
    model: str,
    toolkits: list[str],
    trust: str = "open",
    *,
    preset: str = "custom",
    invite_code: str | None = None,
) -> AgentMeta:
    """Create an agent directory with identity + QR-ready address; does NOT start it."""
    preset = validate_preset(preset)
    if preset == "co-ai":
        selection = []
        trust = "strict"
        invite_code = validate_invite_code(invite_code)
    else:
        selection = validate(toolkits)
        trust = validate_trust(trust)
        invite_code = None
    with registry.locked():
        slug = _unique_slug(name)
        agent_dir = registry.agent_dir(slug)
        (agent_dir / ".co").mkdir(parents=True)
        reserved = {meta.port for meta in registry.load_all()}
        port = ports.allocate(reserved)
        address = identity.create(agent_dir / ".co")
        if config.KEYS_ENV.exists():  # this is how the co/gemini model key flows to the agent
            shutil.copy(config.KEYS_ENV, agent_dir / ".env")
        (agent_dir / "agent.py").write_text(
            render(
                name,
                model,
                port,
                selection,
                trust,
                preset=preset,
                invite_code=invite_code,
            )
        )
        meta = AgentMeta(
            slug=slug,
            name=name,
            address=address,
            port=port,
            model=model,
            toolkits=selection,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            trust=trust,
            preset=preset,
            invite_code=invite_code,
        )
        registry.save(meta)
    return meta
