"""drasl_auth — connect to a Drasl-authenticated Minecraft server.

Prerequisites:
    ./setup.sh   # installs Python deps + pinned npm packages

Copy the example env file and fill in credentials:
    cp examples/demos/drasl_auth/.env.example examples/demos/drasl_auth/.env

Run:
    uv run --env-file examples/demos/drasl_auth/.env examples/demos/drasl_auth/main.py
"""

from __future__ import annotations

import os

from minethon import EventAdaptor, create_bot
from minethon.models import ChatMessage


def main() -> None:
    bot = create_bot(
        host=os.environ["MC_HOST"],
        port=int(os.environ.get("MC_PORT", "25565")),
        username=os.environ["MC_USERNAME"],
        password=os.environ["MC_PASSWORD"],
        auth="mojang",
        auth_server=os.environ["MC_AUTH_SERVER"],
        session_server=os.environ["MC_SESSION_SERVER"],
    )

    class Events(EventAdaptor):
        def on_login(self) -> None:
            print(f"Logged in as {bot.username}")

        def on_spawn(self) -> None:
            p = bot.entity.position
            print(f"Spawned at ({p.x:.1f}, {p.y:.1f}, {p.z:.1f})")
            bot.chat("Hello from minethon!")

        def on_chat(
            self,
            username: str,
            message: str,
            translate: str | None,
            json_msg: ChatMessage,
            matches: list[str] | None,
        ) -> None:
            if username == bot.username:
                return

            if message == "quit":
                bot.quit("bye")

            elif message == "where":
                if (e := bot.entity) is None:
                    return

                if (p := e.position) is None:
                    return

                bot.chat(f"I'm at ({p.x:.1f}, {p.y:.1f}, {p.z:.1f})")

            elif message == "players":
                names = list(bot.players)
                bot.chat(f"Online: {', '.join(names)}")

        def on_kicked(self, reason: str, logged_in: bool) -> None:
            print(f"Kicked (loggedIn={logged_in}): {reason}")

        def on_death(self) -> None:
            print()

        def on_end(self, reason: str) -> None:
            print(f"Disconnected: {reason}")

    bot.bind(Events())
    bot.run_forever()


if __name__ == "__main__":
    main()
