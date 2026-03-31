# Pyflayer 開發提示詞 — 交給 AI 的完整實作指引

---

## 專案定義

你正在開發 **pyflayer**：一套 Python-first 的 Mineflayer SDK。

pyflayer 的核心理念是：
- **不重寫 mineflayer**，而是建立一層 typed Python façade。
- **底層透過 JSPyBridge（`uv add javascript`）驅動 mineflayer**，但 JSPyBridge 是私有實作細節，不對使用者暴露。
- **公開 API 必須是 Pythonic、有型別、有文件、可維護的**。
- **使用者不需要理解 Node.js、JSPyBridge、EventEmitter 就能開發 Minecraft bot。**

---

## 技術棧

- **語言**：Python 3.14+（公開介面）、Node.js 18+（底層 runtime）
- **Bridge**：JSPyBridge（`javascript` pip package）
- **底層核心**：mineflayer + mineflayer-pathfinder + 常用 plugins
- **Async 模型**：asyncio（公開 API 全部基於 async/await）
- **型別檢查**：mypy / pyright 相容，inline type annotations + `py.typed`
- **測試**：pytest + pytest-asyncio
- **Linting**：ruff
- **文件**：mkdocs-material + mkdocstrings（後期）
- **套件管理**：使用 uv 管理 `pyproject.toml`

---

## 三層架構

pyflayer 採用嚴格的三層分離架構。在寫任何程式碼之前，務必確認你要寫的東西屬於哪一層：

### Layer 1：Private Bridge（`pyflayer/_bridge/`）

- 啟動和管理 JSPyBridge runtime
- 載入 mineflayer 和 plugins（`require()`）
- 綁定 JS 事件，將 JS callback 轉為 Python 端的通知
- 執行 JS 方法呼叫
- 管理 JS 物件生命週期
- **此層的所有模組以 `_` 前綴命名，不在 `__init__.py` 中匯出**
- **此層不定義任何公開型別，只操作 JS proxy objects 和內部 dataclass**

### Layer 2：Domain Model（`pyflayer/models/`）

- 定義 Python 可見的純資料結構（dataclass / enum / TypedDict）
- 不依賴 JSPyBridge 或任何 JS 物件
- 可被獨立 import 和單元測試
- 範例：`Vec3`, `Entity`, `Block`, `ItemStack`, `Window`, `ChatMessage`

### Layer 3：Public SDK（`pyflayer/bot.py`, `pyflayer/api/`）

- 使用者直接互動的層
- 依賴 Layer 2 的型別，透過 Layer 1 的 bridge 執行操作
- 提供 docstring、type hints、高階方法
- 範例：`Bot`, `NavigationAPI`, `InventoryAPI`

**絕對禁止：**
- 公開 API 回傳 JS proxy object
- 公開 API 的 type hint 中出現 `javascript` 模組的任何型別
- 使用者需要 `from javascript import ...` 才能使用基本功能

---

## 目錄結構

```
pyflayer/
├── pyproject.toml
├── README.md
├── src/
│   └── pyflayer/
│       ├── __init__.py          # 匯出 Bot, models, errors
│       ├── py.typed
│       ├── bot.py               # Bot 主類別（façade）
│       ├── config.py            # BotConfig dataclass
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── vec3.py          # Vec3
│       │   ├── entity.py        # Entity, EntityKind
│       │   ├── block.py         # Block
│       │   ├── item.py          # ItemStack
│       │   ├── inventory.py     # InventorySnapshot
│       │   ├── events.py        # 所有高階事件 dataclass
│       │   └── errors.py        # 例外層級
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── navigation.py    # NavigationAPI
│       │   ├── inventory_ops.py # InventoryAPI
│       │   ├── collect.py       # CollectAPI
│       │   ├── combat.py        # CombatAPI
│       │   ├── observe.py       # ObserveAPI（事件訂閱）
│       │   └── plugins.py       # PluginManager
│       │
│       ├── _bridge/
│       │   ├── __init__.py
│       │   ├── runtime.py       # JSPyBridge lifecycle, Node.js 檢查
│       │   ├── js_bot.py        # 封裝 JS bot 物件的所有操作
│       │   ├── event_relay.py   # JS 事件 → Python asyncio 事件的橋接
│       │   ├── marshalling.py   # JS proxy → Python model 轉換
│       │   └── plugin_host.py   # JS plugin 載入管理
│       │
│       └── _internal/
│           ├── __init__.py
│           └── converters.py    # 輔助轉換函式
│
├── tests/
│   ├── unit/
│   │   ├── test_models.py
│   │   ├── test_converters.py
│   │   └── test_config.py
│   ├── integration/
│   │   ├── test_connect.py
│   │   └── test_basic_actions.py
│   └── conftest.py
│
└── examples/
    ├── 01_hello_bot.py
    ├── 02_goto_player.py
    ├── 03_collect_wood.py
    └── 04_chest_operations.py
```

---

## Async 模型設計（關鍵決策）

pyflayer 公開 API 採用 **asyncio** 作為唯一的 async 模型：

```python
import asyncio
from pyflayer import Bot

async def main():
    bot = Bot(host="localhost", port=25565, username="demo")
    await bot.connect()
    await bot.wait_until_spawned()
    await bot.chat("Hello!")
    await bot.goto(100, 64, 200)
    await bot.disconnect()

asyncio.run(main())
```

### Bridge 層的 async 橋接策略

JSPyBridge 的 callback 跑在它自己的 thread 上，不在 asyncio event loop 裡。bridge 層必須處理這個問題，且 **所有 JSPyBridge 呼叫必須固定在初始化它的同一個 thread 上（目前就是 asyncio event loop 所在的 thread）**：

1. **JS → Python 事件**：JS 端的事件 callback 透過 `asyncio.get_event_loop().call_soon_threadsafe()` 將事件投遞到 asyncio loop，由 loop thread 上的 event_relay 處理並轉成 Python 事件 / `Future` 完成。
2. **Python → JS 呼叫**：公開 API 的 `await bot.chat(...)` 等方法，會在 **event loop thread 上直接以同步方式呼叫 JSPyBridge / mineflayer**，不使用 `asyncio.to_thread()` 或 `loop.run_in_executor()` 將呼叫搬到其他 thread，避免觸發 JSPyBridge「必須在初始化 thread 呼叫」的限制。
3. **等待型操作**：像 `goto()` 這種需要等 JS 端事件觸發才完成的操作，會在 Python 端建立對應的 `asyncio.Future`，並由 JS → Python 的事件 relay 在收到對應事件時，在 asyncio loop thread 上 `set_result()` / `set_exception()` 來 resolve。

### 重要原則

- 公開 API **全部** 是 `async def`（除了純資料存取的 property）
- 使用者的 callback（透過 `bot.observe.on()`）也必須是 `async def`
- Bridge 層內部允許使用 thread，但 JS ↔ Python 的橋接邏輯必須清楚分工：**JSPyBridge 呼叫只能在初始化它的 thread 上執行，不能被 `asyncio.to_thread()` / `run_in_executor()` 搬到其他 thread。**
- 若某個 JS 行為可能在 JSPyBridge 同步呼叫中阻塞過久，**不得**直接把 JSPyBridge 呼叫包進 executor，而是應在 JS 端設計為非阻塞 / 事件驅動 API，並在 Python 端透過事件 + `asyncio.Future` 的方式等待完成。

---

## 核心型別定義

### Vec3

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Vec3:
    x: float
    y: float
    z: float

    def distance_to(self, other: "Vec3") -> float: ...
    def offset(self, dx: float, dy: float, dz: float) -> "Vec3": ...
    def floored(self) -> "Vec3": ...
    def __add__(self, other: "Vec3") -> "Vec3": ...
    def __sub__(self, other: "Vec3") -> "Vec3": ...
```

### Block

```python
@dataclass(frozen=True, slots=True)
class Block:
    name: str
    display_name: str
    position: Vec3
    hardness: float | None
    is_solid: bool
    is_liquid: bool
    bounding_box: str  # "block" | "empty"
```

### Entity

```python
from enum import Enum

class EntityKind(Enum):
    PLAYER = "player"
    MOB = "mob"
    ANIMAL = "animal"
    HOSTILE = "hostile"
    PROJECTILE = "projectile"
    OBJECT = "object"
    OTHER = "other"

@dataclass(frozen=True, slots=True)
class Entity:
    id: int
    name: str | None
    kind: EntityKind
    position: Vec3
    velocity: Vec3 | None
    health: float | None
    metadata: dict | None
```

### ItemStack

```python
@dataclass(frozen=True, slots=True)
class ItemStack:
    name: str
    display_name: str
    count: int
    slot: int
    max_stack_size: int
    enchantments: list[dict] | None = None
    nbt: dict | None = None
```

### Events（高階事件）

```python
@dataclass(frozen=True)
class SpawnEvent:
    """Bot 已生成於世界中"""
    pass

@dataclass(frozen=True)
class ChatEvent:
    sender: str
    message: str
    timestamp: float

@dataclass(frozen=True)
class WhisperEvent:
    sender: str
    message: str
    timestamp: float

@dataclass(frozen=True)
class HealthChangedEvent:
    health: float
    food: float
    saturation: float

@dataclass(frozen=True)
class DeathEvent:
    reason: str | None

@dataclass(frozen=True)
class KickedEvent:
    reason: str
    logged_in: bool

@dataclass(frozen=True)
class GoalReachedEvent:
    position: Vec3

@dataclass(frozen=True)
class GoalFailedEvent:
    reason: str

@dataclass(frozen=True)
class BlockBrokenEvent:
    block: Block

@dataclass(frozen=True)
class CollectCompletedEvent:
    item_name: str
    count: int
```

### Errors（例外層級）

```python
class PyflayerError(Exception):
    """所有 pyflayer 例外的基底類別"""

class ConnectionError(PyflayerError):
    """連線失敗或斷線"""

class NotSpawnedError(PyflayerError):
    """Bot 尚未生成就嘗試執行動作"""

class NavigationError(PyflayerError):
    """導航失敗（無法到達、路徑不存在）"""

class InventoryError(PyflayerError):
    """背包操作失敗"""

class PluginError(PyflayerError):
    """Plugin 載入或呼叫失敗"""

class BridgeError(PyflayerError):
    """底層 bridge 通訊錯誤（進階 debug 用）"""
    def __init__(self, message: str, js_stack: str | None = None):
        super().__init__(message)
        self.js_stack = js_stack
```

---

## Bot 主類別設計

```python
class Bot:
    """pyflayer 的核心入口。

    Example::

        async def main():
            bot = Bot(host="localhost", username="Steve")
            await bot.connect()
            await bot.wait_until_spawned()
            await bot.chat("Hello!")
            await bot.disconnect()
    """

    def __init__(
        self,
        host: str,
        port: int = 25565,
        username: str = "pyflayer",
        version: str | None = None,
        auth: str | None = None,  # "microsoft" | "offline" | None
        hide_errors: bool = False,
    ) -> None: ...

    # --- Lifecycle ---
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def wait_until_spawned(self, timeout: float = 30.0) -> None: ...

    @property
    def is_connected(self) -> bool: ...

    @property
    def is_alive(self) -> bool: ...

    # --- State properties（同步存取，從快照讀取）---
    @property
    def position(self) -> Vec3: ...

    @property
    def health(self) -> float: ...

    @property
    def food(self) -> float: ...

    @property
    def username(self) -> str: ...

    @property
    def game_mode(self) -> str: ...

    @property
    def players(self) -> dict[str, dict]: ...

    # --- Chat ---
    async def chat(self, message: str) -> None: ...
    async def whisper(self, username: str, message: str) -> None: ...

    # --- Movement ---
    async def goto(self, x: float, y: float, z: float, radius: float = 1.0) -> None: ...
    async def look_at(self, x: float, y: float, z: float) -> None: ...
    async def jump(self) -> None: ...
    async def stop(self) -> None: ...

    # --- World query ---
    async def find_block(
        self,
        name: str,
        *,
        max_distance: float = 64,
        count: int = 1,
    ) -> list[Block]: ...

    async def find_entity(
        self,
        *,
        name: str | None = None,
        kind: EntityKind | None = None,
        max_distance: float = 32,
    ) -> Entity | None: ...

    async def block_at(self, x: int, y: int, z: int) -> Block | None: ...

    # --- Actions ---
    async def dig(self, block: Block) -> None: ...
    async def place_block(
        self,
        reference_block: Block,
        face: Vec3,
        *,
        item_name: str | None = None,
    ) -> None: ...
    async def use_item(self) -> None: ...
    async def attack(self, entity: Entity) -> None: ...

    # --- Sub-APIs ---
    @property
    def navigation(self) -> NavigationAPI: ...

    @property
    def inventory(self) -> InventoryAPI: ...

    @property
    def collect(self) -> CollectAPI: ...

    @property
    def combat(self) -> CombatAPI: ...

    @property
    def observe(self) -> ObserveAPI: ...

    @property
    def plugins(self) -> PluginManager: ...

    # --- Raw escape hatch ---
    @property
    def raw(self) -> "RawBotHandle":
        """進階存取底層 mineflayer JS bot 物件。

        ⚠️ 此介面不保證型別安全、不保證版本穩定。
        回傳的物件是 JSPyBridge proxy，使用方式請參考 mineflayer JS 文件。
        """
        ...
```

---

## 事件系統設計

### 使用者介面

```python
# Decorator 風格
@bot.observe.on(ChatEvent)
async def on_chat(event: ChatEvent):
    print(f"{event.sender}: {event.message}")

# 也可以用方法註冊
async def handle_health(event: HealthChangedEvent):
    if event.health < 5:
        await bot.chat("I'm low on health!")

bot.observe.on(HealthChangedEvent, handle_health)

# 移除監聽
bot.observe.off(HealthChangedEvent, handle_health)

# 等待單次事件
event = await bot.observe.wait_for(SpawnEvent, timeout=30.0)

# 原始事件 escape hatch
@bot.observe.on_raw("entityMoved")
async def on_raw_entity(data: dict):
    # data 是從 JS 端序列化過來的 dict
    pass
```

### 內部實作原則

`event_relay.py` 負責：

1. 在 JS 端用 `@On(bot, 'eventName')` 綁定事件
2. 在 callback 中將 JS payload 轉為 Python dict（用 `.valueOf()`）
3. 用 `call_soon_threadsafe` 將事件投遞到 asyncio loop
4. 在 asyncio 端，根據事件名稱轉換為對應的 Event dataclass
5. 分派給所有已註冊的 handler

**事件節流規則：**
- `move` 事件：預設 100ms 節流
- `entityMoved` 事件：預設不公開，僅 on_raw 可訂閱
- `physicsTick` 事件：不公開
- 高階事件（chat, spawn, death, kicked）：不節流，直接傳遞

---

## Bridge 層實作指引

### runtime.py

```python
class BridgeRuntime:
    """管理 JSPyBridge 的生命週期。"""

    def __init__(self) -> None:
        self._started = False

    def ensure_node_available(self) -> None:
        """檢查 Node.js 是否可用，不可用時拋出有意義的錯誤訊息。"""
        ...

    def start(self) -> None:
        """初始化 JSPyBridge runtime。
        只應被呼叫一次。在這裡 import javascript 模組。
        """
        ...

    def require(self, module: str) -> Any:
        """封裝 JSPyBridge 的 require()。"""
        ...

    def shutdown(self) -> None:
        """關閉 bridge runtime。"""
        ...
```

### js_bot.py

```python
class JSBotController:
    """封裝所有對 JS mineflayer bot 物件的操作。

    這個類別是唯一直接持有 JS bot proxy 的地方。
    所有對 JS bot 的方法呼叫都經過此類別。
    """

    def __init__(self, runtime: BridgeRuntime, config: dict) -> None: ...

    def create_bot(self) -> None:
        """呼叫 mineflayer.createBot()。"""
        ...

    def chat(self, message: str) -> None:
        """同步呼叫 bot.chat()。上層需用 run_in_executor 包裝。"""
        ...

    def get_position(self) -> dict:
        """取得 bot 位置，回傳 {'x': ..., 'y': ..., 'z': ...}。"""
        ...

    def get_health(self) -> float: ...
    def get_food(self) -> float: ...

    # ... 其他 JS 操作的封裝
```

### marshalling.py

```python
def js_vec3_to_vec3(js_obj) -> Vec3:
    """將 JS Vec3 proxy 轉為 Python Vec3。"""
    return Vec3(
        x=float(js_obj.x),
        y=float(js_obj.y),
        z=float(js_obj.z),
    )

def js_block_to_block(js_obj) -> Block:
    """將 JS Block proxy 轉為 Python Block。"""
    ...

def js_entity_to_entity(js_obj) -> Entity:
    """將 JS Entity proxy 轉為 Python Entity。"""
    ...

def js_item_to_item_stack(js_obj) -> ItemStack:
    """將 JS Item proxy 轉為 Python ItemStack。"""
    ...
```

---

## Sub-API 設計

### NavigationAPI

```python
class NavigationAPI:
    """路徑規劃與移動控制。底層使用 mineflayer-pathfinder。"""

    async def goto(self, x: float, y: float, z: float, *, radius: float = 1.0) -> None:
        """移動到指定座標。到達後 resolve，失敗時拋出 NavigationError。"""
        ...

    async def follow(self, username: str, *, distance: float = 2.0) -> None:
        """持續跟隨指定玩家。"""
        ...

    async def stop(self) -> None:
        """停止當前導航。"""
        ...

    @property
    def is_navigating(self) -> bool: ...
```

### InventoryAPI

```python
class InventoryAPI:
    """背包與裝備操作。"""

    def items(self) -> list[ItemStack]:
        """取得背包中所有物品的快照。"""
        ...

    def find(self, name: str) -> ItemStack | None:
        """在背包中尋找指定名稱的物品。"""
        ...

    async def equip(self, item_name: str, destination: str = "hand") -> None:
        """裝備物品。destination: 'hand', 'off-hand', 'head', 'torso', 'legs', 'feet'"""
        ...

    async def toss(self, item_name: str, count: int | None = None) -> None:
        """丟棄物品。count=None 時丟棄整組。"""
        ...

    async def select_best_tool(self, block: Block) -> ItemStack | None:
        """為指定方塊選擇最佳工具並裝備。"""
        ...
```

### CollectAPI

```python
class CollectAPI:
    """採集與資源收集。底層使用 mineflayer-collectblock。"""

    async def collect(self, block_name: str, count: int = 1) -> int:
        """採集指定方塊。回傳實際採集數量。"""
        ...

    async def mine(self, block_name: str, count: int = 1) -> int:
        """挖掘指定方塊（不撿拾掉落物）。"""
        ...
```

### ObserveAPI

```python
from typing import TypeVar, Type, Callable, Awaitable

E = TypeVar("E")

class ObserveAPI:
    """事件訂閱系統。"""

    def on(self, event_type: Type[E], handler: Callable[[E], Awaitable[None]] | None = None):
        """訂閱事件。可作為 decorator 或直接傳入 handler。"""
        ...

    def off(self, event_type: Type[E], handler: Callable[[E], Awaitable[None]]) -> None:
        """取消訂閱。"""
        ...

    async def wait_for(self, event_type: Type[E], *, timeout: float = 30.0) -> E:
        """等待單次事件。逾時拋出 asyncio.TimeoutError。"""
        ...

    def on_raw(self, event_name: str, handler: Callable[[dict], Awaitable[None]] | None = None):
        """訂閱原始 JS 事件（escape hatch）。⚠️ 進階用途。"""
        ...
```

---

## 開發里程碑（具體任務）

### M0：技術驗證（建議 1-2 天）

**目標**：證明 bridge 能穩定工作、async 模型可行。

**任務清單**：
1. 初始化專案結構（`pyproject.toml`、src layout）
2. 實作 `_bridge/runtime.py`：啟動 JSPyBridge、載入 mineflayer
3. 實作 `_bridge/js_bot.py`：最小 createBot + chat + 取得位置
4. 實作 `_bridge/event_relay.py`：將 `spawn` 和 `chat` 事件橋接到 asyncio
5. 實作 `models/vec3.py`、`models/events.py`（最小版本）
6. 實作 `bot.py`：最小 Bot 類別，只有 connect / wait_until_spawned / chat / disconnect
7. 寫一個可以跑的 `examples/01_hello_bot.py`，連上本地測試伺服器並聊天
8. 驗證：event 能從 JS → Python asyncio 正確傳遞

**M0 結束條件**：`01_hello_bot.py` 能正常連線、收到 spawn 事件、發送聊天訊息、乾淨斷線。

### M1：核心 Façade MVP（建議 3-5 天）

**任務清單**：
1. 完善所有 domain model（Block, Entity, ItemStack, InventorySnapshot）
2. 實作 `_bridge/marshalling.py` 完整轉換
3. 為 Bot 加入 position / health / food properties
4. 實作 `find_block()`, `block_at()`, `find_entity()`
5. 實作 `dig()`, `place_block()`
6. 實作 `goto()`（直接用 mineflayer 的基本移動，不含 pathfinder）
7. 實作 `look_at()`, `jump()`, `stop()`
8. 實作 ObserveAPI 的 `on()`, `off()`, `wait_for()`
9. 實作完整的事件 dataclass 和事件分派
10. 建立 errors.py 的完整例外層級
11. 寫單元測試（models, converters）
12. 寫整合測試（connect, chat, dig）

### M2：常用任務層（建議 3-5 天）

**任務清單**：
1. 載入 mineflayer-pathfinder，實作 NavigationAPI
2. 載入 mineflayer-collectblock，實作 CollectAPI
3. 實作 InventoryAPI（items, find, equip, toss, select_best_tool）
4. 實作容器操作（open_chest, withdraw, deposit）
5. 實作基礎 craft / smelt
6. 實作 CombatAPI（attack, attack_nearest）
7. 實作 PluginManager 基本版
8. 完善事件系統（HealthChanged, Death, Kicked, GoalReached, GoalFailed）
9. 寫 cookbook 範例（collect_wood, chest_operations, auto_equip）

### M3：穩定化（建議 2-3 天）

1. Raw escape hatch 實作
2. 完善錯誤處理（JS 例外轉換、timeout handling）
3. 事件節流機制
4. 型別檢查通過（mypy / pyright）
5. 補齊 docstring
6. README 和快速開始指南

---

## 程式碼風格規範

- **所有公開方法必須有 docstring**，格式用 Google style
- **所有公開方法必須有完整 type hints**
- **私有模組的方法至少有 type hints**，docstring 可簡化
- **不使用 `Any` 作為公開 API 的回傳型別**（raw escape hatch 除外）
- **import 順序**：stdlib → third-party → local，用 ruff 管理
- **命名規範**：
  - 公開類別：PascalCase
  - 公開方法/函式：snake_case
  - 私有屬性：`_` 前綴
  - 常數：UPPER_SNAKE_CASE
  - 內部模組：`_` 前綴目錄

---

## 重要提醒

### JSPyBridge 的已知陷阱

1. **不要在 `@On` callback 裡做 blocking 操作**。所有 callback 共用一個 thread，阻塞一個就阻塞全部。
2. **`.valueOf()` 用於序列化 JS 物件為 Python dict**，但對大物件很慢。只在需要快照時使用。
3. **event handler 的第一個參數是 `this`**，不是 event payload。記得在 bridge 層處理掉這個。
4. **JS 的 `undefined` 和 `null` 在 Python 端的行為可能不一致**，轉換時要防禦性處理。
5. **JSPyBridge 的 require() 會自動安裝 npm 套件**，第一次呼叫可能較慢。

### 效能注意

1. **避免在 loop 中逐一呼叫 JS**。例如取得多個方塊資訊時，應在 JS 端批次處理後一次回傳。
2. **property 存取（如 `bot.position`）應盡量從快取的快照讀取**，而非每次都跨 bridge 查詢。
3. **事件是效能瓶頸的最大來源**。高頻事件必須在 JS 端節流後才傳到 Python。

### 測試伺服器

整合測試建議使用離線模式的本地 Minecraft server，或使用 PrismarineJS 的測試伺服器 `pjs.deptofcraft.com:25565`。

---

## 範例程式（M0 結束後應能執行）

```python
"""01_hello_bot.py — 最基本的 pyflayer bot"""
import asyncio
from pyflayer import Bot
from pyflayer.models.events import ChatEvent, SpawnEvent

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

    # 保持運行
    try:
        while bot.is_connected:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await bot.disconnect()

asyncio.run(main())
```

---

## 範例程式（M2 結束後應能執行）

```python
"""03_collect_wood.py — 自動伐木 bot"""
import asyncio
from pyflayer import Bot
from pyflayer.models.events import SpawnEvent

async def main():
    bot = Bot(host="localhost", port=25565, username="lumberjack")

    await bot.connect()
    await bot.wait_until_spawned()

    # 找到附近的木頭
    logs = await bot.find_block("oak_log", max_distance=32, count=5)
    print(f"Found {len(logs)} oak logs")

    for log in logs:
        # 自動選擇最佳工具
        await bot.inventory.select_best_tool(log)
        # 導航到方塊附近
        await bot.goto(log.position.x, log.position.y, log.position.z, radius=3)
        # 挖掘
        await bot.dig(log)
        print(f"Mined log at {log.position}")

    await bot.chat(f"Done! Collected {len(logs)} logs.")
    await bot.disconnect()

asyncio.run(main())
```

---

## 最後提醒

- **永遠從使用者視角出發**：先寫你希望使用者怎麼用的程式碼（example），再往下實作。
- **每完成一個功能就確保 example 能跑**，不要等全部寫完才測試。
- **型別和 docstring 是這個專案的核心價值**，不是事後補的東西。
- **寧可少包幾個 API，也不要暴露半成品的型別**。使用者可以用 `bot.raw` 取得原始能力。
- **這是 façade，不是 reimplementation**。如果某個功能在 mineflayer 已經做得很好，就直接包裝它，不要重新發明。