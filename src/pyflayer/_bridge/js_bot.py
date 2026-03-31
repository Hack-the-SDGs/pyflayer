"""Encapsulates all operations on the JS mineflayer bot object."""

import pathlib
from typing import Any

from pyflayer._bridge.runtime import BridgeRuntime
from pyflayer.config import BotConfig
from pyflayer.models.entity import EntityKind
from pyflayer.models.errors import BridgeError

# Mapping from EntityKind to the JS entity type string used by mineflayer.
# EntityKind.OTHER is intentionally omitted: mineflayer has no literal
# "other" type, so OTHER acts as a catch-all with no JS type filter.
_ENTITY_KIND_TO_JS: dict[EntityKind, str] = {
    EntityKind.PLAYER: "player",
    EntityKind.MOB: "mob",
    EntityKind.ANIMAL: "animal",
    EntityKind.HOSTILE: "hostile",
    EntityKind.PROJECTILE: "projectile",
    EntityKind.OBJECT: "object",
}

_JS_HELPERS_PATH = pathlib.Path(__file__).parent / "js" / "helpers.js"


class JSBotController:
    """The sole holder of the JS bot proxy.

    Quick-returning methods (chat, get_position, …) are synchronous and
    call JSPyBridge directly on the event-loop thread.

    Long-running methods (dig, place, equip, lookAt) use the
    ``start_*`` variants which delegate to ``js/helpers.js`` so they
    return immediately.  Completion is signalled via custom events on
    the JS bot that the :class:`EventRelay` picks up.
    """

    def __init__(self, runtime: BridgeRuntime, config: BotConfig) -> None:
        self._runtime = runtime
        self._config = config
        self._js_bot: Any = None
        self._pathfinder_goals: Any = None
        self._pathfinder_loaded = False
        self._helpers: Any = None

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
        self._helpers = self._runtime.require(str(_JS_HELPERS_PATH))

    @property
    def js_bot(self) -> Any:
        """Raw JS bot proxy (for event binding)."""
        return self._js_bot

    # -- Chat --

    def chat(self, message: str) -> None:
        """Send a chat message."""
        try:
            self._js_bot.chat(message)
        except Exception as exc:
            raise BridgeError(f"chat failed: {exc}") from exc

    def whisper(self, username: str, message: str) -> None:
        """Send a whisper to a player."""
        try:
            self._js_bot.whisper(username, message)
        except Exception as exc:
            raise BridgeError(f"whisper failed: {exc}") from exc

    # -- State queries --

    def get_position(self) -> dict[str, float]:
        """Read bot position as ``{x, y, z}`` dict."""
        try:
            pos = self._js_bot.entity.position
            return {"x": float(pos.x), "y": float(pos.y), "z": float(pos.z)}
        except Exception as exc:
            raise BridgeError(f"get_position failed: {exc}") from exc

    def get_health(self) -> float:
        """Read bot health (0-20)."""
        try:
            return float(self._js_bot.health)
        except Exception as exc:
            raise BridgeError(f"get_health failed: {exc}") from exc

    def get_food(self) -> float:
        """Read bot food level (0-20)."""
        try:
            return float(self._js_bot.food)
        except Exception as exc:
            raise BridgeError(f"get_food failed: {exc}") from exc

    def get_username(self) -> str:
        """Read bot username."""
        try:
            return str(self._js_bot.username)
        except Exception as exc:
            raise BridgeError(f"get_username failed: {exc}") from exc

    def get_game_mode(self) -> str:
        """Read current game mode (``"survival"``, ``"creative"``, etc.)."""
        try:
            gm = self._js_bot.game.gameMode
            return str(gm) if gm is not None else "unknown"
        except Exception as exc:
            raise BridgeError(f"get_game_mode failed: {exc}") from exc

    def get_players_dict(self) -> dict[str, dict[str, object]]:
        """Return online players as a Python dict (no JS proxy leaking)."""
        try:
            js_players = self._js_bot.players
            result: dict[str, dict[str, object]] = {}
            for key in js_players:
                p = js_players[key]
                result[str(key)] = {
                    "username": str(p.username),
                    "ping": int(p.ping) if hasattr(p, "ping") else 0,
                }
            return result
        except Exception as exc:
            raise BridgeError(f"get_players failed: {exc}") from exc

    def is_alive(self) -> bool:
        """Whether the bot entity is alive (health > 0)."""
        try:
            return float(self._js_bot.health) > 0
        except (TypeError, AttributeError):
            return False

    # -- World queries --

    def block_at(self, x: int, y: int, z: int) -> Any | None:
        """Return the raw JS Block at the given position, or ``None``."""
        try:
            Vec3 = self._runtime.require("vec3").Vec3
            pos = Vec3(x, y, z)
            return self._js_bot.blockAt(pos)
        except Exception as exc:
            raise BridgeError(f"block_at failed: {exc}") from exc

    def find_blocks(
        self,
        block_name: str,
        max_distance: float,
        count: int,
    ) -> list[Any]:
        """Find blocks by name. Returns list of raw JS Block proxies."""
        try:
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
        except Exception as exc:
            raise BridgeError(f"find_blocks failed: {exc}") from exc

    def get_entity_by_id(self, entity_id: int) -> Any | None:
        """Look up an entity by its numeric ID."""
        try:
            entities = self._js_bot.entities
            return entities[str(entity_id)]
        except (KeyError, TypeError):
            return None
        except Exception as exc:
            raise BridgeError(f"get_entity_by_id failed: {exc}") from exc

    def get_entity_by_filter(
        self,
        name: str | None,
        kind: EntityKind | None,
        max_distance: float,
    ) -> Any | None:
        """Find the nearest entity matching the filter criteria."""
        entity_type = _ENTITY_KIND_TO_JS.get(kind) if kind is not None else None
        try:
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
        except Exception as exc:
            raise BridgeError(f"get_entity_by_filter failed: {exc}") from exc

    # -- Synchronous actions (quick-returning) --

    def attack(self, js_entity: Any) -> None:
        """Attack an entity."""
        try:
            self._js_bot.attack(js_entity)
        except Exception as exc:
            raise BridgeError(f"attack failed: {exc}") from exc

    def use_item(self) -> None:
        """Activate the held item."""
        try:
            self._js_bot.activateItem()
        except Exception as exc:
            raise BridgeError(f"use_item failed: {exc}") from exc

    # -- Non-blocking actions (long-running, completion via events) --

    def start_dig(self, js_block: Any) -> None:
        """Start digging without blocking. Completion via ``_pyflayer:digDone``."""
        try:
            self._helpers.startDig(self._js_bot, js_block)
        except Exception as exc:
            raise BridgeError(f"start_dig failed: {exc}") from exc

    def start_place(
        self,
        js_reference_block: Any,
        face_x: float,
        face_y: float,
        face_z: float,
    ) -> None:
        """Start placing without blocking. Completion via ``_pyflayer:placeDone``."""
        try:
            Vec3 = self._runtime.require("vec3").Vec3
            face_vec = Vec3(face_x, face_y, face_z)
            self._helpers.startPlace(self._js_bot, js_reference_block, face_vec)
        except Exception as exc:
            raise BridgeError(f"start_place failed: {exc}") from exc

    def start_equip(self, item_name: str) -> bool:
        """Start equipping without blocking. Completion via ``_pyflayer:equipDone``.

        Returns:
            ``True`` if the item was found and equip started,
            ``False`` if the item was not found in inventory.
        """
        try:
            inv = self._js_bot.inventory
            items = inv.items()
            for item in items:
                if str(item.name) == item_name:
                    self._helpers.startEquip(self._js_bot, item, "hand")
                    return True
            return False
        except Exception as exc:
            raise BridgeError(f"start_equip failed: {exc}") from exc

    def start_look_at(self, x: float, y: float, z: float) -> None:
        """Start looking at a position without blocking.

        Completion via ``_pyflayer:lookAtDone``.
        """
        try:
            Vec3 = self._runtime.require("vec3").Vec3
            pos = Vec3(x, y, z)
            self._helpers.startLookAt(self._js_bot, pos)
        except Exception as exc:
            raise BridgeError(f"start_look_at failed: {exc}") from exc

    # -- Pathfinder --

    def load_pathfinder(self) -> None:
        """Load the mineflayer-pathfinder plugin. Call once after create_bot()."""
        if self._pathfinder_loaded:
            return
        try:
            pf_mod = self._runtime.require("mineflayer-pathfinder")
            self._js_bot.loadPlugin(pf_mod.pathfinder)
            self._pathfinder_goals = pf_mod.goals
            self._pathfinder_loaded = True
        except Exception as exc:
            raise BridgeError(f"load_pathfinder failed: {exc}") from exc

    def setup_pathfinder_movements(self) -> None:
        """Configure default Movements. Call after the bot has spawned."""
        try:
            pf_mod = self._runtime.require("mineflayer-pathfinder")
            mcdata = self._runtime.require("minecraft-data")(self._js_bot.version)
            movements = pf_mod.Movements(self._js_bot, mcdata)
            self._js_bot.pathfinder.setMovements(movements)
        except Exception as exc:
            raise BridgeError(f"setup_pathfinder_movements failed: {exc}") from exc

    def set_goal_near(self, x: float, y: float, z: float, radius: float) -> None:
        """Set a GoalNear target. The pathfinder starts navigating immediately."""
        try:
            goal = self._pathfinder_goals.GoalNear(x, y, z, radius)
            self._js_bot.pathfinder.setGoal(goal)
        except Exception as exc:
            raise BridgeError(f"set_goal_near failed: {exc}") from exc

    def stop_pathfinder(self) -> None:
        """Clear the current pathfinder goal."""
        try:
            self._js_bot.pathfinder.setGoal(None)
        except Exception as exc:
            raise BridgeError(f"stop_pathfinder failed: {exc}") from exc

    # -- Movement (quick-returning) --

    def set_control_state(self, control: str, state: bool) -> None:
        """Set a movement control state."""
        try:
            self._js_bot.setControlState(control, state)
        except Exception as exc:
            raise BridgeError(f"set_control_state failed: {exc}") from exc

    def clear_control_states(self) -> None:
        """Stop all movement controls."""
        try:
            self._js_bot.clearControlStates()
        except Exception as exc:
            raise BridgeError(f"clear_control_states failed: {exc}") from exc

    # -- Lifecycle --

    def quit(self) -> None:
        """Graceful disconnect."""
        if self._js_bot is not None:
            try:
                self._js_bot.quit()
            except Exception:
                pass  # Best-effort during shutdown
