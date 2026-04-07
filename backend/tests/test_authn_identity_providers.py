from app.security.authn import (
    IdentityAuthResult,
    IdentityPrincipal,
    IdentityProviderRegistry,
    OIDCIdentityProviderStrategy,
    SAMLIdentityProviderStrategy,
)


class DummyOIDC(OIDCIdentityProviderStrategy):
    provider_name = "oidc-dummy"

    def begin_auth(self, *, relay_state: str | None = None) -> str:
        return f"https://idp.example.com/auth?state={relay_state or ''}"

    def complete_auth(self, *, payload: dict):
        return IdentityAuthResult(
            principal=IdentityPrincipal(
                subject="abc123",
                email=payload.get("email"),
                display_name="OIDC User",
                provider=self.provider_name,
                claims=payload,
            )
        )


class DummySAML(SAMLIdentityProviderStrategy):
    provider_name = "saml-dummy"

    def begin_auth(self, *, relay_state: str | None = None) -> str:
        return f"https://sso.example.com/saml?RelayState={relay_state or ''}"

    def complete_auth(self, *, payload: dict):
        return IdentityAuthResult(
            principal=IdentityPrincipal(
                subject="saml-subj",
                email=payload.get("email"),
                display_name="SAML User",
                provider=self.provider_name,
                claims=payload,
            ),
            raw_token="assertion-token",
        )


def test_identity_provider_registry_register_and_resolve():
    registry = IdentityProviderRegistry()
    oidc = DummyOIDC()
    saml = DummySAML()

    registry.register(oidc)
    registry.register(saml)

    assert registry.resolve("oidc-dummy") is oidc
    assert registry.resolve("saml-dummy") is saml


def test_identity_provider_registry_missing_provider_raises_key_error():
    registry = IdentityProviderRegistry()
    try:
        registry.resolve("missing")
        assert False, "expected KeyError"
    except KeyError:
        assert True
