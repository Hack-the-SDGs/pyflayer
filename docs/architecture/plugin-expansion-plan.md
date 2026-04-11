# Plugin Expansion Architecture — v2 (Source-Verified)

> 本文件基於實際安裝的 npm 原始碼撰寫，所有 API 描述皆附原始碼行號。
> 前版因多處基於 README 臆測被審回，本版逐一修正。

## 目錄

1. [現狀評估](#1-現狀評估)
2. [插件分類：四種整合模式](#2-插件分類四種整合模式)
3. [Phase 0：最小 Registry 重構](#3-phase-0最小-registry-重構)
4. [各插件設計規格（Source-Verified）](#4-各插件設計規格source-verified)
5. [Async 完成策略：Promise vs 自訂事件](#5-async-完成策略promise-vs-自訂事件)
6. [版本相容性矩陣](#6-版本相容性矩陣)
7. [分支策略與合併計畫](#7-分支策略與合併計畫)
8. [決策紀錄](#8-決策紀錄)
9. [風險與待處理](#9-風險與待處理)

---

## 1. 現狀評估

### 1.1 環境

| 項目 | 值 | 來源 |
|------|-----|------|
| mineflayer | 4.37.0 | `.venv/.../mineflayer/package.json` |
| mineflayer `engines.node` | `>=22` | 同上 |
| AGENTS.md 宣稱 Node | 22+ | `AGENTS.md`（已修正） |
| 實際 Node 版本 | v25.8.2 | `node --version` |

Node 版本已對齊：AGENTS.md 和 runtime.py 都要求 Node.js 22+。

### 1.2 main vs dev

零分歧。可直接從 main 開分支。

### 1.3 `bot.raw.plugin()` 路徑

目前 `bot.raw` 的 `plugin_loader` 來自 `PluginHost.raw_plugin`
（`bot.py:1311` → `plugin_host.py:121`）。Phase 0 刪除 `plugin_host.py` 時**必須**保留此路徑，
改由 `PluginRegistry` 或 `BridgeRuntime.require()` 直接提供。

---

## 2. 插件分類：四種整合模式

不是所有插件都能套用同一個 `PluginBridge` 抽象。依實際原始碼，分成四類：

### Type A：`bot.loadPlugin()` facade

插件 export 一個 `(bot) => void` 函式，透過 `bot.loadPlugin()` 載入，
然後在 bot 上掛屬性（`bot.xxx`）。方法回傳 **Promise**。

| 插件 | export | 掛載 | 主方法 | 回傳 |
|------|--------|------|--------|------|
| armor-manager | `module.exports = initializeBot` | `bot.armorManager` | `equipAll()` | Promise | 
| tool | `exports.plugin = plugin` | `bot.tool` | `equipForBlock(block, opts?, cb?)` | Promise |
| collectblock | `exports.plugin = plugin` | `bot.collectBlock` | `collect(target, opts?, cb?)` | Promise |
| gui | `module.exports = (bot) => {}` | `bot.gui` | `Query().run()` | Promise\<boolean\> |
| hawkeye | `exports.default = inject` | `bot.hawkEye` | `autoAttack(target, weapon)` | boolean (sync) |
| panorama | `exports = {panoramaImage, image}` | `bot.panoramaImage`, `bot.image` | Promise\<JPEGStream\> |

**Ref：**
- armor-manager: `dist/index.js:13-35`
- tool: `lib/index.js` — `exports.plugin = plugin`
- collectblock: `lib/index.js` — `exports.plugin = plugin`
- gui: `src/index.js` — `module.exports = (bot) => { bot.gui = new GuiPlugin(bot) }`
- hawkeye: `dist/index.js:28-44`
- panorama: `index.js:23-26` — `module.exports = { panoramaImage, image }`（兩個 inject function，Type A）

### Type B：Server / Service wrapper

插件 export 一個 `(bot, options) => void` 函式，直接呼叫（**不走 `bot.loadPlugin()`**）。
通常啟動 HTTP server 或 terminal UI。

| 插件 | export | 掛載 | 特性 |
|------|--------|------|------|
| web-inventory | `module.exports = function(bot, options)` | `bot.webInventory` | port 在初始化時固定 |
| prismarine-viewer | `exports.mineflayer = function(bot, opts)` | `bot.viewer` | Express + Socket.IO |

**Ref：**
- web-inventory: `index.js:5` — `module.exports = function (bot, options = {})`
- prismarine-viewer: `lib/mineflayer.js` — `module.exports = (bot, { viewDistance, firstPerson, port, prefix }) =>`

> **注意（2026-04-11 修正）**：panorama 先前被歸為 Type B，但實際 export 為
> `{ panoramaImage, image }` 兩個 `(bot) => void` inject function，
> 使用時 `bot.loadPlugin(mod.panoramaImage)` — 這是 Type A 模式。
> 已移入 Type A 範圍。

### Type C：Class Library / DSL

插件 export 一組 **class**，不走 `bot.loadPlugin()`。使用者自行 `new` 實例。

| 插件 | export | 核心 class | 特性 |
|------|--------|-----------|------|
| statemachine | `__exportStar(behaviors, statemachine, webserver)` | `BotStateMachine`, `NestedStateMachine`, `StateTransition` | class library, 不是 plugin |

**Ref：** `lib/index.js:16-24` — 只有 `__exportStar` 和 `globalSettings`，無 `inject` / `plugin` 函式。

### Type D：Higher-Order Function

| 插件 | export | 特性 |
|------|--------|------|
| dashboard | `module.exports = function(options) { return function(bot) {} }` | HOF pattern，`options._client` 偵測直接傳 bot |

**Ref：** `index.js:18-24` — `if (options._client) { return module.exports()(options) }`，
正確用法是 `bot.loadPlugin(require('@ssmidge/mineflayer-dashboard')(options))`。

---

## 3. Phase 0：最小 Registry 重構

### 範圍（嚴格限縮）

1. 新增 `_bridge/plugin_registry.py` + `_bridge/plugins/_base.py`
2. 新增 `_bridge/plugins/pathfinder.py`（從 `plugin_host.py` 搬出）
3. 修改 `bot.py`：connect/disconnect/wait_until_spawned 改用 registry
4. 修改 `api/plugins.py`：改用 PluginRegistry
5. 修改 `api/navigation.py`：接收 PathfinderBridge
6. **保留 `bot.raw.plugin()` 路徑**：registry 內部透過 `runtime.require()` 實作
7. 刪除 `plugin_host.py`
8. 更新所有現有測試
9. CI 全綠

### PluginBridge ABC（修正版）

```python
class PluginBridge(ABC):
    """Base class for Type A (bot.loadPlugin) plugin bridges."""
    NPM_NAME: ClassVar[str]
    DEPENDS_ON: ClassVar[tuple[str, ...]] = ()

    def __init__(self, runtime: BridgeRuntime, js_bot: Any, relay: EventRelay) -> None:
        self._runtime = runtime
        self._js_bot = js_bot
        self._relay = relay
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @abstractmethod
    def _do_load(self) -> None: ...

    def load(self) -> None:
        if self._loaded:
            return
        self._do_load()
        self._loaded = True

    def teardown(self) -> None:
        """Override for cleanup on disconnect."""
```

**不強制 `setup_after_spawn()`**。
原審閱正確指出：armor-manager（`dist/index.js:17`）和 collectblock（`lib/CollectBlock.js:186`）
都不需要 spawn 後初始化。只有 pathfinder 的 `Movements` 需要 spawn 後設定（因為讀 `bot.registry`），
這是 pathfinder 自己的特殊邏輯，不應泛化成 ABC 的 hook。

### `bot.raw.plugin()` 保留策略

```python
# bot.py — raw property 改為：
plugin_loader = self._registry.raw_require if self._registry else None

# plugin_registry.py
def raw_require(self, name: str) -> Any:
    """Escape hatch: load any npm module. Replaces old PluginHost.raw_plugin()."""
    return self._runtime.require(name)
```

### 兩套管理路徑

**`PluginRegistry`** — 管理 Type A / Type D（`bot.loadPlugin()` 類）
- 對應 `bot.plugins.load("mineflayer-armor-manager")` 等
- 負責依賴解析、lifecycle、teardown
- 不涵蓋 service 類

**`bot.<service>` lazy property** — 管理 Type B / Type C（server / class library）
- viewer、web-inventory、panorama 透過 `bot.viewer`、`bot.inventory_viewer`、`bot.panorama` lazy 建立
- 不走 `bot.plugins.load()`，各自有 `start()`/`stop()` 生命週期
- statemachine 的 raw access 走 `bot.raw.plugin("mineflayer-statemachine")`，不另設 `require_module()`
- Service 的 teardown 由 `Bot.disconnect()` 統一呼叫

---

## 4. 各插件設計規格（Source-Verified）

### 4.1 armor-manager

**原始碼**：`dist/index.js:13-35`

```
Export: module.exports = initializeBot  (function)
Loading: bot.loadPlugin(initializeBot)
掛載: bot.armorManager.equipAll()
equipAll(): Promise<void> — 遍歷 inventory，逐一 equip armor
Auto-equip: 監聽 playerCollect，100ms 後自動裝備 (line 24-33)
Events emitted: 無
依賴: 無
```

**Bridge：**
```python
class ArmorManagerBridge(PluginBridge):
    NPM_NAME = "mineflayer-armor-manager"
    def _do_load(self):
        mod = self._runtime.require("mineflayer-armor-manager")
        self._js_bot.loadPlugin(mod)  # mod 本身就是 initializeBot function
```

**Public API（透過 bridge method，不直接碰 JS proxy）：**
```python
class ArmorAPI:
    async def equip_best(self) -> None:
        """Equip best armor."""
        async with self._equip_lock:
            self._bridge.start_equip_all()
            event = await self._relay.wait_for(ArmorEquipDoneEvent, timeout=30.0)
            if event.error is not None:
                raise BridgeError(f"armor equip failed: {event.error}")
```

Bridge 層封裝 JS 呼叫（走 helpers.js wrapper，不直接 await Promise）：
```python
# ArmorManagerBridge
def start_equip_all(self) -> None:
    self._helpers.startArmorEquipAll(self._js_bot)

# helpers.js 新增：
# startArmorEquipAll(bot) {
#     bot.armorManager.equipAll()
#         .then(() => bot.emit("_minethon:armorEquipDone"))
#         .catch(err => bot.emit("_minethon:armorEquipDone", _err(err)));
# },
```

### 4.2 tool

**原始碼**：`lib/index.js`, `lib/Tool.js:107-175`

```
Export: { plugin, Tool }
Loading: bot.loadPlugin(plugin)   — plugin function 內會 setTimeout 自動載入 pathfinder
掛載: bot.tool.equipForBlock(block, options?, cb?)
equipForBlock(): Promise<void> — 可同時接 callback
Events emitted: 無
依賴: pathfinder（軟依賴，plugin 內部 setTimeout 自動載入）
```

**Bridge：**
```python
class ToolBridge(PluginBridge):
    NPM_NAME = "mineflayer-tool"
    # 不需要宣告 DEPENDS_ON — tool 內部自己 setTimeout 載入 pathfinder

    def _do_load(self):
        mod = self._runtime.require("mineflayer-tool")
        self._js_bot.loadPlugin(mod.plugin)
```

**Public API（透過 bridge method）：**
```python
class ToolAPI:
    async def equip_for_block(self, block: Block, *, require_harvest: bool = False) -> None:
        """Equip best tool for mining block."""
        async with self._equip_lock:
            self._bridge.start_equip_for_block(block, require_harvest=require_harvest)
            event = await self._relay.wait_for(ToolEquipDoneEvent, timeout=10.0)
            if event.error is not None:
                raise BridgeError(f"tool equip failed: {event.error}")
```

Bridge 層封裝 JS 呼叫（走 helpers.js wrapper）：
```python
# ToolBridge
def start_equip_for_block(self, block: Block, *, require_harvest: bool = False) -> None:
    js_block = self._controller.block_at(int(block.position.x), ...)
    self._helpers.startToolEquipForBlock(self._js_bot, js_block, {"requireHarvest": require_harvest})
```

### 4.3 collectblock

**原始碼**：`lib/index.js`, `lib/CollectBlock.js:169-238`

```
Export: { plugin, CollectBlock }
Loading: bot.loadPlugin(plugin)  — 內部 setTimeout 自動載入 pathfinder + tool
掛載: bot.collectBlock.collect(target, options?, cb?)
collect(): Promise<void> — target 可以是 Block | Entity | Array
cancelTask(cb?): Promise<void>
findFromVein(block, maxBlocks?, maxDistance?, floodRadius?): Block[] — 同步
Events emitted: 'collectBlock_finished' (bot.emit, CollectBlock.js finally block)
依賴: pathfinder + tool
  ↑ 雖然 plugin 用 setTimeout(...,0) 延後載入 (lib/index.js:9)，
    但 collect() 開頭立刻檢查 bot.pathfinder/bot.tool 存在 (CollectBlock.js:186)。
    若 Python 在 loadPlugin 後立刻呼叫 collect()，setTimeout 可能還沒跑完，
    會拿到 UnresolvedDependency error。必須在 registry 層顯式先載入依賴。
```

**Bridge：**
```python
class CollectBlockBridge(PluginBridge):
    NPM_NAME = "mineflayer-collectblock"
    DEPENDS_ON = ("mineflayer-pathfinder", "mineflayer-tool")
    # ↑ 顯式依賴。registry.load() 會先載入 pathfinder + tool，
    #   避免 setTimeout race condition。

    def _do_load(self):
        mod = self._runtime.require("mineflayer-collectblock")
        self._js_bot.loadPlugin(mod.plugin)
```

**Public API（走 helpers.js wrapper）：**
```python
class CollectorAPI:
    async def collect(self, targets: list[Block] | Block, *, append: bool = False, 
                      ignore_no_path: bool = False) -> None:
        """Collect blocks via helpers.js + _minethon:collectDone event."""
        async with self._collect_lock:
            self._bridge.start_collect(targets, append=append, ignore_no_path=ignore_no_path)
            event = await self._relay.wait_for(CollectDoneEvent, timeout=120.0)
            if event.error is not None:
                raise BridgeError(f"collect failed: {event.error}")

    async def cancel(self) -> None:
        self._bridge.cancel_task()
```

**事件**：`collectBlock_finished` 可透過 `EventRelay.bind_raw_js_event()` 監聯。

### 4.4 hawkeye

**原始碼**：`dist/index.js:28-44`, `dist/hawkEye.js:21-40`, `dist/types/index.js:7-53`

```
Export: exports.default = inject  (function)
Loading: bot.loadPlugin(inject)   — 但需要 inject.default 或直接 inject
掛載: bot.hawkEye.{autoAttack, oneShot, stop, simplyShot, getPlayer, 
      calculateArrowTrayectory, detectProjectiles, detectAim, startRadar, stopRadar}
autoAttack(target, weapon?, isOneShot?): boolean — 同步，回傳是否開始
oneShot(target, weapon?): 等同 autoAttack(target, weapon, true)
stop(): void — 移除 physicsTick listener，emit 'auto_shot_stopped'
simplyShot(yaw, pitch): Promise<void> — look + activate + deactivate (1200ms delay)
Events emitted: 'auto_shot_stopped' (target)
依賴: 無
Weapons: bow, crossbow, trident, ender_pearl, snowball, egg, splash_potion
```

**Bridge：**
```python
class HawkEyeBridge(PluginBridge):
    NPM_NAME = "minecrafthawkeye"
    def _do_load(self):
        mod = self._runtime.require("minecrafthawkeye")
        # module.exports.default = inject
        inject = getattr(mod, "default", mod)
        self._js_bot.loadPlugin(inject)
```

**Public API（透過 bridge method）：** `bot.combat` (主) + `bot.hawkeye` (alias)
```python
class CombatAPI:
    async def auto_attack(self, entity: Entity, weapon: Weapon = Weapon.BOW) -> bool:
        """Start auto-attacking. Returns True if attack started."""
        return self._bridge.auto_attack(entity, weapon)

    async def shoot(self, entity: Entity, weapon: Weapon = Weapon.BOW) -> bool:
        """Fire single shot."""
        return self._bridge.one_shot(entity, weapon)

    def stop(self) -> None:
        self._bridge.stop()
```

Bridge 層封裝 JS 呼叫：
```python
# HawkEyeBridge
def auto_attack(self, entity: Entity, weapon: Weapon) -> bool:
    js_entity = ...  # 透過 controller 取得 JS entity proxy
    return bool(self._js_bot.hawkEye.autoAttack(js_entity, weapon.value))
```

**Models：**
```python
class Weapon(Enum):
    BOW = "bow"
    CROSSBOW = "crossbow"
    TRIDENT = "trident"
    ENDER_PEARL = "ender_pearl"
    SNOWBALL = "snowball"
    EGG = "egg"
    SPLASH_POTION = "splash_potion"
```

### 4.5 gui

**原始碼**：`src/index.js`, `src/query.js:18-72`, `src/plugin.js`

```
Export: module.exports = (bot) => { bot.gui = new GuiPlugin(bot) }
Loading: bot.loadPlugin(module.exports)
掛載: bot.gui.Query()
Query builder 模式：
  Query().Hotbar(comparator).Equip(item).end()
        .Window(comparator).Click(item).Drop(item, count).close()
        .run()  → Promise<boolean>

comparator: (searchItem, inventoryItem) => boolean — JS function
  ↑ 注意：comparator 接收的是 JS Item proxy，不是 Python ItemStack

Queue 機制：每個操作 push 一個 async function 到 queue，run() 順序執行
每次操作後自動插入 Sleep(50ms) — query.js:67
```

**封裝策略**：由於 comparator 需要操作 JS Item proxy，完整 Python 封裝不切實際。
提供兩層：

1. **高階便利方法**：常見操作（click by name, drop by name）封裝成 Python 方法，內部構建 JS comparator
2. **Raw Query builder**：進階用法直接拿 JS Query proxy

```python
class GuiAPI:
    async def click_item(self, name: str, *, window: bool = False) -> bool:
        """Click first item matching name. Returns True if found."""
        return await self._bridge.click_by_name(name, window=window)
    
    async def drop_item(self, name: str, count: int = 1) -> bool:
        """Drop item matching name."""
        return await self._bridge.drop_by_name(name, count=count)

    def raw_query(self) -> Any:
        """Get raw JS Query builder for advanced operations.
        Equivalent to bot.raw.plugin() but scoped to gui.
        """
        return self._bridge.create_query()
```

Bridge 層封裝 JS 呼叫：
```python
# GuiBridge — 內部構建 JS comparator，隱藏 JS proxy
async def click_by_name(self, name: str, *, window: bool = False) -> bool:
    query = self._js_bot.gui.Query()
    # 用 JS eval 構建 comparator，避免 Python callable 橋接問題
    ...
    return await query.run()
```

### 4.6 prismarine-viewer

**原始碼**：`index.js:1-7`, `lib/mineflayer.js`

```
Export: { mineflayer, standalone, headless, viewer, supportedVersions }
Loading: require('prismarine-viewer').mineflayer(bot, options)  — 不走 bot.loadPlugin()
Options: { viewDistance=6, firstPerson=false, port=3000, prefix='' }
  ↑ port 在呼叫時固定
掛載: bot.viewer (EventEmitter)
  .erase(id), .drawBoxGrid(id, start, end, color?), 
  .drawLine(id, points, color?), .drawPoints(id, points, color?, size?),
  .close()
Events: bot.viewer.emit('blockClicked', block, face, button)
依賴: 無
```

**Bridge（Type B — 不繼承 PluginBridge）：**
```python
class ViewerService:
    """Web 3D viewer. Not a bot.loadPlugin() plugin — standalone service."""
    def __init__(self, runtime, js_bot):
        self._runtime = runtime
        self._js_bot = js_bot
        self._started = False

    def start(self, port: int = 3007, view_distance: int = 6, first_person: bool = False):
        mod = self._runtime.require("prismarine-viewer")
        mod.mineflayer(self._js_bot, {
            "viewDistance": view_distance, "firstPerson": first_person, "port": port
        })
        self._started = True

    def stop(self):
        if self._started:
            self._js_bot.viewer.close()
            self._started = False
```

### 4.7 web-inventory

**原始碼**：`index.js:5-188`

```
Export: module.exports = function(bot, options = {})  — 不走 bot.loadPlugin()
Options: { port=3000, startOnLoad=true(default!), webPath='/', windowUpdateDebounceTime=100, 
           express, app, http, io }
  ↑ port 在初始化時固定到 options.port（line 11），之後 start()/stop() 不接 port
掛載: bot.webInventory.{ start(), stop(), options, isRunning }
start(): Promise<void> — listen on options.port
stop(): Promise<void> — close http server
Auto-start: line 181 — startOnLoad !== false 時自動 start()
Events: 無（Socket.IO 內部處理）
依賴: 無
```

**Bridge（Type B）：**
```python
class WebInventoryService:
    """Web inventory viewer. Port fixed at init time."""
    def __init__(self, runtime, js_bot):
        self._runtime = runtime
        self._js_bot = js_bot
        self._initialized = False

    def init_and_start(self, port: int = 3008):
        """Initialize with port and start. Port cannot be changed after init."""
        mod = self._runtime.require("mineflayer-web-inventory")
        mod(self._js_bot, {"port": port, "startOnLoad": True})
        self._initialized = True

    def init_without_start(self, port: int = 3008):
        """Initialize with port but don't start."""
        mod = self._runtime.require("mineflayer-web-inventory")
        mod(self._js_bot, {"port": port, "startOnLoad": False})
        self._initialized = True

    def start_server(self) -> None:
        """Non-blocking: triggers start; resolves via _minethon:webInvStartDone."""
        self._helpers.startWebInventory(self._js_bot)

    def stop_server(self) -> None:
        """Non-blocking: triggers stop; resolves via _minethon:webInvStopDone."""
        self._helpers.stopWebInventory(self._js_bot)

    # Caller (bridge/service layer):
    # async def start(self) -> None:
    #     self._bridge.start_server()
    #     event = await self._relay.wait_for(WebInvStartDoneEvent, timeout=10.0)
    #     if event.error is not None:
    #         raise BridgeError(f"web-inventory start failed: {event.error}")
```

### 4.8 statemachine

**原始碼**：`lib/statemachine.js:10-224`, `lib/webserver.js:18-160`, `lib/index.js:16-24`

```
Export: __exportStar(behaviors) + __exportStar(statemachine) + __exportStar(webserver) + globalSettings
  ↑ 不是 plugin，是 class library。沒有 inject/plugin function。

Classes:
  StateTransition({ parent, child, name?, shouldTransition?, onTransition? })
    - parent/child: StateBehavior objects (must have .stateName, .active, .onStateEntered?, etc.)
    - shouldTransition: () => boolean — 每 tick 檢查
    - onTransition: () => void — 觸發時呼叫
    - .trigger(): void — 強制觸發

  NestedStateMachine(transitions, enter, exit?)
    - transitions: StateTransition[]
    - enter: StateBehavior — 進入狀態
    - exit?: StateBehavior — 結束狀態
    - extends EventEmitter, emits 'stateChanged'
    - .isFinished(): boolean — activeState === exit

  BotStateMachine(bot, rootStateMachine)
    - rootStateMachine: NestedStateMachine
    - 綁定 bot.on('physicTick', () => this.update())
    - extends EventEmitter, emits 'stateChanged'

  StateMachineWebserver(bot, stateMachine, port=8934)
    - 注意：constructor 是 (bot, stateMachine, port)，不是 (bot, port)
    - .startServer(): void
    - .isServerRunning(): boolean

Built-in Behaviors (all implement StateBehavior interface):
  BehaviorIdle, BehaviorFollowEntity, BehaviorLookAtEntity, BehaviorMoveTo,
  BehaviorGetClosestEntity, BehaviorEquipItem, BehaviorFindBlock,
  BehaviorFindInteractPosition, BehaviorMineBlock, BehaviorInteractBlock,
  BehaviorPlaceBlock, AbstractBehaviorInventory

StateBehavior interface:
  { stateName: string, active: boolean, x?: number, y?: number,
    onStateEntered?(): void, update?(): void, onStateExited?(): void }
```

**封裝策略（B: typed builder + raw fallback）**：

由於 `shouldTransition` 和 `onTransition` 是 **JS function**，完整 Python 封裝意味著
要把 Python callable 橋接成 JS callback。JSPyBridge 支援此操作，但有 thread 限制。

Raw access 統一透過既有的 `bot.raw.plugin("mineflayer-statemachine")`，
不在 typed API 裡再開一條 `require_module()` — 避免 raw 邊界膨脹。

Spike 目標：
1. 確認 Python callable 當 `shouldTransition` 的可行性（20 ticks/sec 呼叫頻率）
2. 若可行 → 設計 typed builder API（StateMachineBuilder + Behavior wrappers）
3. 若不可行 → statemachine 僅提供 raw access 路徑 + 使用文件指引

```python
# 使用者用法（raw fallback）
sm = bot.raw.plugin("mineflayer-statemachine")
idle = sm.BehaviorIdle()
follow = sm.BehaviorFollowEntity(bot.raw.js_bot, targets)
# ... 建構 StateTransition, NestedStateMachine, BotStateMachine
```

### 4.9 dashboard

**原始碼**：`index.js:18-168`

```
Export: module.exports = function(options = {}) { return function(bot) {} }
  ↑ Higher-Order Function。偵測 options._client 判斷是否直接傳了 bot。
Loading: bot.loadPlugin(require('@ssmidge/mineflayer-dashboard')(options))
  或: bot.loadPlugin(require('@ssmidge/mineflayer-dashboard')())
NPM 名稱: @ssmidge/mineflayer-dashboard（不是 mineflayer-dashboard）
掛載: bot.dashboard.{ log(...args), addMode(mode), Mode, modeManager, commands }
log(): 寫入 blessed terminal UI logBox + timestamp — 會佔用 terminal
Options: { chatPattern?: RegExp }
Events: 無
依賴: 無
Dev mineflayer: ^2.28.1 — 與 4.37.0 有大版本差距！
```

**風險**：
1. blessed 佔用 terminal stdout/stdin，可能與 Python process 衝突
2. `devDependencies.mineflayer: ^2.28.1` 表示此插件開發時針對的是很舊版本，runtime 相容性未驗證
3. 建議標記為 **experimental**，先做 spike 測試實際相容性

**Bridge（Type D — HOF）：**
```python
class DashboardBridge(PluginBridge):
    NPM_NAME = "@ssmidge/mineflayer-dashboard"
    def _do_load(self):
        mod = self._runtime.require("@ssmidge/mineflayer-dashboard")
        plugin_fn = mod()  # HOF: mod(options) → (bot) => void
        self._js_bot.loadPlugin(plugin_fn)
```

### 4.10 panorama

**原始碼**：`index.js:3-26`, `lib/camera.js:9-119`

```
Export: { panoramaImage, image }  — 兩個獨立 plugin function
Loading: bot.loadPlugin(mod.panoramaImage) + bot.loadPlugin(mod.image)
掛載: 
  bot.panoramaImage.takePanoramaPictures(camPos?) → Promise<JPEGStream>
  bot.image.takePicture(point, direction) → Promise<JPEGStream>
    ↑ 回傳是 JPEG Stream，不是 PNG bytes
    ↑ takePicture 的參數是 (point: Vec3, direction: Vec3)，不是 (lookAt, name)

Camera class 繼承 EventEmitter，emit 'camera_ready'（line 23）。
但 Camera 是每個 plugin function 內部 new 的，不掛在 bot 上。
所以 bot 層面沒有 camera_ready 事件。

camPos 參數（line 51-56）：
  - null/undefined → bot position, cameraHeight=10
  - number → bot position, cameraHeight=camPos
  - Vec3 → specific position, cameraHeight=0

系統依賴: node-canvas-webgl（需要 native build）
Version: 0.0.1 — 非常早期
```

**Bridge（Type A — 需要 native 依賴）：**

> **2026-04-11 修正**：先前歸類為 Type B（Service），但 `bot.loadPlugin()` 模式為 Type A。
> `takePanoramaPictures()` 回傳 Promise，必須走 helpers.js wrapper。

```python
class PanoramaBridge(PluginBridge):
    NPM_NAME = "mineflayer-panorama"

    def _do_load(self):
        mod = self._runtime.require("mineflayer-panorama")
        self._js_bot.loadPlugin(mod.panoramaImage)
        self._js_bot.loadPlugin(mod.image)

    def start_take_panorama(self, cam_pos) -> None:
        self._helpers.startPanorama(self._js_bot, cam_pos)
        # helpers.js:
        # bot.panoramaImage.takePanoramaPictures(camPos)
        #     .then(stream => bot.emit("_minethon:panoramaDone", null, stream))
        #     .catch(err => bot.emit("_minethon:panoramaDone", _err(err)));
```

---

## 5. Async 完成策略：`helpers.js` + `_minethon:*Done` 事件

> **2026-04-11 修正**：前版聲稱「直接 await JS Promise」，但經 JSPyBridge 原始碼驗證
> （`proxy.py:183-289` 無 `__await__`、所有呼叫透過 `threading.Event.wait()` 同步阻塞），
> 此假設不成立。Python 端 `await self._js_bot.xxx.method()` 會先同步阻塞 event loop
> 直到 JS Promise resolve，然後 `await None` 拋出 `TypeError`。
>
> 正確策略是沿用現有 core bot action 的模式：
> `helpers.js` 的 `start*()` 用 `.then()/.catch()` 非阻塞 emit `_minethon:*Done` 事件。

| 插件 | 原始 async 模型 | Python 策略 |
|------|-----------------|-------------|
| armor-manager | `equipAll()` → Promise | helpers.js wrapper + `_minethon:armorEquipDone` |
| tool | `equipForBlock()` → Promise | helpers.js wrapper + `_minethon:toolEquipDone` |
| collectblock | `collect()` → Promise | helpers.js wrapper + `_minethon:collectDone` |
| collectblock | `bot.emit('collectBlock_finished')` | 可選：bind_raw_js_event 監聽 |
| gui | `Query.run()` → Promise\<boolean\> | helpers.js wrapper + `_minethon:guiQueryDone`（帶 result） |
| hawkeye | `autoAttack()` → boolean (sync) | 同步呼叫，不需要 helpers.js wrapper |
| hawkeye | `bot.emit('auto_shot_stopped')` | bind_raw_js_event 監聽 |
| web-inventory | `start()`/`stop()` → Promise | helpers.js wrapper + `_minethon:webInvStartDone` / `webInvStopDone` |
| viewer | sync void | 同步呼叫，無需等待 |
| panorama | `takePanoramaPictures()` → Promise\<Stream\> | helpers.js wrapper + `_minethon:panoramaDone`（帶 result） |
| statemachine | EventEmitter `stateChanged` | bind_raw_js_event 或 raw 操作 |

**原則：所有回傳 Promise 的 JS 方法，在 bridge 層一律走 `helpers.js` → `_minethon:*Done` 事件模式。**
只有同步回傳的 JS 方法（如 hawkeye 的 `autoAttack()`、viewer 的 `erase()`）可以在 bridge 層直接呼叫。
hawkeye 的 `auto_shot_stopped` 和 collectblock 的 `collectBlock_finished` 是 bot-level event，
使用者可能想訂閱，額外走 EventRelay。

---

## 6. 版本相容性矩陣

| 插件 | 版本 | mineflayer 相容 | Node engines | 風險 |
|------|------|-----------------|-------------|------|
| armor-manager | 2.0.1 | peer: ^4.10.0 | >=18 | 低 |
| tool | 1.2.0 | 無宣告 | 無宣告 | 低 |
| collectblock | 1.6.0 | 無宣告 | 無宣告 | 低 |
| gui | 4.0.2 | 無宣告 | 無宣告 | 中（comparator 橋接） |
| hawkeye | 1.3.9 | dev: ^4.20.1 | 無宣告 | 低 |
| statemachine | 1.7.0 | 無宣告 | 無宣告 | 高（callable 橋接） |
| web-inventory | 1.8.5 | dev: ^4.20.0 | 無宣告 | 低 |
| prismarine-viewer | 1.33.0 | dev: ^4.0.0 | 無宣告 | 低 |
| **dashboard** | **2.0.0** | **dev: ^2.28.1** | >=12 | **高（大版本差距）** |
| **panorama** | **0.0.1** | dev: ^4.3.0 | 無宣告 | **高（native 依賴 + 早期版本）** |

---

## 7. 分支策略與合併計畫

### Phase 0：`refactor/plugin-registry`（先 merge）

範圍：§3 所述最小重構。CI 全綠後 merge 到 main。

### Phase 1a：主線插件（並行開發）

從 Phase 0 merge commit 開分支，可完全並行：

```
plugin/armor-manager      ← Type A, 簡單
plugin/tool               ← Type A, 簡單
plugin/hawkeye            ← Type A, 中等
plugin/viewer             ← Type B, 中等
plugin/web-inventory      ← Type B, 中等
```

### Phase 1b：等待依賴（tool merge 後）

```
plugin/collectblock       ← Type A, 依賴 tool（雖然內部軟載入，但測試需要 tool bridge 存在）
```

### Phase 2：需要 spike 的插件（不直接排進主線）

```
spike/gui                 ← 需確認 JS comparator 橋接可行性
spike/statemachine        ← 需確認 Python callable 當 shouldTransition 的可行性
spike/dashboard           ← 需確認 blessed terminal 與 Python stdout 相容性
spike/panorama            ← 需確認 node-canvas-webgl native build 在 CI 環境可行性
```

Spike 結果決定後才開正式 `plugin/*` 分支。

### 衝突最小化

每個分支只觸碰的共享檔案：
- `_bridge/plugin_registry.py` — append import（低風險）
- `bot.py` — append property（按字母序，低風險）
- `__init__.py` — append `__all__`（按字母序，低風險）

---

## 8. 決策紀錄

| 日期 | 決議 |
|------|------|
| 2026-04-11 | scaffold、blockfinder 跳過 |
| 2026-04-11 | statemachine 封裝：B (typed builder + raw fallback)，但需先 spike |
| 2026-04-11 | hawkeye 公開 API：`bot.combat`(主) + `bot.hawkeye`(alias) |
| 2026-04-11 | Web 插件 port 各自固定預設（viewer:3007, web-inv:3008, sm:8934） |
| 2026-04-11 | ~~不發明 `_minethon:*Done` 事件 — 直接 await JS Promise~~ **已撤銷**：JSPyBridge `Proxy` 無 `__await__`，所有呼叫同步阻塞；改為沿用 `helpers.js` + `_minethon:*Done` 事件模式 |
| 2026-04-11 | 插件分四類整合模式（Type A/B/C/D），不硬套同一 PluginBridge ABC；panorama 為 Type A、dashboard 為 Type D |
| 2026-04-11 | gui/statemachine/dashboard/panorama 先 spike 再排主線 |
| 2026-04-11 | collectblock 顯式 DEPENDS_ON pathfinder + tool，不信賴 setTimeout soft-load |
| 2026-04-11 | Public API 層不直接碰 `_js_bot` — 一律透過 bridge method |
| 2026-04-11 | PluginRegistry 只管 Type A/D；Type B/C 用 bot lazy property，不走 `bot.plugins.load()` |
| 2026-04-11 | statemachine raw fallback 走 `bot.raw.plugin()`，不另設 `require_module()` |

---

## 9. 風險與待處理

### 9.1 ~~AGENTS.md Node 版本~~ 已解決

AGENTS.md 已更新為 Node.js 22+，runtime.py 已加入版本檢查。此項不再阻塞。

### 9.2 Dashboard 版本差距

`@ssmidge/mineflayer-dashboard` 的 devDependencies 是 `mineflayer ^2.28.1`，
與目前 4.37.0 有大版本差距。blessed terminal 佔用 stdout。
**建議**：spike 確認相容性，若不相容則僅提供 raw escape hatch。

### 9.3 Panorama native 依賴

`mineflayer-panorama` 依賴 `node-canvas-webgl`（native C++ addon）。
`npm install --ignore-scripts` 跳過了 build。CI 環境需要 build tools。
版本 0.0.1 — 非常早期，API 可能不穩定。

### 9.4 GUI comparator 橋接

gui 的 comparator function 接收 JS Item proxy 物件。
Python callable 橋接到 JS callback 需要透過 JSPyBridge 的 Callable 機制，
可能有 thread ownership 問題。需 spike 確認。

### 9.5 Statemachine shouldTransition 橋接

statemachine 的 `shouldTransition` 每 tick 被呼叫（20 ticks/sec）。
若 Python callable 橋接有延遲，會影響狀態機反應速度。
替代方案：condition 用 JS 寫，Python 只做 state 定義和 trigger。

---

## 附錄 A：PR Checklist

### Type A / D（loadPlugin 類 — 走 PluginRegistry）

- [ ] `_bridge/plugins/<name>.py` — Bridge 層，繼承 PluginBridge
- [ ] `api/<name>.py` — Public API，只呼叫 bridge method，不碰 `_js_bot`
- [ ] 新增 models（如需要）
- [ ] `plugin_registry.py` — `_register_builtins()` 加入
- [ ] `bot.py` — property accessor
- [ ] `__init__.py` — exports
- [ ] 單元測試
- [ ] Docstring 含 `Ref: <npm_package>/<file>:<line>` 標注
- [ ] Ruff + Pyright 通過

### Type B / C（Service 類 — lazy property，不走 PluginRegistry）

- [ ] `_bridge/services/<name>.py` — Service 層，獨立 class
- [ ] `api/<name>.py` — Public API（如需高階封裝）
- [ ] `bot.py` — lazy property + `disconnect()` teardown
- [ ] `__init__.py` — exports
- [ ] 單元測試
- [ ] Ruff + Pyright 通過

## 附錄 B：Plugin 安裝位置

所有插件已安裝在 JSPyBridge 的 node_modules 中：
```
.venv/lib/python3.14/site-packages/javascript/js/node_modules/
```
這是 AGENTS.md 指定的正確位置。使用 `--no-save --ignore-scripts` 安裝，
不影響 JSPyBridge 自身的 `package.json`。native 依賴（panorama 的 node-canvas-webgl）
需要額外 `npm rebuild` 才能在 runtime 使用。
