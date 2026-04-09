"""Encapsulates all operations on the JS mineflayer bot object."""

import pathlib
from typing import Any

from minethon._bridge._util import extract_js_stack
from minethon._bridge.runtime import BridgeRuntime
from minethon.config import BotConfig
from minethon.models.entity import EntityKind
from minethon.models.errors import BridgeError

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
        self._helpers: Any = None

    def create_bot(self) -> None:
        """Call ``mineflayer.createBot()`` — starts connecting immediately."""
        mineflayer = self._runtime.require("mineflayer")
        options: dict[str, Any] = {
            "host": self._config.host,
            "port": self._config.port,
            "username": self._config.username,
        }
        # Optional fields — only set when explicitly provided so mineflayer
        # uses its own defaults for unset values.
        optional_fields: list[tuple[str, str]] = [
            ("password", "password"),
            ("hide_errors", "hideErrors"),
            ("disable_chat_signing", "disableChatSigning"),
            ("version", "version"),
            ("auth", "auth"),
            ("auth_server", "authServer"),
            ("session_server", "sessionServer"),
            ("log_errors", "logErrors"),
            ("check_timeout_interval", "checkTimeoutInterval"),
            ("keep_alive", "keepAlive"),
            ("respawn", "respawn"),
            ("chat_length_limit", "chatLengthLimit"),
            ("view_distance", "viewDistance"),
            ("default_chat_patterns", "defaultChatPatterns"),
            ("physics_enabled", "physicsEnabled"),
            ("brand", "brand"),
            ("skip_validation", "skipValidation"),
            ("profiles_folder", "profilesFolder"),
            ("load_internal_plugins", "loadInternalPlugins"),
        ]
        for py_attr, js_key in optional_fields:
            value = getattr(self._config, py_attr)
            if value is not None:
                options[js_key] = value
        self._js_bot = mineflayer.createBot(options)
        try:
            self._helpers = self._runtime.require(str(_JS_HELPERS_PATH.as_posix()))
        except Exception as exc:
            raise BridgeError(
                f"Failed to load JS helpers at {_JS_HELPERS_PATH}: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

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
            raise BridgeError(f"chat failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def whisper(self, username: str, message: str) -> None:
        """Send a whisper to a player."""
        try:
            self._js_bot.whisper(username, message)
        except Exception as exc:
            raise BridgeError(f"whisper failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    # -- State queries --

    def get_position(self) -> dict[str, float]:
        """Read bot position as ``{x, y, z}`` dict."""
        try:
            pos = self._js_bot.entity.position
            return {"x": float(pos.x), "y": float(pos.y), "z": float(pos.z)}
        except Exception as exc:
            raise BridgeError(f"get_position failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_health(self) -> float:
        """Read bot health (0-20)."""
        try:
            return float(self._js_bot.health)
        except Exception as exc:
            raise BridgeError(f"get_health failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_food(self) -> float:
        """Read bot food level (0-20)."""
        try:
            return float(self._js_bot.food)
        except Exception as exc:
            raise BridgeError(f"get_food failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_username(self) -> str:
        """Read bot username."""
        try:
            return str(self._js_bot.username)
        except Exception as exc:
            raise BridgeError(f"get_username failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_game_mode(self) -> str:
        """Read current game mode (``"survival"``, ``"creative"``, etc.)."""
        try:
            gm = self._js_bot.game.gameMode
            return str(gm) if gm is not None else "unknown"
        except Exception as exc:
            raise BridgeError(f"get_game_mode failed: {exc}", js_stack=extract_js_stack(exc)) from exc

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
            raise BridgeError(f"get_players_dict failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def is_alive(self) -> bool:
        """Whether the bot entity is alive (health > 0)."""
        try:
            return float(self._js_bot.health) > 0
        except (TypeError, AttributeError):
            return False

    # -- Additional state queries --

    def get_food_saturation(self) -> float:
        """Read bot food saturation."""
        try:
            return float(self._js_bot.foodSaturation)
        except Exception as exc:
            raise BridgeError(f"get_food_saturation failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_oxygen_level(self) -> int:
        """Read bot oxygen level (0-20)."""
        try:
            val = getattr(self._js_bot, "oxygenLevel", None)
            return int(val) if val is not None else 20
        except Exception as exc:
            raise BridgeError(f"get_oxygen_level failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_experience(self) -> dict[str, object]:
        """Read experience as ``{level, points, progress}``."""
        try:
            exp = self._js_bot.experience
            return {
                "level": int(exp.level) if exp.level is not None else 0,
                "points": int(exp.points) if exp.points is not None else 0,
                "progress": float(exp.progress) if exp.progress is not None else 0.0,
            }
        except Exception as exc:
            raise BridgeError(f"get_experience failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_game_state(self) -> dict[str, object]:
        """Read game state as a plain dict."""
        try:
            g = self._js_bot.game
            return {
                "game_mode": str(g.gameMode) if getattr(g, "gameMode", None) is not None else "unknown",
                "dimension": str(g.dimension) if getattr(g, "dimension", None) is not None else "unknown",
                "difficulty": str(g.difficulty) if getattr(g, "difficulty", None) is not None else "unknown",
                "hardcore": bool(getattr(g, "hardcore", False)),
                "max_players": int(getattr(g, "maxPlayers", 0)),
                "server_brand": str(getattr(g, "serverBrand", "")),
                "min_y": int(getattr(g, "minY", 0)),
                "height": int(getattr(g, "height", 256)),
            }
        except Exception as exc:
            raise BridgeError(f"get_game_state failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_is_raining(self) -> bool:
        """Whether it is currently raining."""
        try:
            return bool(self._js_bot.isRaining)
        except Exception as exc:
            raise BridgeError(f"get_is_raining failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_thunder_state(self) -> float:
        """Thunder intensity (0 = no thunder)."""
        try:
            return float(self._js_bot.thunderState)
        except Exception as exc:
            raise BridgeError(f"get_thunder_state failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_time(self) -> dict[str, object]:
        """Read world time as a plain dict."""
        try:
            t = self._js_bot.time
            return {
                "time_of_day": int(t.timeOfDay) if t.timeOfDay is not None else 0,
                "day": int(t.day) if t.day is not None else 0,
                "is_day": bool(t.isDay) if t.isDay is not None else True,
                "moon_phase": int(t.moonPhase) if t.moonPhase is not None else 0,
                "age": int(t.age) if t.age is not None else 0,
                "do_daylight_cycle": bool(t.doDaylightCycle) if t.doDaylightCycle is not None else True,
            }
        except Exception as exc:
            raise BridgeError(f"get_time failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_held_item(self) -> Any | None:
        """Return the raw JS item in the bot's main hand, or ``None``."""
        try:
            item = self._js_bot.heldItem
            return item if item is not None else None
        except Exception as exc:
            raise BridgeError(f"get_held_item failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_quick_bar_slot(self) -> int:
        """Currently selected quick bar slot (0-8)."""
        try:
            slot = self._js_bot.quickBarSlot
            return int(slot) if slot is not None else 0
        except Exception as exc:
            raise BridgeError(f"get_quick_bar_slot failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def set_quick_bar_slot(self, slot: int) -> None:
        """Select a quick bar slot (0-8)."""
        try:
            self._js_bot.setQuickBarSlot(slot)
        except Exception as exc:
            raise BridgeError(f"set_quick_bar_slot failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_spawn_point(self) -> dict[str, float]:
        """Read spawn point as ``{x, y, z}``."""
        try:
            sp = self._js_bot.spawnPoint
            return {"x": float(sp.x), "y": float(sp.y), "z": float(sp.z)}
        except Exception as exc:
            raise BridgeError(f"get_spawn_point failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_is_sleeping(self) -> bool:
        """Whether the bot is sleeping in a bed."""
        try:
            return bool(self._js_bot.isSleeping)
        except Exception as exc:
            raise BridgeError(f"get_is_sleeping failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_target_dig_block(self) -> Any | None:
        """Return the JS block currently being dug, or ``None``."""
        try:
            return self._js_bot.targetDigBlock
        except Exception as exc:
            raise BridgeError(f"get_target_dig_block failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_bot_entity(self) -> Any:
        """Return the bot's own JS entity proxy."""
        try:
            return self._js_bot.entity
        except Exception as exc:
            raise BridgeError(f"get_bot_entity failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_entities(self) -> Any:
        """Return the raw JS entities dict proxy."""
        try:
            return self._js_bot.entities
        except Exception as exc:
            raise BridgeError(f"get_entities failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_version(self) -> str:
        """Minecraft version string (e.g. ``"1.20.4"``)."""
        try:
            return str(self._js_bot.version)
        except Exception as exc:
            raise BridgeError(f"get_version failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_physics_enabled(self) -> bool:
        """Whether the physics simulation is enabled."""
        try:
            return bool(self._js_bot.physicsEnabled)
        except Exception as exc:
            raise BridgeError(f"get_physics_enabled failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def set_physics_enabled(self, enabled: bool) -> None:
        """Enable or disable the physics simulation."""
        try:
            self._js_bot.physicsEnabled = enabled
        except Exception as exc:
            raise BridgeError(f"set_physics_enabled failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_firework_rocket_duration(self) -> int:
        """Duration of current firework rocket boost (0 if not boosting)."""
        try:
            val = self._js_bot.fireworkRocketDuration
            return int(val) if val is not None else 0
        except Exception as exc:
            raise BridgeError(f"get_firework_rocket_duration failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_tablist(self) -> dict[str, str]:
        """Read tab list header and footer as plain strings."""
        try:
            tl = self._js_bot.tablist
            header = str(tl.header) if tl.header is not None else ""
            footer = str(tl.footer) if tl.footer is not None else ""
            return {"header": header, "footer": footer}
        except Exception as exc:
            raise BridgeError(f"get_tablist failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_is_alive_js(self) -> bool:
        """Read the JS ``bot.isAlive`` property directly."""
        try:
            return bool(self._js_bot.isAlive)
        except (TypeError, AttributeError):
            return False

    def get_username_js(self) -> str:
        """Read the bot username from the JS bot (may differ from config after auth)."""
        try:
            return str(self._js_bot.username)
        except Exception as exc:
            raise BridgeError(f"get_username_js failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_players_full(self) -> dict[str, dict[str, object]]:
        """Return online players with full details (no JS proxy leaking)."""
        try:
            js_players = self._js_bot.players
            result: dict[str, dict[str, object]] = {}
            for key in js_players:
                p = js_players[key]
                uuid_val = getattr(p, "uuid", None)
                display_name = getattr(p, "displayName", None)
                game_mode = getattr(p, "gamemode", None)
                result[str(key)] = {
                    "username": str(p.username),
                    "uuid": str(uuid_val) if uuid_val is not None else "",
                    "ping": int(p.ping) if hasattr(p, "ping") else 0,
                    "game_mode": int(game_mode) if game_mode is not None else 0,
                    "display_name": str(display_name) if display_name is not None else None,
                }
            return result
        except Exception as exc:
            raise BridgeError(f"get_players_full failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    # -- World queries --

    def block_at(self, x: int, y: int, z: int) -> Any | None:
        """Return the raw JS Block at the given position, or ``None``."""
        try:
            Vec3 = self._runtime.require("vec3").Vec3
            pos = Vec3(x, y, z)
            return self._js_bot.blockAt(pos)
        except Exception as exc:
            raise BridgeError(f"block_at failed: {exc}", js_stack=extract_js_stack(exc)) from exc

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
            raise BridgeError(f"find_blocks failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def get_entity_by_id(self, entity_id: int) -> Any | None:
        """Look up an entity by its numeric ID."""
        try:
            entities = self._js_bot.entities
            return entities[str(entity_id)]
        except (KeyError, TypeError):
            return None
        except Exception as exc:
            raise BridgeError(f"get_entity_by_id failed: {exc}", js_stack=extract_js_stack(exc)) from exc

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

                # Name filter: check username first (players), then
                # name (mobs/objects).  Player entities have name="player"
                # so checking name first would never match by username.
                if name is not None:
                    ename = getattr(entity, "username", None)
                    if ename is None or str(ename) != name:
                        ename = getattr(entity, "name", None)
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
            raise BridgeError(f"get_entity_by_filter failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    # -- Synchronous actions (quick-returning) --

    def attack(self, js_entity: Any) -> None:
        """Attack an entity."""
        try:
            self._js_bot.attack(js_entity)
        except Exception as exc:
            raise BridgeError(f"attack failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def use_item(self) -> None:
        """Activate the held item."""
        try:
            self._js_bot.activateItem()
        except Exception as exc:
            raise BridgeError(f"use_item failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    # -- Non-blocking actions (long-running, completion via events) --

    def start_dig(self, js_block: Any) -> None:
        """Start digging without blocking. Completion via ``_minethon:digDone``."""
        try:
            self._helpers.startDig(self._js_bot, js_block)
        except Exception as exc:
            raise BridgeError(f"start_dig failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def start_place(
        self,
        js_reference_block: Any,
        face_x: float,
        face_y: float,
        face_z: float,
    ) -> None:
        """Start placing without blocking. Completion via ``_minethon:placeDone``."""
        try:
            Vec3 = self._runtime.require("vec3").Vec3
            face_vec = Vec3(face_x, face_y, face_z)
            self._helpers.startPlace(self._js_bot, js_reference_block, face_vec)
        except Exception as exc:
            raise BridgeError(f"start_place failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def start_equip(self, item_name: str) -> bool:
        """Start equipping without blocking. Completion via ``_minethon:equipDone``.

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
            raise BridgeError(f"start_equip failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def start_look_at(self, x: float, y: float, z: float) -> None:
        """Start looking at a position without blocking.

        Completion via ``_minethon:lookAtDone``.
        """
        try:
            Vec3 = self._runtime.require("vec3").Vec3
            pos = Vec3(x, y, z)
            self._helpers.startLookAt(self._js_bot, pos)
        except Exception as exc:
            raise BridgeError(f"start_look_at failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    # -- Movement (quick-returning) --

    def set_control_state(self, control: str, state: bool) -> None:
        """Set a movement control state."""
        try:
            self._js_bot.setControlState(control, state)
        except Exception as exc:
            raise BridgeError(f"set_control_state failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    def clear_control_states(self) -> None:
        """Stop all movement controls."""
        try:
            self._js_bot.clearControlStates()
        except Exception as exc:
            raise BridgeError(f"clear_control_states failed: {exc}", js_stack=extract_js_stack(exc)) from exc

    # -- Lifecycle --

    def quit(self) -> None:
        """Graceful disconnect."""
        if self._js_bot is not None:
            try:
                self._js_bot.quit()
            except Exception:
                pass  # Best-effort during shutdown
