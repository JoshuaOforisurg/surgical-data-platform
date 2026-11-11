from __future__ import annotations

from urllib.parse import quote


AUTH_PROVIDER_LABELS = {
    "aad": "Microsoft",
    "github": "GitHub",
    "google": "Google",
}
AUTH_PROVIDER_ALIASES = {
    "aad": "aad",
    "azuread": "aad",
    "entra": "aad",
    "microsoft": "aad",
    "github": "github",
    "google": "google",
}


def parse_auth_providers(raw_value: str | None) -> list[str]:
    """Return supported Azure auth provider paths from a comma-separated setting."""
    configured_value = raw_value or "aad"
    providers: list[str] = []

    for item in configured_value.split(","):
        provider = AUTH_PROVIDER_ALIASES.get(item.strip().lower())
        if provider and provider not in providers:
            providers.append(provider)

    return providers or ["aad"]


def build_login_links(raw_provider_value: str | None, redirect_path: str = "/") -> list[dict[str, str]]:
    redirect = quote(redirect_path or "/", safe="/")
    return [
        {
            "provider": provider,
            "label": AUTH_PROVIDER_LABELS[provider],
            "href": f"/.auth/login/{provider}?post_login_redirect_uri={redirect}",
        }
        for provider in parse_auth_providers(raw_provider_value)
    ]


def build_logout_link(redirect_path: str = "/") -> str:
    redirect = quote(redirect_path or "/", safe="/")
    return f"/.auth/logout?post_logout_redirect_uri={redirect}"


def auth_endpoints_available(headers, explicit_setting: str | None = None) -> bool:
    """Avoid presenting Azure's /.auth routes as usable on a local Streamlit server."""
    if explicit_setting is not None:
        return explicit_setting.strip().lower() in {"1", "true", "yes", "on"}

    host = ""
    for key, value in (headers or {}).items():
        if key.lower() in {"host", "x-forwarded-host"} and value:
            host = str(value).split(",", 1)[0].strip().lower()
            break
    hostname = host.rsplit(":", 1)[0]
    return bool(hostname and hostname not in {"localhost", "127.0.0.1", "::1"})
