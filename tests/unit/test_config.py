"""Tests for BotConfig."""

import pytest
from pyflayer.config import BotConfig


class TestBotConfig:
    def test_defaults(self) -> None:
        cfg = BotConfig(host="localhost")
        assert cfg.host == "localhost"
        assert cfg.port == 25565
        assert cfg.username == "pyflayer"
        assert cfg.version is None
        assert cfg.auth is None
        assert cfg.hide_errors is False

    def test_custom_values(self) -> None:
        cfg = BotConfig(
            host="mc.example.com",
            port=25566,
            username="TestBot",
            version="1.20.1",
            auth="microsoft",
            hide_errors=True,
        )
        assert cfg.host == "mc.example.com"
        assert cfg.port == 25566
        assert cfg.username == "TestBot"
        assert cfg.version == "1.20.1"
        assert cfg.auth == "microsoft"
        assert cfg.hide_errors is True

    def test_frozen(self) -> None:
        cfg = BotConfig(host="localhost")
        with pytest.raises(AttributeError):
            cfg.host = "other"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = BotConfig(host="localhost", port=25565)
        b = BotConfig(host="localhost", port=25565)
        assert a == b

    def test_inequality(self) -> None:
        a = BotConfig(host="localhost", port=25565)
        b = BotConfig(host="localhost", port=25566)
        assert a != b
