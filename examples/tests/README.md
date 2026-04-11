# Manual Integration Tests

手動整合測試，用於在實際 Minecraft 伺服器上驗證 minethon 所有公開 API 的行為正確性。

## 設定

```bash
cp examples/tests/.env.example examples/tests/.env
# 編輯 .env 填入 Drasl 帳號資訊
```

## 執行

每個測試都是獨立的 Python 腳本：

```bash
uv run --env-file examples/tests/.env examples/tests/<folder>/test_xxx.py
```

## 測試結構

| 目錄 | 測試範圍 | 建議遊戲模式 |
|------|---------|-------------|
| `lifecycle/` | 連線、重生、斷線 | Survival |
| `properties/` | 所有唯讀屬性快照 | Survival |
| `movement/` | 移動、跳躍、騎乘 | Survival / Creative |
| `chat/` | 聊天、私訊、訊息等待 | Any |
| `inventory/` | 物品欄操作 | Survival / Creative |
| `blocks/` | 方塊搜尋、挖掘、放置 | Survival |
| `entities/` | 實體搜尋、攻擊、互動 | Survival |
| `events/` | ObserveAPI 事件系統 | Any |
| `navigation/` | Pathfinder 導航 | Survival |
| `combat/` | Hawkeye 投射物戰鬥 | Survival |
| `plugins/` | 插件系統 + Type A 插件 | Varies |
| `services/` | Type B 服務（viewer、inventory viewer） | Any |
| `windows/` | 容器、合成、村民交易 | Survival |
| `creative/` | 創造模式操作 | Creative |
| `advanced/` | 睡覺、釣魚、鞘翅、設定 | Varies |
| `raw/` | Raw escape hatch | Any |

## 共用基礎設施

- `_common.py` — 提供 `create_bot()`、`connected_bot()` context manager、格式化輸出 helpers
- `.env.example` — 環境變數範本

## 輸出格式

```
[PASS] 屬性名稱: 值
[FAIL] 屬性名稱: 值 (expected 預期值)
[INFO] 說明訊息
[SKIP] 跳過原因
```
