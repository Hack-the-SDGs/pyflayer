"""Internal JS bridge bootstrap.

Not part of the public API. Everything here returns raw JS proxies from
JSPyBridge; callers in `bot.py` are responsible for presenting Pythonic types.

Version pinning policy (AGENTS.md):
    npm packages are pinned to specific versions. First-run lazy install is
    avoided by running `./setup.sh` before the user's first script, which
    pre-installs the modules into the `javascript` package's node_modules.
"""

from __future__ import annotations

from typing import Any

from javascript import require as _js_require

# Pinned — bumped by humans, never `latest`.
# Ref: mineflayer package.json engines.node >= 22
BUNDLED_VERSIONS: dict[str, str] = {
    "mineflayer": "4.37.0",
    "vec3": "0.1.10",
    "mineflayer-pathfinder": "2.4.5",
}
MINEFLAYER_VERSION = BUNDLED_VERSIONS["mineflayer"]
VEC3_VERSION = BUNDLED_VERSIONS["vec3"]


def get_mineflayer() -> Any:
    """Load the pinned mineflayer module.

    Ref: mineflayer/index.js — `module.exports.createBot`
    """
    return _js_require("mineflayer", MINEFLAYER_VERSION)


def get_vec3() -> Any:
    """Load the pinned vec3 module (position math).

    Ref: vec3/index.js — `module.exports.Vec3`
    """
    return _js_require("vec3", VEC3_VERSION)
