from streamlit_services.auth_links import build_login_links, build_logout_link, parse_auth_providers


def test_parse_auth_providers_defaults_to_microsoft():
    assert parse_auth_providers(None) == ["aad"]


def test_parse_auth_providers_accepts_supported_aliases_once():
    assert parse_auth_providers("microsoft, github, aad, unknown") == ["aad", "github"]


def test_build_login_links_use_azure_auth_endpoints():
    links = build_login_links("microsoft,google", "/?tab=access")

    assert links == [
        {
            "provider": "aad",
            "label": "Microsoft",
            "href": "/.auth/login/aad?post_login_redirect_uri=/%3Ftab%3Daccess",
        },
        {
            "provider": "google",
            "label": "Google",
            "href": "/.auth/login/google?post_login_redirect_uri=/%3Ftab%3Daccess",
        },
    ]


def test_build_logout_link_uses_azure_auth_endpoint():
    assert build_logout_link("/") == "/.auth/logout?post_logout_redirect_uri=/"
