"""Encapsulates all operations on the JS mineflayer bot object."""

import pathlib
from typing import TYPE_CHECKING, Any

from minethon._bridge._util import extract_js_stack
from minethon.models.entity import EntityKind
from minethon.models.errors import BridgeError

if TYPE_CHECKING:
    from minethon._bridge.runtime import BridgeRuntime
    from minethon.config import BotConfig

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
            raise BridgeError(
                f"chat failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def whisper(self, username: str, message: str) -> None:
        """Send a whisper to a player."""
        try:
            self._js_bot.whisper(username, message)
        except Exception as exc:
            raise BridgeError(
                f"whisper failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    # -- State queries --

    def get_position(self) -> dict[str, float]:
        """Read bot position as ``{x, y, z}`` dict."""
        try:
            pos = self._js_bot.entity.position
            return {"x": float(pos.x), "y": float(pos.y), "z": float(pos.z)}
        except Exception as exc:
            raise BridgeError(
                f"get_position failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_health(self) -> float:
        """Read bot health (0-20)."""
        try:
            return float(self._js_bot.health)
        except Exception as exc:
            raise BridgeError(
                f"get_health failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_food(self) -> float:
        """Read bot food level (0-20)."""
        try:
            return float(self._js_bot.food)
        except Exception as exc:
            raise BridgeError(
                f"get_food failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_game_mode(self) -> str:
        """Read current game mode (``"survival"``, ``"creative"``, etc.)."""
        try:
            gm = self._js_bot.game.gameMode
            return str(gm) if gm is not None else "unknown"
        except Exception as exc:
            raise BridgeError(
                f"get_game_mode failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    # -- Additional state queries --

    def get_food_saturation(self) -> float:
        """Read bot food saturation."""
        try:
            return float(self._js_bot.foodSaturation)
        except Exception as exc:
            raise BridgeError(
                f"get_food_saturation failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_oxygen_level(self) -> int:
        """Read bot oxygen level (0-20)."""
        try:
            val = getattr(self._js_bot, "oxygenLevel", None)
            return int(val) if val is not None else 20
        except Exception as exc:
            raise BridgeError(
                f"get_oxygen_level failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

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
            raise BridgeError(
                f"get_experience failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_game_state(self) -> dict[str, object]:
        """Read game state as a plain dict."""
        try:
            g = self._js_bot.game
            return {
                "game_mode": str(g.gameMode)
                if getattr(g, "gameMode", None) is not None
                else "unknown",
                "dimension": str(g.dimension)
                if getattr(g, "dimension", None) is not None
                else "unknown",
                "difficulty": str(g.difficulty)
                if getattr(g, "difficulty", None) is not None
                else "unknown",
                "hardcore": bool(getattr(g, "hardcore", False)),
                "max_players": int(getattr(g, "maxPlayers", 0)),
                "server_brand": str(getattr(g, "serverBrand", "")),
                "min_y": int(getattr(g, "minY", 0)),
                "height": int(getattr(g, "height", 256)),
            }
        except Exception as exc:
            raise BridgeError(
                f"get_game_state failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_is_raining(self) -> bool:
        """Whether it is currently raining."""
        try:
            return bool(self._js_bot.isRaining)
        except Exception as exc:
            raise BridgeError(
                f"get_is_raining failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_thunder_state(self) -> float:
        """Thunder intensity (0 = no thunder)."""
        try:
            return float(self._js_bot.thunderState)
        except Exception as exc:
            raise BridgeError(
                f"get_thunder_state failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

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
                "do_daylight_cycle": bool(t.doDaylightCycle)
                if t.doDaylightCycle is not None
                else True,
            }
        except Exception as exc:
            raise BridgeError(
                f"get_time failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_held_item(self) -> Any | None:
        """Return the raw JS item in the bot's main hand, or ``None``."""
        try:
            item = self._js_bot.heldItem
            return item if item is not None else None
        except Exception as exc:
            raise BridgeError(
                f"get_held_item failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_quick_bar_slot(self) -> int:
        """Currently selected quick bar slot (0-8)."""
        try:
            slot = self._js_bot.quickBarSlot
            return int(slot) if slot is not None else 0
        except Exception as exc:
            raise BridgeError(
                f"get_quick_bar_slot failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def set_quick_bar_slot(self, slot: int) -> None:
        """Select a quick bar slot (0-8)."""
        try:
            self._js_bot.setQuickBarSlot(slot)
        except Exception as exc:
            raise BridgeError(
                f"set_quick_bar_slot failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_spawn_point(self) -> dict[str, float]:
        """Read spawn point as ``{x, y, z}``."""
        try:
            sp = self._js_bot.spawnPoint
            if sp is None:
                raise BridgeError(
                    "spawnPoint is not yet available (server has not sent a spawn_position packet)"
                )
            return {"x": float(sp.x), "y": float(sp.y), "z": float(sp.z)}
        except BridgeError:
            raise
        except Exception as exc:
            raise BridgeError(
                f"get_spawn_point failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_is_sleeping(self) -> bool:
        """Whether the bot is sleeping in a bed."""
        try:
            return bool(self._js_bot.isSleeping)
        except Exception as exc:
            raise BridgeError(
                f"get_is_sleeping failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_target_dig_block(self) -> Any | None:
        """Return the JS block currently being dug, or ``None``."""
        try:
            return self._js_bot.targetDigBlock
        except Exception as exc:
            raise BridgeError(
                f"get_target_dig_block failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_bot_entity(self) -> Any:
        """Return the bot's own JS entity proxy."""
        try:
            return self._js_bot.entity
        except Exception as exc:
            raise BridgeError(
                f"get_bot_entity failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_entities_snapshot(self) -> list[dict[str, object]]:
        """Batch-serialise all entities in one JS call.

        Uses ``helpers.snapshotEntities()`` to avoid per-entity bridge
        round-trips.  Each item is converted via ``.valueOf()`` to a
        native Python dict.
        """
        try:
            raw_list = self._helpers.snapshotEntities(self._js_bot)
            return [dict(item.valueOf()) for item in raw_list]
        except Exception as exc:
            raise BridgeError(
                f"get_entities_snapshot failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_version(self) -> str:
        """Minecraft version string (e.g. ``"1.20.4"``)."""
        try:
            return str(self._js_bot.version)
        except Exception as exc:
            raise BridgeError(
                f"get_version failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_physics_enabled(self) -> bool:
        """Whether the physics simulation is enabled."""
        try:
            return bool(self._js_bot.physicsEnabled)
        except Exception as exc:
            raise BridgeError(
                f"get_physics_enabled failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def set_physics_enabled(self, enabled: bool) -> None:
        """Enable or disable the physics simulation."""
        try:
            self._js_bot.physicsEnabled = enabled
        except Exception as exc:
            raise BridgeError(
                f"set_physics_enabled failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_firework_rocket_duration(self) -> int:
        """Duration of current firework rocket boost (0 if not boosting)."""
        try:
            val = self._js_bot.fireworkRocketDuration
            return int(val) if val is not None else 0
        except Exception as exc:
            raise BridgeError(
                f"get_firework_rocket_duration failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def get_tablist(self) -> dict[str, str]:
        """Read tab list header and footer as plain text.

        Uses ``toString()`` on the prismarine-chat ``ChatMessage``
        objects.  If a server sends raw JSON chat components the result
        may still contain JSON fragments; callers should handle that.
        """
        try:
            tl = self._js_bot.tablist
            header = str(tl.header.toString()) if tl.header is not None else ""
            footer = str(tl.footer.toString()) if tl.footer is not None else ""
            return {"header": header, "footer": footer}
        except Exception as exc:
            raise BridgeError(
                f"get_tablist failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_is_alive_js(self) -> bool:
        """Read the JS ``bot.isAlive`` property directly."""
        try:
            return bool(self._js_bot.isAlive)
        except TypeError, AttributeError:
            return False

    def get_username_js(self) -> str:
        """Read the bot username from the JS bot (may differ from config after auth)."""
        try:
            return str(self._js_bot.username)
        except Exception as exc:
            raise BridgeError(
                f"get_username_js failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

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
                    "display_name": str(display_name.toString())
                    if display_name is not None
                    else None,
                }
            return result
        except Exception as exc:
            raise BridgeError(
                f"get_players_full failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    # -- World queries --

    def block_at(self, x: int, y: int, z: int) -> Any | None:
        """Return the raw JS Block at the given position, or ``None``."""
        try:
            Vec3 = self._runtime.require("vec3").Vec3
            pos = Vec3(x, y, z)
            return self._js_bot.blockAt(pos)
        except Exception as exc:
            raise BridgeError(
                f"block_at failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

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
            raise BridgeError(
                f"find_blocks failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_entity_by_id(self, entity_id: int) -> Any | None:
        """Look up an entity by its numeric ID."""
        try:
            entities = self._js_bot.entities
            return entities[str(entity_id)]
        except KeyError, TypeError:
            return None
        except Exception as exc:
            raise BridgeError(
                f"get_entity_by_id failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

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
            raise BridgeError(
                f"get_entity_by_filter failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    # -- Synchronous actions (quick-returning) --

    def attack(self, js_entity: Any) -> None:
        """Attack an entity."""
        try:
            self._js_bot.attack(js_entity)
        except Exception as exc:
            raise BridgeError(
                f"attack failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def use_item(self) -> None:
        """Activate the held item."""
        try:
            self._js_bot.activateItem()
        except Exception as exc:
            raise BridgeError(
                f"use_item failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    # -- Non-blocking actions (long-running, completion via events) --

    def start_dig(self, js_block: Any) -> None:
        """Start digging without blocking. Completion via ``_minethon:digDone``."""
        try:
            self._helpers.startDig(self._js_bot, js_block)
        except Exception as exc:
            raise BridgeError(
                f"start_dig failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

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
            raise BridgeError(
                f"start_place failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_equip(self, item_name: str, destination: str = "hand") -> bool:
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
                    self._helpers.startEquip(self._js_bot, item, destination)
                    return True
            return False
        except Exception as exc:
            raise BridgeError(
                f"start_equip failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_look_at(self, x: float, y: float, z: float) -> None:
        """Start looking at a position without blocking.

        Completion via ``_minethon:lookAtDone``.
        """
        try:
            Vec3 = self._runtime.require("vec3").Vec3
            pos = Vec3(x, y, z)
            self._helpers.startLookAt(self._js_bot, pos)
        except Exception as exc:
            raise BridgeError(
                f"start_look_at failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    # -- Movement (quick-returning) --

    def set_control_state(self, control: str, state: bool) -> None:
        """Set a movement control state."""
        try:
            self._js_bot.setControlState(control, state)
        except Exception as exc:
            raise BridgeError(
                f"set_control_state failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def clear_control_states(self) -> None:
        """Stop all movement controls."""
        try:
            self._js_bot.clearControlStates()
        except Exception as exc:
            raise BridgeError(
                f"clear_control_states failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    # -- Additional state queries (unique, no first-block equivalent) --

    def get_using_held_item(self) -> bool:
        """Whether the bot is currently using the held item."""
        try:
            return bool(self._js_bot.usingHeldItem)
        except AttributeError, TypeError:
            return False

    def get_rain_state(self) -> float:
        """Rain level (0-1)."""
        try:
            return float(self._js_bot.rainState)
        except AttributeError, TypeError:
            return 0.0

    def get_inventory_items(self) -> list[Any]:
        """Return raw JS Item proxies from bot.inventory.items().

        Ref: mineflayer/lib/plugins/inventory.js — bot.inventory.items()
        """
        try:
            return list(self._js_bot.inventory.items())
        except Exception as exc:
            raise BridgeError(
                f"get_inventory_items failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_inventory_snapshot(self) -> list[dict[str, object]]:
        """Batch-serialise all inventory items in one JS call.

        Uses ``helpers.snapshotInventory()`` to avoid per-item bridge
        round-trips.  Each item is a plain Python dict.

        Ref: mineflayer/lib/plugins/inventory.js — bot.inventory.items()
        """
        try:
            raw_list = self._helpers.snapshotInventory(self._js_bot)
            return [dict(item.valueOf()) for item in raw_list]
        except Exception as exc:
            raise BridgeError(
                f"get_inventory_snapshot failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_villager_session_snapshot(self, js_villager: Any) -> dict[str, object]:
        """Batch-serialise a villager session in one JS call.

        Ref: mineflayer/lib/plugins/villager.js — villager trades
        """
        try:
            raw = self._helpers.snapshotVillagerSession(js_villager)
            result = dict(raw.valueOf())
            trades_raw = raw.trades
            trades = []
            for t in trades_raw:
                trade = dict(t.valueOf())
                for key in ("inputItem1", "outputItem", "inputItem2"):
                    val = getattr(t, key, None)
                    trade[key] = dict(val.valueOf()) if val is not None else None
                trades.append(trade)
            result["trades"] = trades
            return result
        except Exception as exc:
            raise BridgeError(
                f"get_villager_session_snapshot failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def find_inventory_item_by_name(self, name: str) -> tuple[int | None, Any | None]:
        """Find first inventory item matching *name*.

        Returns ``(item_type_id, js_item_proxy)`` or ``(None, None)``.
        Performs the search entirely in the bridge layer so the caller
        never iterates live JS proxies from the asyncio thread.

        Ref: mineflayer/lib/plugins/inventory.js — bot.inventory.items()
        """
        try:
            for item in self._js_bot.inventory.items():
                if str(item.name) == name:
                    return int(item.type), item
            return None, None
        except Exception as exc:
            raise BridgeError(
                f"find_inventory_item_by_name failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def get_control_state_value(self, control: str) -> bool:
        """Read a specific control state."""
        try:
            return bool(self._js_bot.getControlState(control))
        except Exception as exc:
            raise BridgeError(
                f"get_control_state failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    # -- Additional synchronous actions --

    def end(self, reason: str | None = None) -> None:
        """End connection with the server."""
        try:
            if reason is not None:
                self._js_bot.end(reason)
            else:
                self._js_bot.end()
        except Exception:
            pass  # Best-effort

    def swing_arm(self, hand: str = "right", show_hand: bool = True) -> None:
        """Play arm swing animation."""
        try:
            self._js_bot.swingArm(hand, show_hand)
        except Exception as exc:
            raise BridgeError(
                f"swing_arm failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def activate_item(self, off_hand: bool = False) -> None:
        """Activate held item (eat, shoot bow, etc.)."""
        try:
            self._js_bot.activateItem(off_hand)
        except Exception as exc:
            raise BridgeError(
                f"activate_item failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def deactivate_item(self) -> None:
        """Deactivate held item (release bow, stop eating)."""
        try:
            self._js_bot.deactivateItem()
        except Exception as exc:
            raise BridgeError(
                f"deactivate_item failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def use_on(self, js_entity: Any) -> None:
        """Use held item on an entity (saddle, shears)."""
        try:
            self._js_bot.useOn(js_entity)
        except Exception as exc:
            raise BridgeError(
                f"use_on failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def mount(self, js_entity: Any) -> None:
        """Mount a vehicle entity."""
        try:
            self._js_bot.mount(js_entity)
        except Exception as exc:
            raise BridgeError(
                f"mount failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def dismount(self) -> None:
        """Dismount from the current vehicle."""
        try:
            self._js_bot.dismount()
        except Exception as exc:
            raise BridgeError(
                f"dismount failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def move_vehicle(self, left: float, forward: float) -> None:
        """Move the vehicle (-1 or 1 for each axis)."""
        try:
            self._js_bot.moveVehicle(left, forward)
        except Exception as exc:
            raise BridgeError(
                f"move_vehicle failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def stop_digging(self) -> None:
        """Stop the current digging operation."""
        try:
            self._js_bot.stopDigging()
        except Exception as exc:
            raise BridgeError(
                f"stop_digging failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def dig_time(self, js_block: Any) -> int:
        """Return dig time in milliseconds for the given block."""
        try:
            return int(self._js_bot.digTime(js_block))
        except Exception as exc:
            raise BridgeError(
                f"dig_time failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def can_dig_block(self, js_block: Any) -> bool:
        """Whether the block is diggable and in range."""
        try:
            return bool(self._js_bot.canDigBlock(js_block))
        except AttributeError, TypeError:
            return False

    def can_see_block(self, js_block: Any) -> bool:
        """Whether the bot can see the block."""
        try:
            return bool(self._js_bot.canSeeBlock(js_block))
        except AttributeError, TypeError:
            return False

    def block_at_cursor(self, max_distance: float = 256) -> Any | None:
        """Return the block the bot is looking at, or None."""
        try:
            return self._js_bot.blockAtCursor(max_distance)
        except AttributeError, TypeError:
            return None

    def entity_at_cursor(self, max_distance: float = 3.5) -> Any | None:
        """Return the entity the bot is looking at, or None."""
        try:
            return self._js_bot.entityAtCursor(max_distance)
        except AttributeError, TypeError:
            return None

    def accept_resource_pack(self) -> None:
        """Accept the server resource pack."""
        try:
            self._js_bot.acceptResourcePack()
        except Exception as exc:
            raise BridgeError(
                f"accept_resource_pack failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def deny_resource_pack(self) -> None:
        """Deny the server resource pack."""
        try:
            self._js_bot.denyResourcePack()
        except Exception as exc:
            raise BridgeError(
                f"deny_resource_pack failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def set_settings(self, options: dict[str, Any]) -> None:
        """Update bot.settings."""
        try:
            self._js_bot.setSettings(options)
        except Exception as exc:
            raise BridgeError(
                f"set_settings failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def support_feature(self, name: str) -> bool:
        """Check if a feature is supported in the current MC version."""
        try:
            return bool(self._js_bot.supportFeature(name))
        except AttributeError, TypeError:
            return False

    def do_respawn(self) -> None:
        """Manually respawn (when auto-respawn is disabled)."""
        try:
            self._js_bot.respawn()
        except Exception as exc:
            raise BridgeError(
                f"respawn failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def is_a_bed(self, js_block: Any) -> bool:
        """Return True if the block is a bed."""
        try:
            return bool(self._js_bot.isABed(js_block))
        except AttributeError, TypeError:
            return False

    def update_sign(self, js_block: Any, text: str, back: bool = False) -> None:
        """Update the text on a sign."""
        try:
            self._js_bot.updateSign(js_block, text, back)
        except Exception as exc:
            raise BridgeError(
                f"update_sign failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def set_command_block(
        self,
        x: int,
        y: int,
        z: int,
        command: str,
        options: dict[str, Any] | None = None,
    ) -> None:
        """Set a command block's properties."""
        try:
            Vec3 = self._runtime.require("vec3").Vec3
            pos = Vec3(x, y, z)
            if options is not None:
                self._js_bot.setCommandBlock(pos, command, options)
            else:
                self._js_bot.setCommandBlock(pos, command)
        except Exception as exc:
            raise BridgeError(
                f"set_command_block failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def close_window(self, js_window: Any) -> None:
        """Close a window."""
        try:
            self._js_bot.closeWindow(js_window)
        except Exception as exc:
            raise BridgeError(
                f"close_window failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def update_held_item(self) -> None:
        """Update bot.heldItem."""
        try:
            self._js_bot.updateHeldItem()
        except Exception as exc:
            raise BridgeError(
                f"update_held_item failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_equipment_dest_slot(self, destination: str) -> int:
        """Get the inventory slot ID for an equipment destination."""
        try:
            return int(self._js_bot.getEquipmentDestSlot(destination))
        except Exception as exc:
            raise BridgeError(
                f"get_equipment_dest_slot failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def recipes_for(
        self,
        item_type: int,
        metadata: int | None,
        min_result_count: int | None,
        crafting_table: Any | None,
    ) -> list[Any]:
        """Return recipes for the given item type."""
        try:
            return list(
                self._js_bot.recipesFor(
                    item_type, metadata, min_result_count, crafting_table
                )
            )
        except Exception as exc:
            raise BridgeError(
                f"recipes_for failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def recipes_all(
        self, item_type: int, metadata: int | None, crafting_table: Any | None
    ) -> list[Any]:
        """Return all recipes for the given item type (regardless of inventory)."""
        try:
            return list(self._js_bot.recipesAll(item_type, metadata, crafting_table))
        except Exception as exc:
            raise BridgeError(
                f"recipes_all failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def get_item_type(self, item_name: str) -> int | None:
        """Resolve a registry item name to its numeric item id."""
        try:
            item_type = getattr(self._js_bot.registry.itemsByName, item_name, None)
            if item_type is None:
                return None
            return int(item_type.id)
        except Exception as exc:
            raise BridgeError(
                f"get_item_type failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def creative_start_flying(self) -> None:
        """Set gravity to 0 for creative flight."""
        try:
            self._js_bot.creative.startFlying()
        except Exception as exc:
            raise BridgeError(
                f"creative_start_flying failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def creative_stop_flying(self) -> None:
        """Restore normal gravity."""
        try:
            self._js_bot.creative.stopFlying()
        except Exception as exc:
            raise BridgeError(
                f"creative_stop_flying failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    # -- Additional non-blocking actions (completion via events) --

    def start_look(self, yaw: float, pitch: float, force: bool = False) -> None:
        """Start looking at yaw/pitch. Completion via ``_minethon:lookDone``."""
        try:
            self._helpers.startLook(self._js_bot, yaw, pitch, force)
        except Exception as exc:
            raise BridgeError(
                f"start_look failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_sleep(self, js_bed_block: Any) -> None:
        """Start sleeping. Completion via ``_minethon:sleepDone``."""
        try:
            self._helpers.startSleep(self._js_bot, js_bed_block)
        except Exception as exc:
            raise BridgeError(
                f"start_sleep failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_wake(self) -> None:
        """Start waking. Completion via ``_minethon:wakeDone``."""
        try:
            self._helpers.startWake(self._js_bot)
        except Exception as exc:
            raise BridgeError(
                f"start_wake failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_unequip(self, destination: str) -> None:
        """Start unequipping. Completion via ``_minethon:unequipDone``."""
        try:
            self._helpers.startUnequip(self._js_bot, destination)
        except Exception as exc:
            raise BridgeError(
                f"start_unequip failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_toss_stack(self, js_item: Any) -> None:
        """Start tossing a stack. Completion via ``_minethon:tossStackDone``."""
        try:
            self._helpers.startTossStack(self._js_bot, js_item)
        except Exception as exc:
            raise BridgeError(
                f"start_toss_stack failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_toss(
        self, item_type: int, metadata: int | None, count: int | None
    ) -> None:
        """Start tossing items. Completion via ``_minethon:tossDone``."""
        try:
            self._helpers.startToss(self._js_bot, item_type, metadata, count)
        except Exception as exc:
            raise BridgeError(
                f"start_toss failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_consume(self) -> None:
        """Start consuming held item. Completion via ``_minethon:consumeDone``."""
        try:
            self._helpers.startConsume(self._js_bot)
        except Exception as exc:
            raise BridgeError(
                f"start_consume failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_fish(self) -> None:
        """Start fishing. Completion via ``_minethon:fishDone``."""
        try:
            self._helpers.startFish(self._js_bot)
        except Exception as exc:
            raise BridgeError(
                f"start_fish failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_elytra_fly(self) -> None:
        """Start elytra flying. Completion via ``_minethon:elytraFlyDone``."""
        try:
            self._helpers.startElytraFly(self._js_bot)
        except Exception as exc:
            raise BridgeError(
                f"start_elytra_fly failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_craft(
        self, recipe: Any, count: int | None, crafting_table: Any | None
    ) -> None:
        """Start crafting. Completion via ``_minethon:craftDone``."""
        try:
            self._helpers.startCraft(self._js_bot, recipe, count, crafting_table)
        except Exception as exc:
            raise BridgeError(
                f"start_craft failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_activate_block(
        self, js_block: Any, direction: Any | None = None, cursor_pos: Any | None = None
    ) -> None:
        """Start activating block. Completion via ``_minethon:activateBlockDone``."""
        try:
            self._helpers.startActivateBlock(
                self._js_bot, js_block, direction, cursor_pos
            )
        except Exception as exc:
            raise BridgeError(
                f"start_activate_block failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_activate_entity(self, js_entity: Any) -> None:
        """Start activating entity. Completion via ``_minethon:activateEntityDone``."""
        try:
            self._helpers.startActivateEntity(self._js_bot, js_entity)
        except Exception as exc:
            raise BridgeError(
                f"start_activate_entity failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_activate_entity_at(
        self, js_entity: Any, x: float, y: float, z: float
    ) -> None:
        """Start activating entity at position. Completion via ``_minethon:activateEntityAtDone``."""
        try:
            Vec3 = self._runtime.require("vec3").Vec3
            pos = Vec3(x, y, z)
            self._helpers.startActivateEntityAt(self._js_bot, js_entity, pos)
        except Exception as exc:
            raise BridgeError(
                f"start_activate_entity_at failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def start_open_container(
        self,
        js_block_or_entity: Any,
        direction: Any | None = None,
        cursor_pos: Any | None = None,
    ) -> None:
        """Start opening container. Completion via ``_minethon:openContainerDone``."""
        try:
            self._helpers.startOpenContainer(
                self._js_bot, js_block_or_entity, direction, cursor_pos
            )
        except Exception as exc:
            raise BridgeError(
                f"start_open_container failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_open_furnace(self, js_block: Any) -> None:
        """Start opening furnace. Completion via ``_minethon:openFurnaceDone``."""
        try:
            self._helpers.startOpenFurnace(self._js_bot, js_block)
        except Exception as exc:
            raise BridgeError(
                f"start_open_furnace failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_open_enchantment_table(self, js_block: Any) -> None:
        """Start opening enchantment table. Completion via ``_minethon:openEnchantmentTableDone``."""
        try:
            self._helpers.startOpenEnchantmentTable(self._js_bot, js_block)
        except Exception as exc:
            raise BridgeError(
                f"start_open_enchantment_table failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def start_open_anvil(self, js_block: Any) -> None:
        """Start opening anvil. Completion via ``_minethon:openAnvilDone``."""
        try:
            self._helpers.startOpenAnvil(self._js_bot, js_block)
        except Exception as exc:
            raise BridgeError(
                f"start_open_anvil failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_open_villager(self, js_entity: Any) -> None:
        """Start opening villager trade. Completion via ``_minethon:openVillagerDone``."""
        try:
            self._helpers.startOpenVillager(self._js_bot, js_entity)
        except Exception as exc:
            raise BridgeError(
                f"start_open_villager failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_trade(
        self, villager_instance: Any, trade_index: int, times: int | None = None
    ) -> None:
        """Start trading. Completion via ``_minethon:tradeDone``."""
        try:
            self._helpers.startTrade(
                self._js_bot, villager_instance, trade_index, times
            )
        except Exception as exc:
            raise BridgeError(
                f"start_trade failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_tab_complete(
        self,
        text: str,
        assume_command: bool = False,
        send_block_in_sight: bool = True,
        timeout: int = 5000,
    ) -> None:
        """Start tab completion. Completion via ``_minethon:tabCompleteDone``."""
        try:
            self._helpers.startTabComplete(
                self._js_bot, text, assume_command, send_block_in_sight, timeout
            )
        except Exception as exc:
            raise BridgeError(
                f"start_tab_complete failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_write_book(self, slot: int, pages: list[str]) -> None:
        """Start writing a book. Completion via ``_minethon:writeBookDone``."""
        try:
            self._helpers.startWriteBook(self._js_bot, slot, pages)
        except Exception as exc:
            raise BridgeError(
                f"start_write_book failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_wait_for_chunks_to_load(self) -> None:
        """Start waiting for chunks. Completion via ``_minethon:chunksLoadedDone``."""
        try:
            self._helpers.startWaitForChunksToLoad(self._js_bot)
        except Exception as exc:
            raise BridgeError(
                f"start_wait_for_chunks_to_load failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def start_wait_for_ticks(self, ticks: int) -> None:
        """Start waiting for ticks. Completion via ``_minethon:waitForTicksDone``."""
        try:
            self._helpers.startWaitForTicks(self._js_bot, ticks)
        except Exception as exc:
            raise BridgeError(
                f"start_wait_for_ticks failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_click_window(self, slot: int, mouse_button: int, mode: int) -> None:
        """Start click window. Completion via ``_minethon:clickWindowDone``."""
        try:
            self._helpers.startClickWindow(self._js_bot, slot, mouse_button, mode)
        except Exception as exc:
            raise BridgeError(
                f"start_click_window failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_transfer(self, options: dict[str, Any]) -> None:
        """Start item transfer. Completion via ``_minethon:transferDone``."""
        try:
            self._helpers.startTransfer(self._js_bot, options)
        except Exception as exc:
            raise BridgeError(
                f"start_transfer failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_move_slot_item(self, source_slot: int, dest_slot: int) -> None:
        """Start moving slot item. Completion via ``_minethon:moveSlotItemDone``."""
        try:
            self._helpers.startMoveSlotItem(self._js_bot, source_slot, dest_slot)
        except Exception as exc:
            raise BridgeError(
                f"start_move_slot_item failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_put_away(self, slot: int) -> None:
        """Start putting away item. Completion via ``_minethon:putAwayDone``."""
        try:
            self._helpers.startPutAway(self._js_bot, slot)
        except Exception as exc:
            raise BridgeError(
                f"start_put_away failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_creative_fly_to(self, x: float, y: float, z: float) -> None:
        """Start creative fly-to. Completion via ``_minethon:creativeFlyToDone``."""
        try:
            Vec3 = self._runtime.require("vec3").Vec3
            dest = Vec3(x, y, z)
            self._helpers.startCreativeFlyTo(self._js_bot, dest)
        except Exception as exc:
            raise BridgeError(
                f"start_creative_fly_to failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    def start_creative_set_inventory_slot(self, slot: int, item: Any) -> None:
        """Start creative set slot. Completion via ``_minethon:creativeSetSlotDone``."""
        try:
            self._helpers.startCreativeSetInventorySlot(self._js_bot, slot, item)
        except Exception as exc:
            raise BridgeError(
                f"start_creative_set_inventory_slot failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def start_creative_clear_slot(self, slot: int) -> None:
        """Start creative clear slot. Completion via ``_minethon:creativeClearSlotDone``."""
        try:
            self._helpers.startCreativeClearSlot(self._js_bot, slot)
        except Exception as exc:
            raise BridgeError(
                f"start_creative_clear_slot failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def start_creative_clear_inventory(self) -> None:
        """Start creative clear inventory. Completion via ``_minethon:creativeClearInventoryDone``."""
        try:
            self._helpers.startCreativeClearInventory(self._js_bot)
        except Exception as exc:
            raise BridgeError(
                f"start_creative_clear_inventory failed: {exc}",
                js_stack=extract_js_stack(exc),
            ) from exc

    def start_place_entity(
        self, js_reference_block: Any, face_x: float, face_y: float, face_z: float
    ) -> None:
        """Start placing entity. Completion via ``_minethon:placeEntityDone``."""
        try:
            Vec3 = self._runtime.require("vec3").Vec3
            face_vec = Vec3(face_x, face_y, face_z)
            self._helpers.startPlaceEntity(self._js_bot, js_reference_block, face_vec)
        except Exception as exc:
            raise BridgeError(
                f"start_place_entity failed: {exc}", js_stack=extract_js_stack(exc)
            ) from exc

    # -- Lifecycle --

    def quit(self) -> None:
        """Graceful disconnect."""
        if self._js_bot is not None:
            try:
                self._js_bot.quit()
            except Exception:
                pass  # Best-effort during shutdown
