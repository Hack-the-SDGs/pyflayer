# minethon

minethon 是教學導向的 Python mineflayer SDK。

它保留 mineflayer 的能力，但把公開 API 收斂成同步 callback、薄門面、完整 stub，讓學生不需要先學 Node.js、EventEmitter、asyncio。

## 目前定位

- Python 3.14+
- Node.js 22+
- bridge: `javascript` / JSPyBridge
- 內建預裝且有型別支援的 plugin: `mineflayer-pathfinder`
- 其他 npm 套件可用 `bot.load_plugin(name, "x.y.z")` 或 `bot.require(name, "x.y.z")`，但必須顯式版本

## 安裝

```bash
./setup.sh
```

`setup.sh` 會：

- `uv sync`
- 檢查 Node.js 22+
- 預裝 pinned 的 `mineflayer`、`vec3`、`mineflayer-pathfinder`

## 快速開始

```python
from minethon import BotEvent, create_bot
from minethon.models import ChatMessage

bot = create_bot(host="localhost", username="pybot")

@bot.on_spawn
def on_spawn() -> None:
    bot.chat("hello")

@bot.on_chat
def on_chat(
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

@bot.on(BotEvent.END)
def on_end(reason: str) -> None:
    print(f"Disconnected: {reason}")

bot.run_forever()
```

## 兩種事件寫法

以下兩種都支援：

```python
@bot.on_chat
def on_chat(...): ...

@bot.on(BotEvent.CHAT)
def on_chat(...): ...
```

如果你用的是 IDEA Ultimate / PyCharm：

- `@bot.on_chat` 通常是最直接的 completion 路徑
- `@bot.on(BotEvent.CHAT)` 適合想保留顯式 event enum 的寫法
- `@bot.on("chat")` 已移除，不再是公開 API

## 型別與匯入

常用型別可從 `minethon.models` 匯入：

```python
from minethon.models import Block, ChatMessage, Entity, Item, Player, Vec3
```

這些是公開型別 shell，實際成員定義以 [`src/minethon/bot.pyi`](src/minethon/bot.pyi) 為準。

## 版本規則

- `create_bot(...)` 內部固定使用 pinned 的 `mineflayer`
- `bot.load_plugin("mineflayer-pathfinder")` 可省略版本，會用內建 pin
- 其他套件必須顯式版本，例如：

```python
viewer = bot.require("prismarine-viewer", "1.33.0")
tool = bot.load_plugin("mineflayer-tool", "1.5.0", export_key="plugin")
```

這是刻意設計，用來避免 JSPyBridge 在 runtime 偷裝 latest。

## 主要檔案

- `src/minethon/bot.py`: runtime façade
- `src/minethon/bot.pyi`: 生成的 IDE 型別層
- `src/minethon/_events.py`: 生成的 `BotEvent`
- `src/minethon/models/`: 可匯入的公開型別 shell
- `scripts/generate_stubs.py`: 從 mineflayer / pathfinder d.ts 生成 stub
- `docs/stubs_zh_tw.md`: 中文 hover 說明來源

## 開發檢查

```bash
uv run python scripts/generate_stubs.py
uv run pytest -m "not integration" --tb=short -q
uv run ruff format --check src/minethon tests/
uv run ruff check src/minethon tests/
uv run pyright src/
```

## 範例

- [`examples/demos/drasl_auth/main.py`](examples/demos/drasl_auth/main.py)
