# drasl_auth demo

Connects to a Minecraft server that uses a custom [Drasl](https://github.com/unmojang/drasl)
auth server (instead of Mojang / Microsoft session servers).

## Setup

```bash
./setup.sh   # one-time install of Python + npm dependencies
cp examples/demos/drasl_auth/.env.example examples/demos/drasl_auth/.env
# Edit .env with your credentials
```

## Run

```bash
uv run --env-file examples/demos/drasl_auth/.env examples/demos/drasl_auth/main.py
```

## What it does

- Logs in via the configured Drasl auth/session servers.
- Announces the spawn position in the terminal and chats a greeting in-game.
- Responds to a few chat triggers sent by other players:
  - `quit` → bot disconnects cleanly
  - `where` → bot replies with its current coords
  - `players` → bot lists the usernames currently online
- Prints reasons on `kicked` / `end` events so you can tell why the bot
  disconnected.

Use Ctrl-C to stop the bot locally — `run_forever()` exits cleanly on
`KeyboardInterrupt`.
