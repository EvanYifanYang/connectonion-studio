"""Create a new agent: slug, port, identity, key copy, rendered agent.py, meta.json."""

from __future__ import annotations

import datetime
import re
import shutil
import string

from . import config, identity, ports, registry
from .registry import AgentMeta
from .toolkits import HINTS, prompt_guides, required_trust, requires_invite, validate


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


def _system_prompt(name: str, capabilities: list[str]) -> str:
    """Compose a general contract plus operating guidance for selected capabilities."""
    abilities = "; ".join(HINTS[t] for t in capabilities) or "plain conversation"
    guide = prompt_guides(capabilities)
    prompt = f"""You are {name}, a capable general-purpose assistant.

Available capabilities: {abilities}.

## Response style
- Answer directly and naturally. Skip greetings, filler, and repeated conclusions.
- Match the user's level of detail: concise by default, more thorough when the task needs it.
- Use plain language and structure longer answers so they are easy to scan.
- Keep a calm, friendly, professional tone. Do not use emojis unless the user asks.

## Accuracy
- Prioritize correct, useful information over agreeing with the user.
- If information is missing or uncertain, say what is unknown instead of inventing an answer.
- Ask a focused clarification only when it materially changes the result.

## Tool use
- Use an available tool when it provides evidence or completes the request more reliably.
- Do not claim a tool action succeeded unless its result confirms success.
- Explain tool results in user-facing language, without exposing internal implementation details."""
    return f"{prompt}\n\n{guide}" if guide else prompt


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


def validate_required_invite_code(invite_code: str | None) -> str:
    """Validate an explicitly supplied code for sensitive Custom Agent capabilities."""
    if invite_code is None or not invite_code.strip():
        raise ValueError("invite code is required for sensitive or dangerous capabilities")
    return validate_invite_code(invite_code)


def _invite_trust_policy(invite_code: str, *, subject: str = "agent") -> str:
    """Deny-by-default policy shared by co-ai and sensitive Custom Agents."""
    return (
        "---\n"
        "allow: [whitelisted, contact]\n"
        "deny: [blocked]\n"
        "onboard:\n"
        f"  invite_code: [{invite_code}]\n"
        "default: deny\n"
        "---\n"
        f"Only clients admitted with the configured invite code may use this {subject}."
    )


def normalize_custom_policy(
    capabilities: list[str],
    invite_code: str | None,
    *,
    require_explicit_code: bool,
) -> tuple[list[str], str, str | None]:
    """Canonicalize capabilities and derive the only access policy they may use.

    New clients must explicitly supply a code. Existing metadata and the legacy
    ``toolkits`` API can be upgraded with Studio's historical default code.
    """
    selection = validate(capabilities)
    trust = required_trust(selection)
    if not requires_invite(selection):
        return selection, trust, None
    validator = validate_required_invite_code if require_explicit_code else validate_invite_code
    return selection, trust, validator(invite_code)


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
            TRUST_POLICY_LITERAL=repr(_invite_trust_policy(code, subject="coding agent")),
        )

    selection, forced_trust, code = normalize_custom_policy(
        toolkits, invite_code, require_explicit_code=False
    )
    trust_policy = _invite_trust_policy(code, subject="agent") if code else forced_trust
    template = string.Template(config.TEMPLATE_PATH.read_text())
    return template.substitute(
        # DOC_NAME lands RAW inside a """...""" docstring, so collapse whitespace and
        # strip backslashes / double-quotes: no `"""` or escape can form to break out.
        DOC_NAME=" ".join(name.split()).replace("\\", "").replace('"', "'"),
        NAME_LITERAL=repr(name),
        MODEL_LITERAL=repr(model),
        PORT=str(port),
        CAPABILITIES_LITERAL=repr(selection),
        SYSTEM_PROMPT_LITERAL=repr(_system_prompt(name, selection)),
        TRUST_LITERAL=repr(trust_policy),
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
        selection, trust, invite_code = normalize_custom_policy(
            toolkits, invite_code, require_explicit_code=True
        )
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
            capabilities=selection,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            trust=trust,
            preset=preset,
            invite_code=invite_code,
        )
        registry.save(meta)
    return meta
