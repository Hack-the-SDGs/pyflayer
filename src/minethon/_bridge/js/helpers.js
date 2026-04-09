"use strict";

/**
 * Async operation wrappers for minethon.
 *
 * These functions start mineflayer actions that return Promises without
 * blocking the caller.  Completion (or failure) is signalled via custom
 * events on the bot EventEmitter so that the Python side can await them
 * with asyncio Futures.
 *
 * Event contract – each helper emits exactly ONE event, namespaced for minethon:
 *   success → bot.emit('_minethon:<name>Done')              // no args
 *   failure → bot.emit('_minethon:<name>Done', errorMsg)    // one string arg
 * where <name> is one of: "dig", "place", "equip", "lookAt".
 */

module.exports = {
    startDig(bot, block) {
        bot.dig(block)
            .then(() => bot.emit("_minethon:digDone"))
            .catch(err => bot.emit("_minethon:digDone", err?.message ?? String(err)));
    },

    startPlace(bot, refBlock, faceVec) {
        bot.placeBlock(refBlock, faceVec)
            .then(() => bot.emit("_minethon:placeDone"))
            .catch(err => bot.emit("_minethon:placeDone", err?.message ?? String(err)));
    },

    startEquip(bot, item, destination) {
        bot.equip(item, destination)
            .then(() => bot.emit("_minethon:equipDone"))
            .catch(err => bot.emit("_minethon:equipDone", err?.message ?? String(err)));
    },

    startLookAt(bot, pos) {
        bot.lookAt(pos)
            .then(() => bot.emit("_minethon:lookAtDone"))
            .catch(err => bot.emit("_minethon:lookAtDone", err?.message ?? String(err)));
    },

    /**
     * Serialise all tracked entities into a plain array in one JS call,
     * avoiding per-entity bridge round-trips from Python.
     *
     * @returns {Array<{id:number, name:string|null, username:string|null,
     *   type:string|null, position:{x:number,y:number,z:number},
     *   velocity:{x:number,y:number,z:number}|null,
     *   health:number|null}>}
     */
    snapshotEntities(bot) {
        const result = [];
        const entities = bot.entities;
        for (const eid in entities) {
            const e = entities[eid];
            if (!e || !e.position) continue;
            const pos = e.position;
            const vel = e.velocity;
            result.push({
                id: e.id,
                name: e.name ?? null,
                username: e.username ?? null,
                type: e.type ?? null,
                position: { x: pos.x, y: pos.y, z: pos.z },
                velocity: vel ? { x: vel.x, y: vel.y, z: vel.z } : null,
                health: e.health ?? null,
            });
        }
        return result;
    },
};
