"""Generate src/minethon/bot.pyi from mineflayer's index.d.ts.

Strategy:
- `Bot` / `BotEvents` / `BotOptions` / mineflayer's aux interfaces are parsed
  out of `index.d.ts` and mechanically converted to Python type stubs.
- External dependencies that mineflayer imports (`vec3`, `prismarine-entity`,
  `prismarine-block`, `prismarine-item`, `prismarine-chat`,
  `prismarine-windows`, `prismarine-recipe`) have their own `.d.ts` files,
  which we parse alongside mineflayer's and inline the relevant classes as
  Python Protocols. Nothing is invented — each definition traces back to a
  TypeScript source.

The generator handles the subset of TypeScript syntax used by these files:
primitives, unions, arrays, mapped dict types, function types, `Promise<T>`
(stripped → sync return), object types, and `Literal` unions. Unsupported
constructs fall through as `object` with a comment.

Run: uv run python scripts/generate_stubs.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDORED_DTS_ROOT = REPO_ROOT / "src/mineflayer/js/node_modules"
OUT_PATH = REPO_ROOT / "src/minethon/bot.pyi"
OUT_EVENTS_PATH = REPO_ROOT / "src/minethon/_events.py"
OUT_HANDLERS_PATH = REPO_ROOT / "src/minethon/_handlers.py"
STUBS_DOC = REPO_ROOT / "docs/stubs_zh_tw.md"


def _find_runtime_node_modules() -> Path | None:
    candidates = sorted(
        REPO_ROOT.glob(".venv/lib/python*/site-packages/javascript/js/node_modules")
    )
    return candidates[0] if candidates else None


RUNTIME_DTS_ROOT = _find_runtime_node_modules()


def _resolve_package_dir(package: str) -> Path:
    """Resolve a package directory, preferring the pinned runtime installation."""
    if RUNTIME_DTS_ROOT is not None:
        aliased = sorted(RUNTIME_DTS_ROOT.glob(f"{package}--*"))
        if aliased:
            return aliased[0]
        runtime_plain = RUNTIME_DTS_ROOT / package
        if runtime_plain.exists():
            return runtime_plain
    vendored = VENDORED_DTS_ROOT / package
    if vendored.exists():
        return vendored
    raise FileNotFoundError(f"Cannot resolve npm package directory for {package!r}")


MF_DIR = _resolve_package_dir("mineflayer")
PATHFINDER_DIR = _resolve_package_dir("mineflayer-pathfinder")
MF_INDEX = MF_DIR / "index.d.ts"
PATHFINDER_INDEX = PATHFINDER_DIR / "index.d.ts"


# --------------------------------------------------------------------------- #
#  Stubs doc parsing & docstring injection
# --------------------------------------------------------------------------- #


def parse_stubs_doc() -> dict[str, str]:
    """Parse docs/stubs_zh_tw.md into `{lookup_key: description_body}`.

    Heading → key mapping:
      - ``### bot.chat(message)``         → ``bot.chat``
      - ``### bot.health``                → ``bot.health``
      - ``### "chat"``                    → ``event:chat``
      - ``### Vec3``                      → ``Vec3``
      - ``### Vec3.offset(dx, dy, dz)``   → ``Vec3.offset``
      - ``### Entity.position``           → ``Entity.position``

    Sections whose body is empty return an empty string — callers should
    treat empty body as "no docstring".
    """
    if not STUBS_DOC.exists():
        return {}
    text = STUBS_DOC.read_text()
    sections: dict[str, str] = {}
    current_key: str | None = None
    current_body: list[str] = []

    def _key_from_heading(heading: str) -> str:
        t = heading.removeprefix("### ").strip()
        m = re.match(r'^"([^"]+)"', t)
        if m:
            return f"event:{m.group(1)}"
        # Strip trailing `(...)` argument list
        m2 = re.match(r"^([^()\s]+)\s*\(", t)
        if m2:
            return m2.group(1)
        return t

    def _finalize(body: list[str]) -> str:
        # Drop trailing "---" thematic breaks, empty lines, and `## `-level
        # section separators that belong to file-level layout rather than the
        # symbol's description.
        while body:
            t = body[-1].strip()
            if not t or t == "---" or t.startswith("## "):
                body.pop()
                continue
            break
        return "\n".join(body).strip("\n")

    for raw in text.split("\n"):
        if raw.startswith("### "):
            if current_key is not None:
                sections[current_key] = _finalize(current_body)
            current_key = _key_from_heading(raw)
            current_body = []
        elif current_key is not None:
            current_body.append(raw)
    if current_key is not None:
        sections[current_key] = _finalize(current_body)
    return sections


def format_doc_block(body: str, indent: str) -> list[str]:
    """Format a description body as lines of a triple-quoted Python docstring.

    Returns an empty list if body is empty / whitespace-only.
    """
    body = body.strip("\n").rstrip()
    if not body.strip():
        return []
    body_lines = body.split("\n")
    if len(body_lines) == 1:
        return [f'{indent}"""{body_lines[0]}"""']
    out = [f'{indent}"""{body_lines[0]}']
    out.extend(f"{indent}{bl}" if bl else "" for bl in body_lines[1:])
    out.append(f'{indent}"""')
    return out


def inject_docstrings(text: str, descriptions: dict[str, str]) -> str:
    """Post-process the generated `.pyi` text to splice in docstrings."""
    lines = text.split("\n")
    out: list[str] = []
    current_class: str | None = None
    i = 0
    n = len(lines)

    def key_for_member(name: str) -> str:
        if current_class == "Bot":
            return f"bot.{name}"
        if current_class:
            return f"{current_class}.{name}"
        return name

    while i < n:
        line = lines[i]
        indent_prefix = line[: len(line) - len(line.lstrip(" "))]
        stripped = line.strip()

        # Module-level: detect class end by top-level non-class content
        if current_class and line and not line.startswith(" "):
            # Any line at column 0 that isn't blank terminates the class scope
            if not stripped.startswith(("class ", "#")):
                current_class = None

        # Class declaration
        m_cls = re.match(r"^class (\w+)(?:\([^)]*\))?:$", stripped)
        if m_cls:
            current_class = m_cls.group(1)
            out.append(line)
            # Consume existing docstring (if any) directly below the class line
            j = i + 1
            ex_doc_consumed = False
            if j < n and lines[j].lstrip().startswith('"""'):
                ex_doc_consumed = True
                first_ds = lines[j]
                # Single-line docstring: contains two pairs of triple quotes
                if first_ds.count('"""') >= 2:
                    j += 1
                else:
                    j += 1
                    while j < n and '"""' not in lines[j]:
                        j += 1
                    if j < n:
                        j += 1
            new_doc = descriptions.get(current_class)
            if new_doc:
                out.extend(format_doc_block(new_doc, indent_prefix + "    "))
            elif ex_doc_consumed:
                out.extend(lines[i + 1 : j])
            i = j
            continue

        # @overload followed by def on/once
        if stripped == "@overload":
            out.append(line)
            j = i + 1
            if j < n:
                next_line = lines[j]
                m_ov = re.match(
                    r'^( +)def (on|once)\(self, event: Literal\["([^"]+)"\]\)'
                    r"\s*->\s*[^:]+:\s*\.\.\.\s*$",
                    next_line,
                )
                if m_ov:
                    ov_indent = m_ov.group(1)
                    event_name = m_ov.group(3)
                    doc = descriptions.get(f"event:{event_name}")
                    if doc:
                        # Replace ` : ...` with multi-line body; docstring alone
                        # is a valid Python body, so no trailing `...` needed —
                        # keeps ruff format from tightening blank lines away.
                        sig_part = next_line[:-4].rstrip()
                        out.append(sig_part)
                        out.extend(format_doc_block(doc, ov_indent + "    "))
                        i = j + 1
                        continue
                    # Rewrite `: ...` into multi-line `: pass` so E301 blank
                    # lines survive ruff format in .pyi files.
                    sig_part = next_line[:-4].rstrip()
                    out.append(sig_part)
                    out.append(f"{ov_indent}    pass")
                    i = j + 1
                    continue
            i += 1
            continue

        # Single-line method: `<indent>def name(...) -> T: ...`
        m_method_single = re.match(
            r"^( +)def (\w+)\([^)]*\)(?:\s*->\s*[^:]+)?:\s*\.\.\.\s*$", line
        )
        if m_method_single:
            m_indent = m_method_single.group(1)
            name = m_method_single.group(2)
            key = key_for_member(name)
            doc = descriptions.get(key)
            sig_part = line[:-4].rstrip()
            if doc:
                out.append(sig_part)
                out.extend(format_doc_block(doc, m_indent + "    "))
            else:
                out.append(sig_part)
                out.append(f"{m_indent}    pass")
            i += 1
            continue

        # Multi-line method: `<indent>def name(` then continuation lines
        m_method_start = re.match(r"^( +)def (\w+)\(\s*$", line)
        if m_method_start:
            m_indent = m_method_start.group(1)
            name = m_method_start.group(2)
            method_lines = [line]
            j = i + 1
            # Collect until we see either `    pass` or `...` or `: ...` tail
            while j < n:
                method_lines.append(lines[j])
                last_stripped = method_lines[-1].rstrip()
                if (
                    last_stripped.endswith("...")
                    or last_stripped == f"{m_indent}    pass"
                ):
                    j += 1
                    break
                j += 1
            last = method_lines[-1]
            key = key_for_member(name)
            doc = descriptions.get(key)
            if doc and last.rstrip().endswith(": ..."):
                # Old stub-style tail (shouldn't happen after render_method
                # update, kept for safety): strip trailing `: ...`, append doc.
                out.extend(method_lines[:-1])
                out.append(last.rstrip()[:-4].rstrip())
                out.extend(format_doc_block(doc, m_indent + "    "))
            elif doc and last.rstrip() == f"{m_indent}    pass":
                # New multi-line `pass` shape: replace the `pass` with docstring.
                out.extend(method_lines[:-1])
                out.extend(format_doc_block(doc, m_indent + "    "))
            else:
                out.extend(method_lines)
            i = j
            continue

        # Class attribute / property: `    name: Type` (skip type aliases at column 0)
        m_attr = re.match(r"^( +)(\w+): ", line)
        if m_attr and current_class:
            attr_indent = m_attr.group(1)
            name = m_attr.group(2)
            key = key_for_member(name)
            out.append(line)
            doc = descriptions.get(key)
            if doc:
                out.extend(format_doc_block(doc, attr_indent))
            i += 1
            continue

        # Module-level function: `def create_bot(...) -> Bot: ...`
        m_func = re.match(r"^def (\w+)\([^)]*\)(?:\s*->\s*[^:]+)?:\s*\.\.\.\s*$", line)
        if m_func:
            name = m_func.group(1)
            doc = descriptions.get(name)
            if doc:
                sig_part = line[:-4].rstrip()
                out.append(sig_part)
                out.extend(format_doc_block(doc, "    "))
                out.append("    ...")
            else:
                out.append(line)
            i += 1
            continue

        out.append(line)
        i += 1

    return "\n".join(out)


# --------------------------------------------------------------------------- #
#  TypeScript → Python type conversion
# --------------------------------------------------------------------------- #


TS_PRIMITIVES = {
    "string": "str",
    "number": "float",
    "boolean": "bool",
    "void": "None",
    "null": "None",
    "undefined": "None",
    "any": "object",
    "unknown": "object",
    "bigint": "int",
    "BigInt": "int",
    "object": "object",
    "Object": "object",
    "Function": "Callable[..., object]",
    "Buffer": "bytes",
    "this": "Self",
    "Error": "Exception",
    "RegExp": "object",
    "Date": "object",
    # Cross-package TS types with no locally-parsed d.ts — keep opaque.
    # (Registry / IndexedData live in prismarine-registry / minecraft-data;
    # Client / ClientOptions in minecraft-protocol; NBT, World, AStar are
    # internal helpers the student-facing API does not surface directly.)
    "NBT": "object",
    "ClientOptions": "object",
    "Client": "object",
    "Registry": "object",
    "IndexedData": "object",
    "World": "object",
    "AStar": "object",
    "PluginOptions": "dict[str, object]",
    "Plugin": "Callable[..., object]",
    "Callback": "Callable[..., None]",
}

# Re-exported name overrides
TS_NAME_REMAP = {
    "TypedEmitter": "object",  # TS utility; irrelevant for Python stubs
}

EVENT_CALLBACK_OVERRIDES = {
    "message": "Callable[[ChatMessage, MessagePosition], None]",
    "messagestr": "Callable[[str, MessagePosition, ChatMessage], None]",
}

# Parameter names and types for events whose callback signature comes from
# EVENT_CALLBACK_OVERRIDES (so there is no parsed arg list to reuse). Kept in
# parallel with EVENT_CALLBACK_OVERRIDES; used by the BotHandlers stub render.
EVENT_HANDLER_SIGNATURES: dict[str, list[tuple[str, str]]] = {
    "message": [("msg", "ChatMessage"), ("position", "MessagePosition")],
    "messagestr": [
        ("message", "str"),
        ("position", "MessagePosition"),
        ("json_msg", "ChatMessage"),
    ],
}


def split_top_level(text: str, sep: str) -> list[str]:
    """Split `text` by `sep`, skipping occurrences inside <>, {}, (), [] groups."""
    depth = {"<": 0, "{": 0, "(": 0, "[": 0}
    pairs = {">": "<", "}": "{", ")": "(", "]": "["}
    parts: list[str] = []
    buf = []
    for ch in text:
        if ch in depth:
            depth[ch] += 1
        elif ch in pairs:
            depth[pairs[ch]] = max(0, depth[pairs[ch]] - 1)
        at_top = all(v == 0 for v in depth.values())
        if ch == sep and at_top:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf).strip())
    return [p for p in parts if p]


def ts_to_py(ts: str) -> str:
    """Convert a TypeScript type expression to a Python type expression."""
    ts = ts.strip()
    if not ts:
        return "object"

    # Strip surrounding parens: (T) → T, but only if they wrap the whole thing
    while ts.startswith("(") and ts.endswith(")"):
        inner = ts[1:-1]
        if _balanced(inner):
            ts = inner.strip()
        else:
            break

    # Function type: (args) => R
    fn_match = re.match(r"^\((.*)\)\s*=>\s*(.+)$", ts, re.DOTALL)
    if fn_match:
        args_str, ret_str = fn_match.groups()
        arg_parts = split_top_level(args_str, ",") if args_str.strip() else []
        py_args: list[str] = []
        for arg in arg_parts:
            # Drop rest-spread marker
            arg = arg.lstrip(".").strip()
            # Pull off name?: type or name: type
            m = re.match(r"^(\w+)(\?)?\s*:\s*(.+)$", arg)
            if m:
                _, opt, type_str = m.groups()
                py = ts_to_py(type_str)
                if opt and py != "None":
                    py = f"{py} | None"
                py_args.append(py)
            else:
                py_args.append(ts_to_py(arg))
        ret_py = ts_to_py(ret_str)
        if not py_args:
            return f"Callable[[], {ret_py}]"
        return f"Callable[[{', '.join(py_args)}], {ret_py}]"

    # Intersection A & B — use first part (best-effort)
    if "&" in ts and _no_generic_ampersand(ts):
        parts = split_top_level(ts, "&")
        if parts and parts[0] != ts:
            return ts_to_py(parts[0])

    # Union
    union_parts = split_top_level(ts, "|")
    if len(union_parts) > 1:
        # Literal detection
        if all(_is_literal_token(p) for p in union_parts):
            return f"Literal[{', '.join(union_parts)}]"
        py_parts = [ts_to_py(p) for p in union_parts]
        # Deduplicate while preserving order
        seen = []
        for p in py_parts:
            if p not in seen:
                seen.append(p)
        # Move None to the end
        if "None" in seen:
            seen = [p for p in seen if p != "None"] + ["None"]
        return " | ".join(seen)

    # Array: T[]
    arr_match = re.match(r"^(.+)\[\]$", ts)
    if arr_match and _balanced(arr_match.group(1)):
        return f"list[{ts_to_py(arr_match.group(1))}]"

    # Tuple: [A, B, C]
    if ts.startswith("[") and ts.endswith("]"):
        inner = ts[1:-1]
        if _balanced(inner):
            parts = split_top_level(inner, ",")
            py = [ts_to_py(p) for p in parts]
            return f"tuple[{', '.join(py)}]"

    # Array<T>
    arr_g = re.match(r"^Array<(.+)>$", ts)
    if arr_g:
        return f"list[{ts_to_py(arr_g.group(1))}]"

    # Set<T>
    set_g = re.match(r"^Set<(.+)>$", ts)
    if set_g:
        return f"set[{ts_to_py(set_g.group(1))}]"

    # Record<K, V>
    record_g = re.match(r"^Record<.+?,\s*(.+)>$", ts)
    if record_g:
        return f"dict[str, {ts_to_py(record_g.group(1))}]"

    # IterableIterator<T>
    iterator_g = re.match(r"^IterableIterator<(.+)>$", ts)
    if iterator_g:
        return f"Iterator[{ts_to_py(iterator_g.group(1))}]"

    # Promise<T> — strip, sync return
    prom = re.match(r"^Promise<(.+)>$", ts)
    if prom:
        return ts_to_py(prom.group(1))

    # Partial<T> → T (loose)
    part = re.match(r"^Partial<(.+)>$", ts)
    if part:
        return ts_to_py(part.group(1))

    # Readonly<T> → T
    ro = re.match(r"^Readonly<(.+)>$", ts)
    if ro:
        return ts_to_py(ro.group(1))

    # Mapped dict type: { [k: string]: V } or { [K in Foo]: V }
    map_m = re.match(
        r"^\{\s*\[\s*\w+\s*(?::\s*\w+|\s+in\s+\w+)\s*\]\s*:\s*(.+?)\s*,?\s*\}$",
        ts,
        re.DOTALL,
    )
    if map_m:
        return f"dict[str, {ts_to_py(map_m.group(1))}]"

    # Literal primitives
    if re.match(r"^'[^']*'$", ts):
        return f"Literal[{ts}]"
    if re.match(r"^\"[^\"]*\"$", ts):
        return f"Literal[{ts}]"
    if re.match(r"^-?\d+(\.\d+)?$", ts):
        return f"Literal[{ts}]"
    if ts in ("true", "false"):
        return f"Literal[{ts.capitalize()}]"

    # Generic ref: Foo<T, U> — drop generic params
    gen = re.match(r"^([A-Za-z_]\w*)<.+>$", ts)
    if gen:
        return TS_NAME_REMAP.get(gen.group(1), gen.group(1))

    # Known primitive / remapped name
    if ts in TS_PRIMITIVES:
        return TS_PRIMITIVES[ts]
    if ts in TS_NAME_REMAP:
        return TS_NAME_REMAP[ts]

    # Keyof / typeof / other exotic — fall back to object
    if ts.startswith(("keyof ", "typeof ")):
        return "object"

    # Class / interface reference: keep the name as-is
    if re.match(r"^[A-Za-z_]\w*$", ts):
        return ts

    # Unknown — fall back to object
    return "object"


def _balanced(text: str) -> bool:
    # `=>` inside arrow-function types contributes a `>` that isn't part of a
    # generic closure; discount it so `(a: X) => Y` stays "balanced" and
    # outer-paren stripping / array detection work on function types.
    adjusted_gt = text.count(">") - text.count("=>")
    return (
        text.count("<") == adjusted_gt
        and text.count("(") == text.count(")")
        and text.count("[") == text.count("]")
        and text.count("{") == text.count("}")
    )


def _is_literal_token(token: str) -> bool:
    token = token.strip()
    if re.match(r"^'[^']*'$", token):
        return True
    if re.match(r"^\"[^\"]*\"$", token):
        return True
    if re.match(r"^-?\d+(\.\d+)?$", token):
        return True
    return False


def _no_generic_ampersand(ts: str) -> bool:
    # Naive: treat `&` outside <> / () as intersection
    depth = 0
    for ch in ts:
        if ch in "<({[":
            depth += 1
        elif ch in ">)}]":
            depth = max(0, depth - 1)
        elif ch == "&" and depth == 0:
            return True
    return False


# --------------------------------------------------------------------------- #
#  .d.ts block parsing
# --------------------------------------------------------------------------- #


@dataclass
class Member:
    name: str
    ts_type: str
    optional: bool = False
    is_method: bool = False
    params: str = ""  # Raw arg list for methods
    returns: str = "void"


@dataclass
class InterfaceBlock:
    name: str
    extends: list[str] = field(default_factory=list)
    members: list[Member] = field(default_factory=list)


def strip_ts_comments(text: str) -> str:
    """Remove `/* ... */` and `//` comments from TS source."""
    # Block comments
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    # Line comments (preserve URLs by only stripping from `//` after a column)
    text = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"(?<=\s)//.*$", "", text, flags=re.MULTILINE)
    return text


def find_interface(text: str, name: str) -> str | None:
    """Extract the body of `interface NAME { ... }` (balanced braces)."""
    pattern = rf"(?:export\s+)?interface\s+{re.escape(name)}\b[^{{]*\{{"
    m = re.search(pattern, text)
    if not m:
        return None
    start = m.end()  # Position after opening brace
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i]
        i += 1
    return None


def find_interface_extends(text: str, name: str) -> list[str]:
    pattern = rf"(?:export\s+)?interface\s+{re.escape(name)}\s+extends\s+([^{{]+)\{{"
    m = re.search(pattern, text)
    if not m:
        return []
    raw = m.group(1).strip()
    # Split by comma, strip generics
    parts = split_top_level(raw, ",")
    out = []
    for p in parts:
        base = re.sub(r"<.*>", "", p).strip()
        if base:
            out.append(base)
    return out


def find_class(text: str, name: str) -> str | None:
    """Extract the body of `export [declare ]class NAME [extends ...] { ... }`."""
    pattern = rf"export\s+(?:declare\s+)?class\s+{re.escape(name)}\b[^{{]*\{{"
    m = re.search(pattern, text)
    if not m:
        return None
    start = m.end()
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i]
        i += 1
    return None


def parse_members(body: str) -> list[Member]:
    """Parse interface/class body into Member list.

    Handles:
    - `name: type` (property)
    - `name?: type` (optional property)
    - `name(args): return` (method)
    - `name?(args): return` (optional method)

    Splits on top-level `;` or newline boundaries.
    """
    # Normalize: drop leading `readonly`, `static`, access modifiers, `get `, `set `, `declare `
    body = body.strip()

    # Members are separated by `;` or newlines; but function types span multiple lines.
    # We scan token-by-token, tracking depth and splitting at top-level `;` or top-level newline
    # that isn't inside a type declaration.

    members: list[Member] = []
    i = 0
    while i < len(body):
        # Skip whitespace / semicolons
        while i < len(body) and body[i] in " \t\n;,":
            i += 1
        if i >= len(body):
            break

        start = i
        depth = 0
        # Scan until top-level `;`, newline at top-level, or end
        while i < len(body):
            ch = body[i]
            if ch in "<({[":
                depth += 1
            elif ch in ">)}]":
                depth = max(0, depth - 1)
            elif ch in ";" and depth == 0:
                break
            elif ch == "\n" and depth == 0:
                # But only treat newline as separator if the next non-space char
                # starts a new member (identifier-ish) or closes the block
                j = i + 1
                while j < len(body) and body[j] in " \t\r":
                    j += 1
                if j >= len(body):
                    break
                # Looks like a new member if next line starts with identifier
                if re.match(r"[A-Za-z_]|['\"]|\}", body[j]):
                    break
            i += 1

        raw_member = body[start:i].strip()
        if raw_member:
            parsed = _parse_single_member(raw_member)
            if parsed:
                members.append(parsed)
        # Skip the separator
        i += 1
    return members


def _parse_single_member(raw: str) -> Member | None:
    """Parse one member declaration."""
    # Drop modifiers
    raw = re.sub(
        r"^\s*(public|private|protected|readonly|static|declare|get|set)\s+",
        "",
        raw,
    )
    raw = raw.strip()
    if not raw:
        return None

    # Constructor — skip for our purposes (Python users don't call class constructors
    # directly for these proxies)
    if raw.startswith("constructor"):
        return None

    # Quoted key: 'foo'(args): ret or 'foo': type
    quoted_match = re.match(r"^(['\"])([^'\"]+)\1\s*(.*)$", raw, re.DOTALL)
    if quoted_match:
        name = quoted_match.group(2)
        rest = quoted_match.group(3).strip()
    else:
        ident_match = re.match(r"^([A-Za-z_]\w*)(\??)(.*)$", raw, re.DOTALL)
        if not ident_match:
            return None
        name = ident_match.group(1)
        opt_mark = ident_match.group(2)
        rest = ident_match.group(3).strip()

    optional = False
    if not quoted_match:
        optional = opt_mark == "?"

    # Method signature: `(args): return` or `(args)`
    if rest.startswith("("):
        # Balance-scan to end of args
        depth = 1
        j = 1
        while j < len(rest) and depth > 0:
            if rest[j] == "(":
                depth += 1
            elif rest[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        args_str = rest[1:j]
        after = rest[j + 1 :].strip()
        if after.startswith(":"):
            returns = after[1:].strip()
        else:
            returns = "void"
        return Member(
            name=name,
            ts_type="",
            optional=optional,
            is_method=True,
            params=args_str,
            returns=returns,
        )

    # Property: `: type`
    if rest.startswith(":"):
        ts_type = rest[1:].strip()
        # Remove trailing comma/semicolon
        ts_type = ts_type.rstrip(",;").strip()
        return Member(name=name, ts_type=ts_type, optional=optional)

    # No match
    return None


def _parse_arrow_fn_args(ts_type: str) -> list[tuple[str, str]]:
    """Extract named params from a TS arrow-function type like ``(a: X) => Y``."""
    ts_type = ts_type.strip()
    if not ts_type.startswith("("):
        return []
    depth = 0
    end = -1
    for i, ch in enumerate(ts_type):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0:
        return []
    args = parse_method_args(ts_type[1:end])
    return [(_py_name(n), py) for n, py, _opt in args]


def parse_method_args(params: str) -> list[tuple[str, str, bool]]:
    """Parse a TS method argument list → list of (py_name, py_type, has_default)."""
    if not params.strip():
        return []
    parts = split_top_level(params, ",")
    out: list[tuple[str, str, bool]] = []
    for raw in parts:
        raw = raw.strip().lstrip(".").strip()  # strip rest-spread
        m = re.match(r"^(\w+)(\?)?\s*:\s*(.+)$", raw, re.DOTALL)
        if not m:
            # Bare param with no type
            name = raw.split(":", 1)[0].strip().rstrip("?")
            out.append((_py_name(name), "object", False))
            continue
        name, opt, ts_type = m.groups()
        py_type = ts_to_py(ts_type)
        has_default = bool(opt)
        if has_default and "None" not in py_type:
            py_type = f"{py_type} | None"
        out.append((_py_name(name), py_type, has_default))
    return out


_PY_KEYWORDS = {
    # Hard keywords
    "class",
    "def",
    "if",
    "else",
    "for",
    "while",
    "return",
    "from",
    "import",
    "is",
    "and",
    "or",
    "not",
    "in",
    "as",
    "with",
    "yield",
    "lambda",
    "pass",
    "raise",
    "try",
    "except",
    "finally",
    "global",
    "nonlocal",
    "assert",
    "break",
    "continue",
    "del",
    "elif",
    "True",
    "False",
    "None",
    # Common builtins worth shadowing with a trailing underscore
    "type",
    "hash",
    "id",
    "list",
    "dict",
    "set",
    "str",
    "int",
    "float",
    "bool",
    "bytes",
    "input",
    "format",
    "filter",
    "map",
    "range",
    "len",
    "open",
    "print",
}


def _py_name(name: str) -> str:
    """Convert JS camelCase → snake_case and dodge Python reserved words."""
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    snake = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", snake).lower()
    if snake in _PY_KEYWORDS:
        return f"{snake}_"
    return snake


# --------------------------------------------------------------------------- #
#  External-type Protocol stubs (from vec3 / prismarine-* .d.ts)
# --------------------------------------------------------------------------- #


EXTERNAL_STUBS = '''\
# --- External types (from vec3 / prismarine-* packages) ---
# These are Protocol stubs mirroring the fields/methods used by mineflayer.
# Ref: src/mineflayer/js/node_modules/<pkg>/index.d.ts

class Vec3:
    """3D vector (from `vec3` package).

    Ref: vec3/index.d.ts — Vec3
    """
    x: float
    y: float
    z: float
    def isZero(self) -> bool: ...
    def at(self, id: int) -> float: ...
    def xz(self) -> tuple[float, float]: ...
    def xy(self) -> tuple[float, float]: ...
    def yz(self) -> tuple[float, float]: ...
    def xzy(self) -> Vec3: ...
    def set(self, x: float, y: float, z: float) -> Self: ...
    def update(self, other: Vec3) -> Self: ...
    def rounded(self) -> Vec3: ...
    def round(self) -> Self: ...
    def floored(self) -> Vec3: ...
    def floor(self) -> Self: ...
    def offset(self, dx: float, dy: float, dz: float) -> Vec3: ...
    def translate(self, dx: float, dy: float, dz: float) -> Self: ...
    def add(self, other: Vec3) -> Self: ...
    def subtract(self, other: Vec3) -> Self: ...
    def multiply(self, other: Vec3) -> Self: ...
    def divide(self, other: Vec3) -> Self: ...
    def plus(self, other: Vec3) -> Vec3: ...
    def minus(self, other: Vec3) -> Vec3: ...
    def scaled(self, scalar: float) -> Vec3: ...
    def abs(self) -> Vec3: ...
    def volume(self) -> float: ...
    def modulus(self, other: Vec3) -> Vec3: ...
    def distanceTo(self, other: Vec3) -> float: ...
    def distanceSquared(self, other: Vec3) -> float: ...
    def equals(self, other: Vec3, error: float = ...) -> bool: ...
    def toString(self) -> str: ...
    def clone(self) -> Vec3: ...
    def min(self, other: Vec3) -> Vec3: ...
    def max(self, other: Vec3) -> Vec3: ...
    def norm(self) -> float: ...
    def dot(self, other: Vec3) -> float: ...
    def cross(self, other: Vec3) -> Vec3: ...
    def unit(self) -> Vec3: ...
    def normalize(self) -> Vec3: ...
    def scale(self, scalar: float) -> Self: ...
    def xyDistanceTo(self, other: Vec3) -> float: ...
    def xzDistanceTo(self, other: Vec3) -> float: ...
    def yzDistanceTo(self, other: Vec3) -> float: ...
    def innerProduct(self, other: Vec3) -> float: ...
    def manhattanDistanceTo(self, other: Vec3) -> float: ...
    def toArray(self) -> tuple[float, float, float]: ...


class ChatMessageScore:
    """Score payload inside a `ChatMessage`.

    Ref: prismarine-chat/index.d.ts — ChatMessage.score
    """
    name: str
    objective: str


class ChatMessage:
    """Minecraft chat message (from `prismarine-chat` package).

    Ref: prismarine-chat/index.d.ts — ChatMessage
    """
    json: object
    extra: list[ChatMessage] | None
    translate: str | None
    selector: str | None
    keybind: str | None
    score: ChatMessageScore | None
    def append(self, *messages: object) -> None: ...
    def clone(self) -> ChatMessage: ...
    def toString(self, language: object = ...) -> str: ...
    def toMotd(self, language: object = ...) -> str: ...
    def toAnsi(self, language: object = ...) -> str: ...
    def toHTML(self, language: object = ..., styles: object = ...) -> str: ...
    def length(self) -> int: ...
    def getText(self, idx: int, language: object = ...) -> str: ...
    def valueOf(self) -> str: ...
    @staticmethod
    def fromNotch(str: str) -> ChatMessage: ...
    @staticmethod
    def fromNetwork(messageType: int, parameters: dict[str, object]) -> ChatMessage: ...


EntityType = Literal['player', 'mob', 'object', 'global', 'orb', 'projectile', 'hostile', 'other']


class Effect:
    """Potion effect on an entity.

    Ref: prismarine-entity/index.d.ts — Effect
    """
    id: int
    amplifier: int
    duration: int


class Entity:
    """A world entity (player, mob, dropped item, projectile, etc.).

    Ref: prismarine-entity/index.d.ts — Entity
    """
    id: int
    type: EntityType
    uuid: str | None
    username: str | None
    mobType: str | None
    displayName: str | None
    entityType: int | None
    kind: str | None
    name: str | None
    objectType: str | None
    count: int | None
    position: Vec3
    velocity: Vec3
    yaw: float
    pitch: float
    height: float
    width: float
    onGround: bool
    equipment: list[Item]
    heldItem: Item
    metadata: list[object]
    isValid: bool
    health: float | None
    food: float | None
    foodSaturation: float | None
    elytraFlying: bool | None
    player: object | None
    effects: list[Effect]
    vehicle: Entity
    passengers: list[Entity]
    def setEquipment(self, index: int, item: Item) -> None: ...
    def getCustomName(self) -> ChatMessage | None: ...
    def getDroppedItem(self) -> Item | None: ...


class Block:
    """A world block.

    Ref: prismarine-block/index.d.ts — Block
    """
    stateId: int
    type: int
    metadata: int
    light: int
    skyLight: int
    blockEntity: object
    entity: object | None
    hash: int | None
    biome: object
    name: str
    displayName: str
    shapes: list[tuple[float, float, float, float, float, float]]
    hardness: float
    boundingBox: Literal['block', 'empty']
    transparent: bool
    diggable: bool
    isWaterlogged: bool | None
    material: str | None
    harvestTools: dict[str, bool] | None
    position: Vec3
    def canHarvest(self, heldItemType: int | None) -> bool: ...
    def getProperties(self) -> dict[str, object]: ...
    def digTime(
        self,
        heldItemType: int | None,
        creative: bool,
        inWater: bool,
        notOnGround: bool,
        enchantments: object = ...,
        effects: list[Effect] | None = ...,
    ) -> float: ...


class Item:
    """An inventory item.

    Ref: prismarine-item/index.d.ts — Item
    """
    type: int
    slot: int
    count: int
    metadata: int
    nbt: object | None
    stackId: int | None
    name: str
    displayName: str
    stackSize: int
    maxDurability: int
    durabilityUsed: int
    enchants: list[dict[str, object]]
    blocksCanPlaceOn: list[tuple[str]]
    blocksCanDestroy: list[tuple[str]]
    repairCost: int
    customName: str | None
    customLore: str | list[str] | None
    customModel: str | None
    spawnEggMobName: str


class Window:
    """An open window / container (chest, furnace, inventory, etc.).

    Ref: prismarine-windows/index.d.ts — Window
    """
    id: int
    type: int | str
    title: str
    slots: list[Item | None]
    inventoryStart: int
    inventoryEnd: int
    hotbarStart: int
    craftingResultSlot: int
    requiresConfirmation: bool
    selectedItem: Item | None
    def findInventoryItem(
        self, itemType: int, metadata: int | None, notFull: bool
    ) -> Item | None: ...
    def findContainerItem(
        self, itemType: int, metadata: int | None, notFull: bool
    ) -> Item | None: ...
    def firstEmptySlotRange(self, start: int, end: int) -> int | None: ...
    def firstEmptyHotbarSlot(self) -> int | None: ...
    def firstEmptyContainerSlot(self) -> int | None: ...
    def firstEmptyInventorySlot(self, hotbarFirst: bool = ...) -> int | None: ...
    def items(self) -> list[Item]: ...
    def containerItems(self) -> list[Item]: ...
    def count(self, itemType: int | str, metadata: int | None) -> int: ...
    def emptySlotCount(self) -> int: ...


class Recipe:
    """A crafting recipe.

    Ref: prismarine-recipe/index.d.ts — Recipe
    """
    result: object
    inShape: list[list[object]]
    outShape: list[list[object]]
    ingredients: list[object]
    delta: list[object]
    requiresTable: bool


# --- mineflayer-pathfinder stubs ---
# Only pathfinder gets a typed wrapper (AGENTS.md: all other plugins go
# through `bot.require(...)` and their own README).
# Ref: node_modules/mineflayer-pathfinder/index.d.ts

class Move:
    x: float
    y: float
    z: float
    cost: float
    remainingBlocks: int
    toBreak: list[Move]
    toPlace: list[Move]
    parkour: bool
    hash: str


class Goal:
    """Base class for all pathfinder goals."""
    def heuristic(self, node: Move) -> float: ...
    def isEnd(self, node: Move) -> bool: ...
    def hasChanged(self) -> bool: ...
    def isValid(self) -> bool: ...


class GoalBlock(Goal):
    """Reach this exact block (integer coords)."""
    x: float
    y: float
    z: float
    def __init__(self, x: float, y: float, z: float) -> None: ...


class GoalNear(Goal):
    """Reach within `range` blocks of (x, y, z)."""
    x: float
    y: float
    z: float
    rangeSq: float
    def __init__(self, x: float, y: float, z: float, range: float) -> None: ...


class GoalXZ(Goal):
    """Reach the XZ column, any Y."""
    x: float
    z: float
    def __init__(self, x: float, z: float) -> None: ...


class GoalNearXZ(Goal):
    """Reach within `range` blocks of (x, z) column, any Y."""
    x: float
    z: float
    rangeSq: float
    def __init__(self, x: float, z: float, range: float) -> None: ...


class GoalY(Goal):
    """Reach the given Y level."""
    y: float
    def __init__(self, y: float) -> None: ...


class GoalGetToBlock(Goal):
    """Get adjacent to (not on) the block at (x, y, z) — e.g. reach a chest."""
    x: float
    y: float
    z: float
    def __init__(self, x: float, y: float, z: float) -> None: ...


class GoalFollow(Goal):
    """Follow an entity, staying within `range` blocks."""
    x: float
    y: float
    z: float
    entity: Entity
    rangeSq: float
    def __init__(self, entity: Entity, range: float) -> None: ...


class GoalCompositeAll(Goal):
    """Only satisfied when ALL sub-goals are reached."""
    def __init__(self, goals: list[Goal] = ...) -> None: ...
    def push(self, goal: Goal) -> None: ...


class GoalCompositeAny(Goal):
    """Satisfied when ANY sub-goal is reached."""
    def __init__(self, goals: list[Goal] = ...) -> None: ...
    def push(self, goal: Goal) -> None: ...


class GoalInvert(Goal):
    """Avoid another goal (move AWAY from it)."""
    def __init__(self, goal: Goal) -> None: ...


class GoalPlaceBlock(Goal):
    pos: Vec3
    world: object
    options: object
    def __init__(self, pos: Vec3, world: object, options: object) -> None: ...


class GoalLookAtBlock(Goal):
    pos: Vec3
    reach: float
    entityHeight: float
    world: object
    def __init__(self, pos: Vec3, world: object, options: object | None = ...) -> None: ...


class GoalBreakBlock(GoalLookAtBlock):
    pass


class Goals:
    """Container exposing pathfinder's goal constructors.

    Accessed via `pf.goals.GoalNear(...)` where
    `pf = bot.load_plugin('mineflayer-pathfinder')`.
    """
    Goal: type[Goal]
    GoalBlock: type[GoalBlock]
    GoalNear: type[GoalNear]
    GoalXZ: type[GoalXZ]
    GoalNearXZ: type[GoalNearXZ]
    GoalY: type[GoalY]
    GoalGetToBlock: type[GoalGetToBlock]
    GoalFollow: type[GoalFollow]
    GoalCompositeAll: type[GoalCompositeAll]
    GoalCompositeAny: type[GoalCompositeAny]
    GoalInvert: type[GoalInvert]
    GoalPlaceBlock: type[GoalPlaceBlock]
    GoalLookAtBlock: type[GoalLookAtBlock]
    GoalBreakBlock: type[GoalBreakBlock]


class Movements:
    """Per-bot pathfinder movement configuration.

    Construct with `pf.Movements(bot)`, tweak flags/costs, then call
    `bot.pathfinder.setMovements(move)`.
    """
    canDig: bool
    canOpenDoors: bool
    allow1by1towers: bool
    allowFreeMotion: bool
    allowParkour: bool
    allowSprinting: bool
    allowEntityDetection: bool
    dontCreateFlow: bool
    dontMineUnderFallingBlock: bool
    digCost: float
    placeCost: float
    entityCost: float
    maxDropDown: int
    exclusionAreasStep: list[Callable[[Block], float]]
    exclusionAreasBreak: list[Callable[[Block], float]]
    exclusionAreasPlace: list[Callable[[Block], float]]
    def __init__(self, bot: object) -> None: ...
    def countScaffoldingItems(self) -> int: ...
    def getScaffoldingItem(self) -> Item | None: ...
    def clearCollisionIndex(self) -> None: ...
    def updateCollisionIndex(self) -> None: ...


class Pathfinder:
    """Runtime pathfinder API — attached to the bot as `bot.pathfinder`.

    Only available after `bot.load_plugin('mineflayer-pathfinder')`.
    Ref: node_modules/mineflayer-pathfinder/index.d.ts — Pathfinder
    """
    thinkTimeout: int
    tickTimeout: int
    goal: Goal | None
    movements: Movements
    def setGoal(self, goal: Goal | None, dynamic: bool = ...) -> None: ...
    def setMovements(self, movements: Movements) -> None: ...
    def getPathTo(
        self, movements: Movements, goal: Goal, timeout: float | None = ...
    ) -> ComputedPath: ...
    def getPathFromTo(
        self,
        movements: Movements,
        startPos: Vec3 | None,
        goal: Goal,
        options: object | None = ...,
    ) -> Iterator[object]: ...
    def goto(self, goal: Goal) -> None: ...
    def stop(self) -> None: ...
    def isMoving(self) -> bool: ...
    def isMining(self) -> bool: ...
    def isBuilding(self) -> bool: ...
    def bestHarvestTool(self, block: Block) -> Item | None: ...


PathComputationStatus = Literal['noPath', 'timeout', 'success']
PartialPathComputationStatus = Literal['noPath', 'timeout', 'success', 'partial']
PathResetReason = Literal[
    'goal_updated',
    'movements_updated',
    'block_updated',
    'chunk_loaded',
    'goal_moved',
    'dig_error',
    'no_scaffolding_blocks',
    'place_error',
    'stuck',
]


class ComputedPath:
    cost: float
    time: float
    visitedNodes: int
    generatedNodes: int
    path: list[Move]
    status: PathComputationStatus


class PartiallyComputedPath:
    cost: float
    time: float
    visitedNodes: int
    generatedNodes: int
    path: list[Move]
    status: PartialPathComputationStatus


class PathfinderModule:
    """The npm module returned by `bot.load_plugin('mineflayer-pathfinder')`.

    Ref: node_modules/mineflayer-pathfinder/index.d.ts — top-level exports
    """
    pathfinder: Callable[[Bot], None]
    goals: Goals
    Movements: type[Movements]
'''


# --------------------------------------------------------------------------- #
#  Emission helpers
# --------------------------------------------------------------------------- #


# Source-verified overrides for fields whose runtime value can be `None`
# before login/spawn or after the entity disappears. JSPyBridge returns
# missing/null JS properties as Python `None`, so the stub must reflect that
# even when upstream `.d.ts` types them as non-null.
# Ref:
#   mineflayer/lib/plugins/entities.js — `bot.entity` / `player.entity` assign
#   mineflayer/lib/plugins/digging.js  — `bot.targetDigBlock` reset to null
NULLABLE_FIELD_OVERRIDES: frozenset[str] = frozenset(
    {
        "Bot.username",
        "Bot.entity",
        "Bot.targetDigBlock",
        "Player.entity",
    }
)

# Source-verified overrides for fields whose runtime value is a raw JSPyBridge
# proxy, not a real Python dict. The proxy supports `__getitem__`, `__iter__`,
# and `__contains__` but NOT `.keys()` / `.items()` / `len(...)`; typing it as
# `dict[...]` mis-teaches the IDE. Expose as `Mapping` until a real wrapper
# ships (see AGENTS.md "當前狀態" — collection wrapper TODO).
MAPPING_FIELD_OVERRIDES: dict[str, str] = {
    "Bot.players": "Mapping[str, Player]",
    "Bot.entities": "Mapping[str, Entity]",
}


_ARROW_FN_RE = re.compile(r"^\((.*)\)\s*=>\s*(.+)$", re.DOTALL)


def _as_method_if_arrow(member: Member) -> Member:
    """Return a method-shaped Member when `member` is a `name: (args) => ret` property.

    Mineflayer declares most Bot methods as arrow-typed properties. Rendering
    them as `name: Callable[...]` loses parameter names — a critical hit to
    IDE completion for a teaching SDK. This helper reshapes them so
    `render_method` emits `def name(self, message: str) -> None: pass`
    instead.

    If the ts_type is an intersection of arrow types (e.g. `dig`), the first
    overload is used as the primary signature; that matches the historical
    fallback behaviour but no longer mangles brackets.
    """
    if member.is_method or not member.ts_type:
        return member
    ts = member.ts_type.strip()
    # Peel the leading overload from an intersection type.
    if "&" in ts and _no_generic_ampersand(ts):
        head = split_top_level(ts, "&")[0]
        ts = head.strip()
    # Strip redundant wrapping parens around an arrow type.
    while ts.startswith("(") and ts.endswith(")") and _balanced(ts[1:-1]):
        ts = ts[1:-1].strip()
    arrow = _ARROW_FN_RE.match(ts)
    if not arrow:
        return member
    return Member(
        name=member.name,
        ts_type="",
        optional=member.optional,
        is_method=True,
        params=arrow.group(1),
        returns=arrow.group(2),
    )


def render_property(member: Member, *, class_name: str | None = None) -> str:
    qualified = f"{class_name}.{member.name}" if class_name else ""
    if qualified in MAPPING_FIELD_OVERRIDES:
        return f"    {member.name}: {MAPPING_FIELD_OVERRIDES[qualified]}"
    py_type = ts_to_py(member.ts_type)
    if member.optional and "None" not in py_type:
        py_type = f"{py_type} | None"
    if qualified in NULLABLE_FIELD_OVERRIDES and "None" not in py_type:
        py_type = f"{py_type} | None"
    return f"    {member.name}: {py_type}"


def render_method(member: Member) -> str:
    """Emit a method with a multi-line ``pass`` body.

    Multi-line ``pass`` bodies (instead of stub-style ``def foo(): ...``) are
    required so that ruff format preserves blank lines between methods in
    ``.pyi`` files — PyCharm's PEP 8 checker fires E301 otherwise.
    """
    args = parse_method_args(member.params)
    ret_py = ts_to_py(member.returns)
    parts = ["self"]
    for name, py_type, has_default in args:
        default = " = ..." if has_default else ""
        parts.append(f"{name}: {py_type}{default}")
    return f"    def {member.name}({', '.join(parts)}) -> {ret_py}:\n        pass"


def render_interface(
    name: str, body: str, *, ref_path: str = "mineflayer/index.d.ts"
) -> list[str]:
    """Render a mineflayer interface body as a Python class.

    Spacing rule: blank line before each method (PEP 8 E301), but properties
    stay tight — consecutive attributes read as a single declaration block.
    """
    members = parse_members(body)
    lines = [f"class {name}:", f'    """Ref: {ref_path} — {name}"""']
    if not members:
        lines.append("    pass")
        return lines
    for raw in members:
        m = _as_method_if_arrow(raw)
        if m.is_method:
            lines.append("")  # blank line before each method for E301
            lines.append(render_method(m))
        else:
            lines.append(render_property(m, class_name=name))
    return lines


def render_type_alias(name: str, ts_expr: str) -> str:
    py = ts_to_py(ts_expr)
    return f"{name} = {py}"


# --------------------------------------------------------------------------- #
#  Event-specific rendering
# --------------------------------------------------------------------------- #


def render_bot_events(
    events_body: str,
) -> tuple[list[str], list[tuple[str, str, list[tuple[str, str]]]]]:
    """Parse BotEvents body, emit callback type aliases.

    Returns the alias lines and a list of ``(event, alias, handler_args)``
    where ``handler_args`` is the ``[(name, py_type)]`` list used to render
    ``BotHandlers.on_<event>`` signatures.
    """
    members = parse_members(events_body)
    lines: list[str] = ["# --- Event callback type aliases ---"]
    event_callbacks: list[tuple[str, str, list[tuple[str, str]]]] = []
    for m in members:
        if not m.is_method and not m.ts_type:
            continue
        override = EVENT_CALLBACK_OVERRIDES.get(m.name)
        if override is not None:
            alias = f"_OnEvent_{_sanitize_alias(m.name)}"
            lines.append(f"{alias} = {override}")
            handler_args = list(EVENT_HANDLER_SIGNATURES.get(m.name, []))
            event_callbacks.append((m.name, alias, handler_args))
            continue
        # Each event is declared as a property whose type is a function:
        # `chat: (username: string, message: string, ...) => Promise<void> | void`
        # But our parse_members may emit it as `is_method=True` if we catch the "("...
        # Fix: events body member either has ts_type starting with "(" OR is_method due
        # to our argument-list detection.
        handler_args: list[tuple[str, str]] = []
        if m.is_method:
            # Build a Callable from params + returns
            args = parse_method_args(m.params)
            ret_py = ts_to_py(m.returns)
            py_args = [py for _, py, _ in args]
            cb_type = (
                f"Callable[[{', '.join(py_args)}], {ret_py}]"
                if py_args
                else f"Callable[[], {ret_py}]"
            )
            handler_args = [(_py_name(n), py) for n, py, _opt in args]
        else:
            cb_type = ts_to_py(m.ts_type)
            # Property-style event: `chat: (a: X, b: Y) => void`. Recover the
            # named parameter list so BotHandlers.on_<event> can be fully typed.
            handler_args = _parse_arrow_fn_args(m.ts_type)
        alias = f"_OnEvent_{_sanitize_alias(m.name)}"
        lines.append(f"{alias} = {cb_type}")
        event_callbacks.append((m.name, alias, handler_args))
    return lines, event_callbacks


def _sanitize_alias(name: str) -> str:
    """Event names like 'blockUpdate:(x, y, z)' → identifier-safe."""
    return re.sub(r"\W", "_", name)


def _event_member_name(event: str) -> str:
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", event)
    snake = re.sub(r"\W+", "_", snake).strip("_")
    return snake.upper()


def _event_attr_name(event: str, *, prefix: str) -> str:
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", event)
    snake = re.sub(r"\W+", "_", snake).strip("_").lower()
    return f"{prefix}_{snake}"


def render_event_enum(
    event_callbacks: list[tuple[str, str, list[tuple[str, str]]]],
) -> list[str]:
    lines = [
        "class BotEvent(StrEnum):",
        '    """Source-verified mineflayer event names."""',
    ]
    for event, _alias, _args in event_callbacks:
        lines.append(f'    {_event_member_name(event)} = "{event}"')
    return lines


def render_event_decorator_aliases(
    event_callbacks: list[tuple[str, str, list[tuple[str, str]]]],
    method: str,
) -> list[str]:
    lines: list[str] = []
    for event, alias, _args in event_callbacks:
        attr_name = _event_attr_name(event, prefix=method)
        member = _event_member_name(event)
        lines.append(f"    {attr_name}: Callable[[{alias}], {alias}]")
        lines.append(f'    """Same as `bot.{method}(BotEvent.{member})`. """')
    return lines


def render_on_overloads(
    event_callbacks: list[tuple[str, str, list[tuple[str, str]]]],
    method: str,
) -> list[str]:
    """Emit @overload defs for `on` or `once`."""
    lines: list[str] = []
    for event, alias, _args in event_callbacks:
        member = _event_member_name(event)
        lines.append("    @overload")
        lines.append(
            f"    def {method}(self, event: Literal[BotEvent.{member}]) -> "
            f"Callable[[{alias}], {alias}]: ..."
        )
    # No string overload on purpose — public API only accepts BotEvent.
    return lines


# --------------------------------------------------------------------------- #
#  Bot rendering
# --------------------------------------------------------------------------- #


def render_bot(
    bot_body: str,
    event_callbacks: list[tuple[str, str, list[tuple[str, str]]]],
) -> list[str]:
    members = parse_members(bot_body)
    lines = [
        "class Bot:",
        '    """Pythonic façade over a mineflayer Bot proxy.\n\n'
        "    Every property and method below mirrors mineflayer's Bot interface.\n\n"
        '    Ref: mineflayer/index.d.ts — interface Bot\n    """',
        "    def __init__(self, js_bot: object) -> None: ...",
    ]
    # Skip private `_client` field (exposed as raw JS only)
    for raw in members:
        if raw.name.startswith("_"):
            continue
        m = _as_method_if_arrow(raw)
        if m.is_method:
            lines.append(render_method(m))
        else:
            lines.append(render_property(m, class_name="Bot"))

    # Event overloads
    lines.append("")
    lines.append("    # --- Typed event overloads (generated from BotEvents) ---")
    lines.extend(render_on_overloads(event_callbacks, "on"))
    lines.append("")
    lines.append(
        "    # Shortcut decorators for better IDE completion in JetBrains/Pylance"
    )
    lines.extend(render_event_decorator_aliases(event_callbacks, "on"))
    lines.append("")
    lines.extend(render_on_overloads(event_callbacks, "once"))
    lines.append("")
    lines.extend(render_event_decorator_aliases(event_callbacks, "once"))
    lines.append("")
    # Minethon-specific additions — defined in bot.py at runtime.
    lines.append("    # --- Minethon-specific methods (defined in bot.py) ---")
    lines.append("    # Populated after bot.load_plugin('mineflayer-pathfinder'):")
    lines.append("    pathfinder: Pathfinder")
    lines.append("")
    lines.append("    @overload")
    lines.append("    def load_plugin(")
    lines.append("        self,")
    lines.append('        name: Literal["mineflayer-pathfinder"],')
    lines.append("        version: str | None = ...,")
    lines.append("        *,")
    lines.append("        export_key: str | None = ...,")
    lines.append("        **options: object,")
    lines.append("    ) -> PathfinderModule: ...")
    lines.append("    @overload")
    lines.append("    def load_plugin(")
    lines.append("        self,")
    lines.append("        name: str,")
    lines.append("        version: str | None = ...,")
    lines.append("        *,")
    lines.append("        export_key: str | None = ...,")
    lines.append("        **options: object,")
    lines.append("    ) -> object: ...")
    lines.append(
        "    def require(self, name: str, version: str | None = ...) -> object: ..."
    )
    lines.append("    def run_forever(self) -> None: ...")
    return lines


# --------------------------------------------------------------------------- #
#  Options & createBot
# --------------------------------------------------------------------------- #


def _bot_options_members(body: str) -> list[Member]:
    """Parse BotOptions body and merge in ClientOptions common fields."""
    members = parse_members(body)
    # minecraft-protocol ClientOptions (merged in) — surface the common fields
    extras = [
        Member(name="host", ts_type="string"),
        Member(name="port", ts_type="number"),
        Member(name="username", ts_type="string"),
        Member(name="password", ts_type="string", optional=True),
        Member(name="version", ts_type="string", optional=True),
        Member(
            name="auth", ts_type="'mojang' | 'microsoft' | 'offline'", optional=True
        ),
        Member(name="authServer", ts_type="string", optional=True),
        Member(name="sessionServer", ts_type="string", optional=True),
        Member(name="onMsaCode", ts_type="(data: object) => void", optional=True),
        Member(name="authTitle", ts_type="string", optional=True),
    ]
    parsed_names = {m.name for m in members}
    for extra in extras:
        if extra.name not in parsed_names:
            members.append(extra)
    return members


def render_bot_options(body: str) -> list[str]:
    """BotOptions → TypedDict (total=False since most are optional).

    Mirrors mineflayer's camelCase keys verbatim — power-user surface that
    lets callers build an options dict and splat it as-is into the JS layer.
    """
    members = _bot_options_members(body)
    lines = [
        "class BotOptions(TypedDict, total=False):",
        '    """Raw mineflayer options (camelCase).\n\n'
        "    Matches mineflayer's `BotOptions` exactly — useful when you\n"
        "    need to construct options programmatically. For the common\n"
        "    keyword-argument path, prefer `create_bot(host=..., "
        "auth_server=...)`\n"
        "    which is typed by `CreateBotOptions` (snake_case).\n\n"
        '    Ref: mineflayer/index.d.ts — interface BotOptions\n    """',
    ]
    for m in members:
        if m.is_method:
            # TypedDict can't hold methods — serialize as callable prop
            continue
        py_type = ts_to_py(m.ts_type)
        lines.append(f"    {m.name}: {py_type}")
    return lines


def render_create_bot_options(body: str) -> list[str]:
    """CreateBotOptions → TypedDict with snake_case keys.

    Mirrors BotOptions but uses the public snake_case spelling that
    `create_bot(**opts)` accepts — `bot.py` converts each key to camelCase
    before handing the dict to `mineflayer.createBot()`.
    """
    members = _bot_options_members(body)
    lines = [
        "class CreateBotOptions(TypedDict, total=False):",
        '    """Snake-case options accepted by `create_bot(**opts)`.\n\n'
        "    Every field mirrors `BotOptions` but uses the Python spelling\n"
        "    (`auth_server` instead of `authServer`). `create_bot` converts\n"
        "    each key to camelCase before calling mineflayer.\n\n"
        '    Ref: mineflayer/index.d.ts — interface BotOptions\n    """',
    ]
    emitted: set[str] = set()
    for m in members:
        if m.is_method:
            continue
        py_name = _py_name(m.name)
        if py_name in emitted:
            continue
        emitted.add(py_name)
        py_type = ts_to_py(m.ts_type)
        lines.append(f"    {py_name}: {py_type}")
    return lines


# --------------------------------------------------------------------------- #
#  Main
# --------------------------------------------------------------------------- #


HEADER = """\
# GENERATED FROM mineflayer/index.d.ts — DO NOT EDIT MANUALLY.
# Regenerate via: uv run python scripts/generate_stubs.py
#
# This file is the IDE completion overlay for src/minethon/bot.py.
# Runtime behavior lives in bot.py; types live here.
#
# Ref: {mf_index}
# Ref: {vec3_index}
# Ref: {entity_index}
# Ref: {block_index}
# Ref: {item_index}
# Ref: {chat_index}
# Ref: {windows_index}
# Ref: {recipe_index}
# Ref: {pathfinder_index}
from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from typing import Literal, Self, TypedDict, Unpack, overload

from minethon._events import BotEvent

"""

# Mineflayer type aliases and aux interfaces we want to emit (selectively)
MINEFLAYER_TYPE_ALIASES = [
    "ChatLevel",
    "ViewDistance",
    "MainHands",
    "LevelType",
    "GameMode",
    "Dimension",
    "Difficulty",
    "ControlState",
    "EquipmentDestination",
    "DisplaySlot",
]

MINEFLAYER_INTERFACES = [
    "Player",
    "SkinData",
    "ChatPattern",
    "SkinParts",
    "GameSettings",
    "GameState",
    "Experience",
    "PhysicsOptions",
    "Time",
    "ControlStateStatus",
    "Instrument",
    "FindBlockOptions",
    "TransferOptions",
    "creativeMethods",
    "simpleClick",
    "Tablist",
    "chatPatternOptions",
    "CommandBlockOptions",
    "VillagerTrade",
    "Enchantment",
    "ScoreBoardItem",
]

# Classes from mineflayer/index.d.ts we need to expose (Window subclasses +
# mineflayer-owned classes that the Bot interface references by name).
MINEFLAYER_CLASSES = [
    "Chest",
    "Dispenser",
    "Furnace",
    "EnchantmentTable",
    "Anvil",
    "Villager",
    "ScoreBoard",
    "Team",
    "BossBar",
    "Particle",
    "Location",
    "Painting",
]


def extract_type_alias(text: str, name: str) -> str | None:
    """Pull a one- or multi-line `export type NAME = ...` declaration.

    mineflayer's `.d.ts` doesn't end type aliases with `;`, so we collect
    lines until we hit either a blank line or another top-level declaration.
    """
    lines = text.split("\n")
    start_re = re.compile(rf"^\s*export\s+type\s+{re.escape(name)}\s*=\s*(.*)$")
    for i, line in enumerate(lines):
        m = start_re.match(line)
        if not m:
            continue
        expr = m.group(1).strip()
        j = i + 1
        while j < len(lines):
            nxt = lines[j].strip()
            if not nxt:
                break
            # Stop at the start of the next declaration
            if re.match(
                r"^(export\s+|declare\s+|interface\s+|class\s+|function\s+|type\s+)",
                nxt,
            ):
                break
            # Accept continuation if the current expression is incomplete OR
            # the next line starts with a union / intersection operator.
            if expr.rstrip().endswith(("|", "&", ",", "=", "<")) or nxt.startswith(
                ("|", "&", ",")
            ):
                expr = (expr + " " + nxt).strip()
                j += 1
            else:
                break
        expr = re.sub(r"\s+", " ", expr).rstrip(";").strip()
        return expr
    return None


def render_events_module(
    event_callbacks: list[tuple[str, str, list[tuple[str, str]]]],
) -> str:
    lines = [
        "# GENERATED FROM mineflayer/index.d.ts — DO NOT EDIT MANUALLY.",
        "# Regenerate via: uv run python scripts/generate_stubs.py",
        "from __future__ import annotations",
        "",
        "from enum import StrEnum",
        "",
        "",
        "class BotEvent(StrEnum):",
        '    """Source-verified event names for `bot.on(...)`."""',
    ]
    for event, _alias, _args in event_callbacks:
        lines.append(f'    {_event_member_name(event)} = "{event}"')
    lines.extend(
        [
            "",
            "EVENT_ATTRIBUTE_MAP = {",
        ]
    )
    for event, _alias, _args in event_callbacks:
        lines.append(
            f'    "{_event_attr_name(event, prefix="on")[3:]}": '
            f"BotEvent.{_event_member_name(event)},"
        )
    lines.extend(
        [
            "}",
            "",
            # Order matches ruff's RUF022 sort (ALL_CAPS before CamelCase).
            '__all__ = ["EVENT_ATTRIBUTE_MAP", "BotEvent"]',
            "",
        ]
    )
    return "\n".join(lines)


def render_handlers_runtime(
    event_callbacks: list[tuple[str, str, list[tuple[str, str]]]],
    *,
    inline_aliases: dict[str, str] | None = None,
) -> str:
    """Emit the runtime ``BotHandlers`` class for `src/minethon/_handlers.py`.

    Every ``on_<event>`` method is a no-op with the same typed signature as
    the stub class in ``bot.pyi``. Subclasses override just the events they
    care about; ``bot.bind(handlers)`` wires those up to the JS EventEmitter.
    Annotations are lazy (`from __future__ import annotations`) so type names
    only need to resolve for static type checkers, not at import time.
    """
    # Identifiers referenced in parameter annotations — we TYPE_CHECKING-import
    # the ones that are published shells so strict type checkers can resolve
    # them. Builtins (str, list, int, ...) don't need importing.
    referenced: set[str] = set()
    for _event, _alias, args in event_callbacks:
        for _name, py_type in args:
            for ident in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", py_type):
                if ident[:1].isupper() or ident in {
                    "chatPatternOptions",
                    "creativeMethods",
                    "simpleClick",
                }:
                    referenced.add(ident)

    alias_map = dict(inline_aliases or {})
    shell_imports = sorted(
        referenced & set(_type_shell_names()) - set(alias_map),
    )
    # MessagePosition is defined at module scope (Literal alias), not a shell.
    uses_message_position = "MessagePosition" in referenced
    inlined = [name for name in sorted(alias_map) if name in referenced]

    lines = [
        "# GENERATED FROM mineflayer/index.d.ts — DO NOT EDIT MANUALLY.",
        "# Regenerate via: uv run python scripts/generate_stubs.py",
        '"""Optional class-based event handler base.',
        "",
        "Subclass :class:`BotHandlers`, override the ``on_<event>`` methods",
        "you care about, then wire the instance via ``bot.bind(handlers)``.",
        "",
        "Method signatures here mirror ``bot.pyi`` so IDE hover, 'Override",
        "methods', and `inspect.signature` all see the real parameter list.",
        "Annotations are lazy — imports are only needed by type checkers.",
        '"""',
        "from __future__ import annotations",
        "",
    ]
    # Combine `typing` imports; order matches ruff I001 (ALL_CAPS first).
    typing_imports = ["TYPE_CHECKING"]
    if uses_message_position or inlined:
        typing_imports.append("Literal")
    lines.append(f"from typing import {', '.join(typing_imports)}")
    lines.append("")
    if uses_message_position:
        lines.append('MessagePosition = Literal["chat", "system", "game_info"]')
        lines.append("")
    for name in inlined:
        lines.append(f"{name} = {alias_map[name]}")
        lines.append("")
    if shell_imports:
        lines.append("if TYPE_CHECKING:")
        lines.append("    from minethon._type_shells import (")
        for name in shell_imports:
            lines.append(f"        {name},")
        lines.append("    )")
        lines.append("")
    lines.extend(
        [
            '__all__ = ["BotHandlers"]',
            "",
            "",
            "class BotHandlers:",
            '    """Base class for class-based event handlers."""',
            "",
        ]
    )
    # Runtime methods use `pass` bodies (not stub-style `...`) so ruff format
    # inserts blank lines between them — otherwise PyCharm's PEP 8 checker
    # flags every method pair with E301.
    for event, _alias, args in event_callbacks:
        attr = _event_attr_name(event, prefix="on")
        if args:
            sig = ", ".join(["self"] + [f"{name}: {py_type}" for name, py_type in args])
        else:
            sig = "self"
        lines.append(f"    def {attr}({sig}) -> None:")
        lines.append("        pass")
    lines.append("")
    return "\n".join(lines)


def _type_shell_names() -> tuple[str, ...]:
    """Source-of-truth shell names — kept in sync with `_type_shells.py`."""
    return (
        "Vec3",
        "ChatMessageScore",
        "ChatMessage",
        "Effect",
        "Entity",
        "Block",
        "Item",
        "Window",
        "Recipe",
        "Move",
        "Goal",
        "GoalBlock",
        "GoalNear",
        "GoalXZ",
        "GoalNearXZ",
        "GoalY",
        "GoalGetToBlock",
        "GoalFollow",
        "GoalCompositeAll",
        "GoalCompositeAny",
        "GoalInvert",
        "GoalPlaceBlock",
        "GoalLookAtBlock",
        "GoalBreakBlock",
        "Goals",
        "Movements",
        "Pathfinder",
        "ComputedPath",
        "PartiallyComputedPath",
        "PathfinderModule",
        "Player",
        "SkinData",
        "ChatPattern",
        "SkinParts",
        "GameSettings",
        "GameState",
        "Experience",
        "PhysicsOptions",
        "Time",
        "ControlStateStatus",
        "Instrument",
        "FindBlockOptions",
        "TransferOptions",
        "creativeMethods",
        "simpleClick",
        "Tablist",
        "chatPatternOptions",
        "CommandBlockOptions",
        "VillagerTrade",
        "Enchantment",
        "Chest",
        "Dispenser",
        "Furnace",
        "EnchantmentTable",
        "Anvil",
        "Villager",
        "ScoreBoard",
        "ScoreBoardItem",
        "Team",
        "BossBar",
        "Particle",
        "Location",
        "Painting",
    )


def render_handlers_stub(
    event_callbacks: list[tuple[str, str, list[tuple[str, str]]]],
) -> list[str]:
    """Emit the typed ``BotHandlers`` class for bot.pyi."""
    lines = [
        "",
        "class BotHandlers:",
        '    """Class-based handler base. Subclass, override `on_<event>`, '
        "then call `bot.bind(handlers)`.",
        "",
        '    Typed signatures are provided here so IDE "Override methods" '
        "auto-fill produces the correct parameter list.",
        '    """',
    ]
    for event, _alias, args in event_callbacks:
        attr = _event_attr_name(event, prefix="on")
        if args:
            sig = ", ".join(["self"] + [f"{name}: {py_type}" for name, py_type in args])
        else:
            sig = "self"
        lines.append(f"    def {attr}({sig}) -> None: ...")
    return lines


def normalize_pyi_method_bodies(text: str) -> str:
    """Rewrite stub-style `...` method bodies to multi-line `pass`.

    Required so PyCharm's PEP 8 checker stops firing E301 on `.pyi` files:
    ruff format keeps `def foo(): ...` methods tight (no blank lines between)
    in stubs, but preserves blanks when the body is a real multi-line statement
    (docstring or ``pass``). After this transform, the formatter leaves our
    explicit blank lines in place.

    Also inserts a blank line between adjacent methods where missing.
    """
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        # Single-line `<indent>def name(...) -> T: ...` at end-of-line.
        m_single = re.match(
            r"^(\s+)def \w+\([^)]*\)(?:\s*->\s*[^:]+)?:\s*\.\.\.\s*$", line
        )
        if m_single:
            indent = m_single.group(1)
            sig_part = line[:-4].rstrip()  # drop trailing ` ...`
            out.append(sig_part)
            out.append(f"{indent}    pass")
            i += 1
            continue

        # Multi-line `<indent>def name(` … last line `) -> T: ...`.
        m_multi = re.match(r"^(\s+)def \w+\(\s*$", line)
        if m_multi:
            indent = m_multi.group(1)
            block = [line]
            j = i + 1
            while j < n:
                block.append(lines[j])
                if block[-1].rstrip().endswith("..."):
                    j += 1
                    break
                j += 1
            last = block[-1]
            if last.rstrip().endswith(": ..."):
                block[-1] = last.rstrip()[:-4].rstrip()
                block.append(f"{indent}    pass")
            out.extend(block)
            i = j
            continue

        out.append(line)
        i += 1

    # Second pass — insert blank line before every method "head" (`def ` or
    # `@overload` / `@staticmethod` etc.) when it follows another method's end
    # (pass / docstring / closing paren / property line).
    final: list[str] = []
    for idx, cur in enumerate(out):
        if idx > 0:
            stripped_cur = cur.lstrip()
            prev = final[-1] if final else ""
            prev_stripped = prev.strip()
            cur_indent = len(cur) - len(stripped_cur)
            is_method_head = stripped_cur.startswith(("def ", "@"))
            if (
                is_method_head
                and cur_indent >= 4
                and prev_stripped != ""
                and not prev_stripped.startswith(("class ", "@", "#"))
                and not prev_stripped.endswith(":")
            ):
                final.append("")
        final.append(cur)
    return "\n".join(final)


def format_generated_files(*paths: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "ruff", "format", *(str(path) for path in paths)],
        check=True,
    )


def main() -> None:
    mf_text = MF_INDEX.read_text()
    mf_text = strip_ts_comments(mf_text)
    pathfinder_text = strip_ts_comments(PATHFINDER_INDEX.read_text())

    out: list[str] = [
        HEADER.format(
            mf_index=MF_INDEX,
            vec3_index=_resolve_package_dir("vec3") / "index.d.ts",
            entity_index=_resolve_package_dir("prismarine-entity") / "index.d.ts",
            block_index=_resolve_package_dir("prismarine-block") / "index.d.ts",
            item_index=_resolve_package_dir("prismarine-item") / "index.d.ts",
            chat_index=_resolve_package_dir("prismarine-chat") / "index.d.ts",
            windows_index=_resolve_package_dir("prismarine-windows") / "index.d.ts",
            recipe_index=_resolve_package_dir("prismarine-recipe") / "index.d.ts",
            pathfinder_index=PATHFINDER_INDEX,
        ),
        EXTERNAL_STUBS,
        "",
        "# --- Mineflayer type aliases ---",
    ]

    # Type aliases
    type_alias_expressions: dict[str, str] = {}
    for alias in MINEFLAYER_TYPE_ALIASES:
        expr = extract_type_alias(mf_text, alias)
        if expr is None:
            print(f"warn: type alias {alias} not found", file=sys.stderr)
            continue
        type_alias_expressions[alias] = ts_to_py(expr)
        out.append(render_type_alias(alias, expr))
    out.append('MessagePosition = Literal["chat", "system", "game_info"]')
    out.append("")

    # Supporting interfaces
    out.append("# --- Mineflayer aux interfaces ---")
    for iface in MINEFLAYER_INTERFACES:
        body = find_interface(mf_text, iface)
        if body is None:
            print(f"warn: interface {iface} not found", file=sys.stderr)
            continue
        out.append("")
        out.extend(render_interface(iface, body))
    out.append("")

    # Window-family container classes
    out.append("# --- Mineflayer container classes ---")
    for cls in MINEFLAYER_CLASSES:
        body = find_class(mf_text, cls)
        if body is None:
            print(f"warn: class {cls} not found", file=sys.stderr)
            continue
        out.append("")
        out.extend(render_interface(cls, body))
    out.append("")

    # BotEvents → callback aliases
    events_body = find_interface(mf_text, "BotEvents")
    if events_body is None:
        raise SystemExit("Cannot find BotEvents interface")
    ev_lines, event_callbacks = render_bot_events(events_body)
    pathfinder_events_body = find_interface(pathfinder_text, "BotEvents")
    if pathfinder_events_body is not None:
        pf_ev_lines, pf_event_callbacks = render_bot_events(pathfinder_events_body)
        ev_lines.extend(pf_ev_lines[1:])
        event_callbacks.extend(pf_event_callbacks)
    event_callbacks.sort(key=lambda item: item[0])
    out.extend(ev_lines)
    out.append("")

    # BotOptions (camelCase, power-user) and CreateBotOptions (snake_case)
    bot_opts_body = find_interface(mf_text, "BotOptions")
    if bot_opts_body is None:
        raise SystemExit("Cannot find BotOptions interface")
    out.extend(render_bot_options(bot_opts_body))
    out.append("")
    out.extend(render_create_bot_options(bot_opts_body))
    out.append("")

    # Bot
    bot_body = find_interface(mf_text, "Bot")
    if bot_body is None:
        raise SystemExit("Cannot find Bot interface")
    out.extend(render_bot(bot_body, event_callbacks))
    out.append("")

    # Class-based handler base (typed stub)
    out.extend(render_handlers_stub(event_callbacks))
    out.append("")

    # Module-level factory
    out.append("")
    out.append("def create_bot(**options: Unpack[CreateBotOptions]) -> Bot: ...")
    out.append("")

    raw_text = "\n".join(out)
    descriptions = parse_stubs_doc()
    if descriptions:
        final_text = inject_docstrings(raw_text, descriptions)
        print(
            f"injected docstrings for {len(descriptions)} symbols from {STUBS_DOC.name}"
        )
    else:
        final_text = raw_text
        print(f"no stubs doc at {STUBS_DOC}; skipping docstring injection")
    final_text = normalize_pyi_method_bodies(final_text)
    OUT_PATH.write_text(final_text)
    events_text = render_events_module(event_callbacks)
    OUT_EVENTS_PATH.write_text(events_text)
    runtime_inline_aliases = {
        name: type_alias_expressions[name]
        for name in ("DisplaySlot",)
        if name in type_alias_expressions
    }
    handlers_text = render_handlers_runtime(
        event_callbacks, inline_aliases=runtime_inline_aliases
    )
    OUT_HANDLERS_PATH.write_text(handlers_text)
    format_generated_files(OUT_PATH, OUT_EVENTS_PATH, OUT_HANDLERS_PATH)
    final_text = OUT_PATH.read_text(encoding="utf-8")
    events_text = OUT_EVENTS_PATH.read_text(encoding="utf-8")
    handlers_text = OUT_HANDLERS_PATH.read_text(encoding="utf-8")
    print(f"Wrote {OUT_PATH} ({len(final_text.splitlines())} lines)")
    print(f"Wrote {OUT_EVENTS_PATH} ({len(events_text.splitlines())} lines)")
    print(f"Wrote {OUT_HANDLERS_PATH} ({len(handlers_text.splitlines())} lines)")


if __name__ == "__main__":
    main()
