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
 *
 *   Void methods (no return value):
 *     success -> bot.emit('_minethon:<name>Done')                    // no args
 *     failure -> bot.emit('_minethon:<name>Done', errorMsg)          // one string arg
 *
 *   Value-returning methods (openContainer, tabComplete, etc.):
 *     success -> bot.emit('_minethon:<name>Done', null, result)      // null error + result
 *     failure -> bot.emit('_minethon:<name>Done', errorMsg)          // one string arg
 */

const _err = (err) => err?.message ?? String(err);

module.exports = {

    // -- Digging / Placing --

    startDig(bot, block) {
        bot.dig(block)
            .then(() => bot.emit("_minethon:digDone"))
            .catch(err => bot.emit("_minethon:digDone", _err(err)));
    },

    startPlace(bot, refBlock, faceVec) {
        bot.placeBlock(refBlock, faceVec)
            .then(() => bot.emit("_minethon:placeDone"))
            .catch(err => bot.emit("_minethon:placeDone", _err(err)));
    },

    // -- Equipment --

    startEquip(bot, item, destination) {
        bot.equip(item, destination)
            .then(() => bot.emit("_minethon:equipDone"))
            .catch(err => bot.emit("_minethon:equipDone", _err(err)));
    },

    startUnequip(bot, destination) {
        bot.unequip(destination)
            .then(() => bot.emit("_minethon:unequipDone"))
            .catch(err => bot.emit("_minethon:unequipDone", _err(err)));
    },

    // -- Movement / Look --

    startLookAt(bot, pos) {
        bot.lookAt(pos)
            .then(() => bot.emit("_minethon:lookAtDone"))
            .catch(err => bot.emit("_minethon:lookAtDone", _err(err)));
    },

    startLook(bot, yaw, pitch, force) {
        bot.look(yaw, pitch, force)
            .then(() => bot.emit("_minethon:lookDone"))
            .catch(err => bot.emit("_minethon:lookDone", _err(err)));
    },

    // -- Sleep --

    startSleep(bot, bedBlock) {
        bot.sleep(bedBlock)
            .then(() => bot.emit("_minethon:sleepDone"))
            .catch(err => bot.emit("_minethon:sleepDone", _err(err)));
    },

    startWake(bot) {
        bot.wake()
            .then(() => bot.emit("_minethon:wakeDone"))
            .catch(err => bot.emit("_minethon:wakeDone", _err(err)));
    },

    // -- Inventory --

    startTossStack(bot, item) {
        bot.tossStack(item)
            .then(() => bot.emit("_minethon:tossStackDone"))
            .catch(err => bot.emit("_minethon:tossStackDone", _err(err)));
    },

    startToss(bot, itemType, metadata, count) {
        bot.toss(itemType, metadata, count)
            .then(() => bot.emit("_minethon:tossDone"))
            .catch(err => bot.emit("_minethon:tossDone", _err(err)));
    },

    // -- Actions --

    startConsume(bot) {
        bot.consume()
            .then(() => bot.emit("_minethon:consumeDone"))
            .catch(err => bot.emit("_minethon:consumeDone", _err(err)));
    },

    startFish(bot) {
        bot.fish()
            .then(() => bot.emit("_minethon:fishDone"))
            .catch(err => bot.emit("_minethon:fishDone", _err(err)));
    },

    startElytraFly(bot) {
        bot.elytraFly()
            .then(() => bot.emit("_minethon:elytraFlyDone"))
            .catch(err => bot.emit("_minethon:elytraFlyDone", _err(err)));
    },

    // -- Crafting --

    startCraft(bot, recipe, count, craftingTable) {
        bot.craft(recipe, count, craftingTable)
            .then(() => bot.emit("_minethon:craftDone"))
            .catch(err => bot.emit("_minethon:craftDone", _err(err)));
    },

    // -- Block / Entity Interaction --

    startActivateBlock(bot, block, direction, cursorPos) {
        bot.activateBlock(block, direction, cursorPos)
            .then(() => bot.emit("_minethon:activateBlockDone"))
            .catch(err => bot.emit("_minethon:activateBlockDone", _err(err)));
    },

    startActivateEntity(bot, entity) {
        bot.activateEntity(entity)
            .then(() => bot.emit("_minethon:activateEntityDone"))
            .catch(err => bot.emit("_minethon:activateEntityDone", _err(err)));
    },

    startActivateEntityAt(bot, entity, position) {
        bot.activateEntityAt(entity, position)
            .then(() => bot.emit("_minethon:activateEntityAtDone"))
            .catch(err => bot.emit("_minethon:activateEntityAtDone", _err(err)));
    },

    // -- Containers (value-returning) --

    startOpenContainer(bot, containerBlockOrEntity, direction, cursorPos) {
        bot.openContainer(containerBlockOrEntity, direction, cursorPos)
            .then(window => bot.emit("_minethon:openContainerDone", null, window))
            .catch(err => bot.emit("_minethon:openContainerDone", _err(err)));
    },

    startOpenFurnace(bot, furnaceBlock) {
        bot.openFurnace(furnaceBlock)
            .then(furnace => bot.emit("_minethon:openFurnaceDone", null, furnace))
            .catch(err => bot.emit("_minethon:openFurnaceDone", _err(err)));
    },

    startOpenEnchantmentTable(bot, block) {
        bot.openEnchantmentTable(block)
            .then(table => bot.emit("_minethon:openEnchantmentTableDone", null, table))
            .catch(err => bot.emit("_minethon:openEnchantmentTableDone", _err(err)));
    },

    startOpenAnvil(bot, block) {
        bot.openAnvil(block)
            .then(anvil => bot.emit("_minethon:openAnvilDone", null, anvil))
            .catch(err => bot.emit("_minethon:openAnvilDone", _err(err)));
    },

    startOpenVillager(bot, entity) {
        bot.openVillager(entity)
            .then(villager => bot.emit("_minethon:openVillagerDone", null, villager))
            .catch(err => bot.emit("_minethon:openVillagerDone", _err(err)));
    },

    // -- Trading --

    startTrade(bot, villagerInstance, tradeIndex, times) {
        bot.trade(villagerInstance, tradeIndex, times)
            .then(() => bot.emit("_minethon:tradeDone"))
            .catch(err => bot.emit("_minethon:tradeDone", _err(err)));
    },

    // -- Tab Completion (value-returning) --

    startTabComplete(bot, str, assumeCommand, sendBlockInSight, timeout) {
        bot.tabComplete(str, assumeCommand, sendBlockInSight, timeout)
            .then(matches => bot.emit("_minethon:tabCompleteDone", null, matches))
            .catch(err => bot.emit("_minethon:tabCompleteDone", _err(err)));
    },

    // -- Writing --

    startWriteBook(bot, slot, pages) {
        bot.writeBook(slot, pages)
            .then(() => bot.emit("_minethon:writeBookDone"))
            .catch(err => bot.emit("_minethon:writeBookDone", _err(err)));
    },

    // -- World --

    startWaitForChunksToLoad(bot) {
        bot.waitForChunksToLoad()
            .then(() => bot.emit("_minethon:chunksLoadedDone"))
            .catch(err => bot.emit("_minethon:chunksLoadedDone", _err(err)));
    },

    startWaitForTicks(bot, ticks) {
        bot.waitForTicks(ticks)
            .then(() => bot.emit("_minethon:waitForTicksDone"))
            .catch(err => bot.emit("_minethon:waitForTicksDone", _err(err)));
    },

    // -- Lower-level Window / Slot Operations --

    startClickWindow(bot, slot, mouseButton, mode) {
        bot.clickWindow(slot, mouseButton, mode)
            .then(() => bot.emit("_minethon:clickWindowDone"))
            .catch(err => bot.emit("_minethon:clickWindowDone", _err(err)));
    },

    startTransfer(bot, options) {
        bot.transfer(options)
            .then(() => bot.emit("_minethon:transferDone"))
            .catch(err => bot.emit("_minethon:transferDone", _err(err)));
    },

    startMoveSlotItem(bot, sourceSlot, destSlot) {
        bot.moveSlotItem(sourceSlot, destSlot)
            .then(() => bot.emit("_minethon:moveSlotItemDone"))
            .catch(err => bot.emit("_minethon:moveSlotItemDone", _err(err)));
    },

    startPutAway(bot, slot) {
        bot.putAway(slot)
            .then(() => bot.emit("_minethon:putAwayDone"))
            .catch(err => bot.emit("_minethon:putAwayDone", _err(err)));
    },

    // -- Creative Mode --

    startCreativeFlyTo(bot, destination) {
        bot.creative.flyTo(destination)
            .then(() => bot.emit("_minethon:creativeFlyToDone"))
            .catch(err => bot.emit("_minethon:creativeFlyToDone", _err(err)));
    },

    startCreativeSetInventorySlot(bot, slot, item) {
        bot.creative.setInventorySlot(slot, item)
            .then(() => bot.emit("_minethon:creativeSetSlotDone"))
            .catch(err => bot.emit("_minethon:creativeSetSlotDone", _err(err)));
    },

    startCreativeClearSlot(bot, slot) {
        bot.creative.clearSlot(slot)
            .then(() => bot.emit("_minethon:creativeClearSlotDone"))
            .catch(err => bot.emit("_minethon:creativeClearSlotDone", _err(err)));
    },

    startCreativeClearInventory(bot) {
        bot.creative.clearInventory()
            .then(() => bot.emit("_minethon:creativeClearInventoryDone"))
            .catch(err => bot.emit("_minethon:creativeClearInventoryDone", _err(err)));
    },

    // -- Entity Placement (value-returning) --

    startPlaceEntity(bot, refBlock, faceVec) {
        bot.placeEntity(refBlock, faceVec)
            .then(entity => bot.emit("_minethon:placeEntityDone", null, entity))
            .catch(err => bot.emit("_minethon:placeEntityDone", _err(err)));
    },
};
