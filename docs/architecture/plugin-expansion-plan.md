# Plugin Expansion Plan

這份舊文件已不再描述目前的 minethon 架構。

原因：

- 它基於已刪除的 async facade / registry 設計
- 內容假設了 `bot.raw.plugin()`、`wait_until_spawned()`、大量 plugin bridge 與 async API
- 這些都不符合目前專案已採用的同步 callback + thin facade 路線

目前應以這兩份文件為準：

- `AGENTS.md`
- `README.md`

目前正式決策摘要：

- 公開事件入口同時支援 `@bot.on("chat")`、`@bot.on_chat`、`@bot.on(BotEvent.CHAT)`
- runtime façade 在 `src/minethon/bot.py`
- IDE 型別層由 `scripts/generate_stubs.py` 生成 `src/minethon/bot.pyi`
- `BotEvent` 由 `src/minethon/_events.py` 生成
- 可 import 的公開型別在 `src/minethon/models/`
- 內建 typed plugin 目前只有 `mineflayer-pathfinder`
- 非 bundled npm 套件必須顯式版本，避免 JSPyBridge runtime lazy install / 偷裝 latest

如果未來要再寫新的架構文件，必須先符合 `AGENTS.md`，再補 source-verified 依據。
