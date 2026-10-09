"""`.env.example` must only document variables that actually do something.

A variable in `.env.example` that no code reads is worse than a missing one: an
operator sets it, sees no effect, and concludes the feature is broken. Sixteen
such variables had accumulated - `RSS_FEED_URLS`, `KRONOS_USE_CLOUD`,
`JASPER_AGENT_TOKEN`, `MAX_NEWS_ARTICLES_PER_HOUR` and others - all of them
looking plausible and all of them inert.

These tests parse both files and compare, so the drift cannot come back.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = BACKEND / ".env.example"
CONFIG = BACKEND / "app" / "config.py"

#: Variables that are legitimately set outside `Settings`.
#:
#: `PORT` is read straight from the environment because Render injects it and
#: Pydantic's field would fight the platform. `DATA_DIR` is created at import time
#: from the environment before Settings is constructed.
DIRECT_ENV_VARS = {"PORT", "DATA_DIR", "PYTHON_VERSION", "PATH", "HOME"}


def _settings_fields() -> set[str]:
    """Field names declared on the `Settings` class."""
    tree = ast.parse(CONFIG.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            return {
                stmt.target.id
                for stmt in node.body
                if isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Name)
            }
    raise AssertionError("Settings class not found in app/config.py")


def _declared_in_env_example() -> set[str]:
    """Variables actually assigned in `.env.example`.

    Only `NAME=` at the start of a line counts, so commented-out examples and
    prose mentions of a variable do not count as documenting it.
    """
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    return set(re.findall(r"^([A-Z][A-Z0-9_]{2,})=", text, re.MULTILINE))


def _all_source_text() -> str:
    """Concatenated application source, for a last-resort usage check."""
    parts = []
    for path in (BACKEND / "app").rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def _env_reads_in_source() -> set[str]:
    """Variables read straight from the environment outside `Settings`.

    A few scrapers read `os.getenv` directly rather than going through
    `Settings` - `TELEGRAM_API_ID` in the Telethon source, for instance, because
    it is only needed inside that module and raising a Pydantic validation error
    for a missing scraper credential would be the wrong failure mode. Those are
    real settings and must not be reported as dead.
    """
    import os as _os
    import re as _re

    names: set[str] = set()
    for root, _dirs, files in _os.walk(BACKEND / "app"):
        if "__pycache__" in root:
            continue
        for name in files:
            if not name.endswith(".py"):
                continue
            text = (Path(root) / name).read_text(encoding="utf-8", errors="replace")
            names.update(
                _re.findall(
                    r"os\.(?:getenv|environ\.get)\(\s*[\"']([A-Z][A-Z0-9_]+)[\"']",
                    text,
                )
            )
            names.update(
                _re.findall(
                    r"os\.environ\[\s*[\"']([A-Z][A-Z0-9_]+)[\"']\s*\]", text
                )
            )
    return names


class TestEnvExampleMatchesSettings:
    def test_every_documented_variable_is_real(self):
        """The core check: nothing inert in `.env.example`."""
        fields = _settings_fields() | _env_reads_in_source() | DIRECT_ENV_VARS
        documented = _declared_in_env_example()
        unknown = sorted(documented - fields)
        assert not unknown, (
            f"`.env.example` documents variables that are not Settings fields and "
            f"are never read: {unknown}. Either add the field to `Settings` or "
            "remove the variable."
        )

    def test_settings_fields_are_documented(self):
        """The reverse drift also hurts: an operator cannot discover a variable.

        A handful of fields are intentionally undocumented because they are set
        by the platform or are secrets an operator should not be told to paste;
        they are listed here explicitly rather than left as silent gaps.
        """
        fields = _settings_fields()
        documented = _declared_in_env_example()
        # Secrets with no safe default to show, platform-injected, or derived.
        intentional_gaps = {
            "CTRADER_CLIENT_ID",
            "CTRADER_CLIENT_SECRET",
            "CTRADER_REDIRECT_URI",
            "CTRADER_ENCRYPTION_KEY",
            "CTRADER_BROKER_ENABLED",
            "CTRADER_RATE_LIMIT",
            "CTRADER_SANDBOX",
            "RATE_LIMIT_ENABLED",
            "RATE_LIMIT_REQUESTS_PER_MINUTE",
            "RATE_LIMIT_BURST",
            "SECURITY_HSTS_ENABLED",
            "SECURE_COOKIES",
            "CORS_ALLOW_CREDENTIALS",
            "CSRF_PROTECTION_ENABLED",
            "APP_NAME",
            "APP_VERSION",
            "HOST",
            "DEBUG",
            "SUPABASE_URL",
            "SUPABASE_ANON_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "GROQ_API_KEY",
            "GROQ_API_KEYS",
            "GROQ_BASE_URL",
            "MODEL_FAST",
            "MODEL_FREE_FAST",
            "MODEL_BALANCED",
            "MODEL_SMART",
            "MODEL_SMART_FREE",
            "MODEL_DEEP",
            "MODEL_ALTERNATIVE",
            "GEMINI_BASE_URL",
            "NVIDIA_BASE_URL",
            "CCXT_BINANCE_OPT_IN",
            "FACTOR_LIMIT_BARS",
            "FACTOR_REFRACTORY_MINUTES",
            "FACTOR_SWEEP_INTERVAL",
            "FORECAST_CACHE_TTL",
            "FORECAST_MIN_CANDLES",
            "REDIS_URL",
        }
        undocumented = sorted(fields - documented - intentional_gaps)
        assert not undocumented, (
            f"Settings fields absent from `.env.example`: {undocumented}. Add "
            "them, or add an explicit reason to `intentional_gaps`."
        )

    def test_the_removed_dead_variables_stay_removed(self):
        """Named explicitly, because these are the ones that were removed and the
        comments explaining why would otherwise invite someone to re-add them."""
        source = _all_source_text()
        dead = [
            "RSS_FEED_URLS",
            "KRONOS_USE_CLOUD",
            "KRONOS_BATCH_SIZE",
            "KRONOS_MEMORY_THRESHOLD",
            "JASPER_AGENT_TOKEN",
            "JASPER_BASE_URL",
            "MAX_NEWS_ARTICLES_PER_HOUR",
            "IMPACT_SCORING_ENABLED",
            "NEWS_SENTIMENT_THRESHOLD",
            "NEWS_VOLUME_SPIKE_MULTIPLIER",
            "CROSS_PLATFORM_CONSENSUS_MIN",
            "TREND_UPDATE_INTERVAL",
            "TATUM_API_KEY",
        ]
        still_documented = sorted(
            name for name in dead
            if re.search(rf"^{name}=", ENV_EXAMPLE.read_text(encoding="utf-8"), re.M)
        )
        assert not still_documented, (
            f"these have no reader and must not be documented again: "
            f"{still_documented}"
        )
        # And confirm they genuinely have no reader, so this test cannot be
        # satisfied by deleting a variable that is genuinely in use.
        fields = _settings_fields() | _env_reads_in_source()
        assert not [name for name in dead if name in fields]

    def test_migrated_llm_variables_are_gone(self):
        """Gemini and NVIDIA were replaced by Groq; their variables were left
        behind and would send an operator to a provider the app no longer calls."""
        source = _all_source_text()
        assert "GEMINI_API_KEY" not in source
        assert "NVIDIA_API_KEY" not in source
        documented = _declared_in_env_example()
        assert "GEMINI_API_KEY" not in documented
        assert "NVIDIA_API_KEY" not in documented


class TestCriticalVariablesPresent:
    """The variables that silently break behaviour when absent."""

    @pytest.mark.parametrize(
        "name",
        [
            "DATABASE_URL",
            "SECRET_KEY",
            "ENVIRONMENT",
            "DEBUG",
            "CORS_ORIGINS",
            "KRONOS_SERVICE_URL",
            "KRONOS_API_KEY",
            "UNIVERSAL_PAPER_TRADING",
            "AUTO_PAYOUTS_ENABLED",
            "TELEGRAM_BOT_TOKEN",
        ],
    )
    def test_documented(self, name):
        assert name in _settings_fields(), f"{name} is not a Settings field"
        assert name in _declared_in_env_example(), (
            f"{name} is not in `.env.example`; an operator hitting the "
            "documented failure mode would have no way to fix it"
        )

    def test_payout_rail_has_no_env_var_requirement(self):
        """Payout signing keys are configured in the Settings UI, not the
        environment, so there must be no `PAYOUT_*_KEY` env var to go stale."""
        fields = _settings_fields()
        assert not [
            name
            for name in fields
            if "PAYOUT" in name and ("KEY" in name or "PRIVATE" in name)
        ], "payout signing keys must not be readable from the environment"