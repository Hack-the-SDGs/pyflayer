"""Tests for BotConfig."""

import pytest

from minethon.config import BotConfig


class TestBotConfig:
    def test_defaults(self) -> None:
        cfg = BotConfig(host="localhost")
        assert cfg.host == "localhost"
        assert cfg.port == 25565
        assert cfg.username == "minethon"
        assert cfg.password is None
        assert cfg.version is None
        assert cfg.auth is None
        assert cfg.auth_server is None
        assert cfg.session_server is None
        assert cfg.hide_errors is None
        assert cfg.log_errors is None
        assert cfg.disable_chat_signing is None
        assert cfg.check_timeout_interval is None
        assert cfg.keep_alive is None
        assert cfg.respawn is None
        assert cfg.chat_length_limit is None
        assert cfg.view_distance is None
        assert cfg.default_chat_patterns is None
        assert cfg.physics_enabled is None
        assert cfg.brand is None
        assert cfg.skip_validation is None
        assert cfg.profiles_folder is None
        assert cfg.load_internal_plugins is None

    def test_custom_values(self) -> None:
        cfg = BotConfig(
            host="mc.example.com",
            port=25566,
            username="TestBot",
            password="hunter2",
            version="1.20.1",
            auth="microsoft",
            auth_server="https://drasl.example.com/auth",
            session_server="https://drasl.example.com/session",
            hide_errors=True,
            log_errors=False,
            disable_chat_signing=True,
            check_timeout_interval=60000,
            keep_alive=False,
            respawn=False,
            chat_length_limit=256,
            view_distance="far",
            default_chat_patterns=False,
            physics_enabled=False,
            brand="minethon",
            skip_validation=True,
            profiles_folder="/tmp/profiles",
            load_internal_plugins=False,
        )
        assert cfg.host == "mc.example.com"
        assert cfg.port == 25566
        assert cfg.username == "TestBot"
        assert cfg.password == "hunter2"
        assert cfg.version == "1.20.1"
        assert cfg.auth == "microsoft"
        assert cfg.auth_server == "https://drasl.example.com/auth"
        assert cfg.session_server == "https://drasl.example.com/session"
        assert cfg.hide_errors is True
        assert cfg.log_errors is False
        assert cfg.disable_chat_signing is True
        assert cfg.check_timeout_interval == 60000
        assert cfg.keep_alive is False
        assert cfg.respawn is False
        assert cfg.chat_length_limit == 256
        assert cfg.view_distance == "far"
        assert cfg.default_chat_patterns is False
        assert cfg.physics_enabled is False
        assert cfg.brand == "minethon"
        assert cfg.skip_validation is True
        assert cfg.profiles_folder == "/tmp/profiles"
        assert cfg.load_internal_plugins is False

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
