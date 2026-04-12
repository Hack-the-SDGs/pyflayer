# AGENTS.md — Minethon 開發指引

## 本文件的維護規則

- 本文件是 minethon 的唯一 ground truth。
- 發現程式碼與本文件不一致時，**先詢問使用者**再更新。
- 新增或修改架構決策時同步更新本文件。
- 保持精簡。記錄「原則與決策」，不記錄「API 簽名」——那是 `.pyi` 與 docstring 的工作。

## 客戶畫像（決定一切顆粒度）

- **主要使用者**：暑期營學員 ~60 人（以高中生為主），工作人員 ~40 人
- **課程時數**：約 24 小時
- **Python 水準**：具備 function / for / if；**未學過 asyncio、class 設計、generic type**
- **AI 輔助**：搭配 Google Gemini Credit 與自訂 skill 協助編碼
- **伺服器**：Drasl 正版驗證、內建 HMCL 啟動器、300 人上限，無運維負擔

> 驗收第一標準：「學生能一行一行看懂並自己仿寫」。看不懂的設計就是過度設計。

## 互動原則

- **禁止阿諛奉承。** 使用者質疑你的判斷時，先思考、查證，再回應。
- **遇到不確定的事，問。** 不要猜測使用者意圖或偏好。
- **不要用修補式做法。** 遇到 bug：
  1. 先讀 mineflayer 的 `index.d.ts` 或 JS 原始碼，理解其意圖
  2. 判斷問題來源是橋接層、非同步時序還是設計層
  3. 從根本解決，不用 sleep / monkey-patch / 特殊 flag 繞過
- **所有設計決策必須有 mineflayer 文件或原始碼依據。** 不要憑直覺定義 Python 介面。
  - TypeScript 宣告：`node_modules/mineflayer/index.d.ts`
  - API 文件：`.venv/lib/python3.14/site-packages/javascript/js/node_modules/mineflayer/docs/api.md`
  - 插件文件：各自 `.venv/lib/python3.14/site-packages/javascript/js/node_modules/<plugin>/README.md`

## 專案定義

**minethon** 是一套**教學導向**的 Python mineflayer SDK。

- 不重寫 mineflayer；提供**薄門面**（thin facade）+ `.pyi` 型別檔
- 使用者不需要理解 Node.js / JSPyBridge / asyncio / EventEmitter
- 公開 API 採原生 Python 風格：`@bot.on('chat')`、`bot.players['alice']`、`bot.players.get('alice')`
- IDE 補全覆蓋：event 名稱、event 回呼參數、bot 方法與屬性、常用插件 API

## 技術棧

- Python 3.14+、Node.js 22+（mineflayer `engines.node >=22`）
- Bridge：JSPyBridge（`javascript` 套件）
- Python 套件管理：uv（`pyproject.toml`）
- npm 套件：**所有版本必須釘死**，由 `setup.sh` 明確安裝（禁用 `require()` lazy install）
- 並行模型：**同步 callback 為主**。長時任務一律透過事件完成，不提供 async/await
- 型別：pyright 相容；公開 API 全部 annotated；`_types.pyi` 提供補全
- 測試：pytest，分單元測試（CI 跑）與整合測試（手動 / sprint 收尾跑）
- Lint / Format：ruff

## 架構四層（嚴格分離）

1. **`minethon/__init__.py`** — 使用者入口。`create_bot()` 與 `Bot` class 的原生 Python 方法（`on`、`load_plugin`、`require`、dict-friendly collection 包裝）
2. **`minethon/_types.pyi`** — IDE 補全來源。`Bot` 方法 / 屬性 / event overload，**由 `index.d.ts` 機械轉換而來**，禁手刻
3. **`minethon/models/`** — 純 Python `@dataclass`（Vec3、Entity、Block、Item、...）。不依賴 JS，可獨立 import 與測試
4. **`minethon/plugins/`** — 插件 `.pyi` 宣告。**目前只寫 pathfinder**；其他插件學生透過 `bot.require()` 原生使用

**硬性規則**：
- `Bot` class 保持薄。行為委託給 JS，只加 Python 糖衣（decorator、dict iteration）
- 不為每個 mineflayer 方法寫手工 wrapper；全走 `__getattr__` 代理 + `.pyi` 宣告
- `.pyi` 中禁止出現 `Any`（raw escape hatch 例外）
- 不對外暴露 JSPyBridge 的 `Proxy` 類型，除非明確標示 raw

## 公開 API 風格

```python
from minethon import create_bot

bot = create_bot(host='play.camp.tw', username='alice')

@bot.on('chat')
def on_chat(username: str, message: str, *_): ...

@bot.on('death')
def on_death(): ...

bot.chat('hello')
player = bot.players['alice']        # dict-like collection
entities = list(bot.entities)            # iterable

pf = bot.load_plugin('mineflayer-pathfinder') # pf = bot.load_plugin('mineflayer-pathfinder', '2.4.5')
bot.pathfinder.setGoal(x, y, z)
bot.pathfinder.setGoal(pf.goals.GoalNear(x, y, z, 1))

@bot.on('goal_reached')
def arrived():
    bot.chat('我到了')
```

## 插件整合（簡化為二元介面）

| API | 用途 | 覆蓋範圍 |
|-----|------|---------|
| `bot.load_plugin(name, version, **opts)` | 一鍵載入 Type A 插件（`bot.loadPlugin(fn)` 模式） | pathfinder、armor-manager、tool、collectblock、gui、hawkeye、panorama |
| `bot.require(name, version)` | Raw escape hatch，回傳原生 JS module，由使用者自行初始化 | Type B / C / D 插件（viewer、web-inventory、statemachine、dashboard） |

- 只為 **pathfinder** 寫 `.pyi`。其他插件使用者需要時讀該 plugin README
- Type B/C/D 初始化邏輯使用者自己寫——~5% 使用率不值得 ~15% 框架成本
- 版本參數**可選填**，預設為內定寫死的常數版本

## 事件契約（教學核心）

- 所有長時任務（dig / goto / place / equip / fish / sleep / ...）**不回傳可等待的物件**，透過事件完成
- `.pyi` 為每個事件定義 `@overload`，讓 `@bot.on(...)` 自動補全回呼參數
- Event 名稱 = `Literal[...]`，IDE 輸入 `bot.on('` 立即跳出完整清單
- Event payload 以 `index.d.ts` 為準，**不憑記憶或推測**

## 同步模型與 callback thread 約束

- 所有 `@bot.on(...)` handler 跑在 JSPyBridge 的 callback thread（只有一條）
- **handler 內禁止 blocking 操作**（`time.sleep`、長迴圈、阻塞 I/O、等待外部服務）
- 需要延遲執行 → 透過 JS 層 `setTimeout` 包裝的 helper，或以事件鏈接續
- 多個 handler 的執行順序 = 註冊順序

## JSPyBridge 已知陷阱

學生會踩的五個雷，minethon 必須在包裝層處理好：

1. `@bot.on(event)` 第一個 callback 參數語意依 Node / JSPyBridge 版本而異——minethon 在 wrapper 層正規化，學生不需關心
2. `undefined` 轉 Python 多數為 `None`，但部分情況是空 proxy（truthy）。**API 與範例統一用 `x is None` 判斷**，禁 truthy 判斷
3. JS Promise **不能** `await`——所有長任務走事件。課程不教 `async/await`
4. `.valueOf()` 大物件序列化慢——僅用於快照，不可在高頻路徑使用
5. `require()` 首次呼叫會自動安裝 npm（慢、可能失敗）——`setup.sh` 強制預裝，專案內 `require()` 的版本參數皆為硬要求

## 風格原則

- 命名：Python 側 PEP 8（snake_case）；直接轉發的 mineflayer 原生屬性保留 camelCase
- 公開 API 命名使用動詞/名詞短語，避免技術術語（e.g. `bot.load_plugin` 優於 `bot.register_plugin`）
- 公開方法：Google style docstring + 完整型別
- 禁止 `Any` 作為公開回傳型別（raw escape hatch 例外）
- **所有跨 bridge 的行為必須標註 mineflayer 原始碼來源**，格式 `Ref: mineflayer/lib/<file>.js — <symbol>`，寫在 docstring 或行內註解

## 錯誤處理

- JS 層錯誤不直接冒到學生面前。包一層 `MinethonError` 體系：
  - `NotSpawnedError` — bot 未 spawn 時呼叫位置相關 API
  - `PlayerNotFoundError` — 查無玩家
  - `PluginNotInstalledError` — plugin 未載入
- 錯誤訊息優先提供「下一步動作建議」，而非技術細節
- 底層 JS stack 保留在 `error.__cause__`，進階使用者可檢視

## 效能原則

- 避免在 `move` / `physicsTick` 等高頻事件內跨 bridge 呼叫
- bot 屬性（`position`、`health`）每次存取都跨 bridge——handler 開頭讀一次區域變數後再使用
- 大集合（`bot.entities`）iteration 慢——collection wrapper 應提供 JS 端過濾的 `.filter()` / `.find()`

## 不做的事（保持 scope 收斂）

- 不提供 `async def` API（24hr 課程不教 asyncio）
- 不為 pathfinder 以外的插件寫 typed wrapper
- 不主動追 mineflayer 小版本；每學期手動評估升版
- 不支援多 mineflayer 版本並存
- 不提供 server-side（spigot/paper）整合——minethon 只做 client bot

## CI / Commit 前置檢查

```bash
uv run pytest -m "not integration" --tb=short -q
uv run ruff format --check src/ tests/
uv run ruff check src/
uv run pyright src/
```

- `integration` 標記的測試不在 CI 跑，但**每個 sprint 收尾必須手動跑一次並記錄結果**
- commit 前上述全部通過才可提交

## 現有狀態

- [x] 核心骨架：`src/minethon/{__init__.py, bot.py, _bridge.py, py.typed}`。`Bot` 用 `__getattr__` 轉發 JS proxy，`@bot.on(event)`/`@bot.once(event)` 走 `javascript.On`/`javascript.Once`，`create_bot(**opts)` 做 snake_case → camelCase 轉換，`bot.run_forever()` 透過 `end` 事件阻塞
- [x] `_types.pyi`（即 `src/minethon/bot.pyi`）— 由 `scripts/generate_stubs.py` 從 mineflayer/vec3/prismarine-* 的 `index.d.ts` 機械產生，含 94 個 event overload、完整 Bot 方法/屬性、BotOptions TypedDict；pyright strict 下 0 error
- [x] 插件介面二元化：`bot.load_plugin(name, version, *, export_key=None, **opts)`（Type A）+ `bot.require(name, version)`（raw escape hatch）
- [x] Pathfinder typed wrapper：`Pathfinder` / `Goals` / `Movements` / `GoalNear`/`GoalBlock`/`GoalXZ`/... 完整型別；`load_plugin('mineflayer-pathfinder')` 回傳強型別 `PathfinderModule`
- [x] `setup.sh`：檢查 Node 22+ / uv，執行 `uv sync` 並於 JSPyBridge 的 node_modules 預裝固定版本（mineflayer@4.37.0 / vec3@0.1.10 / mineflayer-pathfinder@2.4.5），避免 lazy install
- [x] `examples/demos/drasl_auth/main.py` — 以新同步 API 重寫（登入、spawn、chat 觸發字、kicked、end），示範 `bot.entity.position` / `bot.players` / `bot.chat` / `bot.quit` / `bot.run_forever()`
- [ ] `tests/` 單元測試尚未重建（舊測試已隨舊 facade 刪除）
- [ ] `bot.players` / `bot.entities` 為 JSPyBridge 原生 proxy；`__iter__`/`__getitem__` 來自 JSPyBridge，尚未包自家 Mapping wrapper
- [ ] `MinethonError` / `NotSpawnedError` / `PlayerNotFoundError` / `PluginNotInstalledError` 錯誤體系尚未實作

## 決策紀錄

2026-04-13 — 重寫啟動：刪除舊 `src/minethon/`（~12.2k 行 async facade）、`tests/`、`examples/tests/`、其他 demos，僅保留 `examples/demos/drasl_auth/.env*`。改採純同步 callback 模型。
2026-04-13 — `Bot.__getattr__` 轉發所有未覆寫屬性到 `_js`；型別由 sibling `.pyi` 提供，`.py` 只放 runtime 行為。
2026-04-13 — `_types.pyi` 機械產生，來源六份 `index.d.ts`（mineflayer、vec3、prismarine-entity/block/item/chat/windows/recipe）；禁手刻、禁憑記憶。Pathfinder 的型別就近掛在同一個 `bot.pyi`，保持 single-file 結構。
2026-04-13 — `bot.on(event)` 不提供 `event: str` fallback overload——強制學生使用 Literal 事件名以取得 IDE 補全；typo 會被 pyright 擋。
2026-04-13 — Pyright 設定：strict + `reportMissingTypeStubs="none"` + `reportUnknown*="none"` + `reportUnusedFunction="none"`。前三者因 JSPyBridge 無 stub；後者因 `@bot.on()` 裝飾器上的 inner function 會被誤判為 unused。
2026-04-13 — npm 版本全釘死於 `setup.sh`，`_bridge.py` 宣告 `MINEFLAYER_VERSION`/`VEC3_VERSION` 常數；`require()` 傳入版本參數。lazy install 由 `setup.sh` 預裝規避，不走 runtime check。
2026-04-13 — `load_plugin` 使用內建 `_PLUGIN_EXPORT_KEY` 對照表處理 pathfinder（模組 export `.pathfinder` 才是 installer）；其他 Type A 插件假設 module 本身就是 installer。支援 `export_key` kwarg 與 `**options`（HOF 模式如 dashboard）。
