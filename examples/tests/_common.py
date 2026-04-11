"""Shared helpers for manual integration tests.

Every test script imports ``create_bot()`` and ``run_test()`` from here
to avoid duplicating connection boilerplate.

Setup:
    cp examples/tests/.env.example examples/tests/.env
    # Fill in credentials, then run any test:
    uv run --env-file examples/tests/.env examples/tests/<folder>/test_xxx.py
"""

import os
import sys
import traceback
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from minethon import Bot

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

_PASS = "[PASS]"
_FAIL = "[FAIL]"
_INFO = "[INFO]"
_SKIP = "[SKIP]"


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def check(label: str, value: object, expected: object | None = None) -> None:
    """Print a property check line. If *expected* is given, compare."""
    if expected is not None:
        ok = value == expected
        tag = _PASS if ok else _FAIL
        print(f"  {tag} {label}: {value!r} (expected {expected!r})")
    else:
        print(f"  {_INFO} {label}: {value!r}")


def check_type(label: str, value: object, expected_type: type) -> None:
    ok = isinstance(value, expected_type)
    tag = _PASS if ok else _FAIL
    print(
        f"  {tag} {label}: {type(value).__name__} (expected {expected_type.__name__})"
    )


def check_true(label: str, value: bool) -> None:
    tag = _PASS if value else _FAIL
    print(f"  {tag} {label}: {value}")


def check_false(label: str, value: bool) -> None:
    tag = _PASS if not value else _FAIL
    print(f"  {tag} {label}: {value}")


def check_not_none(label: str, value: object) -> None:
    tag = _PASS if value is not None else _FAIL
    print(f"  {tag} {label}: {value!r}")


def check_range(label: str, value: float, lo: float, hi: float) -> None:
    ok = lo <= value <= hi
    tag = _PASS if ok else _FAIL
    print(f"  {tag} {label}: {value} (expected {lo}..{hi})")


def info(msg: str) -> None:
    print(f"  {_INFO} {msg}")


def skip(msg: str) -> None:
    print(f"  {_SKIP} {msg}")


def passed(msg: str) -> None:
    print(f"  {_PASS} {msg}")


def failed(msg: str) -> None:
    print(f"  {_FAIL} {msg}")


def wait_prompt(msg: str) -> None:
    """Print a prompt telling the tester to do something in-game."""
    print(f"\n  >>> {msg}")
    print("  >>> Press Enter when ready...")
    input()


# ---------------------------------------------------------------------------
# Bot creation
# ---------------------------------------------------------------------------


def create_bot(**overrides: object) -> Bot:
    """Create a Bot from environment variables.

    All ``MC_*`` env vars are read. Individual fields can be
    overridden via keyword arguments.
    """
    kwargs: dict[str, object] = {
        "host": os.environ["MC_HOST"],
        "port": int(os.environ.get("MC_PORT", "25565")),
        "username": os.environ["MC_USERNAME"],
        "password": os.environ.get("MC_PASSWORD"),
        "auth": "mojang",
        "auth_server": os.environ.get("MC_AUTH_SERVER"),
        "session_server": os.environ.get("MC_SESSION_SERVER"),
    }
    kwargs.update(overrides)
    return Bot(**kwargs)  # type: ignore[arg-type]


@asynccontextmanager
async def connected_bot(**overrides: object) -> AsyncIterator[Bot]:
    """Context manager: create, connect, spawn, yield, disconnect."""
    bot = create_bot(**overrides)
    try:
        await bot.connect()
        await bot.wait_until_spawned()
        info(f"Bot spawned at {bot.position}")
        yield bot
    finally:
        await bot.disconnect()


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------


async def run_test(
    name: str,
    test_fn: Callable[[Bot], Awaitable[None]],
    **bot_overrides: object,
) -> None:
    """Connect a bot, run *test_fn*, then disconnect. Catches exceptions."""
    print(f"\n{'#' * 60}")
    print(f"# Test: {name}")
    print(f"{'#' * 60}")
    try:
        async with connected_bot(**bot_overrides) as bot:
            await test_fn(bot)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception:
        failed("Unhandled exception:")
        traceback.print_exc()
        sys.exit(1)
    print(f"\n--- {name} finished ---\n")
