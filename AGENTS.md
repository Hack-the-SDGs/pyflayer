# AGENTS.md — Minethon 開發指引

## 本文件的維護規則

- 本文件是 minethon 專案的唯一 ground truth。
- 當你發現程式碼與本文件描述不一致時，**不要自行判斷哪邊正確**，先詢問使用者，確認後更新本文件。
- 每次原則、約定或架構決策有新增或修改，都必須同步更新本文件，不僅限於重大架構變更。
- 保持精簡。本文件記錄「原則與決策」，不記錄「完整 API 簽名」——那是程式碼和 docstring 的工作。

## 互動原則

- **禁止阿諛奉承。** 當使用者質疑你的判斷時，先思考、查證，再回應。不要為了迎合而直接肯定使用者。
- **遇到不確定的事，問。** 不要猜測使用者的意圖或偏好。
- **不要用修補的方式解決問題。** 遇到 bug 或異常行為時：
  1. 先去讀 mineflayer 的 JS 原始碼，理解它的意圖和流程
  2. 判斷問題來源是橋接層、非同步時序、還是設計層
  3. 從根本解決，不要用 sleep / monkey-patch / 特殊 flag 繞過
- **所有設計決策必須基於 mineflayer API 文件和原始碼。** 不要憑直覺定義 Python 介面。
  - mineflayer 文件位置：`.venv/lib/python3.14/site-packages/javascript/js/node_modules/mineflayer/docs`
  - 相關插件的文件也在對應的 node_modules 目錄下

## 專案定義

**minethon** 是一套 Python-first 的 Mineflayer SDK。

- 不重寫 mineflayer，而是建立一層 typed Python façade
- 底層透過 JSPyBridge（`javascript` pip package）驅動，但 JSPyBridge 是私有實作細節，不對使用者暴露
- 公開 API 必須是 Pythonic、有型別、有文件、可維護的
- 使用者不需要理解 Node.js、JSPyBridge、EventEmitter 就能開發 bot
- 提供明確標示的 raw escape hatches 給進階使用者直接操作 JS 物件；未標示為 raw 的 API 一律不得洩漏 JS proxy

## 技術棧

- Python 3.14+、Node.js 22+（mineflayer 4.37.0 要求 `node >=22`）
- Bridge：JSPyBridge
- 套件管理：uv（`pyproject.toml`）
- Async 模型：asyncio（公開 API 全部 async/await，純資料存取的 property 除外）
- 型別：mypy / pyright 相容，inline annotations + `py.typed`
- 測試：pytest + pytest-asyncio
- Linting：ruff

## 核心插件範圍

以下插件需要在設計中考慮支援。不代表全部要在第一天實作，但架構必須能容納它們：

- mineflayer（核心）
- mineflayer-pathfinder
- prismarine-viewer（npm 名稱，非 mineflayer-prismarine-viewer）
- mineflayer-web-inventory
- mineflayer-statemachine
- mineflayer-armor-manager
- mineflayer-collectblock
- @ssmidge/mineflayer-dashboard（npm 名稱，非 mineflayer-dashboard）
- mineflayer-tool
- minecrafthawkeye（npm 名稱，非 mineflayer-hawkeye）
- mineflayer-gui
- mineflayer-panorama

插件系統需要有明確的擴充介面，讓上述插件以及未來的第三方插件能以一致的方式接入。

### 插件整合模式

不是所有 mineflayer 插件都走同一種模式。依原始碼分四類：

- **Type A（`bot.loadPlugin()` facade）**：export 一個 `(bot) => void` 函式，透過 `bot.loadPlugin()` 載入。包括 armor-manager、tool、collectblock、gui、hawkeye、panorama。走 `PluginRegistry` 管理。
- **Type B（Server / Service）**：直接呼叫 `module(bot, options)` 初始化，不走 `bot.loadPlugin()`。包括 prismarine-viewer、web-inventory。透過 `bot.<service>` lazy property 管理。
- **Type C（Class Library / DSL）**：export 一組 class，使用者自行 `new` 實例。包括 statemachine。透過 `bot.raw.plugin()` 存取。
- **Type D（Higher-Order Function）**：export 一個 `(options) => (bot) => void` 的 HOF。包括 @ssmidge/mineflayer-dashboard。使用時 `bot.loadPlugin(mod(options))`，走 `PluginRegistry` 管理。

Public API 層（`api/`）不直接碰 `_js_bot`，一律透過 bridge / service 層的方法。

### JS Promise 橋接策略

**JSPyBridge 不支援 Python async await JS Promise。** `Proxy` 類別沒有 `__await__` 方法（`proxy.py:183-289`），所有 JS 呼叫透過 `threading.Event.wait()` 同步阻塞呼叫執行緒（`proxy.py:39, 134, 143`）。`bridge.js` 裡的 `await` 發生在 JS 端（`bridge.js:133-138`），Python 端看到的只是同步阻塞直到 Promise resolve。

因此，**所有回傳 Promise 的 JS 方法都必須走 `helpers.js` → `_minethon:*Done` 事件模式**：
1. `helpers.js` 中的 `start*` function 呼叫 JS Promise method，用 `.then()/.catch()` 非阻塞地 emit `_minethon:*Done` 事件
2. `js_bot.py` 中的 `start_*` method 同步呼叫 helpers（快速返回，不等 Promise）
3. `bot.py` 中的 async method 用 `await self._relay.wait_for(DoneEvent)` 真正 yield 給 asyncio event loop

只有同步返回的 JS 方法（如 `bot.chat()`、`bot.attack()`）可以在 bridge 層直接呼叫。

詳細規格見 `docs/architecture/plugin-expansion-plan.md`。

## 架構原則

### 三層分離

1. **Private Bridge（`_bridge/`）**— 啟動 JSPyBridge、載入 JS 模組、綁定事件、執行 JS 呼叫、管理 JS 物件生命週期。不定義任何公開型別。
2. **Domain Model（`models/`）**— 純 Python 資料結構（dataclass / enum / TypedDict）。不依賴 JSPyBridge。可獨立 import 和測試。
3. **Public SDK（`bot.py`, `api/`）**— 使用者直接互動的層。依賴 models，透過 bridge 執行操作。

**硬性規則：**
- 除明確標示為 raw 的 escape hatch 外，公開 API 不得回傳 JS proxy object
- 除 raw escape hatch 外，公開 API 的 type hint 不得出現 `javascript` 模組的任何型別
- 使用者不需要 `from javascript import ...`

### Async 橋接策略

JSPyBridge 的 callback 跑在自己的 thread 上，不在 asyncio event loop 裡。關鍵約束：

- **所有 JSPyBridge 呼叫必須在初始化它的同一個 thread 上執行**，不能用 `to_thread()` / `run_in_executor()` 搬走
- **JS → Python 事件**：透過 `call_soon_threadsafe()` 投遞到 asyncio loop
- **JS callback thread 只做最小工作**：不要在 callback thread 內遍歷 live JS proxy；若需要事件資料，優先在 JS 端先整理成 plain payload，再投遞到 Python loop
- **等待型操作**（如 goto）：Python 端建立 `asyncio.Future`，由事件 relay 在收到對應 JS 事件時 resolve
- 若 JS 操作可能阻塞過久，在 JS 端設計為非阻塞/事件驅動，不要在 Python 端包 executor
- **公開同步 property 必須來自 Python snapshot/cache**；若資料必須 live 查詢 JS，應提供明確的 async 方法，而不是隱性同步跨 bridge I/O

### 風格原則

- 避免歧義：能用 Enum 就用，不接受 magic string
- Python 側命名遵循 PEP 8（snake_case），與 JS 側 camelCase 做明確映射
- 所有公開方法必須有 Google style docstring 和完整 type hints
- 不使用 `Any` 作為公開 API 回傳型別（raw escape hatch 除外）
- **所有與 mineflayer JS 互動的方法與屬性，必須標注對應的 mineflayer 原始碼來源。** 格式為 `Ref: mineflayer/lib/plugins/<file>.js — <property/method/event>`，寫在 docstring 或行內註解中。確保每個跨 bridge 行為都有可追溯的依據，便於除錯與審查。

### JSPyBridge 已知陷阱

1. `@On` callback 裡不要做 blocking 操作——所有 callback 共用一個 thread
2. `.valueOf()` 可序列化 JS 物件為 Python dict，但對大物件很慢，只在需要快照時用
3. `@On` callback 的參數語意與 JSPyBridge / Node 版本有關：舊版 patched emitter 可能會把 emitter/`this` 放在第一個參數；目前 Node 22+ 目標環境通常直接收到 event payload。bridge 層必須依實際 runtime 正規化，不能硬編碼假設第一個參數一定是 `this`
4. JS 的 `undefined` / `null` 在 Python 端行為不一致，轉換時防禦性處理
5. `require()` 首次呼叫會自動安裝 npm 套件，可能較慢

### 效能原則

- 避免在迴圈中逐一跨 bridge 呼叫——批次處理
- 公開同步 property 必須從快取快照讀取，不要每次跨 bridge
- 高頻事件（move, entityMoved, physicsTick）必須在進入 Python 前於 JS 端節流，或不公開
- tick 敏感的邏輯可以用 JS 實作，避免 Python 跨 bridge 延遲造成的差異

## 現有狀態

<!-- 隨開發進展更新此區塊 -->
- [x] 已實作：`_bridge/` 的 runtime / controller / event relay / marshalling、`models/` 基本資料型別、`Bot` 公開入口、`ObserveAPI`、`NavigationAPI`（mineflayer-pathfinder）、`raw` escape hatch，以及基本 hello / goto / drasl auth 範例
- [x] 已知痛點：事件 payload 與 mineflayer docs 尚未全面對齊；raw escape hatch 邊界仍偏寬；插件系統目前實際只有 pathfinder 的初步接入；npm 插件版本未釘選（JSPyBridge lazy install 會拉 latest）

## 決策紀錄

<!-- 格式：日期 — 決策內容 — 原因 -->
<!-- 範例：2025-01-15 — 事件系統改用 typed event class 而非 string key — 避免拼字錯誤且支援 IDE 自動補全 -->
2026-04-10 — raw JS proxy 僅允許出現在明確標示為 raw 的 escape hatch — 維持預設 SDK 為 Python-first typed façade
2026-04-10 — 公開同步 property 必須由 Python snapshot/cache 提供，不直接做 live bridge 讀取 — 避免 thread ownership 問題與隱性同步 I/O
2026-04-10 — `@On` callback payload 必須依實際 JSPyBridge / Node runtime 正規化，不假設第一個參數一定是 `this` — 舊版 emitter patch 與目前 Node 18+ 行為不同
2026-04-10 — 所有跨 bridge 的方法與屬性必須標注 mineflayer 原始碼來源 — 確保行為有依據，加速除錯與審查
2026-04-11 — 插件分四類整合模式（Type A/B/C/D），不硬套同一抽象 — 原始碼驗證各插件 export pattern 不同；dashboard 為 Type D（HOF）、panorama 為 Type A（兩個 inject function）
2026-04-11 — Node.js 版本要求從 18+ 更新為 22+ — mineflayer 4.37.0 的 `engines.node` 為 `>=22`
2026-04-11 — Public API 不直接碰 `_js_bot`，一律透過 bridge method — 維持三層分離
2026-04-11 — ~~能 await JS Promise 的直接 await，不自造 Done event~~ **已撤銷** — JSPyBridge `Proxy` 無 `__await__`，所有呼叫同步阻塞（`proxy.py:39,134,143`）；`bridge.js:133-138` 的 await 發生在 JS 端不是 Python 端
2026-04-11 — 所有回傳 Promise 的 JS 方法必須走 `helpers.js` → `_minethon:*Done` 事件模式 — 這是 JSPyBridge 限制下唯一不阻塞 asyncio event loop 的做法
2026-04-11 — 插件 npm 名稱以實際 package.json 為準 — prismarine-viewer（非 mineflayer-prismarine-viewer）、minecrafthawkeye（非 mineflayer-hawkeye）、@ssmidge/mineflayer-dashboard（非 mineflayer-dashboard）
