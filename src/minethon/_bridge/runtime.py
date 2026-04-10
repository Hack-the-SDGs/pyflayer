"""JSPyBridge lifecycle management."""

import shutil
import subprocess
from types import ModuleType
from typing import Any

from minethon.models.errors import BridgeError


class BridgeRuntime:
    """Manages the JSPyBridge runtime lifecycle.

    Defers ``import javascript`` to :meth:`start` so that importing
    minethon does not spawn a Node.js process.
    """

    def __init__(self) -> None:
        self._started = False
        self._js: ModuleType | None = None

    def ensure_node_available(self) -> None:
        """Check that Node.js >= 18 is on PATH."""
        node = shutil.which("node")
        if node is None:
            raise BridgeError(
                "Node.js not found in PATH. "
                "Please install Node.js 18+ from https://nodejs.org/"
            )
        try:
            result = subprocess.run(
                [node, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                raise BridgeError(
                    f"'node --version' failed (exit {result.returncode}): {stderr}"
                )
            version_str = result.stdout.strip().lstrip("v")
            major = int(version_str.split(".")[0])
            if major < 18:
                raise BridgeError(f"Node.js 18+ required, found v{version_str}.")
        except (subprocess.SubprocessError, ValueError) as exc:
            raise BridgeError(f"Failed to check Node.js version: {exc}") from exc

    def start(self) -> None:
        """Initialize JSPyBridge. Spawns a Node.js process."""
        if self._started:
            return
        self.ensure_node_available()
        import javascript  # type: ignore[import-untyped]

        self._js = javascript
        self._started = True

    def require(self, module: str) -> Any:
        """Import an npm module via JSPyBridge ``require()``."""
        self._check_started()
        assert self._js is not None
        return self._js.require(module)

    @property
    def js_module(self) -> ModuleType:
        """Access the raw ``javascript`` module (for On/Once/off)."""
        self._check_started()
        assert self._js is not None
        return self._js

    def shutdown(self) -> None:
        """Mark runtime as stopped. Node.js cleanup is handled by atexit."""
        self._started = False
        self._js = None

    def _check_started(self) -> None:
        if not self._started:
            raise BridgeError("Bridge runtime not started. Call start() first.")
