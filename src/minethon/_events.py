# GENERATED FROM mineflayer/index.d.ts — DO NOT EDIT MANUALLY.
# Regenerate via: uv run python scripts/generate_stubs.py
from __future__ import annotations

from enum import StrEnum


class BotEvent(StrEnum):
    """Source-verified event names for `bot.on(...)`."""

    ACTION_BAR = "actionBar"
    BLOCK_BREAK_PROGRESS_END = "blockBreakProgressEnd"
    BLOCK_BREAK_PROGRESS_OBSERVED = "blockBreakProgressObserved"
    BLOCK_UPDATE = "blockUpdate"
    BOSS_BAR_CREATED = "bossBarCreated"
    BOSS_BAR_DELETED = "bossBarDeleted"
    BOSS_BAR_UPDATED = "bossBarUpdated"
    BREATH = "breath"
    CHAT = "chat"
    CHEST_LID_MOVE = "chestLidMove"
    CHUNK_COLUMN_LOAD = "chunkColumnLoad"
    CHUNK_COLUMN_UNLOAD = "chunkColumnUnload"
    DEATH = "death"
    DIGGING_ABORTED = "diggingAborted"
    DIGGING_COMPLETED = "diggingCompleted"
    DISMOUNT = "dismount"
    END = "end"
    ENTITY_ATTACH = "entityAttach"
    ENTITY_ATTRIBUTES = "entityAttributes"
    ENTITY_CRITICAL_EFFECT = "entityCriticalEffect"
    ENTITY_CROUCH = "entityCrouch"
    ENTITY_DEAD = "entityDead"
    ENTITY_DETACH = "entityDetach"
    ENTITY_EAT = "entityEat"
    ENTITY_EATING_GRASS = "entityEatingGrass"
    ENTITY_EFFECT = "entityEffect"
    ENTITY_EFFECT_END = "entityEffectEnd"
    ENTITY_ELYTRA_FLEW = "entityElytraFlew"
    ENTITY_EQUIP = "entityEquip"
    ENTITY_GONE = "entityGone"
    ENTITY_HAND_SWAP = "entityHandSwap"
    ENTITY_HURT = "entityHurt"
    ENTITY_MAGIC_CRITICAL_EFFECT = "entityMagicCriticalEffect"
    ENTITY_MOVED = "entityMoved"
    ENTITY_SHAKING_OFF_WATER = "entityShakingOffWater"
    ENTITY_SLEEP = "entitySleep"
    ENTITY_SPAWN = "entitySpawn"
    ENTITY_SWING_ARM = "entitySwingArm"
    ENTITY_TAMED = "entityTamed"
    ENTITY_TAMING = "entityTaming"
    ENTITY_UNCROUCH = "entityUncrouch"
    ENTITY_UPDATE = "entityUpdate"
    ENTITY_WAKE = "entityWake"
    ERROR = "error"
    EXPERIENCE = "experience"
    FORCED_MOVE = "forcedMove"
    GAME = "game"
    GOAL_REACHED = "goal_reached"
    GOAL_UPDATED = "goal_updated"
    HARDCODED_SOUND_EFFECT_HEARD = "hardcodedSoundEffectHeard"
    HEALTH = "health"
    INJECT_ALLOWED = "inject_allowed"
    ITEM_DROP = "itemDrop"
    KICKED = "kicked"
    LOGIN = "login"
    MESSAGE = "message"
    MESSAGESTR = "messagestr"
    MOUNT = "mount"
    MOVE = "move"
    NOTE_HEARD = "noteHeard"
    PARTICLE = "particle"
    PATH_RESET = "path_reset"
    PATH_STOP = "path_stop"
    PATH_UPDATE = "path_update"
    PHYSIC_TICK = "physicTick"
    PHYSICS_TICK = "physicsTick"
    PISTON_MOVE = "pistonMove"
    PLAYER_COLLECT = "playerCollect"
    PLAYER_JOINED = "playerJoined"
    PLAYER_LEFT = "playerLeft"
    PLAYER_UPDATED = "playerUpdated"
    RAIN = "rain"
    RESOURCE_PACK = "resourcePack"
    RESPAWN = "respawn"
    SCORE_REMOVED = "scoreRemoved"
    SCORE_UPDATED = "scoreUpdated"
    SCOREBOARD_CREATED = "scoreboardCreated"
    SCOREBOARD_DELETED = "scoreboardDeleted"
    SCOREBOARD_POSITION = "scoreboardPosition"
    SCOREBOARD_TITLE_CHANGED = "scoreboardTitleChanged"
    SLEEP = "sleep"
    SOUND_EFFECT_HEARD = "soundEffectHeard"
    SPAWN = "spawn"
    SPAWN_RESET = "spawnReset"
    TEAM_CREATED = "teamCreated"
    TEAM_MEMBER_ADDED = "teamMemberAdded"
    TEAM_MEMBER_REMOVED = "teamMemberRemoved"
    TEAM_REMOVED = "teamRemoved"
    TEAM_UPDATED = "teamUpdated"
    TIME = "time"
    TITLE = "title"
    UNMATCHED_MESSAGE = "unmatchedMessage"
    USED_FIREWORK = "usedFirework"
    WAKE = "wake"
    WHISPER = "whisper"
    WINDOW_CLOSE = "windowClose"
    WINDOW_OPEN = "windowOpen"


EVENT_ATTRIBUTE_MAP = {
    "action_bar": BotEvent.ACTION_BAR,
    "block_break_progress_end": BotEvent.BLOCK_BREAK_PROGRESS_END,
    "block_break_progress_observed": BotEvent.BLOCK_BREAK_PROGRESS_OBSERVED,
    "block_update": BotEvent.BLOCK_UPDATE,
    "boss_bar_created": BotEvent.BOSS_BAR_CREATED,
    "boss_bar_deleted": BotEvent.BOSS_BAR_DELETED,
    "boss_bar_updated": BotEvent.BOSS_BAR_UPDATED,
    "breath": BotEvent.BREATH,
    "chat": BotEvent.CHAT,
    "chest_lid_move": BotEvent.CHEST_LID_MOVE,
    "chunk_column_load": BotEvent.CHUNK_COLUMN_LOAD,
    "chunk_column_unload": BotEvent.CHUNK_COLUMN_UNLOAD,
    "death": BotEvent.DEATH,
    "digging_aborted": BotEvent.DIGGING_ABORTED,
    "digging_completed": BotEvent.DIGGING_COMPLETED,
    "dismount": BotEvent.DISMOUNT,
    "end": BotEvent.END,
    "entity_attach": BotEvent.ENTITY_ATTACH,
    "entity_attributes": BotEvent.ENTITY_ATTRIBUTES,
    "entity_critical_effect": BotEvent.ENTITY_CRITICAL_EFFECT,
    "entity_crouch": BotEvent.ENTITY_CROUCH,
    "entity_dead": BotEvent.ENTITY_DEAD,
    "entity_detach": BotEvent.ENTITY_DETACH,
    "entity_eat": BotEvent.ENTITY_EAT,
    "entity_eating_grass": BotEvent.ENTITY_EATING_GRASS,
    "entity_effect": BotEvent.ENTITY_EFFECT,
    "entity_effect_end": BotEvent.ENTITY_EFFECT_END,
    "entity_elytra_flew": BotEvent.ENTITY_ELYTRA_FLEW,
    "entity_equip": BotEvent.ENTITY_EQUIP,
    "entity_gone": BotEvent.ENTITY_GONE,
    "entity_hand_swap": BotEvent.ENTITY_HAND_SWAP,
    "entity_hurt": BotEvent.ENTITY_HURT,
    "entity_magic_critical_effect": BotEvent.ENTITY_MAGIC_CRITICAL_EFFECT,
    "entity_moved": BotEvent.ENTITY_MOVED,
    "entity_shaking_off_water": BotEvent.ENTITY_SHAKING_OFF_WATER,
    "entity_sleep": BotEvent.ENTITY_SLEEP,
    "entity_spawn": BotEvent.ENTITY_SPAWN,
    "entity_swing_arm": BotEvent.ENTITY_SWING_ARM,
    "entity_tamed": BotEvent.ENTITY_TAMED,
    "entity_taming": BotEvent.ENTITY_TAMING,
    "entity_uncrouch": BotEvent.ENTITY_UNCROUCH,
    "entity_update": BotEvent.ENTITY_UPDATE,
    "entity_wake": BotEvent.ENTITY_WAKE,
    "error": BotEvent.ERROR,
    "experience": BotEvent.EXPERIENCE,
    "forced_move": BotEvent.FORCED_MOVE,
    "game": BotEvent.GAME,
    "goal_reached": BotEvent.GOAL_REACHED,
    "goal_updated": BotEvent.GOAL_UPDATED,
    "hardcoded_sound_effect_heard": BotEvent.HARDCODED_SOUND_EFFECT_HEARD,
    "health": BotEvent.HEALTH,
    "inject_allowed": BotEvent.INJECT_ALLOWED,
    "item_drop": BotEvent.ITEM_DROP,
    "kicked": BotEvent.KICKED,
    "login": BotEvent.LOGIN,
    "message": BotEvent.MESSAGE,
    "messagestr": BotEvent.MESSAGESTR,
    "mount": BotEvent.MOUNT,
    "move": BotEvent.MOVE,
    "note_heard": BotEvent.NOTE_HEARD,
    "particle": BotEvent.PARTICLE,
    "path_reset": BotEvent.PATH_RESET,
    "path_stop": BotEvent.PATH_STOP,
    "path_update": BotEvent.PATH_UPDATE,
    "physic_tick": BotEvent.PHYSIC_TICK,
    "physics_tick": BotEvent.PHYSICS_TICK,
    "piston_move": BotEvent.PISTON_MOVE,
    "player_collect": BotEvent.PLAYER_COLLECT,
    "player_joined": BotEvent.PLAYER_JOINED,
    "player_left": BotEvent.PLAYER_LEFT,
    "player_updated": BotEvent.PLAYER_UPDATED,
    "rain": BotEvent.RAIN,
    "resource_pack": BotEvent.RESOURCE_PACK,
    "respawn": BotEvent.RESPAWN,
    "score_removed": BotEvent.SCORE_REMOVED,
    "score_updated": BotEvent.SCORE_UPDATED,
    "scoreboard_created": BotEvent.SCOREBOARD_CREATED,
    "scoreboard_deleted": BotEvent.SCOREBOARD_DELETED,
    "scoreboard_position": BotEvent.SCOREBOARD_POSITION,
    "scoreboard_title_changed": BotEvent.SCOREBOARD_TITLE_CHANGED,
    "sleep": BotEvent.SLEEP,
    "sound_effect_heard": BotEvent.SOUND_EFFECT_HEARD,
    "spawn": BotEvent.SPAWN,
    "spawn_reset": BotEvent.SPAWN_RESET,
    "team_created": BotEvent.TEAM_CREATED,
    "team_member_added": BotEvent.TEAM_MEMBER_ADDED,
    "team_member_removed": BotEvent.TEAM_MEMBER_REMOVED,
    "team_removed": BotEvent.TEAM_REMOVED,
    "team_updated": BotEvent.TEAM_UPDATED,
    "time": BotEvent.TIME,
    "title": BotEvent.TITLE,
    "unmatched_message": BotEvent.UNMATCHED_MESSAGE,
    "used_firework": BotEvent.USED_FIREWORK,
    "wake": BotEvent.WAKE,
    "whisper": BotEvent.WHISPER,
    "window_close": BotEvent.WINDOW_CLOSE,
    "window_open": BotEvent.WINDOW_OPEN,
}

__all__ = ["EVENT_ATTRIBUTE_MAP", "BotEvent"]
