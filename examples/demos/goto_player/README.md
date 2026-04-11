# Goto Player

導航到指定玩家位置並跟隨的 bot。

## 功能

- 聊天指令 `come` — 導航到發訊者位置
- 聊天指令 `follow` — 持續跟隨發訊者
- 聊天指令 `stop` — 停止移動

## 前置條件

- 本地 Minecraft Java Edition 伺服器（`localhost:25565`）
- 伺服器設定 `online-mode=false`
- 至少一個玩家在線上

## 執行

```bash
uv run examples/demos/goto_player/main.py
```
