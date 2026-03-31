"""Encapsulates all operations on the JS mineflayer bot object."""

from typing import Any

from pyflayer._bridge.runtime import BridgeRuntime
from pyflayer.config import BotConfig


class JSBotController:
    """The sole holder of the JS bot proxy.

    All methods are **synchronous** — they block on JSPyBridge IPC which
    is fast enough to call directly.  The public :class:`~pyflayer.bot.Bot`
    layer should *not* wrap these with ``asyncio.to_thread``.
    """

    def __init__(self, runtime: BridgeRuntime, config: BotConfig) -> None:
        self._runtime = runtime
        self._config = config
        self._js_bot: Any = None
        self._pathfinder_goals: Any = None
        self._pathfinder_loaded = False

    def create_bot(self) -> None:
        """Call ``mineflayer.createBot()`` — starts connecting immediately."""
        mineflayer = self._runtime.require("mineflayer")
        options: dict[str, Any] = {
            "host": self._config.host,
            "port": self._config.port,
            "username": self._config.username,
            "hideErrors": self._config.hide_errors,
        }
        if self._config.version is not None:
            options["version"] = self._config.version
        if self._config.auth is not None:
            options["auth"] = self._config.auth
        self._js_bot = mineflayer.createBot(options)

    @property
    def js_bot(self) -> Any:
        """Raw JS bot proxy (for event binding)."""
        return self._js_bot

    # -- Chat --

    def chat(self, message: str) -> None:
        """Send a chat message. Blocking."""
        self._js_bot.chat(message)

    def whisper(self, username: str, message: str) -> None:
        """Send a whisper to a player. Blocking."""
        self._js_bot.whisper(username, message)

    # -- State queries --

    def get_position(self) -> dict[str, float]:
        """Read bot position as ``{x, y, z}`` dict."""
        pos = self._js_bot.entity.position
        return {"x": float(pos.x), "y": float(pos.y), "z": float(pos.z)}

    def get_health(self) -> float:
        """Read bot health (0–20)."""
        return float(self._js_bot.health)

    def get_food(self) -> float:
        """Read bot food level (0–20)."""
        return float(self._js_bot.food)

    def get_username(self) -> str:
        """Read bot username."""
        return str(self._js_bot.username)

    def get_game_mode(self) -> str:
        """Read current game mode (``"survival"``, ``"creative"``, etc.)."""
        gm = self._js_bot.game.gameMode
        return str(gm) if gm is not None else "unknown"

    def get_players(self) -> Any:
        """Return the raw JS ``bot.players`` object."""
        return self._js_bot.players

    def is_alive(self) -> bool:
        """Whether the bot entity is alive (health > 0)."""
        try:
            return float(self._js_bot.health) > 0
        except (TypeError, AttributeError):
            return False

    # -- World queries --

    def block_at(self, x: int, y: int, z: int) -> Any | None:
        """Return the raw JS Block at the given position, or ``None``."""
        Vec3 = self._runtime.require("vec3").Vec3
        pos = Vec3(x, y, z)
        block = self._js_bot.blockAt(pos)
        return block

    def find_blocks(
        self,
        block_name: str,
        max_distance: float,
        count: int,
    ) -> list[Any]:
        """Find blocks by name. Returns list of raw JS Block proxies."""
        mcdata = self._js_bot.registry
        block_type = getattr(mcdata.blocksByName, block_name, None)
        if block_type is None:
            return []
        block_id = int(block_type.id)

        positions = self._js_bot.findBlocks(
            {
                "matching": block_id,
                "maxDistance": max_distance,
                "count": count,
            }
        )
        results: list[Any] = []
        for pos in positions:
            block = self._js_bot.blockAt(pos)
            if block is not None:
                results.append(block)
        return results

    def get_entity_by_filter(
        self,
        name: str | None,
        entity_type: str | None,
        max_distance: float,
    ) -> Any | None:
        """Find the nearest entity matching the filter criteria.

        Returns the raw JS Entity proxy or ``None``.
        """
        bot_pos = self._js_bot.entity.position
        best: Any = None
        best_dist: float = max_distance

        entities = self._js_bot.entities
        for eid in entities:
            entity = entities[eid]
            if entity is None:
                continue

            # Skip the bot itself
            if int(entity.id) == int(self._js_bot.entity.id):
                continue

            # Name filter
            if name is not None:
                ename = getattr(entity, "name", None) or getattr(
                    entity, "username", None
                )
                if ename is None or str(ename) != name:
                    continue

            # Type filter
            if entity_type is not None:
                etype = getattr(entity, "type", None)
                if etype is None or str(etype) != entity_type:
                    continue

            # Distance check
            epos = entity.position
            dx = float(epos.x) - float(bot_pos.x)
            dy = float(epos.y) - float(bot_pos.y)
            dz = float(epos.z) - float(bot_pos.z)
            dist = (dx * dx + dy * dy + dz * dz) ** 0.5

            if dist < best_dist:
                best_dist = dist
                best = entity

        return best

    # -- Actions --

    def dig(self, js_block: Any) -> None:
        """Dig a block. Blocking.

        Mineflayer's ``bot.dig()`` returns a Promise. JSPyBridge
        transparently blocks until the promise settles, so this call
        does not return until the dig animation finishes.
        """
        self._js_bot.dig(js_block)

    def place_block(
        self,
        js_reference_block: Any,
        face_x: float,
        face_y: float,
        face_z: float,
    ) -> None:
        """Place a block against a reference block face. Blocking.

        JSPyBridge blocks until the JS promise returned by
        ``bot.placeBlock()`` settles.
        """
        Vec3 = self._runtime.require("vec3").Vec3
        face_vec = Vec3(face_x, face_y, face_z)
        self._js_bot.placeBlock(js_reference_block, face_vec)

    def equip_item(self, item_name: str) -> None:
        """Equip an item by name to the hand. Blocking.

        JSPyBridge blocks until the JS promise returned by
        ``bot.equip()`` settles.

        Raises:
            ValueError: If the item is not found in the inventory.
        """
        inv = self._js_bot.inventory
        items = inv.items()
        for item in items:
            if str(item.name) == item_name:
                self._js_bot.equip(item, "hand")
                return
        raise ValueError(f"Item '{item_name}' not found in inventory")

    def attack(self, js_entity: Any) -> None:
        """Attack an entity. Blocking."""
        self._js_bot.attack(js_entity)

    def use_item(self) -> None:
        """Activate the held item. Blocking."""
        self._js_bot.activateItem()

    # -- Pathfinder --

    def load_pathfinder(self) -> None:
        """Load the mineflayer-pathfinder plugin. Call once after create_bot()."""
        if self._pathfinder_loaded:
            return
        pf_mod = self._runtime.require("mineflayer-pathfinder")
        self._js_bot.loadPlugin(pf_mod.pathfinder)
        self._pathfinder_goals = pf_mod.goals
        self._pathfinder_loaded = True

    def setup_pathfinder_movements(self) -> None:
        """Configure default Movements. Call after the bot has spawned."""
        pf_mod = self._runtime.require("mineflayer-pathfinder")
        mcdata = self._runtime.require("minecraft-data")(self._js_bot.version)
        movements = pf_mod.Movements(self._js_bot, mcdata)
        self._js_bot.pathfinder.setMovements(movements)

    def set_goal_near(self, x: float, y: float, z: float, radius: float) -> None:
        """Set a GoalNear target. The pathfinder starts navigating immediately."""
        goal = self._pathfinder_goals.GoalNear(x, y, z, radius)
        self._js_bot.pathfinder.setGoal(goal)

    def stop_pathfinder(self) -> None:
        """Clear the current pathfinder goal."""
        self._js_bot.pathfinder.setGoal(None)

    # -- Movement --

    def look_at(self, x: float, y: float, z: float) -> None:
        """Rotate to look at a position. Blocking."""
        Vec3 = self._runtime.require("vec3").Vec3
        pos = Vec3(x, y, z)
        self._js_bot.lookAt(pos)

    def set_control_state(self, control: str, state: bool) -> None:
        """Set a movement control state.

        Args:
            control: One of ``"forward"``, ``"back"``, ``"left"``,
                ``"right"``, ``"jump"``, ``"sprint"``, ``"sneak"``.
            state: ``True`` to activate, ``False`` to deactivate.
        """
        self._js_bot.setControlState(control, state)

    def clear_control_states(self) -> None:
        """Stop all movement controls."""
        self._js_bot.clearControlStates()

    # -- Lifecycle --

    def quit(self) -> None:
        """Graceful disconnect. Blocking."""
        if self._js_bot is not None:
            self._js_bot.quit()
