<div align="center">

[![Banner](.github/assets/banner.png)](https://github.com/Hack-the-SDGs/pyflayer)
[![License](https://img.shields.io/github/license/Hack-the-SDGs/pyflayer?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.14%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-24%2B-339933?style=for-the-badge&logo=node.js&logoColor=white)](https://nodejs.org)

</div>

## 總覽

pyflayer 讓你用 Python 寫 Minecraft bot，不需要碰 JavaScript。

底層透過 [JSPyBridge](https://github.com/extremeheat/JSPyBridge) 驅動 [mineflayer](https://github.com/PrismarineJS/mineflayer)，但公開 API 是純 Python — 全 async/await、有完整型別提示、有 docstring。

### 特色

- **Pythonic API** — `await bot.goto(100, 64, 200)` 就這麼簡單
- **完整型別** — 所有公開 API 都有 type hints，IDE 自動補全
- **事件系統** — decorator 風格的事件訂閱，支援 async handler
- **Pathfinding** — 內建 mineflayer-pathfinder，A* 導航
- **Escape Hatch** — `bot.raw` 直接存取底層 JS bot，進階用途不受限

## 前置需求

| 項目 | 需求 |
|------|------|
| Python | 3.14+ |
| Node.js | 18+ |
| Minecraft Server | Java Edition |

## 安裝

```bash
uv add pyflayer
```

> Node.js 必須在 PATH 中可用。pyflayer 啟動時會自動檢查。

## 快速開始

```python
import asyncio
from pyflayer import Bot
from pyflayer.models.events import ChatEvent

async def main():
    bot = Bot(host="localhost", port=25565, username="pybot")

    @bot.observe.on(ChatEvent)
    async def on_chat(event: ChatEvent):
        if event.sender != bot.username:
            await bot.chat(f"You said: {event.message}")

    await bot.connect()
    await bot.wait_until_spawned()
    print(f"Bot spawned at {bot.position}")
    await bot.chat("Hello from pyflayer!")

    try:
        while bot.is_connected:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await bot.disconnect()

asyncio.run(main())
```

## 範例

| 範例 | 說明 |
|------|------|
| [01_hello_bot](examples/01_hello_bot/) | 基本連線與聊天回覆 |
| [02_goto_player](examples/02_goto_player/) | 導航到玩家位置、跟隨指令 |
| [03_drasl_auth](examples/03_drasl_auth/) | 透過自建 Drasl 驗證伺服器連線 |

## 專案結構

```
src/pyflayer/
├── bot.py              # Bot 主類別（公開入口）
├── config.py           # BotConfig 設定
├── raw.py              # Raw escape hatch
├── models/             # 純 Python 資料結構
│   ├── vec3.py         # Vec3 座標
│   ├── block.py        # Block 方塊
│   ├── entity.py       # Entity 實體
│   ├── item.py         # ItemStack 物品
│   ├── events.py       # 事件 dataclass
│   └── errors.py       # 例外層級
├── api/                # 子 API
│   ├── navigation.py   # 路徑規劃
│   └── observe.py      # 事件訂閱
└── _bridge/            # 私有 JSPyBridge 橋接層
    ├── runtime.py      # Node.js 生命週期
    ├── js_bot.py       # JS bot 操作封裝
    ├── event_relay.py  # 事件橋接
    └── marshalling.py  # JS→Python 轉換
```

## 開發

```bash
# 安裝開發依賴
uv sync --group dev

# 執行測試
uv run pytest

# Lint
uv run ruff check src/

# 型別檢查
uv run pyright
```

## 貢獻
歡迎 PR 與 Issue！

送出前請確認
1. 遵循現有的程式碼風格與架構慣例
2. 通過所有檢查測試 
    - uv run pytest
    - uv run ruff check src/
    - uv run pyright
3. 以 `feature/your-feature` 或 `fix/your-fix` 命名分支
4. 發布 PR 時，目標分支為 `dev`

## 授權
本專案採用 [GNU Affero General Public License v3.0](LICENSE) 授權。
