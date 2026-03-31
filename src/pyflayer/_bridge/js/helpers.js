"use strict";

/**
 * Async operation wrappers for pyflayer.
 *
 * These functions start mineflayer actions that return Promises without
 * blocking the caller.  Completion (or failure) is signalled via custom
 * events on the bot EventEmitter so that the Python side can await them
 * with asyncio Futures.
 *
 * Event contract – each helper emits exactly ONE event:
 *   success → bot.emit('<name>Done')            // no args
 *   failure → bot.emit('<name>Done', errorMsg)   // one string arg
 */

module.exports = {
    startDig(bot, block) {
        bot.dig(block)
            .then(() => bot.emit("_pyflayer:digDone"))
            .catch(err => bot.emit("_pyflayer:digDone", err?.message ?? String(err)));
    },

    startPlace(bot, refBlock, faceVec) {
        bot.placeBlock(refBlock, faceVec)
            .then(() => bot.emit("_pyflayer:placeDone"))
            .catch(err => bot.emit("_pyflayer:placeDone", err?.message ?? String(err)));
    },

    startEquip(bot, item, destination) {
        bot.equip(item, destination)
            .then(() => bot.emit("_pyflayer:equipDone"))
            .catch(err => bot.emit("_pyflayer:equipDone", err?.message ?? String(err)));
    },

    startLookAt(bot, pos) {
        bot.lookAt(pos)
            .then(() => bot.emit("_pyflayer:lookAtDone"))
            .catch(err => bot.emit("_pyflayer:lookAtDone", err?.message ?? String(err)));
    },
};
