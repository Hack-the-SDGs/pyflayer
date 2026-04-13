from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

import minethon.bot as bot_module
from minethon import BotEvent
from minethon.errors import PluginNotInstalledError, VersionPinRequiredError

_normalize_handler: Any = cast("Any", bot_module)._normalize_handler


class _FakeJsBot:
    def loadPlugin(self, plugin: object) -> None:  # noqa: N802
        self.plugin = plugin


def test_on_accepts_bot_event(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[object, str, object]] = []
    calls: list[tuple[object | None, object | None, object | None]] = []

    def fake_on(js_bot: object, event: str):
        def decorator(func: object) -> object:
            seen.append((js_bot, event, func))
            return func

        return decorator

    monkeypatch.setattr(bot_module, "On", fake_on)
    js_bot = _FakeJsBot()
    bot = bot_module.Bot(js_bot)

    @bot.on(BotEvent.CHAT)
    def on_chat(
        username: str,
        message: str,
        translate: str | None,
        json_msg: object,
        matches: list[str] | None,
    ) -> None:
        calls.append((username, message, translate))
        assert json_msg is not None or matches is None

    assert len(seen) == 1
    assert seen[0][:2] == (js_bot, "chat")
    assert seen[0][2] is not on_chat
    registered = seen[0][2]
    assert callable(registered)
    registered(js_bot, "alice", "hello")
    assert calls == [("alice", "hello", None)]


def test_on_chat_shortcut_uses_same_event(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake_on(js_bot: object, event: str):
        def decorator(func: object) -> object:
            seen.append(event)
            return func

        return decorator

    monkeypatch.setattr(bot_module, "On", fake_on)
    bot = bot_module.Bot(_FakeJsBot())

    @bot.on_chat
    def on_chat(
        username: str,
        message: str,
        translate: str | None,
        json_msg: object,
        matches: list[str] | None,
    ) -> None:
        assert username or message
        assert translate is None or isinstance(translate, str)
        assert json_msg is not None or matches is None

    assert seen == ["chat"]


def test_on_rejects_string_event() -> None:
    bot = bot_module.Bot(_FakeJsBot())

    with pytest.raises(TypeError):
        cast("Any", bot).on("chat")


def test_unknown_event_shortcut_raises_informative_attribute_error() -> None:
    bot = bot_module.Bot(_FakeJsBot())

    with pytest.raises(AttributeError, match="未知的事件 shortcut"):
        _ = bot.on_typo_event  # type: ignore[attr-defined]

    with pytest.raises(AttributeError, match="未知的事件 shortcut"):
        _ = bot.once_typo_event  # type: ignore[attr-defined]


def test_once_chat_shortcut_registers_once(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake_once(js_bot: object, event: str):
        def decorator(func: object) -> object:
            seen.append(event)
            return func

        return decorator

    monkeypatch.setattr(bot_module, "Once", fake_once)
    bot = bot_module.Bot(_FakeJsBot())

    @bot.once_chat
    def _on_chat(*_args: object, **_kwargs: object) -> None:
        pass

    assert seen == ["chat"]


def test_normalize_handler_drops_injected_emitter_and_pads_missing_args() -> None:
    calls: list[tuple[object | None, object | None]] = []
    emitter = object()

    def handler(username: object | None, message: object | None) -> None:
        calls.append((username, message))

    wrapped = _normalize_handler(handler, emitter=emitter)
    wrapped(emitter, "alice")

    assert calls == [("alice", None)]


def test_missing_pathfinder_raises_user_facing_error() -> None:
    bot = bot_module.Bot(SimpleNamespace())

    with pytest.raises(PluginNotInstalledError):
        _ = bot.pathfinder


def test_require_without_version_rejects_unbundled_packages() -> None:
    bot = bot_module.Bot(_FakeJsBot())

    with pytest.raises(VersionPinRequiredError):
        bot.require("mineflayer-tool")


def test_bind_wires_only_overridden_handlers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from minethon import BotHandlers

    registered: list[str] = []

    def fake_on(js_bot: object, event: str):
        def decorator(func: object) -> object:
            registered.append(event)
            return func

        return decorator

    monkeypatch.setattr(bot_module, "On", fake_on)
    bot = bot_module.Bot(_FakeJsBot())

    class MyHandlers(BotHandlers):
        def on_chat(self, *_args: object, **_kwargs: object) -> None:
            pass

        def on_spawn(self, *_args: object, **_kwargs: object) -> None:
            pass

    returned = bot.bind(MyHandlers())

    assert isinstance(returned, MyHandlers)
    assert set(registered) == {"chat", "spawn"}
