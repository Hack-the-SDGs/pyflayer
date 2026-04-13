const mineflayer = require('mineflayer')
require("dotenv").config();

const bot = mineflayer.createBot({
    host: process.env.MC_HOST,
    port: 25565,
    username: process.env.MC_USERNAME,
    password: process.env.MC_PASSWORD,
    auth: 'mojang',
    authServer: process.env.MC_AUTH_SERVER,
    sessionServer: process.env.MC_SESSION_SERVER,
})

bot.on('chat', (username, message) => {
    if (username === bot.username) return;

    if (message.startsWith('can see')) {
        try {
            const coords = message.split('see')[1]
                .replace(/,/g, ' ')
                .trim()
                .split(/\s+/)
                .map(Number);

            if (coords.length === 3 && !coords.some(isNaN)) {
                canSee(new Vec3(...coords));
            } else {
                bot.chat('Bad syntax');
            }
        } catch (e) {
            bot.chat('Bad syntax');
        }
    } else if (message.startsWith('pos')) {
        sayPosition(username);
    } else if (message.startsWith('wearing')) {
        sayEquipment(username);
    } else if (message.startsWith('block')) {
        sayBlockUnder(username);
    } else if (message.startsWith('spawn')) {
        saySpawn();
    } else if (message.startsWith('quit')) {
        quitGame(username);
    } else {
        bot.chat("That's nice");
    }
});

function canSee(pos) {
    const block = bot.blockAt(pos);
    if (!block) return;

    const isVisible = bot.canSeeBlock(block);
    bot.chat(isVisible
        ? `I can see the block of ${block.displayName} at ${pos}`
        : `I can't see the block of ${block.displayName} at ${pos}`
    );
}

function sayPosition(username) {
    bot.chat(`I am at ${bot.entity.position}`);
    const targetEntity = bot.players[username]?.entity;
    if (targetEntity) {
        bot.chat(`You are at ${targetEntity.position}`);
    }
}

function sayEquipment(username) {
    const eq = bot.players[username]?.entity?.equipment;
    if (!eq) {
        bot.chat("I can't see you right now.");
        return;
    }

    const eqText = [];
    if (eq[0]) eqText.push(`holding a ${eq[0].displayName}`);
    if (eq[1]) eqText.push(`wearing a ${eq[1].displayName} on your feet`);
    if (eq[2]) eqText.push(`wearing a ${eq[2].displayName} on your legs`);
    if (eq[3]) eqText.push(`wearing a ${eq[3].displayName} on your torso`);
    if (eq[4]) eqText.push(`wearing a ${eq[4].displayName} on your head`);

    if (eqText.length) {
        bot.chat(`You are ${eqText.join(', ')}.`);
    } else {
        bot.chat("You are naked!");
    }
}

function saySpawn() {
    bot.chat(`Spawn is at ${bot.spawnPoint}`);
}

function sayBlockUnder(username) {
    const targetEntity = bot.players[username]?.entity;
    if (!targetEntity) return;

    const block = bot.blockAt(targetEntity.position.offset(0, -1, 0));
    if (block) {
        bot.chat(`Block under you is ${block.displayName} in the ${block.biome.name} biome`);
        console.log(block);
    }
}

function quitGame(username) {
    bot.quit(`${username} told me to`);
}

bot.on('whisper', (username, message) => {
    console.log(`I received a message from ${username}: ${message}`);
    bot.whisper(username, "I can tell secrets too.");
});

bot.on('nonSpokenChat', (message) => {
    console.log(`Non spoken chat: ${message}`);
});

bot.on('login', () => {
    bot.chat("Hi everyone!");
});

bot.on('spawn', () => {
    bot.chat("I spawned, watch out!");
});

bot.on('spawnReset', () => {
    bot.chat("Oh noez! My bed is broken.");
});

bot.on('forcedMove', () => {
    bot.chat(`I have been forced to move to ${bot.entity.position}`);
});

bot.on('health', () => {
    bot.chat(`I have ${bot.health} health and ${bot.food} food`);
});

bot.on('death', () => {
    bot.chat("I died x.x");
});

bot.on('kicked', (reason) => {
    console.log("I was kicked", reason);
});

bot.on('time', () => {
    // bot.chat(`Current time: ${bot.time.timeOfDay}`);
});

bot.on('rain', () => {
    bot.chat(bot.isRaining ? "It started raining" : "It stopped raining");
});

bot.on('noteHeard', (block, instrument, pitch) => {
    bot.chat(`Music for my ears! I just heard a ${instrument.name}`);
});

bot.on('chestLidMove', (block, isOpen) => {
    const action = isOpen ? "open" : "close";
    bot.chat(`Hey, did someone just ${action} a chest?`);
});

bot.on('pistonMove', (block, isPulling, direction) => {
    const action = isPulling ? "pulling" : "pushing";
    // bot.chat(`A piston is ${action} near me, i can hear it.`);
});

bot.on('playerJoined', (player) => {
    console.log("joined", player.username);
    if (player.username !== bot.username) {
        bot.chat(`Hello, ${player.username}! Welcome to the server.`);
    }
});

bot.on('playerLeft', (player) => {
    if (player.username === bot.username) return;
    bot.chat(`Bye ${player.username}`);
});

bot.on('entitySpawn', (entity) => {
    if (entity.type === 'mob') {
        console.log(`Look out! A ${entity.displayName} spawned at ${entity.position}`);
    } else if (entity.type === 'player') {
        bot.chat(`Look who decided to show up: ${entity.username}`);
    } else if (entity.type === 'object') {
        console.log(`There's a ${entity.displayName} at ${entity.position}`);
    } else if (entity.type === 'global') {
        bot.chat("Ooh lightning!");
    } else if (entity.type === 'orb') {
        bot.chat("Gimme dat exp orb!");
    }
});

bot.on('entityHurt', (entity) => {
    if (entity.type === 'mob') {

        bot.chat(`Haha! The ${entity.displayName} got hurt!`);
    } else if (entity.type === 'player') {
        const ping = bot.players[entity.username]?.ping;
        bot.chat(`Aww, poor ${entity.username} got hurt. Maybe you shouldn't have a ping of ${ping}`);
    }
});

bot.on('entitySwingArm', (entity) => {
    bot.chat(`${entity.username}, I see that your arm is working fine.`);
});

bot.on('entityCrouch', (entity) => {
    bot.chat(`${entity.username}: you so sneaky.`);
});

bot.on('entityUncrouch', (entity) => {
    bot.chat(`${entity.username}: welcome back from the land of hunchbacks.`);
});

bot.on('entitySleep', (entity) => {
    bot.chat(`Good night, ${entity.username}`);
});

bot.on('entityWake', (entity) => {
    bot.chat(`Top of the morning, ${entity.username}`);
});

bot.on('entityEat', (entity) => {
    bot.chat(`${entity.username}: OM NOM NOM NOMONOM. That's what you sound like.`);
});

bot.on('entityAttach', (entity, vehicle) => {
    if (entity.type === 'player' && vehicle.type === 'object') {
        console.log(`Sweet, ${entity.username} is riding that ${vehicle.displayName}`);
    }
});

bot.on('entityDetach', (entity, vehicle) => {
    if (entity.type === 'player' && vehicle.type === 'object') {
        console.log(`Lame, ${entity.username} stopped riding the ${vehicle.displayName}`);
    }
});

bot.on('entityEquipmentChange', (entity) => {
    console.log("entityEquipmentChange", entity.username || entity.displayName);
});

bot.on('entityEffect', (entity, effect) => {
    console.log("entityEffect", entity.username || entity.displayName, effect);
});

bot.on('entityEffectEnd', (entity, effect) => {
    console.log("entityEffectEnd", entity.username || entity.displayName, effect);
});