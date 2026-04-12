# ==========================================================================
# This example demonstrates how easy it is to create a bot
# that sends chat messages whenever something interesting happens
# on the server you are connected to.
#
# Below you can find a wide range of different events you can watch
# but remember to check out the API documentation to find even more!
#
# Some events may be commented out because they are very frequent and
# may flood the chat, feel free to check them out for other purposes though.
#
# This bot also replies to some specific chat messages so you can ask him
# a few information while you are in game.
# ===========================================================================
import os

from javascript import require, On, console

mineflayer = require("mineflayer", "latest")
Vec3 = require("vec3").Vec3
username = os.environ["MC_USERNAME"]
bot = mineflayer.createBot({
    'host': os.environ["MC_HOST"],
    'port': 25565,
    'username': os.environ["MC_USERNAME"],
    'password': os.environ["MC_PASSWORD"],
    'auth': "mojang",
    'authServer': os.environ["MC_AUTH_SERVER"],
    'sessionServer': os.environ["MC_SESSION_SERVER"],
})


@On(bot, "chat")
def handle(username, message, *args):
    if username == bot.username:
        return

    if message.startswith("can see"):
        # Extract x, y and z
        # e.g. "can see 327 60 -120" or "can see 327, -23, -120"
        try:
            x, y, z = map(lambda v: int(v), message.split("see")[1].replace(",", " ").split())
        except Exception:
            bot.chat("Bad syntax")
    elif message.startswith("pos"):
        say_position(username)
    elif message.startswith("wearing"):
        say_equipment(username)
    elif message.startswith("block"):
        say_block_under()
    elif message.startswith("spawn"):
        say_spawn()
    elif message.startswith("quit"):
        quit_game(username)
    else:
        bot.chat("That's nice")


def can_see(pos):
    block = bot.blockAt(pos)
    canSee = bot.canSeeBlock(block)

    if canSee:
        bot.chat(f"I can see the block of {block.displayName} at {pos}")
    else:
        bot.chat(f"I can't see the block of {block.displayName} at {pos}")


def say_position(username):
    p = bot.entity.position
    bot.chat(f"I am at {p.toString()}")
    if username in bot.players:
        p = bot.players[username].entity.position
        bot.chat(f"You are at {p.toString()}")


def say_equipment(username):
    eq = bot.players[username].entity.equipment
    eqText = []
    if eq[0]:
        eqText.append(f"holding a {eq[0].displayName}")
    if eq[1]:
        eqText.append(f"wearing a {eq[1].displayName} on your feet")
    if eq[2]:
        eqText.append(f"wearing a {eq[2].displayName} on your legs")
    if eq[3]:
        eqText.append(f"wearing a {eq[3].displayName} on your torso")
    if eq[4]:
        eqText.append(f"wearing a {eq[4].displayName} on your head")
    if len(eqText):
        bot.chat(f"You are {', '.join(eqText)}.")
    else:
        bot.chat("You are naked!")


def say_spawn():
    bot.chat(f"Spawn is at {bot.spawnPoint.toString()}")


def say_block_under():
    block = bot.blockAt(bot.players[username].entity.position.offset(0, -1, 0))
    bot.chat(f"Block under you is {block.displayName} in the {block.biome.name} biome")
    print(block)


def quit_game(username):
    bot.quit(f"{username} told me to")


def say_nick():
    bot.chat(f"My name is {bot.player.displayName}")


@On(bot, "whisper")
def whisper(username, message, rawMessage, *a):
    console.log(f"I received a message from {username}: {message}")
    bot.whisper(username, "I can tell secrets too.")


@On(bot, "nonSpokenChat")
def nonSpokenChat(message):
    console.log(f"Non spoken chat: {message}")


@On(bot, "login")
def login():
    bot.chat("Hi everyone!")


@On(bot, "spawn")
def spawn():
    bot.chat("I spawned, watch out!")


@On(bot, "spawnReset")
def spawnReset(message):
    bot.chat("Oh noez! My bed is broken.")


@On(bot, "forcedMove")
def forcedMove():
    p = bot.entity.position
    bot.chat(f"I have been forced to move to {p.toString()}")


@On(bot, "health")
def health():
    bot.chat(f"I have {bot.health} health and {bot.food} food")


@On(bot, "death")
def death():
    bot.chat("I died x.x")


@On(bot, "kicked")
def kicked(reason, *a):
    print("I was kicked", reason, a)
    console.log(f"I got kicked for {reason}")


@On(bot, "time")
def time():
    ...
    # bot.chat(f"Current time: " + str(bot.time.timeOfDay))


@On(bot, "rain")
def rain():
    if bot.isRaining:
        bot.chat("It started raining")
    else:
        bot.chat("It stopped raining")


@On(bot, "noteHeard")
def noteHeard(block, instrument, pitch):
    bot.chat(f"Music for my ears! I just heard a {instrument.name}")


@On(bot, "chestLidMove")
def chestLidMove(block, isOpen, *a):
    action = "open" if isOpen else "close"
    bot.chat(f"Hey, did someone just {action} a chest?")


@On(bot, "pistonMove")
def pistonMove(block, isPulling, direction):
    action = "pulling" if isPulling else "pushing"
    # bot.chat(f"A piston is {action} near me, i can hear it.")


@On(bot, "playerJoined")
def playerJoined(player):
    print("joined", player)
    if player["username"] != bot.username:
        bot.chat(f"Hello, {player['username']}! Welcome to the server.")


@On(bot, "playerLeft")
def playerLeft(player):
    if player["username"] == bot.username:
        return
    bot.chat(f"Bye ${player.username}")


@On(bot, "entitySpawn")
def entitySpawn(entity):
    if entity.type == "mob":
        p = entity.position
        console.log(f"Look out! A {entity.displayName} spawned at {p.toString()}")
    elif entity.type == "player":
        bot.chat(f"Look who decided to show up: {entity.username}")
    elif entity.type == "object":
        p = entity.position
        console.log(f"There's a {entity.displayName} at {p.toString()}")
    elif entity.type == "global":
        bot.chat("Ooh lightning!")
    elif entity.type == "orb":
        bot.chat("Gimme dat exp orb!")


@On(bot, "entityHurt")
def entityHurt(this, entity):
    if entity.type == "mob":
        bot.chat(f"Haha! The ${entity.displayName} got hurt!")
    elif entity.type == "player":
        if entity.username in bot.players:
            ping = bot.players[entity.username].ping
            bot.chat(f"Aww, poor {entity.username} got hurt. Maybe you shouldn't have a ping of {ping}")


@On(bot, "entitySwingArm")
def entitySwingArm(entity):
    bot.chat(f"{entity.username}, I see that your arm is working fine.")


@On(bot, "entityCrouch")
def entityCrouch(entity):
    bot.chat(f"${entity.username}: you so sneaky.")


@On(bot, "entityUncrouch")
def entityUncrouch(entity):
    bot.chat(f"{entity.username}: welcome back from the land of hunchbacks.")


@On(bot, "entitySleep")
def entitySleep(entity):
    bot.chat(f"Good night, {entity.username}")


@On(bot, "entityWake")
def entityWake(entity):
    bot.chat(f"Top of the morning, {entity.username}")


@On(bot, "entityEat")
def entityEat(entity):
    bot.chat(f"{entity.username}: OM NOM NOM NOMONOM. That's what you sound like.")


@On(bot, "entityAttach")
def entityAttach(entity, vehicle):
    if entity.type == "player" and vehicle.type == "object":
        print(f"Sweet, {entity.username} is riding that {vehicle.displayName}")


@On(bot, "entityDetach")
def entityDetach(entity, vehicle):
    if entity.type == "player" and vehicle.type == "object":
        print(f"Lame, {entity.username} stopped riding the {vehicle.displayName}")


@On(bot, "entityEquipmentChange")
def entityEquipmentChange(entity):
    print("entityEquipmentChange", entity)


@On(bot, "entityEffect")
def entityEffect(entity, effect):
    print("entityEffect", entity, effect)


@On(bot, "entityEffectEnd")
def entityEffectEnd(entity, effect):
    print("entityEffectEnd", entity, effect)
