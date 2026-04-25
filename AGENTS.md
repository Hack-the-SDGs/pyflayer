# AGENTS.md — minethon 開發指引

## 維護規則

- 本文件是目前專案的 ground truth。
- 發現實作與本文件不一致時，先修其中一邊，不要讓兩邊長期漂移。
- 記錄原則、公開 API 形狀、版本規則；不要把每個細節 API 簽名重複抄在這裡。

## 產品目標

minethon 是教學導向的 Python mineflayer SDK。

- 學生不需要先懂 Node.js、EventEmitter、asyncio
- 公開 API 以同步 callback 為主
- `bot.py` 保持薄，盡量直接委託 mineflayer
- 補全與 hover 體驗由生成的 `bot.pyi` 承擔

第一驗收標準：

> 學生能一行一行看懂並自己仿寫。

## 事件 API

事件入口只保留兩種公開寫法：

```python
@bot.on_chat
def on_chat(...): ...

@bot.on(BotEvent.CHAT)
def on_chat(...): ...
```

設計決策：

- `bot.on(...)` / `bot.once(...)` 只接受 `BotEvent`
- `@bot.on_<event>` 是給 JetBrains / Pylance 更穩定 completion 的 sugar
- `BotEvent` 是 `StrEnum`，給 enum-style completion 與 refactor 安全性
- event callback 參數以 upstream d.ts 為主；若 JS runtime 明確更嚴格或更少參數，可做 source-verified 正規化

## IDE 與型別層

- `src/minethon/bot.pyi` 是 IDE completion 的主要來源，必須由 `scripts/generate_stubs.py` 生成
- generator 的 source of truth 優先讀 `.venv/.../javascript/js/node_modules/` 的實際安裝版本；缺少時才 fallback 到 repo vendored `src/mineflayer/js/node_modules/`
- 中文 hover docstring 直接住在 `bot.pyi` 內；regen 時從現有 `.pyi` 讀回 docstring 再注入，所以人工編輯不會被沖掉（過去的 `docs/stubs_zh_tw.md` 已停用並刪除）
- `src/minethon/_events.py` 由 generator 生成，提供 `BotEvent`
- `src/minethon/models/` 提供可 import 的公開型別 shell，方便使用者寫 annotation；實際成員面仍以 `bot.pyi` 為準

## 公開模組分層

1. `src/minethon/__init__.py`
   - 使用者入口
   - re-export `create_bot`、`Bot`、`BotEvent`、公開錯誤類
2. `src/minethon/bot.py`
   - 公開 module 名 — 純 re-export 自 `_bot_runtime`
   - 維持薄殼，`from minethon.bot import Bot` 不會把 runtime 細節帶進 IDE 視野
3. `src/minethon/_bot_runtime.py`
   - 真正的 runtime façade — `class Bot` 實作、`__getattr__` JS proxy 委託、event decorator、plugin loading、version pin guard
   - 從 `bot.py` 拆出，避免 `.py` + `.pyi` 雙重 `class Bot` 在 IDE 解析時產生衝突源
4. `src/minethon/bot.pyi`
   - 生成的型別面 — `minethon.bot` 模組的 sole `class Bot` declaration
5. `src/minethon/models/`
   - 可 import 的型別 shell
6. `src/minethon/errors.py`
   - 使用者可見的錯誤類

> 補充：PyCharm 的 completion popup 對 Python class member 預設右側顯示 owner class，不顯示型別 annotation — 這是 PyCharm 對 Python 的 UI 設計（純 `class Foo: a = 10` 也是這樣），跟 stub / .pyi 結構無關。要看完整型別請按 `Ctrl+J` (Quick Documentation) 或 hover；assign 後變數型別會正確顯示。

## Source-Verified 原則

所有設計決策必須有 mineflayer / plugin 原始碼依據。

主要來源：

- mineflayer d.ts：`.venv/lib/python3.14/site-packages/javascript/js/node_modules/mineflayer--*/index.d.ts`
- mineflayer JS：`.venv/lib/python3.14/site-packages/javascript/js/node_modules/mineflayer--*/lib/**/*.js`
- pathfinder d.ts：`.venv/lib/python3.14/site-packages/javascript/js/node_modules/mineflayer-pathfinder--*/index.d.ts`

禁止：

- 只看 README 就定義 Python API
- 用 sleep / monkey-patch 硬繞 bridge 問題
- 在沒有 source 依據時擅自把 runtime 行為講成既定契約

## 版本規則

- Python 3.14+
- Node.js 22+
- bundled / pinned npm packages：
  - `mineflayer`
  - `vec3`
  - `mineflayer-pathfinder`
- 對 bundled package，可省略版本
- 對其他 npm 套件，`bot.load_plugin(...)` / `bot.require(...)` 必須顯式版本
- Python 端的 `javascript` (JSPyBridge) 套件在 `pyproject.toml` 用 minor 級 ceiling 鎖（目前 `>=1!1.2.6,<1!1.3`）。理由：minethon 依賴 `On`/`Once` 的 emitter 注入與 Promise `await`-before-return 行為，這兩件事是實作細節不是正式契約；升 minor 前要先跑 `./scripts/format.sh` 與 integration smoke。

理由：

- 避免 JSPyBridge 在 runtime 偷裝 latest
- 讓教學範例與學生環境可重現

## Plugin scope

- 內建 typed / documented plugin：只有 `mineflayer-pathfinder`
- 其他 plugin 目前不提供 typed façade
- 其他 plugin 若要使用，走：
  - `bot.load_plugin(name, "x.y.z", export_key=...)`
  - `bot.require(name, "x.y.z")`

## Callback thread 規則

- 所有 event handler 跑在 JSPyBridge callback thread
- handler 內不要 blocking
- bridge 層必須處理 JSPyBridge 可選的 emitter 注入，以及 runtime 少於 d.ts 宣告參數的情況

## 錯誤處理

至少要維持下列公開錯誤類存在：

- `MinethonError`
- `NotSpawnedError`
- `PlayerNotFoundError`
- `PluginNotInstalledError`
- `VersionPinRequiredError`

使用者訊息優先告訴下一步該做什麼。

## 檢查指令

一鍵跑完（regen stubs → format → lint → type-check → test）：

```bash
./scripts/format.sh            # 寫回格式修正
./scripts/format.sh --check    # 只檢查不寫入（CI 模式）
```

對應的個別指令（與 `format.sh` 內部順序相同）：

```bash
uv run python scripts/generate_stubs.py
uv run ruff format src scripts tests
uv run ruff check src scripts tests
uv run pyright src/
uv run pytest -m "not integration" --tb=short -q
uv run python scripts/check_stubs.py        # TS d.ts ↔ bot.pyi drift gate
```

`scripts/parse_dts.py` 是 TS 解析器的 stable public surface（目前 façade
re-export 自 `generate_stubs.py`）；`scripts/check_stubs.py` 用它比對
mineflayer d.ts 跟現存 `bot.pyi` 的 class member 列表，缺項會 exit 1。

`src/mineflayer/` 是 legacy / scratch 區，不納入目前 package 的 lint 與 pyright 範圍。

## Lint 策略

- `[tool.ruff.lint]` 全域 `select = ["ALL"]`，只對「全案都不適用」的規則做全域忽略。
- 針對情境的豁免一律走 `[tool.ruff.lint.per-file-ignores]`，不要擴張全域 `ignore`。
- 已有的 per-file 區塊：
  - `src/minethon/_bridge.py` / `src/minethon/bot.py` / `src/minethon/_bot_runtime.py` — JSPyBridge proxy 必然是 `Any`，豁免 `ANN401`
  - `src/minethon/**/*.pyi` — 型別覆蓋層；豁免 `N`（命名）、`A`（遮 builtin）、`ANN`、`ARG`、`PLR`、`PYI`、`UP`、`TRY`、`SIM`、`TC`、`RUF001`-`003`（zh-TW 全形符號）、`ERA001`、`PIE790`、`I001`；rationale 留在 `pyproject.toml` 註解
  - `scripts/*.py` — 產生器工具；豁免複雜度與風格類
  - `tests/*` — 允許 magic values、私有存取、硬編 fixtures
  - `examples/**` — 教學 demo，放寬 `ANN`、`T201`、broad-except 等
- 新增豁免時：先嘗試用更具體的規則號（`PIE790`、`RUF022`）而不是整個家族（`PYI`、`RUF`）；只在「整個家族都不適用」時才用前綴。
- generator 輸出要符合 ruff 的規則，`format.sh` 跑完必須 idempotent（第二次跑不再變動）。

## 當前狀態

- [x] 同步 callback façade
- [x] `BotEvent` 與 `@bot.on_<event>` sugar
- [x] pathfinder event augmentation 併入 typed event overload
- [x] `minethon.models` 可 import 型別 shell
- [x] 顯式版本 guard
- [x] 最小單元測試重建
- [ ] 自家 collection wrapper（`bot.players` / `bot.entities` 目前仍是 bridge proxy）
- [ ] 更完整的 user-facing error wrapping
- [ ] 除 pathfinder 以外的 plugin typed 支援
