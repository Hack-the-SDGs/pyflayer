# GENERATED FROM mineflayer/index.d.ts — DO NOT EDIT MANUALLY.
# Regenerate via: uv run python scripts/generate_stubs.py
"""Optional class-based event handler base.

Subclass :class:`BotHandlers`, override the ``on_<event>`` methods
you care about, then wire the instance via ``bot.bind(handlers)``.

Method signatures here mirror ``bot.pyi`` so IDE hover, 'Override
methods', and `inspect.signature` all see the real parameter list.
Annotations are lazy — imports are only needed by type checkers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

MessagePosition = Literal["chat", "system", "game_info"]

DisplaySlot = Literal[
    "list",
    "sidebar",
    "belowName",
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
]

if TYPE_CHECKING:
    from minethon._type_shells import (
        Block,
        BossBar,
        ChatMessage,
        Effect,
        Entity,
        Goal,
        Instrument,
        PartiallyComputedPath,
        Particle,
        Player,
        ScoreBoard,
        Team,
        Vec3,
        Window,
    )

__all__ = ["BotHandlers"]


class BotHandlers:
    """Base class for class-based event handlers."""

    def on_action_bar(self, json_msg: ChatMessage) -> None:
        pass

    def on_block_break_progress_end(self, block: Block) -> None:
        pass

    def on_block_break_progress_observed(
        self, block: Block, destroy_stage: float
    ) -> None:
        pass

    def on_block_update(self, old_block: Block | None, new_block: Block) -> None:
        pass

    def on_boss_bar_created(self, boss_bar: BossBar) -> None:
        pass

    def on_boss_bar_deleted(self, boss_bar: BossBar) -> None:
        pass

    def on_boss_bar_updated(self, boss_bar: BossBar) -> None:
        pass

    def on_breath(self) -> None:
        pass

    def on_chat(
        self,
        username: str,
        message: str,
        translate: str | None,
        json_msg: ChatMessage,
        matches: list[str] | None,
    ) -> None:
        pass

    def on_chest_lid_move(
        self, block: Block, is_open: float, block2: Block | None
    ) -> None:
        pass

    def on_chunk_column_load(self, entity: Vec3) -> None:
        pass

    def on_chunk_column_unload(self, entity: Vec3) -> None:
        pass

    def on_death(self) -> None:
        pass

    def on_digging_aborted(self, block: Block) -> None:
        pass

    def on_digging_completed(self, block: Block) -> None:
        pass

    def on_dismount(self, vehicle: Entity) -> None:
        pass

    def on_end(self, reason: str) -> None:
        pass

    def on_entity_attach(self, entity: Entity, vehicle: Entity) -> None:
        pass

    def on_entity_attributes(self, entity: Entity) -> None:
        pass

    def on_entity_critical_effect(self, entity: Entity) -> None:
        pass

    def on_entity_crouch(self, entity: Entity) -> None:
        pass

    def on_entity_dead(self, entity: Entity) -> None:
        pass

    def on_entity_detach(self, entity: Entity, vehicle: Entity) -> None:
        pass

    def on_entity_eat(self, entity: Entity) -> None:
        pass

    def on_entity_eating_grass(self, entity: Entity) -> None:
        pass

    def on_entity_effect(self, entity: Entity, effect: Effect) -> None:
        pass

    def on_entity_effect_end(self, entity: Entity, effect: Effect) -> None:
        pass

    def on_entity_elytra_flew(self, entity: Entity) -> None:
        pass

    def on_entity_equip(self, entity: Entity) -> None:
        pass

    def on_entity_gone(self, entity: Entity) -> None:
        pass

    def on_entity_hand_swap(self, entity: Entity) -> None:
        pass

    def on_entity_hurt(self, entity: Entity, source: Entity) -> None:
        pass

    def on_entity_magic_critical_effect(self, entity: Entity) -> None:
        pass

    def on_entity_moved(self, entity: Entity) -> None:
        pass

    def on_entity_shaking_off_water(self, entity: Entity) -> None:
        pass

    def on_entity_sleep(self, entity: Entity) -> None:
        pass

    def on_entity_spawn(self, entity: Entity) -> None:
        pass

    def on_entity_swing_arm(self, entity: Entity) -> None:
        pass

    def on_entity_tamed(self, entity: Entity) -> None:
        pass

    def on_entity_taming(self, entity: Entity) -> None:
        pass

    def on_entity_uncrouch(self, entity: Entity) -> None:
        pass

    def on_entity_update(self, entity: Entity) -> None:
        pass

    def on_entity_wake(self, entity: Entity) -> None:
        pass

    def on_error(self, err: Exception) -> None:
        pass

    def on_experience(self) -> None:
        pass

    def on_forced_move(self) -> None:
        pass

    def on_game(self) -> None:
        pass

    def on_goal_reached(self, goal: Goal) -> None:
        pass

    def on_goal_updated(self, goal: Goal, dynamic: bool) -> None:
        pass

    def on_hardcoded_sound_effect_heard(
        self,
        sound_id: float,
        sound_category: float,
        position: Vec3,
        volume: float,
        pitch: float,
    ) -> None:
        pass

    def on_health(self) -> None:
        pass

    def on_inject_allowed(self) -> None:
        pass

    def on_item_drop(self, entity: Entity) -> None:
        pass

    def on_kicked(self, reason: str, logged_in: bool) -> None:
        pass

    def on_login(self) -> None:
        pass

    def on_message(self, msg: ChatMessage, position: MessagePosition) -> None:
        pass

    def on_messagestr(
        self, message: str, position: MessagePosition, json_msg: ChatMessage
    ) -> None:
        pass

    def on_mount(self) -> None:
        pass

    def on_move(self, position: Vec3) -> None:
        pass

    def on_note_heard(self, block: Block, instrument: Instrument, pitch: float) -> None:
        pass

    def on_particle(self, particle: Particle) -> None:
        pass

    def on_path_reset(
        self,
        reason: Literal[
            "goal_updated",
            "movements_updated",
            "block_updated",
            "chunk_loaded",
            "goal_moved",
            "dig_error",
            "no_scaffolding_blocks",
            "place_error",
            "stuck",
        ],
    ) -> None:
        pass

    def on_path_stop(self) -> None:
        pass

    def on_path_update(self, path: PartiallyComputedPath) -> None:
        pass

    def on_physic_tick(self) -> None:
        pass

    def on_physics_tick(self) -> None:
        pass

    def on_piston_move(self, block: Block, is_pulling: float, direction: float) -> None:
        pass

    def on_player_collect(self, collector: Entity, collected: Entity) -> None:
        pass

    def on_player_joined(self, player: Player) -> None:
        pass

    def on_player_left(self, entity: Player) -> None:
        pass

    def on_player_updated(self, player: Player) -> None:
        pass

    def on_rain(self) -> None:
        pass

    def on_resource_pack(self, url: str, hash_: str | None, uuid: str | None) -> None:
        pass

    def on_respawn(self) -> None:
        pass

    def on_score_removed(self, scoreboard: ScoreBoard, item: float) -> None:
        pass

    def on_score_updated(self, scoreboard: ScoreBoard, item: float) -> None:
        pass

    def on_scoreboard_created(self, scoreboard: ScoreBoard) -> None:
        pass

    def on_scoreboard_deleted(self, scoreboard: ScoreBoard) -> None:
        pass

    def on_scoreboard_position(
        self, position: DisplaySlot, scoreboard: ScoreBoard
    ) -> None:
        pass

    def on_scoreboard_title_changed(self, scoreboard: ScoreBoard) -> None:
        pass

    def on_sleep(self) -> None:
        pass

    def on_sound_effect_heard(
        self, sound_name: str, position: Vec3, volume: float, pitch: float
    ) -> None:
        pass

    def on_spawn(self) -> None:
        pass

    def on_spawn_reset(self) -> None:
        pass

    def on_team_created(self, team: Team) -> None:
        pass

    def on_team_member_added(self, team: Team) -> None:
        pass

    def on_team_member_removed(self, team: Team) -> None:
        pass

    def on_team_removed(self, team: Team) -> None:
        pass

    def on_team_updated(self, team: Team) -> None:
        pass

    def on_time(self) -> None:
        pass

    def on_title(self, text: str, type_: Literal["subtitle", "title"]) -> None:
        pass

    def on_unmatched_message(self, string_msg: str, json_msg: ChatMessage) -> None:
        pass

    def on_used_firework(self) -> None:
        pass

    def on_wake(self) -> None:
        pass

    def on_whisper(
        self,
        username: str,
        message: str,
        translate: str | None,
        json_msg: ChatMessage,
        matches: list[str] | None,
    ) -> None:
        pass

    def on_window_close(self, window: Window) -> None:
        pass

    def on_window_open(self, window: Window) -> None:
        pass
