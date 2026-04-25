"""TypeScript d.ts → Python schema for minethon stub tooling.

Documented public interface for the TS parser used by both
`generate_stubs.py` (full regen) and `check_stubs.py` (drift gate).
The parser implementation currently lives inside `generate_stubs.py`
for historical reasons; this module re-exports the symbols that other
tools should depend on, and is the planned home for the parser
implementation when the file is physically split.

Treat anything imported from here as the **stable internal API** for
TS-side tooling. Reach for `generate_stubs` directly only when you
know you need the rendering layer.

CLI usage:
    uv run python scripts/parse_dts.py            # dump JSON schema for inspection
    uv run python scripts/parse_dts.py --pretty   # pretty-printed JSON
"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path

# Load generate_stubs without polluting sys.path globally — keeps the import
# chain explicit and survives being called from any cwd.
_SPEC = importlib.util.spec_from_file_location(
    "_generate_stubs_for_parse_dts",
    Path(__file__).resolve().parent / "generate_stubs.py",
)
if _SPEC is None or _SPEC.loader is None:
    msg = "Cannot locate generate_stubs.py next to parse_dts.py"
    raise RuntimeError(msg)
_GEN = importlib.util.module_from_spec(_SPEC)
# Register before exec so @dataclass can resolve cls.__module__ → ns lookup
sys.modules[_SPEC.name] = _GEN
_SPEC.loader.exec_module(_GEN)

# Public re-exports — the parser's stable interface
Member = _GEN.Member
InterfaceBlock = _GEN.InterfaceBlock
MF_DIR = _GEN.MF_DIR
MF_INDEX = _GEN.MF_INDEX
PATHFINDER_DIR = _GEN.PATHFINDER_DIR
PATHFINDER_INDEX = _GEN.PATHFINDER_INDEX
TS_PRIMITIVES = _GEN.TS_PRIMITIVES
TS_NAME_REMAP = _GEN.TS_NAME_REMAP
ts_to_py = _GEN.ts_to_py
strip_ts_comments = _GEN.strip_ts_comments
find_interface = _GEN.find_interface
find_interface_extends = _GEN.find_interface_extends
find_class = _GEN.find_class
parse_members = _GEN.parse_members
parse_method_args = _GEN.parse_method_args

__all__ = [
    "INTERFACES_OF_INTEREST",
    "MF_DIR",
    "MF_INDEX",
    "PATHFINDER_DIR",
    "PATHFINDER_INDEX",
    "TS_NAME_REMAP",
    "TS_PRIMITIVES",
    "InterfaceBlock",
    "Member",
    "build_schema",
    "find_class",
    "find_interface",
    "find_interface_extends",
    "parse_members",
    "parse_method_args",
    "strip_ts_comments",
    "ts_to_py",
]


# Top-level interface names worth tracking for drift detection. Mirrors the
# subset rendered by generate_stubs into bot.pyi (Bot, BotOptions, etc. are
# tracked separately because they map to different output classes).
INTERFACES_OF_INTEREST: tuple[str, ...] = (
    "Bot",
    "BotOptions",
)


def build_schema() -> dict[str, list[dict[str, object]]]:
    """Return ``{interface_name: [member_dict, ...]}`` from the pinned d.ts.

    Each ``member_dict`` is a JSON-serialisable view of :class:`Member` so
    the schema can be cached, diffed, or shipped to non-Python tooling.
    Source files are the runtime-installed ones (see
    ``_resolve_package_dir`` in ``generate_stubs``).
    """
    text = strip_ts_comments(MF_INDEX.read_text())
    schema: dict[str, list[dict[str, object]]] = {}
    for name in INTERFACES_OF_INTEREST:
        body = find_interface(text, name)
        if body is None:
            schema[name] = []
            continue
        schema[name] = [asdict(m) for m in parse_members(body)]
    return schema


def main() -> None:
    pretty = "--pretty" in sys.argv[1:]
    schema = build_schema()
    if pretty:
        json.dump(schema, sys.stdout, indent=2, ensure_ascii=False)
    else:
        json.dump(schema, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
