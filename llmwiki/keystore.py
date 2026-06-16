"""Persisted API keys.

Keys still reach the providers through the environment (``OPENAI_API_KEY`` /
``ANTHROPIC_API_KEY``, read by the SDK clients at init); this module just lets a
user store them once in ``~/.config/llmwiki/.env`` and loads that into
``os.environ`` at startup so they need not be exported in every new shell. A real
exported env var always wins over the file.
"""

from __future__ import annotations

import os
from pathlib import Path

# Environment variable holding the API key for each provider backend. Canonical
# home for this map (cli.py imports it from here).
PROVIDER_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}


def key_file() -> Path:
    """Location of the persisted key file: ``${XDG_CONFIG_HOME:-~/.config}/llmwiki/.env``."""
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "llmwiki" / ".env"


def resolve_env(provider_or_env: str) -> str:
    """Map a provider name to its env var, or pass a raw env var name through."""
    return PROVIDER_ENV.get(provider_or_env.lower(), provider_or_env)


def _parse(path: Path) -> dict[str, str]:
    """Read a ``.env``-style file into a ``{KEY: value}`` dict (last wins).

    Skips blanks and ``#`` comments, tolerates a leading ``export``, and strips a
    single pair of surrounding quotes from the value.
    """
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for raw in path.read_text("utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            result[key] = value
    return result


def load_into_env() -> None:
    """Populate ``os.environ`` from the key file without overriding existing vars."""
    for key, value in _parse(key_file()).items():
        os.environ.setdefault(key, value)


def stored_keys() -> dict[str, str]:
    """The ``{KEY: value}`` pairs currently saved in the key file."""
    return _parse(key_file())


def set_key(provider_or_env: str, value: str) -> Path:
    """Write/replace a single ``KEY=value`` line in the key file (mode 0600).

    Accepts a provider name (``openai``/``anthropic``) or a raw env var name.
    Returns the file path.
    """
    env = resolve_env(provider_or_env)
    path = key_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text("utf-8").splitlines() if path.exists() else []
    out: list[str] = []
    replaced = False
    for line in lines:
        stripped = line.strip()
        name = stripped[len("export "):].lstrip() if stripped.startswith("export ") else stripped
        if name.partition("=")[0].strip() == env:
            out.append(f"{env}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{env}={value}")
    path.write_text("\n".join(out) + "\n", "utf-8")
    path.chmod(0o600)
    return path
