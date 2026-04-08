"""Backwards-compatible config exports.

Primary implementation lives in app.config.settings.
"""

from app.config.settings import (  # noqa: F401
    AppSettings,
    AwsSecretsManagerSettingsSource,
    LocalSettings,
    ProdSettings,
    Settings,
    StagingSettings,
    TestSettings,
    build_settings,
    settings,
)
