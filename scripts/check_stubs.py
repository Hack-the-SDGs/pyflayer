"""Drift gate: warn when bot.pyi misses a TS-declared symbol.

Today the generator is full-regen: every run rewrites bot.pyi from the TS
d.ts, so missing items are normally zero by construction. The check is the
safety net for two failure modes:

1. Someone hand-edits bot.pyi and accidentally drops a member that TS still
   declares (would be silently restored on next regen — or, in the future
   additive `patch_stubs` model, would stay deleted).
2. mineflayer adds new TS surface and the generator's interface enumeration
   hasn't been updated yet — the new symbol is silently absent.

Designed to grow into the gate for the planned `patch_stubs.py` (additive)
generator. Today it operates against the existing full-regen output.

Exit codes:
    0 — bot.pyi covers every TS-declared member tracked here
    1 — one or more TS members missing from bot.pyi
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import parse_dts

REPO_ROOT = Path(__file__).resolve().parent.parent
PYI_PATH = REPO_ROOT / "src/minethon/bot.pyi"


def _ts_member_names(schema: dict[str, list[dict[str, object]]]) -> dict[str, set[str]]:
    """Schema → ``{interface: {member_name, ...}}``.

    Underscore-prefixed names are dropped to match the generator's filter:
    they're private-by-Python-convention even when TS declares them
    (e.g., ``Bot._client`` is the internal minecraft-protocol handle that
    the generator deliberately omits from the public stub).
    """
    return {
        iface: {m["name"] for m in members if not str(m["name"]).startswith("_")}
        for iface, members in schema.items()
    }


def _pyi_member_names(path: Path) -> dict[str, set[str]]:
    """AST-walk the .pyi → ``{class_name: {member_name, ...}}``."""
    if not path.exists():
        msg = f"bot.pyi not found at {path}"
        raise FileNotFoundError(msg)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: dict[str, set[str]] = {}
    for top in tree.body:
        if not isinstance(top, ast.ClassDef):
            continue
        members: set[str] = set()
        for item in top.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                members.add(item.target.id)
            elif isinstance(item, ast.FunctionDef):
                members.add(item.name)
        out[top.name] = members
    return out


def _check() -> int:
    schema = parse_dts.build_schema()
    ts_names = _ts_member_names(schema)
    pyi_names = _pyi_member_names(PYI_PATH)

    missing: dict[str, set[str]] = {}
    for iface, ts_members in ts_names.items():
        pyi_members = pyi_names.get(iface, set())
        gap = ts_members - pyi_members
        if gap:
            missing[iface] = gap

    if not missing:
        total = sum(len(v) for v in ts_names.values())
        print(f"check_stubs: OK — {total} TS members all present in bot.pyi")
        return 0

    print("check_stubs: DRIFT detected — TS members missing from bot.pyi:")
    for iface, gap in sorted(missing.items()):
        print(f"  {iface}: {sorted(gap)}")
    return 1


if __name__ == "__main__":
    sys.exit(_check())
