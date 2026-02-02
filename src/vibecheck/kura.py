"""
Kura secrets management - age-encrypted secrets from dotfiles-private.

Decrypts ~/dotfiles-private/amplifier-secrets.env.age using the age identity
at ~/.config/age/secrets.key.
"""

import subprocess
from functools import lru_cache
from pathlib import Path


SECRETS_FILE = Path.home() / "dotfiles-private" / "amplifier-secrets.env.age"
IDENTITY_FILE = Path.home() / ".config" / "age" / "secrets.key"


class KuraError(Exception):
    """Error accessing kura secrets."""
    pass


@lru_cache(maxsize=1)
def _load_secrets() -> dict[str, str]:
    """Decrypt and parse the secrets file. Cached for performance."""
    if not SECRETS_FILE.exists():
        raise KuraError(f"Secrets file not found: {SECRETS_FILE}")

    if not IDENTITY_FILE.exists():
        raise KuraError(f"Age identity not found: {IDENTITY_FILE}")

    try:
        result = subprocess.run(
            ["age", "--decrypt", "-i", str(IDENTITY_FILE), str(SECRETS_FILE)],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise KuraError(f"Failed to decrypt secrets: {e.stderr}") from e
    except FileNotFoundError:
        raise KuraError("age command not found. Install with: brew install age")

    secrets: dict[str, str] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            secrets[key.strip()] = value.strip()

    return secrets


def get_secret(name: str) -> str:
    """Get a secret by name from kura.

    Args:
        name: The secret name (e.g., "SUPABASE_DB_PASSWORD")

    Returns:
        The secret value

    Raises:
        KuraError: If the secret is not found or decryption fails
    """
    secrets = _load_secrets()
    if name not in secrets:
        raise KuraError(f"Secret not found: {name}")
    return secrets[name]


def get_secret_or_none(name: str) -> str | None:
    """Get a secret by name, returning None if not found."""
    try:
        return get_secret(name)
    except KuraError:
        return None
