# minethon — 繁體中文 IDE 說明

<!--
維護規則（請先讀）
========================================================================
這個檔案是 src/minethon/bot.pyi 上所有 docstring 的唯一來源
scripts/generate_stubs.py 讀這份檔案，把每個 `### xxx` 區段的內文注入到
對應 symbol 的 Python docstring 裡。IDE hover 就會顯示這些中文說明

寫作規則：
  1. 每個 symbol 一個 `### ` 開頭的標題。標題本身的格式決定 symbol 類別：
       - `### bot.chat(message)`        → Bot 方法
       - `### bot.health`               → Bot 屬性（無括號）
       - `### "chat"`                   → 事件（雙引號包住事件名）
       - `### Vec3`                     → 類別（class-level docstring）
       - `### Vec3.offset(dx, dy, dz)`  → 類別的方法
       - `### Entity.position`          → 類別的屬性
  2. 標題後的所有內容，直到下一個 `### ` 為止，都屬於這個 symbol
  3. 參數 / 事件回呼參數用清單格式：  - `name` — 說明
  4. 可以放 markdown 程式碼區塊當範例；generator 會原樣保留在 docstring
  5. 沒寫的 symbol：整段不要放就好，IDE hover 會退回只顯示型別簽名
  6. `## 頂層區塊` 與本段 HTML 註解都只是給人看的分類／指示，parser 會忽略

新增 symbol 時的檢查清單：
  [ ] 標題完全符合 symbol 類別的格式
  [ ] 參數全部列出（和 bot.pyi 的簽名對齊；請以 index.d.ts 為主要依據，
      但最終正確性請回 node_modules/mineflayer/lib/ 的 JS 實作確認）
  [ ] 一句話可以說完的，就一句話；避免把 docstring 寫成論文

遇到疑慮時：先讀 mineflayer 的 JS 實作（lib/plugins/*.js），那才是 ground truth
========================================================================
-->


## Bot 類別

### Bot
操縱 Minecraft 機器人的核心物件
由 `create_bot(...)` 建立，透過 `@bot.on(event)` 註冊事件處理器、呼叫 `bot.chat(...)` 等方法操作機器人

機器人連線完成後會非同步地進入世界
**請務必等 `spawn` 事件觸發後**，再呼叫跟位置 / 世界有關的 API；在此之前 `bot.entity` 等屬性尚未就緒

---

## 事件（events）

### "login"
成功登入伺服器但**尚未進入世界**時觸發事件（無參數）
此時世界尚未載入，請勿呼叫位置相關的 API，要等待 `"spawn"` 事件觸發後才可以呼叫
此事件通常只拿來印 log 或做連線成功的標記

### "spawn"
機器人在世界中生成（或重新生成）後觸發事件（無參數）
這是可以真正開始移動的時機

可查詢 `bot.entity.position`、發聊天訊息、載入插件等都應該在這個事件**之後**進行

死亡重生、跨維度傳送也會再次觸發事件

### "chat"
頻道上有公開聊天訊息時觸發事件
**自己發的訊息也會觸發**，需自行以 `username == bot.username` 比對忽略

Args:
    username: 發話者的遊戲名稱
    message: 已去除顏色碼與控制字元的純文字
    translate: 聊天類型字串（例如 `chat.type.text`）；多數 Bukkit 系伺服器會是 `None`
    jsonMsg: 伺服器原始的 JSON 訊息物件，保留顏色、點擊事件等 metadata
    matches: 若有自訂 chat pattern 且比中時，是捕獲的字串陣列；否則為 `None`

See Also:
    `"whisper"`

```python
@bot.on_chat
def on_chat(username, message, *_):
    if username == bot.username:
        return
    if message == "hi":
        bot.chat("哈囉")
```

### "whisper"
有玩家對你私聊（`/tell`、`/msg` 指令）時觸發事件

Args:
    username: 發話者的遊戲名稱
    message: 已去除顏色碼與控制字元的純文字
    translate: 聊天類型字串（例如 `chat.type.text`）；多數 Bukkit 系伺服器會是 `None`
    jsonMsg: 伺服器原始的 JSON 訊息物件，保留顏色、點擊事件等 metadata
    matches: 若有自訂 chat pattern 且比中時，是捕獲的字串陣列；否則為 `None`

See Also:
    `"chat"`

### "kicked"
被伺服器踢出時觸發事件
通常緊接著會觸發 `"end"` 事件

Args:
    reason: 伺服器送出的踢出原因原始字串，由 mineflayer 原樣轉送未做解析；現代伺服器通常是 JSON 格式的 `ChatMessage`，要顯示給使用者時用 `ChatMessage.fromNotch(reason).toString()` 轉純文字
    loggedIn: `True` 代表已登入後才被踢、`False` 代表握手階段就被拒絕

### "end"
連線斷開時觸發事件
正常離線、被踢、網路中斷都會觸發事件
這也是 `bot.run_forever()` 結束阻塞並讓 script 退出的訊號

Args:
    reason: 斷線原因

### "death"
機器人死亡時觸發事件（無參數）
mineflayer 會自動重生，稍後會再次觸發 `"spawn"` 事件

### "health"
血量或飽食度有變動時觸發事件（無參數）
要讀取新值請直接看 `bot.health` / `bot.food`

### "move"
機器人位置或視角改變時觸發事件
**這是高頻事件**，每 tick 都可能觸發，請勿在此做耗時工作

Args:
    position: 移動前的 `Vec3`（可以和 `bot.entity.position` 比較得知移動方向 / 距離）

### "playerJoined"
有玩家加入伺服器時觸發事件

Args:
    player: 加入的 `Player` 物件（含 `.username`、`.uuid`、`.ping` 等）

### "playerLeft"
有玩家離線時觸發事件

Args:
    player: 離線的 `Player` 物件

### "diggingCompleted"
`bot.dig(block)` 成功挖掉方塊時觸發事件

Args:
    block: 被挖掉的 `Block`（此時方塊類型多半已變成空氣，位置資訊仍可用）

### "diggingAborted"
`bot.dig(block)` 被中斷時觸發事件
例如玩家移動離開太遠、或方塊被他人搶挖

Args:
    block: 中途放棄的目標方塊

### "actionBar"
伺服器在動作列推送訊息時觸發事件
（血條上方的懸浮文字）

Args:
    jsonMsg: 伺服器原始的 JSON 訊息物件

### "error"
機器人遇到不致命的例外（例如解析封包失敗）時觸發事件
把這個事件印出來有助於 debug

Args:
    err: `Error` 物件

### "message"
**任何**文字訊息抵達時觸發事件
公開聊天、私聊、系統訊息、指令輸出都涵蓋
用來記錄所有進入機器人的文字

Args:
    jsonMsg: 伺服器原始的 JSON 訊息物件
    position: 訊息來源位置字串：`"chat"`（一般聊天）、`"system"`（系統訊息）、`"game_info"`（動作列）

### "messagestr"
**任何**文字訊息抵達時觸發事件
公開聊天、私聊、系統訊息、指令輸出都涵蓋
用來記錄所有進入機器人的文字
同 `"message"` 但把內容用 `toString()` 攤平成純字串，方便直接印

Args:
    message: 已攤平的字串訊息
    position: 訊息來源位置字串：`"chat"`（一般聊天）、`"system"`（系統訊息）、`"game_info"`（動作列）
    jsonMsg: 伺服器原始的 JSON 訊息物件

### "unmatchedMessage"
系統訊息沒有對應到任何已註冊的 chat pattern 時觸發事件
一般玩家很少用到，多半是開發自訂 pattern 時才會監聽

Args:
    stringMsg: 原始純文字訊息
    jsonMsg: 原始 JSON 訊息物件

### "inject_allowed"
mineflayer 載入 `minecraft-data` 並允許插件 inject 時觸發事件（無參數）
這是**插件開發**的 hook，一般腳本不需要監聽；建議還是等 `"spawn"` 事件觸發後再動作

### "title"
伺服器推送大型標題或副標題時觸發事件

Args:
    text: 標題文字
    type: `"title"` 或 `"subtitle"`

### "rain"
天氣開始下雨或停雨時觸發事件（無參數）
要判斷現在狀態請讀 `bot.isRaining`

### "time"
世界時間有更新時觸發事件（無參數）
伺服器定時同步、或 `/time set` 指令
由於幾乎每個 tick 都會觸發，**不要在這裡做耗時工作**

### "respawn"
機器人重生進入世界時觸發事件（無參數）
（`"death"` 後會先觸發此事件，接著才是 `"spawn"`）

### "game"
遊戲模式、維度、難度等 `bot.game` 欄位有變更時觸發事件（無參數）
要讀新值請直接看 `bot.game.*`

### "spawnReset"
床被破壞 / 重生點重置時觸發事件（無參數）
例如睡覺用的床被人敲掉

### "breath"
氧氣量有變動時觸發（無參數）
要讀新值請看 `bot.oxygenLevel`

### "experience"
經驗值有變動時觸發（無參數）
要讀新值請看 `bot.experience`

### "forcedMove"
被伺服器強制傳送時觸發事件（無參數）
（例如teleport、`/tp` 指令等）
重要：此事件觸發後，機器人的當前位置會跟路徑規劃的預期不符，常需重新規劃路線

### "mount"
機器人騎上載具時觸發事件（無參數）
（例如馬、船、礦車等）
可讀 `bot.vehicle` 看載具

### "dismount"
機器人下載具時觸發事件

Args:
    vehicle: 剛離開的載具 `Entity`

### "sleep"
機器人自己進入睡眠狀態時觸發事件（無參數）

### "wake"
機器人自己醒來時觸發事件（無參數）

### "physicsTick"
每個物理 tick（~20Hz）觸發一次（無參數）
**這是高頻事件**，每 tick 都可能觸發，請勿在此做耗時工作

### "physicTick"
`"physicsTick"` 的舊別名（無參數）
新程式碼請用 `"physicsTick"`；保留只是為了相容老插件

### "windowOpen"
物品欄之外的視窗被打開時觸發事件
（例如箱子、熔爐、鐵砧、交易面板等）

Args:
    window: 剛開啟的 `Window`

### "windowClose"
視窗關閉時觸發事件

Args:
    window: 剛關閉的 `Window`

### "heldItemChanged"
手上主手拿的物品變動時觸發事件

Args:
    heldItem: 新手持的 `Item`，若變為空手則為 `None`

### "particle"
伺服器在世界中生成粒子效果時觸發事件
（例如爆炸、煙霧、藥水光芒）

Args:
    particle: `Particle` 物件，含位置、類型等資訊

### "soundEffectHeard"
可識別的音效事件觸發時觸發事件

Args:
    soundName: 音效名稱字串（例如 `"entity.creeper.primed"`）
    position: 音效發生位置 `Vec3`
    volume: 音量（浮點數）
    pitch: 音高（浮點數）

### "hardcodedSoundEffectHeard"
舊版硬編碼音效觸發時觸發事件
多數情境下用 `"soundEffectHeard"` 就夠了

Args:
    soundId: 音效的數字 ID
    soundCategory: 類別 ID
    position: 位置 `Vec3`
    volume: 音量
    pitch: 音高

### "noteHeard"
音符盒被擊發時觸發事件

Args:
    block: 音符盒 `Block`
    instrument: 演奏的樂器（含 `id` 與 `name` 如 `"harp"`、`"bassDrum"`）
    pitch: 音高 `0` ~ `24`

### "pistonMove"
任何活塞推/拉動作發生時觸發事件

Args:
    block: 活塞方塊
    isPulling: `1` 為拉、`0` 為推
    direction: 方向編號 `0` ~ `5`（下、上、北、南、西、東）

### "chestLidMove"
任何箱子被打開或關上時觸發事件
（例如動畫狀態變化時）

Args:
    block: 箱子方塊
    isOpen: `1` 為開啟動畫、`0` 為關閉動畫
    block2: 若為雙箱，另一半的方塊；單箱為 `None`

### "blockBreakProgressObserved"
看見附近有人在挖方塊時觸發（不是自己挖的）

Args:
    block: 正在被挖的 `Block`
    destroyStage: 破壞進度 `0` ~ `9`；`9` 時接近挖斷

### "blockBreakProgressEnd"
挖掘動作結束時觸發（可能挖斷，也可能中途放棄）

Args:
    block: 對應的 `Block`

### "blockUpdate"
**任何**方塊變動時觸發事件
**這是高頻事件**，每 tick 都可能觸發，請勿在此做耗時工作

Args:
    oldBlock: 變更前的 `Block`（可能為 `None`，如果原本是載入邊界）
    newBlock: 變更後的 `Block`

### "blockUpdate:(x, y, z)"
特定座標的方塊發生變化時觸發事件
事件名裡的 `(x, y, z)` 要換成實際整數，例如 `"blockUpdate:(100,64,200)"`

Args:
    oldBlock: 變更前 `Block`，可能為 `None`
    newBlock: 變更後 `Block`，可能為 `None`

### "chunkColumnLoad"
區塊柱載入到機器人視野時觸發事件

Args:
    position: 區塊柱的角落座標 `Vec3`（只有 x、z 有意義）

### "chunkColumnUnload"
區塊柱卸載時觸發事件

Args:
    position: 區塊柱角落座標

### "entitySpawn"
視野中有新實體出現時觸發事件
若是玩家實體會另外觸發 `"playerJoined"`

Args:
    entity: 新出現的 `Entity`

### "entityGone"
實體離開視野或被移除時觸發事件

Args:
    entity: 消失的 `Entity`（讀取它的資料仍可，但不再更新）

### "entityMoved"
實體位置有變動時觸發事件
**這是高頻事件**，每 tick 都可能觸發，請勿在此做耗時工作

Args:
    entity: 移動中的 `Entity`

### "entityUpdate"
實體的 metadata（旁枝屬性，如染色、坐騎狀態等）變動時觸發事件

Args:
    entity: 被更新的 `Entity`

### "entityAttributes"
實體的屬性表變動時觸發事件
（移動速度、最大血量等）

Args:
    entity: 被更新的 `Entity`

### "entityHurt"
實體受傷時觸發事件

Args:
    entity: 受傷的 `Entity`
    source: 傷害來源 `Entity`（可能是攻擊者或 `None`）

### "entityDead"
實體死亡時觸發事件

Args:
    entity: 死亡的 `Entity`

### "entitySwingArm"
實體揮手時觸發事件
（近戰攻擊、採集動作）

Args:
    entity: 揮手的 `Entity`

### "entityCrouch"
實體開始蹲下時觸發事件
（按下 shift）

Args:
    entity: 潛行中的 `Entity`

### "entityUncrouch"
實體結束蹲下時觸發事件

Args:
    entity: 對應 `Entity`

### "entitySleep"
實體上床睡覺時觸發事件

Args:
    entity: 上床的 `Entity`

### "entityWake"
實體從床上醒來時觸發事件

Args:
    entity: 對應 `Entity`

### "entityEat"
實體在吃東西時觸發事件
伺服器每次送出吃東西動畫封包（`packet.animation` = 3）時觸發一次

Args:
    entity: 吃東西的 `Entity`

### "entityEquip"
實體換裝備或更換手持物品時觸發事件

Args:
    entity: 對應 `Entity`

### "entityCriticalEffect"
實體被打出暴擊時觸發事件
（有爆擊粒子效果）

Args:
    entity: 對應 `Entity`

### "entityMagicCriticalEffect"
附魔武器的特殊效果觸發時

Args:
    entity: 對應 `Entity`

### "entityEffect"
實體被套上狀態效果時觸發事件

Args:
    entity: 對應 `Entity`
    effect: `Effect` 物件（含 `id`、`amplifier`、`duration`）

### "entityEffectEnd"
實體身上的狀態效果消失時觸發事件

Args:
    entity: 對應 `Entity`
    effect: 剛結束的 `Effect`

### "entityAttach"
實體掛上載具時觸發事件
（騎上馬、船等）

Args:
    entity: 乘員 `Entity`
    vehicle: 載具 `Entity`

### "entityDetach"
實體離開載具時觸發事件

Args:
    entity: 乘員
    vehicle: 載具

### "entityTaming"
玩家正在嘗試馴服動物時觸發事件
（例如餵骨頭給狼）

Args:
    entity: 被馴服中的 `Entity`

### "entityTamed"
動物成功被馴服時觸發事件

Args:
    entity: 被馴服的 `Entity`

### "entityShakingOffWater"
動物抖水時觸發事件

Args:
    entity: 抖水的 `Entity`

### "entityEatingGrass"
羊在吃草時觸發事件

Args:
    entity: 吃草的 `Entity`

### "entityHandSwap"
實體左右手物品互換時觸發事件

Args:
    entity: 對應 `Entity`

### "entityElytraFlew"
實體張開鞘翅飛行時觸發事件

Args:
    entity: 飛行中的 `Entity`

### "usedFirework"
玩家使用煙火時觸發事件
（通常用於鞘翅推進）

Args:
    fireworkEntityId: 煙火實體的數字 ID

### "itemDrop"
實體丟出物品時觸發事件
（例如死亡時掉落）

Args:
    entity: 被掉出的物品 `Entity`

### "playerCollect"
玩家撿起掉落物或其他實體時觸發事件

Args:
    collector: 撿拾的 `Entity`（通常是玩家）
    collected: 被撿拾的 `Entity`

### "playerUpdated"
玩家資訊更新時觸發事件
**這是高頻事件**，每 tick 都可能觸發，請勿在此做耗時工作
（延遲、顯示名稱、遊戲模式等）

Args:
    player: 被更新的 `Player`

### "scoreboardCreated"
有新記分板被建立時觸發事件

Args:
    scoreboard: 剛建立的 `ScoreBoard`

### "scoreboardDeleted"
記分板被刪除時觸發事件

Args:
    scoreboard: 被刪除的 `ScoreBoard`

### "scoreboardTitleChanged"
記分板標題變動時觸發事件

Args:
    scoreboard: 對應 `ScoreBoard`

### "scoreUpdated"
記分板裡某個項目的分數被更新時觸發事件

Args:
    scoreboard: 對應 `ScoreBoard`
    item: 被更新的條目編號

### "scoreRemoved"
記分板裡某條目被移除時觸發事件

Args:
    scoreboard: 對應 `ScoreBoard`
    item: 被移除的條目編號

### "scoreboardPosition"
記分板顯示位置被切換時觸發事件
（側邊欄、玩家名下方等）

Args:
    position: 新的顯示位置（`DisplaySlot`）
    scoreboard: 對應 `ScoreBoard`

### "teamCreated"
有隊伍被建立時觸發事件

Args:
    team: 新的 `Team`

### "teamRemoved"
隊伍被移除時觸發事件

Args:
    team: 被移除的 `Team`

### "teamUpdated"
隊伍資訊變動時觸發事件
（顏色、前綴等）

Args:
    team: 被更新的 `Team`

### "teamMemberAdded"
有玩家被加進隊伍時觸發事件

Args:
    team: 隊伍 `Team`（新成員列表可從 `team.members` 讀）

### "teamMemberRemoved"
玩家被踢出隊伍時觸發事件

Args:
    team: 對應 `Team`

### "bossBarCreated"
伺服器推送新的 Boss 血條時觸發事件

Args:
    bossBar: 新的 `BossBar`

### "bossBarDeleted"
Boss 血條被移除時觸發事件

Args:
    bossBar: 被移除的 `BossBar`

### "bossBarUpdated"
Boss 血條（血量、標題、顏色等）有變動時觸發事件

Args:
    bossBar: 對應 `BossBar`

### "resourcePack"
伺服器要求客戶端下載資源包時觸發事件
**注意**：mineflayer 三個呼叫點傳入的參數順序不一致（`resource_pack.js:23/43/46`），收到的資料語意會隨觸發路徑不同
需要使用此事件時，請對照 JS 原始碼判斷當下情境

Args:
    url: 資源包網址（通常是，但不保證）
    hash: SHA-1 雜湊值或 uuid，**順序視路徑而定**
    uuid: 套件 UUID，**順序視路徑而定**

---

## 方法（methods）

### bot.chat(message)
在公開聊天中發送一則訊息

Args:
    message: 要送出的內容字串；以 `/` 開頭會被當作指令送出。單則訊息超過伺服器長度限制時，會自動切成多則送出

```python
bot.chat("大家好")
bot.chat("/time set day")  # 以斜線開頭會被當作指令
```

### bot.whisper(username, message)
對指定玩家傳送私聊訊息
（相當於 `/tell`、`/msg`）

Args:
    username: 目標玩家的遊戲名稱
    message: 訊息內容

### bot.quit(reason)
主動斷線離開伺服器
會觸發 `"end"` 事件，並讓 `bot.run_forever()` 返回

Args:
    reason: 斷線原因字串（顯示在自己的 log 中）；可以省略，預設為 `"disconnect.quitting"`

### bot.lookAt(point, force)
讓機器人轉頭看向世界座標中的某個點

Args:
    point: 目標 `Vec3`（世界絕對座標）。看玩家臉的話常傳 `target.position.offset(0, target.height, 0)`
    force: 是否強制瞬間轉向；預設 `False` 會以物理角速度平滑轉動，設 `True` 立即到位（比較適合自動化場景）

### bot.setControlState(control, state)
按下或放開一個移動鍵，效果會**一直持續**直到下次設定變更
搭配事件使用，在想停下的時機再把狀態設回 `False`

Args:
    control: `"forward"` / `"back"` / `"left"` / `"right"` / `"jump"` / `"sprint"` / `"sneak"` 其中之一
    state: `True` 按下、`False` 放開

範例：進入世界後一直往前走，收到 `"stop"` 訊息才停下

```python
@bot.on_spawn
def on_spawn():
    bot.setControlState("forward", True)

@bot.on_chat
def on_chat(username, message, *_):
    if message == "stop":
        bot.setControlState("forward", False)
```

### bot.clearControlStates()
一次放開所有移動鍵，回到靜止狀態
出事時「全部停下」的緊急按鈕

### bot.dig(block, forceLook, digFace)
對指定方塊進行挖掘
完成或失敗會透過 `"diggingCompleted"` / `"diggingAborted"` 事件回報
**handler 內呼叫會阻塞**當下的 callback thread，建議在主執行流程呼叫

Args:
    block: 目標 `Block` 物件（用 `bot.blockAt(pos)` 或 `bot.findBlock(...)` 取得）
    forceLook: `True` / `False` / `"ignore"`；`"ignore"` 代表完全不轉頭，直接挖（通常是呼叫者已自己對準過）
    digFace: `"auto"`（預設）、`"raycast"`，或傳一個 `Vec3` 指定從哪個方向打。多數情況留預設即可

### bot.placeBlock(referenceBlock, faceVector)
對著 `referenceBlock` 的某一面放下一個方塊
（放的是目前手上的物品）

Args:
    referenceBlock: 當作「貼著」的現存方塊
    faceVector: 單位向量，指出要貼在哪一面（例如 `Vec3(0, 1, 0)` 是貼在上表面）

### bot.blockAt(point, extraInfos)
查詢世界中某個座標的方塊

Args:
    point: 要查的 `Vec3`（整數座標）
    extraInfos: 預設 `True`，會多解析一些屬性（招牌文字、箱子內容等 metadata）；設 `False` 可以省一點效能

Returns:
    `Block` 或 `None`（該區塊尚未載入時）

### bot.findBlock(options)
從附近尋找一個符合條件的方塊

Args:
    options: 字典，至少需要 `matching`：
        - `matching`：方塊 ID 整數、ID 整數的陣列、或接受 `Block` 回傳布林的函式
        - `maxDistance`：(選填) 搜尋半徑，預設 16
        - `count`：(選填) 傳給 `findBlocks` 用，`findBlock` 通常不用設
        - `point`：(選填) 搜尋中心座標，預設為機器人當前位置

Returns:
    第一個找到的 `Block`，沒找到回 `None`

```python
diamond = bot.findBlock({"matching": 56, "maxDistance": 32})
if diamond is not None:
    print("找到鑽石礦在", diamond.position)
```

### bot.canSeeBlock(block)
檢查機器人目前是否能「看到」某方塊

Args:
    block: 要檢查的 `Block`

Returns:
    布林

### bot.attack(entity)
對指定實體進行一次近戰攻擊

Args:
    entity: 目標 `Entity`

### bot.activateItem(offhand)
使用目前手上的物品（相當於按右鍵）——吃東西、拉弓、擋盾、喝藥水都用這個
要「停下」請呼叫 `bot.deactivateItem()`

Args:
    offhand: `True` 使用副手物品；預設 `False` 用主手

### bot.deactivateItem()
停止「持續使用」的物品動作
（停止拉弓、放下盾等等）

### bot.equip(item, destination)
把某個物品裝備到指定裝備槽

Args:
    item: 要裝備的 `Item`，或它的數字 ID
    destination: `"hand"` / `"head"` / `"torso"` / `"legs"` / `"feet"` / `"off-hand"`；傳 `None` 代表用預設對應

### bot.toss(itemType, metadata, count)
丟出指定數量的物品

Args:
    itemType: 物品 ID 整數
    metadata: 物品的 metadata 值，不關心就傳 `None`
    count: 要丟的數量

### bot.sleep(bedBlock)
讓機器人躺上床睡覺
**只在夜晚或雷雨時有效**，白天呼叫會出錯

Args:
    bedBlock: 目標床（`Block`）

### bot.wake()
從床上起床
一般白天會自動醒，這個方法是強制提前起

### bot.load_plugin(name, version, export_key, **options)
一鍵載入一個 Type A 的 mineflayer 插件（例如 `mineflayer-pathfinder`）

Args:
    name: npm 套件名稱
    version: 要釘住的版本字串。對 minethon 內建預裝的 plugin（目前是 `mineflayer-pathfinder`）可省略，其餘套件必須顯式填寫
    export_key: 該套件的 installer 函式掛在 module 的哪個屬性上。pathfinder 已內建對照，其他套件不相符時可傳這個覆寫
    **options: 會轉傳給「HOF 風格」的插件（例如 `@ssmidge/mineflayer-dashboard`）。普通插件會忽略

Returns:
    該插件的原生 JS module，方便取用它匯出的 class / 常數

### bot.require(name, version)
原始逃生口——載入任意 JS 套件並回傳原生 proxy
用在 Type B / C / D 插件（prismarine-viewer、web-inventory、statemachine 等）需要自行初始化時

Args:
    name: npm 套件名稱
    version: 要釘住的版本字串。非內建預裝套件必填，避免 JSPyBridge 在 runtime 偷裝 latest

Returns:
    的物件未做型別包裝，請對照該插件 README 操作

### bot.run_forever()
阻塞呼叫它的執行緒，直到機器人斷線（`"end"` 事件觸發）
學生腳本最後通常加這一行讓 script 不會提早結束
按 Ctrl-C 會乾淨退出

### bot.bind(handlers)
Class-based handler 註冊入口——一次把 `BotHandlers` 子類別上所有被 override 的 `on_<event>` 方法，依對應事件掛到底層 JS EventEmitter 上

會略過沒有被子類別覆寫的方法（繼承自 base 的 no-op 不會被註冊），所以學生只需要覆寫自己關心的事件

handler 參數個數不需要跟 d.ts 一模一樣——minethon 的 `_normalize_handler` 會自動補 `None` / 截斷

```python
from minethon import BotHandlers, create_bot


class My(BotHandlers):
    def on_chat(self, username, message, *_):
        print(username, message)


bot = create_bot(host="localhost", username="Student")
bot.bind(My())
bot.run_forever()
```

Args:
    handlers: `BotHandlers` 的實例；會走訪它的類別並把每個 override 過的 `on_<event>` 綁到對應事件

Returns:
    傳入的 `handlers` 實例，方便 fluent chain

### bot.on(event)
註冊事件處理器的 decorator
會自動把回呼函式裝到 mineflayer 的 JS EventEmitter 上
各事件的回呼參數數量由 `bot.pyi` 的 Literal overload 決定；IDE 會跳出完整清單

手寫 handler 時**參數個數不符也沒關係**——minethon 的 `_normalize_handler` 會自動補 `None` / 截斷，不會噴 TypeError

```python
from minethon import BotEvent

@bot.on(BotEvent.CHAT)
def on_chat(username, message, *_):
    print(username, message)
```

Args:
    event: `BotEvent` 成員，例如 `BotEvent.CHAT`

### bot.once(event)
同 `bot.on(event)` 但只觸發一次，之後自動解除

Args:
    event: `BotEvent` 成員，例如 `BotEvent.CHAT`

### create_bot(**options)
建立並啟動一個 mineflayer 機器人
常用選項以 `snake_case` 傳入，內部會自動轉成 `camelCase` 給 JS 端

常用選項：

Args:
    host: Minecraft 伺服器網址或 IP
    port: 連線 port（預設 `25565`）
    username: 機器人的遊戲名稱
    password: 正版帳號密碼（Mojang / Drasl 等自訂 auth 時用）
    version: 強制協議版本字串，例如 `"1.20.4"`；省略會自動偵測
    auth: 驗證方式：`"mojang"` / `"microsoft"` / `"offline"`
    auth_server: 自訂 auth 伺服器網址（Drasl / Yggdrasil-compatible）
    session_server: 自訂 session 伺服器網址
        - 其他 `mineflayer.createBot()` 接受的選項都能直接傳

回傳 `Bot`。連線是非同步進行的；請監聽 `"spawn"` 事件之後再動手操作世界

```python
bot = create_bot(
    host="play.camp.tw",
    username="alice",
    auth="mojang",
    auth_server="https://drasl.example.com/auth",
    session_server="https://drasl.example.com/session",
)
```

### bot.connect(options)
對已建立但尚未連線的 bot 做一次 reconnect
一般腳本用不到——`create_bot(...)` 已自動連線

Args:
    options: `BotOptions` dict

### bot.end(reason)
主動關掉連線
`bot.quit(...)` 是把協定層的 quit 送出再關；`bot.end(...)` 比較直接，伺服器可能看不到離線原因
除非明白兩者差異，建議優先用 `bot.quit(...)`

Args:
    reason: (選填) 原因字串

### bot.supportFeature(feature)
查詢當前連線的協定版本是否支援某個功能字串
用於跨版本相容邏輯

Args:
    feature: 功能名稱字串（對應 `minecraft-data` 的 feature 列表）
        - 回傳 `True` / `False`

### bot.blockInSight(maxSteps, vectorLength)
沿機器人視線往前逐步推進，回傳第一個碰到的方塊；超過範圍或沒碰到就回 `None`

Args:
    maxSteps: 最多走幾步取樣
    vectorLength: 每一步的向量長度

### bot.blockAtCursor(maxDistance, matcher)
從機器人的視線方向投射，回傳視線末端所指的方塊
`bot.blockInSight(...)` 的高階版本

Args:
    maxDistance: 最遠測距（預設 `256`）
    matcher: 自訂篩選函式，接受 `Block` 回傳布林；預設收下所有方塊

### bot.blockAtEntityCursor(entity, maxDistance, matcher)
跟 `blockAtCursor` 類似，但從指定實體的視線出發
常用來偵測別人正在看的方塊

Args:
    entity: 觀察者 `Entity`，預設是機器人自己
    maxDistance: 最遠測距
    matcher: 篩選函式

### bot.findBlocks(options)
跟 `bot.findBlock` 同樣的參數結構，但會回傳**所有**符合的方塊 `Vec3` 座標的列表

Args:
    options: 見 `bot.findBlock`；多加一個 `count` 限制回傳數量（預設 `1`）

### bot.canDigBlock(block)
檢查當前手上的工具能不能挖動該方塊

Args:
    block: 要檢查的 `Block`

Returns:
    布林

### bot.recipesFor(itemType, metadata, minResultCount, craftingTable)
查詢目前物品欄能合成指定物品的配方列表

Args:
    itemType: 目標物品 ID 整數
    metadata: 目標的 metadata；不關心傳 `None`
    minResultCount: 最少要產出幾個才列入結果
    craftingTable: 傳 `Block` 代表用該工作台；`True` 代表允許 3x3 配方；`False` / `None` 代表只找玩家 2x2

### bot.recipesAll(itemType, metadata, craftingTable)
同 `recipesFor`，但回傳**所有**可能的配方

### bot.quit(reason)
送出協定層的斷線封包再關閉連線，`"end"` 事件會隨後觸發
對伺服器比較友善

Args:
    reason: 顯示在機器人自己 log 的字串；可省略

### bot.tabComplete(str, assumeCommand, sendBlockInSight, timeout)
請伺服器回傳聊天框 Tab 自動補全結果

Args:
    str: 要補全的開頭字串
    assumeCommand: 是否當作指令補全（斜線後面的字串）
    sendBlockInSight: 是否附帶視線所指方塊（伺服器上下文提示用）
    timeout: 等待伺服器回覆的毫秒數

### bot.chatAddPattern(pattern, chatType, description)
新增一個 chat pattern，符合 pattern 的聊天訊息會以 `chatType` 指定的事件名觸
**已停用**，請改用 `addChatPattern(name, pattern, options)`

### bot.addChatPattern(name, pattern, options)
註冊一個 chat pattern，讓特定格式的聊天訊息觸發自訂事件

Args:
    name: 事件名稱（會觸發 `f"chat:{name}"` 事件）
    pattern: 正則表達式物件（使用 JavaScript 的 `RegExp`）
    options: (選填) `{repeat: bool, parse: bool}`。`parse=True` 時會把 regex 捕獲組傳進事件；`repeat=True` 表示事件可多次觸發事件

### bot.addChatPatternSet(name, patterns, options)
同 `addChatPattern`，但傳入多個 pattern 當一組（全部順序比中才觸發）
適合跨行訊息

### bot.removeChatPattern(name)
移除之前註冊的 chat pattern

Args:
    name: pattern 名稱，或 `addChatPattern` 回傳的整數 ID

### bot.awaitMessage(*patterns)
阻塞等待第一則符合任一 pattern 的聊天訊息

Args:
    *patterns: 一到多個字串或 `RegExp`

Returns:
    符合的字串

### bot.setSettings(options)
更新 `bot.settings`

Args:
    options: `GameSettings` 的部分欄位 dict

### bot.loadPlugin(plugin)
`bot.load_plugin(...)` 的原生版本：直接接收 mineflayer 風格的 `(bot, options) => void` 函式
**學生請改用 `bot.load_plugin(name)`**，這個是給進階使用者／minethon 內部用的

Args:
    plugin: 插件 installer 函式

### bot.loadPlugins(plugins)
`bot.load_plugin(...)` 的原生版本：直接接收 mineflayer 風格的 `(bot, options) => void` 函式
**學生請改用 `bot.load_plugin(name)`**，這個是給進階使用者／minethon 內部用的

Args:
    plugins: 插件 installer 函式的陣列

### bot.hasPlugin(plugin)
查詢某個 installer 函式是否已載入

Returns:
    布林

### bot.isABed(bedBlock)
判斷指定方塊是不是床

Args:
    bedBlock: 要檢查的 `Block`
        - 回傳布林

### bot.elytraFly()
張開鞘翅開始滑翔
要已站在空中且穿著鞘翅

### bot.getControlState(control)
讀取當前某個移動按鍵的按住狀態

Args:
    control: 同 `setControlState` 的按鍵名

Returns:
    布林

### bot.getExplosionDamages(targetEntity, position, radius, rawDamages)
計算如果在 `position` 發生爆炸，指定實體會吃到多少傷害

Args:
    targetEntity: 受害 `Entity`
    position: 爆炸中心 `Vec3`
    radius: 爆炸半徑
    rawDamages: `True` 回傳原始傷害；`False`（預設）回傳考慮護甲後的實際傷害

Returns:
    浮點數或 `None`

### bot.look(yaw, pitch, force)
直接設定機器人的視角角度

Args:
    yaw: 水平角度
    pitch: 俯仰角度
    force: `True` 瞬間到位；`False`（預設）平滑轉動

### bot.updateSign(block, text, back)
改寫一個招牌的文字內容

Args:
    block: 招牌 `Block`
    text: 新文字（可用 `\n` 分行）
    back: `True` 寫到背面（1.20+）；預設寫正面

### bot.unequip(destination)
卸下指定裝備槽的裝備

Args:
    destination: `"hand"` / `"head"` / `"torso"` / `"legs"` / `"feet"` / `"off-hand"`，或 `None` 用預設

### bot.tossStack(item)
整疊丟出某個物品

Args:
    item: 物品欄中的 `Item`

### bot.stopDigging()
停止當前挖掘動作
會觸發 `"diggingAborted"` 事件

### bot.digTime(block)
估算挖完指定方塊需要的毫秒數

Args:
    block: 目標 `Block`
        - 回傳毫秒整數

### bot.placeEntity(referenceBlock, faceVector)
同 `placeBlock`，但放置的是實體（例如終界箱蓋、盔甲架、船），回傳放出的 `Entity`

### bot.activateBlock(block, direction, cursorPos)
對方塊「使用」（右鍵點擊），例如拉桿、按鈕、打開門

Args:
    block: 目標 `Block`
    direction: 點擊的面向量；省略會自動判斷
    cursorPos: 精細的點擊位置；一般省略即可

### bot.activateEntity(entity)
對實體「使用」（右鍵）——例如騎馬、交易、上色羊

Args:
    entity: 目標 `Entity`

### bot.activateEntityAt(entity, position)
同 `activateEntity`，但指定精細的點擊位置

Args:
    entity: 目標 `Entity`
    position: 點擊座標 `Vec3`

### bot.consume()
吃掉當前手持的食物或喝掉藥水
等同於長按右鍵直到完成

### bot.fish()
執行釣魚動作：在手持釣竿時拋出、等魚上鉤、收竿
整個流程用一次呼叫完成，過程中若要中斷請呼叫 `bot.activateItem()` 收竿或直接換槽

### bot.useOn(targetEntity)
對實體使用手上物品

Args:
    targetEntity: 目標 `Entity`

### bot.swingArm(hand, showHand)
播放揮手動畫

Args:
    hand: `"left"` / `"right"` 或省略（預設主手）
    showHand: `True` 實際播動畫；`False` 靜默

### bot.mount(entity)
騎上指定載具

Args:
    entity: 載具 `Entity`（馬、船、礦車等）

### bot.dismount()
下目前所騎載具

### bot.moveVehicle(left, forward)
控制目前所騎載具的移動

Args:
    left: 左右方向（`-1` ~ `1`）
    forward: 前後方向（`-1` ~ `1`）

### bot.setQuickBarSlot(slot)
切換快捷欄槽位

Args:
    slot: `0` 到 `8` 的整數

### bot.craft(recipe, count, craftingTable)
用指定配方合成物品
要有對應材料

Args:
    recipe: 從 `bot.recipesFor(...)` 取得的 `Recipe`
    count: 要合成幾次（每次產出 recipe 定義的量），省略為 1
    craftingTable: 若是 3x3 配方，指定要使用的工作台 `Block`

### bot.writeBook(slot, pages)
把一本「未寫字的書」（write book）寫滿內容

Args:
    slot: 物品欄中空白書所在的槽位整數
    pages: 每一頁的文字字串陣列

### bot.openContainer(chest, direction, cursorPos)
打開任意容器方塊或實體

Args:
    chest: 目標 `Block` 或 `Entity`
    direction: 點擊的面；通常不需指定
    cursorPos: 精細點擊座標

### bot.openChest(chest, direction, cursorPos)
打開箱子，回傳 `Chest` 物件

### bot.openFurnace(furnace)
打開熔爐，回傳 `Furnace`

### bot.openDispenser(dispenser)
打開發射器或投擲器，回傳 `Dispenser`

### bot.openEnchantmentTable(enchantmentTable)
打開附魔台，回傳 `EnchantmentTable`

### bot.openAnvil(anvil)
打開鐵砧，回傳 `Anvil`

### bot.openVillager(villager)
與村民互動打開交易面板，回傳 `Villager`

Args:
    villager: 村民 `Entity`

### bot.trade(villagerInstance, tradeIndex, times)
跟村民完成一筆交易

Args:
    villagerInstance: `bot.openVillager` 回傳的 `Villager`
    tradeIndex: 交易列表中的第幾筆（0-based，可用字串名稱或整數）
    times: 要交易幾次，省略為 1

### bot.setCommandBlock(pos, command, options)
修改指令方塊內容

Args:
    pos: 指令方塊座標 `Vec3`
    command: 要寫入的指令字串（不需要開頭 `/`）
    options: `{mode, trackOutput, conditional, alwaysActive}` 設定字典

### bot.clickWindow(slot, mouseButton, mode)
低階視窗點擊——直接模擬滑鼠事件
一般請用更高階的 `bot.equip` / `bot.toss` 等

Args:
    slot: 槽位整數
    mouseButton: `0` 左鍵、`1` 右鍵
    mode: 點擊模式 `0` ~ `6`（協定層定義）

### bot.putSelectedItemRange(start, end, window, slot)
把當前游標上的物品塞進某視窗指定槽位範圍

### bot.putAway(slot)
把視窗裡 `slot` 的物品收回到物品欄

### bot.closeWindow(window)
關掉指定視窗

Args:
    window: 由 `openX` 方法取得的 `Window`

### bot.transfer(options)
在視窗內移動物品

Args:
    options: 含 `window`、`itemType`、`metadata`、`count`、`sourceStart` / `sourceEnd`、`destStart` / `destEnd` 的 dict

### bot.openBlock(block, direction, cursorPos)
開啟任意有視窗的方塊；實際回傳型別依方塊而定

### bot.openEntity(block, Class)
使用指定 Class 構造視窗，用在自訂實體或非標準 Interactive Entity
進階用法

### bot.moveSlotItem(sourceSlot, destSlot)
在物品欄裡把某槽物品移到另一槽

### bot.updateHeldItem()
立即將「目前快捷欄選中」的變更同步到伺服器
多數情況不用手動呼叫

### bot.getEquipmentDestSlot(destination)
查詢裝備類型對應的槽位編號

Args:
    destination: `"hand"` / `"head"` / `"torso"` / `"legs"` / `"feet"` / `"off-hand"`
        - 回傳整數槽位

### bot.waitForChunksToLoad()
阻塞等周遭的區塊全部載入完成再繼續
`spawn` 事件後呼叫可確保 `bot.blockAt` 之類都有結果

### bot.entityAtCursor(maxDistance)
從機器人視線方向投射，回傳第一個碰到的實體
沒找到則回傳 `None`

Args:
    maxDistance: 最遠測距，預設 `3`

### bot.nearestEntity(filter)
找出最近的一個實體，可自訂篩選函式
沒找到則回傳 `None`

Args:
    filter: (選填) 接受 `Entity` 回傳布林的函式

### bot.waitForTicks(ticks)
等指定 tick 數（每 tick 約 50ms）
阻塞式：會卡住呼叫它的執行緒，**handler 內不要用**

Args:
    ticks: 要等的 tick 數整數

### bot.acceptResourcePack()
同意伺服器的資源包請求

### bot.denyResourcePack()
拒絕伺服器的資源包請求

### bot.respawn()
死後手動重生


---

## 屬性（properties）

### bot.username
機器人登入伺服器用的遊戲名稱
登入前可能還是 `None`

### bot.health
機器人目前血量，範圍 `[0, 20]`，每 1 代表半顆心

### bot.food
機器人目前飽食度，範圍 `[0, 20]`，每 1 代表半支雞腿

### bot.foodSaturation
飽食度的「隱藏緩衝」
飽食度緩衝 > 0 時，`bot.food` 不會下降；吃東西同時會增加 `food` 和 `foodSaturation`

### bot.oxygenLevel
氧氣量，範圍 `[0, 20]`
水中會持續扣減，歸零後開始扣血

### bot.experience.level
經驗等級

### bot.experience.points
總經驗點數

### bot.entity
機器人自身的 `Entity` 物件
常用欄位：`position` / `velocity` / `yaw` / `pitch` / `onGround` / `height` 等

### bot.players
所有連線玩家的對應表，key 是玩家名稱、value 是 `Player`
支援 `bot.players["alice"]` 查找，也支援 `for name in bot.players:` 迭代取得全部名稱

```python
for name in bot.players:
    print(name, "延遲", bot.players[name].ping, "ms")
```

### bot.entities
所有機器人可見實體的對應表，key 是實體數字 ID、value 是 `Entity`
含玩家、怪物、掉落物、箭、船等

### bot.isRaining
當前世界是否在下雨

### bot.time.timeOfDay
一天中的時間（tick），範圍 `[0, 24000)`
`0` = 日出、`6000` = 正午、`12000` = 日落、`18000` = 午夜

### bot.time.day
遊戲世界目前是第幾天

### bot.inventory
機器人的物品欄 `Window` 物件
用 `bot.inventory.items()` 取所有物品、`bot.inventory.findInventoryItem(...)` 搜尋特定物品

### bot.heldItem
機器人目前手上拿的物品 `Item`，空手時為 `None`

### bot.quickBarSlot
快捷欄目前選取的槽位

### bot.game.gameMode
目前遊戲模式：`"survival"` / `"creative"` / `"adventure"` / `"spectator"`

### bot.game.dimension
目前所在維度：`"overworld"` / `"the_nether"` / `"the_end"`

### bot.game.hardcore
伺服器是否為極限模式

### bot.game.difficulty
難度字串：`"peaceful"` / `"easy"` / `"normal"` / `"hard"`

### bot.game.maxPlayers
伺服器人數上限

### bot.game.levelType
世界類型字串

### bot.game.serverBrand
伺服器回報的 brand 字串

### bot.version
伺服器協議對應的 Minecraft 版本字串

### bot.protocolVersion
伺服器協議版本數字；跨版本邏輯用的

### bot.majorVersion
大版本字串

### bot.player
機器人自己的 `Player` 物件（名單上的那一筆，含 `ping`、顯示名稱等），等同 `bot.players[bot.username]`

### bot.spawnPoint
世界出生點 `Vec3` 座標

### bot.thunderState
目前雷雨強度（`0` ~ `1` 浮點）
搭配 `bot.isRaining` 判斷天氣

### bot.isSleeping
機器人目前是否躺在床上

### bot.fireworkRocketDuration
機器人使用煙火飛行時剩餘推進的 tick 數

### bot.physicsEnabled
是否啟用物理模擬（布林）
關掉後機器人不會自動落地、移動等，完全靠指令控制

### bot.targetDigBlock
目前正在挖的方塊 `Block`，沒有在挖時為 `None`

### bot.usingHeldItem
機器人目前是否正在「使用」（長按右鍵）手上的物品

### bot.currentWindow
目前開啟的視窗（若有）
沒開任何視窗時為 `None`

### bot.experience.progress
當前等級的經驗進度，範圍 `[0, 1]`

### bot.time.time
自世界第 0 天起的總 tick 數

### bot.time.bigTime
自世界第 0 天起的總 tick 數

### bot.time.isDay
是否為白天

### bot.time.day
當前是第幾天

### bot.time.age
世界總運轉時間

### bot.time.bigAge
世界總運轉時間的 `BigInt` 版本

### bot.time.moonPhase
月相編號 `0` ~ `7`

### bot.time.doDaylightCycle
`doDaylightCycle` gamerule 是否開啟

### bot.controlState.forward
`"forward"` 鍵目前是否按住（布林）
其他同名欄位：`.back`、`.left`、`.right`、`.jump`、`.sprint`、`.sneak`
這些值是由 `bot.setControlState(...)` 調整的；純讀參考用

### bot.controlState.back
`"back"` 鍵當前狀態

### bot.controlState.left
`"left"` 鍵當前狀態

### bot.controlState.right
`"right"` 鍵當前狀態

### bot.controlState.jump
`"jump"` 鍵當前狀態

### bot.controlState.sprint
`"sprint"` 鍵當前狀態

### bot.controlState.sneak
`"sneak"` 鍵當前狀態

### bot.settings
遊戲設定物件
含 `chat`（`"enabled"` / `"commandsOnly"` / `"disabled"`）、`colorsEnabled`、`viewDistance`、`difficulty`、`mainHand`、`skinParts` 等欄位

### bot.settings.chat
聊天設定：`"enabled"`（都看）、`"commandsOnly"`（只看指令）、`"disabled"`

### bot.settings.viewDistance
視距：`"far"` / `"normal"` / `"short"` / `"tiny"` 或整數 chunk 數

### bot.settings.mainHand
主手：`"left"` 或 `"right"`

### bot.settings.colorsEnabled
是否顯示聊天顏色碼

### bot.physics
物理參數字典：`gravity`、`terminalVelocity`、`walkingAcceleration`、`jumpSpeed`、`sprintSpeed`、`maxGroundSpeed` 等可調數值
改寫會直接影響機器人運動；**後果自負**

### bot.physics.gravity
重力加速度

### bot.physics.jumpSpeed
跳躍初速度

### bot.physics.maxGroundSpeed
地面最高速度

### bot.physics.sprintSpeed
跑步額外速度倍率

### bot.physics.terminalVelocity
自由落體終端速度

### bot.physics.walkingAcceleration
步行加速度

### bot.scoreboards
所有記分板 `{name: ScoreBoard}` 對應表

### bot.scoreboard
按顯示槽位取得當前顯示的記分板 `{slot: ScoreBoard}`

### bot.teams
所有隊伍 `{name: Team}` 對應表

### bot.teamMap
以玩家名稱或實體名稱對應到所屬 `Team` 的快速查表

### bot.tablist
玩家名單（Tab 鍵那一塊）
含 `header`（`ChatMessage`）與 `footer`

### bot.tablist.header
玩家名單頂端的 `ChatMessage`

### bot.tablist.footer
玩家名單底端的 `ChatMessage`

### bot.registry
mineflayer 持有的 `minecraft-data` registry
用來反查方塊 / 物品 / 生物的 ID 與 metadata

### bot.world
世界資料物件（`prismarine-world` 的 `WorldSync`）
多數情況不直接碰；用 `bot.blockAt` 等高階 API 即可

### bot.creative
創造模式輔助方法集合：`bot.creative.setInventorySlot`、`bot.creative.flyTo`、`bot.creative.startFlying` 等
僅在伺服器給予 creative 權限時可用

### bot.creative.setInventorySlot(slot, item)
創造模式下直接把某個槽位設定成指定物品

Args:
    slot: 槽位編號整數
    item: 要設定的 `Item`，或 `None` 代表清空

### bot.creative.clearSlot(slot)
創造模式下清空指定槽位

Args:
    slot: 槽位編號整數

### bot.creative.clearInventory()
清空整個物品欄

### bot.creative.flyTo(destination)
創造模式下直接飛到指定座標
阻塞直到抵達

Args:
    destination: 目標 `Vec3`

### bot.creative.startFlying()
開始飛行

### bot.creative.stopFlying()
停止飛行

### bot.simpleClick
視窗點擊的簡單包裝
通常只需要 `bot.simpleClick.leftMouse(slot)` 或 `bot.simpleClick.rightMouse(slot)`

### bot.simpleClick.leftMouse(slot)
對指定槽位左鍵點擊一下

Args:
    slot: 槽位整數

### bot.simpleClick.rightMouse(slot)
對指定槽位右鍵點擊一下

Args:
    slot: 槽位整數

### bot.chatPatterns
目前註冊的 chat pattern 列表（含 regex、類型、描述）
偵錯用


---

## 外部類別（vec3 / prismarine-*）

### Vec3
三維向量
Minecraft 的位置、速度、方向都用這個類
支援各種位移、距離、算術運算；**多數「帶 `ed` 結尾」的 method 回傳新物件，不會修改自身**；不帶的多為 in-place 修改

### Vec3.x
X 軸座標

### Vec3.y
Y 軸座標

### Vec3.z
Z 軸座標

### Vec3.offset(dx, dy, dz)
Args:
    dx: 各軸偏移量（浮點數）
    dy: 各軸偏移量（浮點數）
    dz: 各軸偏移量（浮點數）

Returns:
    一個新的 `Vec3`，座標為自身加上 `(dx, dy, dz)`。**不會修改自身**

```python
feet = bot.entity.position
head = feet.offset(0, bot.entity.height, 0)
```

### Vec3.distanceTo(other)
Returns:
    到另一個向量的歐氏距離

### Vec3.equals(other, error)
判斷兩個向量是否「近乎相等」

Args:
    other: 要比較的另一個 `Vec3`
    error: 允許的誤差；省略時要完全相等

### Vec3.plus(other)
Returns:
    新的 `Vec3`，座標是自身加上 `other` 的各軸值

### Vec3.minus(other)
Returns:
    新的 `Vec3`，座標是自身減去 `other`

### Vec3.scaled(scalar)
Returns:
    新的 `Vec3`，各軸座標都乘上 `scalar`

### Vec3.clone()
Returns:
    一個和自身相同座標的新 `Vec3`。避免意外修改共用物件時使用

### Vec3.isZero()
是否為零向量（三軸皆為 `0`）

Returns:
    布林

### Vec3.at(id)
依索引取軸座標：`0` 取 x、`1` 取 y、`2` 取 z

Args:
    id: 索引 `0` / `1` / `2`

### Vec3.xz()
以 `(x, z)` 回傳長度 2 的 tuple

### Vec3.xy()
以 `(x, y)` 回傳長度 2 的 tuple

### Vec3.yz()
以 `(y, z)` 回傳長度 2 的 tuple

### Vec3.xzy()
Returns:
    一個新 `Vec3`，y 與 z 互換（座標變 `(x, z, y)`）

### Vec3.set(x, y, z)
**原地**修改三軸為給定值，回傳自身

Args:
    x: 新的軸座標值
    y: 新的軸座標值
    z: 新的軸座標值

### Vec3.update(other)
**原地**把自己的值複製成 `other` 的值，回傳自身

Args:
    other: 來源 `Vec3`

### Vec3.rounded()
Returns:
    一個新 `Vec3`，各軸四捨五入到整數

### Vec3.round()
**原地**四捨五入各軸，回傳自身

### Vec3.floored()
Returns:
    一個新 `Vec3`，各軸向下取整。用來把浮點位置對齊到所屬方塊座標時常用

### Vec3.floor()
**原地**向下取整，回傳自身

### Vec3.translate(dx, dy, dz)
**原地**位移，回傳自身

Args:
    dx: 各軸位移量
    dy: 各軸位移量
    dz: 各軸位移量

### Vec3.add(other)
**原地**加上另一向量，回傳自身

Args:
    other: `Vec3`

### Vec3.subtract(other)
**原地**減去另一向量

### Vec3.multiply(other)
**原地**各軸相乘

### Vec3.divide(other)
**原地**各軸相除

### Vec3.abs()
Returns:
    一個新 `Vec3`，各軸取絕對值

### Vec3.volume()
Returns:
    `x * y * z` 的體積

### Vec3.modulus(other)
Returns:
    一個新 `Vec3`，對 `other` 取 modulo

### Vec3.distanceSquared(other)
Returns:
    到另一向量的歐氏距離**平方**

### Vec3.toString()
Returns:
    `"(x, y, z)"` 格式的字串

### Vec3.min(other)
Returns:
    新 `Vec3`，各軸取兩者最小值

### Vec3.max(other)
Returns:
    新 `Vec3`，各軸取兩者最大值

### Vec3.norm()
Returns:
    向量長度

### Vec3.dot(other)
Returns:
    與另一向量的點積

### Vec3.cross(other)
Returns:
    與另一向量的外積結果新 `Vec3`

### Vec3.unit()
Returns:
    單位化後的新 `Vec3`（方向相同、長度 1）；零向量會回傳零向量

### Vec3.normalize()
**原地**單位化，回傳自身

### Vec3.scale(scalar)
**原地**把各軸乘上 `scalar`，回傳自身

Args:
    scalar: 純量

### Vec3.xyDistanceTo(other)
只考慮 x、y 軸的距離

### Vec3.xzDistanceTo(other)
只考慮 x、z 軸的距離（忽略 y）
Minecraft 算「水平距離」最常用這個

### Vec3.yzDistanceTo(other)
只考慮 y、z 軸的距離

### Vec3.innerProduct(other)
Returns:
    內積

### Vec3.manhattanDistanceTo(other)
Returns:
    曼哈頓距離

### Vec3.toArray()
Returns:
    `[x, y, z]` 的 tuple

### Entity
世界中任意實體的抽象
玩家、怪物、掉落物、箭、船、末影珍珠等都是 `Entity`

### Entity.id
實體在當前世界中的整數 ID

### Entity.type
實體類別字串：`"player"` / `"mob"` / `"object"` / `"global"` / `"orb"` / `"projectile"` / `"hostile"` / `"other"`
用來快速判斷要如何對待它

### Entity.username
若為玩家實體（`type == "player"`），這裡是玩家名稱；其他實體則為 `None`

### Entity.position
實體目前位置的 `Vec3`

### Entity.velocity
實體當下的速度向量

### Entity.yaw
水平朝向

### Entity.pitch
俯仰角（弧度）；正值朝下、負值朝上

### Entity.height
實體的高度（方塊為單位）
玩家約 `1.8`

### Entity.onGround
是否站在地上

### Entity.health
實體目前血量（若伺服器有送出血量資訊）；無資訊時為 `None`

### Entity.heldItem
實體手上拿的物品 `Item`

### Entity.uuid
實體的 UUID 字串

### Entity.mobType
生物類型字串（例如 `"Zombie"`、`"Cow"`）；非生物 entity 為 `None`

### Entity.displayName
實體的顯示名稱字串；若沒有自訂名稱可能為 `None`

### Entity.entityType
舊版用的實體類型數字 ID

### Entity.kind
大分類字串，例如 `"Hostile mobs"`、`"Passive mobs"`、`"Vehicles"`

### Entity.name
內部名稱字串

### Entity.objectType
非生物類實體（如物品、投擲物）的類別字串

### Entity.count
掉落物實體的數量；非掉落物為 `None`

### Entity.width
實體寬度

### Entity.equipment
實體身上的裝備陣列，索引 `0` = 主手、`1` = 腳、`2` = 腿、`3` = 胸、`4` = 頭
沒穿為 `None`

### Entity.metadata
實體的 raw metadata 陣列
包含旗標（例如著火、隱形）、當前狀態值等
結構原生、不易解析，除錯用

### Entity.isValid
實體是否仍在世界中（布林）
已消失 / 超出視野的實體會變 `False`

### Entity.food
若為玩家，這裡是飽食度 `[0, 20]`；其他實體為 `None`

### Entity.foodSaturation
若為玩家，飽食度緩衝；其他實體為 `None`

### Entity.elytraFlying
實體目前是否張開鞘翅飛行中

### Entity.player
若為玩家實體，這裡是 `Player` 物件（含 `ping`、`uuid` 等）；其他實體為 `None`

### Entity.effects
實體身上的狀態效果陣列，每個元素是 `Effect`

### Entity.vehicle
實體目前所騎的載具 `Entity`，沒有則為 `None`

### Entity.passengers
騎在這個實體身上的乘員 `Entity` 陣列

### Entity.setEquipment(index, item)
更新實體指定裝備槽的顯示物品

Args:
    index: `0` 主手、`1` 腳、`2` 腿、`3` 胸、`4` 頭
    item: 要顯示的 `Item`

### Entity.getCustomName()
Returns:
    實體的自訂名稱 `ChatMessage`，沒有則為 `None`

### Entity.getDroppedItem()
若此實體是掉落物 entity，回傳其物品 `Item`，否則為 `None`

### Block
世界中一格方塊的表示

### Block.name
方塊的 Minecraft 名稱 ID，例如 `"stone"` / `"diamond_ore"`

### Block.displayName
方塊的顯示名稱（英文），例如 `"Stone"` / `"Diamond Ore"`

### Block.position
方塊在世界中的 `Vec3` 座標

### Block.diggable
這個方塊是否可以被挖（布林）
基岩這類是 `False`

### Block.hardness
方塊的硬度值（浮點數）；愈大代表空手打愈久

### Block.type
方塊的數字 ID

### Block.stateId
方塊的 state 數字 ID（1.13+ flattening 後的真正唯一識別碼）
新版 pattern 請優先用這個

### Block.metadata
方塊的 metadata 整數值；依方塊類型有不同語意

### Block.light
方塊的可見光等級 `0` ~ `15`

### Block.skyLight
方塊的天光等級 `0` ~ `15`

### Block.boundingBox
物理判定的大致形狀字串：`"block"`（實心 / 半實心）或 `"empty"`

### Block.transparent
方塊視覺上是否半透明

### Block.isWaterlogged
方塊目前是否含水（1.13+ 的水方塊疊加機制）
非水方塊型態可能為 `None`

### Block.material
材質分類字串：`"rock"`、`"wood"`、`"plant"`、`"dirt"`、`"web"` 等；可能為 `None`
用來判斷該用什麼工具挖

### Block.harvestTools
可以有效採集此方塊的工具 ID 字典 `{itemId: True}`；空的話代表空手也能採集

### Block.biome
所在生物群系 `Biome` 物件

### Block.shapes
方塊的碰撞形狀陣列，每個元素是 `[xmin, ymin, zmin, xmax, ymax, zmax]` 的邊界盒

### Block.blockEntity
若為含資料的方塊（招牌、箱子、音符盒等），這裡是它的 NBT-like 物件

### Block.entity
若方塊本身是 entity（少見），這裡是 raw NBT；否則為 `None`

### Block.hash
Bedrock Edition 專用的方塊狀態雜湊值；Java 平台上通常為 `None`

### Block.canHarvest(heldItemType)
能否用目前持有的工具收穫這個方塊

Args:
    heldItemType: 手上工具的物品 ID 整數，或 `None` 代表空手

### Block.getProperties()
解析 block state，回傳屬性字典

### Block.digTime(heldItemType, creative, inWater, notOnGround, enchantments, effects)
估算挖掉此方塊所需毫秒數（與 `bot.digTime(block)` 相似但更細，可指定環境參數）

Args:
    heldItemType: 手持工具 ID，空手為 `None`
    creative: 是否創造模式
    inWater: 是否在水中
    notOnGround: 是否在空中（沒踏地）
    enchantments: (選填) 工具上的附魔列表
    effects: (選填) 身上的狀態效果列表

### Item
物品堆疊的表示

### Item.name
物品的 Minecraft 名稱 ID，例如 `"diamond"` / `"iron_pickaxe"`

### Item.displayName
物品的顯示名稱

### Item.count
這堆物品的數量

### Item.stackSize
這種物品單格最多能疊幾個

### Item.maxDurability
工具 / 武器 / 護甲的最大耐久；沒有耐久概念的物品為 `0`

### Item.durabilityUsed
工具已經消耗掉多少耐久
剩餘耐久 = `maxDurability - durabilityUsed`

### Item.type
物品的數字 ID

### Item.slot
這個物品目前所在的槽位編號

### Item.metadata
物品的 metadata 整數值

### Item.nbt
raw NBT 資料物件（附魔、自訂名稱、耐久等都在裡面）；沒有則為 `None`

### Item.stackId
多玩家共享場景中物品堆疊的識別碼，1.17.1+ 才有；否則為 `None`

### Item.enchants
附魔列表，陣列元素形如 `{name: "sharpness", lvl: 3}`

### Item.blocksCanPlaceOn
冒險模式下此物品可以放置在哪些方塊上

### Item.blocksCanDestroy
冒險模式下此物品可以破壞哪些方塊

### Item.repairCost
物品在鐵砧維修所需的等級代價

### Item.customName
玩家自訂的顯示名稱字串，沒取名為 `None`

### Item.customLore
玩家自訂的 lore（補充說明），可能是單一字串、字串陣列，或 `None`

### Item.customModel
自訂 model string（用於資源包），沒有為 `None`

### Item.spawnEggMobName
若為生怪蛋，這裡是它會生出的生物名稱字串

### ChatMessage
Minecraft 聊天訊息物件
伺服器 emit 的事件參數多半是這個類型；需要印字時用 `.toString()` 或 `.toAnsi()`

### ChatMessage.json
原始的 JSON 物件

### ChatMessage.extra
額外 children 訊息陣列（ChatMessage 本身是樹狀結構），沒有則為 `None`

### ChatMessage.translate
(選填) 訊息對應的翻譯 key，例如 `"chat.type.text"`

### ChatMessage.append(*messages)
把一到多個子訊息或字串附加到自身

### ChatMessage.clone()
Returns:
    一個同內容的新 `ChatMessage`

### ChatMessage.toString(language)
攤平為純文字字串（**去除所有顏色與樣式**）
通常學生只會用這個

Args:
    language: (選填) 翻譯字典物件；預設使用內建 English 翻譯表

### ChatMessage.toMotd(language)
攤平為含 `§x` 顏色碼的字串

### ChatMessage.toAnsi(language)
攤平為 ANSI 跳脫碼字串——印到終端機會顯示真正的顏色

### ChatMessage.toHTML(language, styles)
攤平為 HTML 字串，含內嵌 CSS

### ChatMessage.length()
取得這則訊息的子元件數量

### ChatMessage.getText(idx, language)
取得第 `idx` 個子元件的純文字

### ChatMessage.valueOf()
同 `toString()`，供 `str()` / `+` 字串拼接使用

### Effect
狀態效果物件

### Effect.id
狀態效果的數字 ID

### Effect.amplifier
等級 `0` ~ `N`（**從 0 開始**）
Minecraft 的「力量 II」在這裡是 `amplifier=1`

### Effect.duration
剩餘持續時間

### Player
伺服器玩家名單中的一筆資料；由 `bot.players[username]` 取得

### Player.uuid
玩家 UUID 字串

### Player.username
玩家遊戲名稱

### Player.displayName
玩家的顯示名稱 `ChatMessage`

### Player.gamemode
玩家的遊戲模式數字 ID

### Player.ping
玩家延遲毫秒

### Player.entity
玩家的 `Entity` 物件（若該玩家目前在視野內）；否則為 `None`

### Player.skinData
玩家膚色貼圖資料 dict（含 `url` 和 `model`），可能為 `None`

### Window
開啟的任意容器 / 視窗

### Window.id
視窗的協定 ID

### Window.title
視窗標題字串

### Window.slots
視窗中所有物品槽位的陣列；空槽為 `None`

### Window.inventoryStart
玩家物品欄區塊在整個 slots 陣列中的起始索引

### Window.inventoryEnd
玩家物品欄區塊的結束索引

### Window.hotbarStart
快捷欄區塊的起始索引

### Window.craftingResultSlot
合成結果槽的索引；沒有合成區則為 `-1`

### Window.selectedItem
目前游標上拿著的 `Item`（滑鼠按住拖放用），沒有則為 `None`

### Window.items()
Returns:
    玩家物品欄中的所有物品 `Item` 陣列

### Window.containerItems()
Returns:
    容器區所有物品 `Item` 陣列

### Window.count(itemType, metadata)
玩家物品欄中有多少指定物品

Args:
    itemType: 物品 ID 或名稱
    metadata: 目標 metadata；不關心傳 `None`

### Window.emptySlotCount()
玩家物品欄中空槽的數量

### Window.firstEmptySlotRange(start, end)
在指定範圍中找第一個空槽的編號，沒找到回 `None`

### Window.firstEmptyHotbarSlot()
快捷欄中第一個空槽的編號，找不到回 `None`

### Window.firstEmptyContainerSlot()
容器區中第一個空槽的編號

### Window.firstEmptyInventorySlot(hotbarFirst)
物品欄中第一個空槽的編號

Args:
    hotbarFirst: 預設 `True`，先從快捷欄找

### Window.findInventoryItem(itemType, metadata, notFull)
在玩家物品欄中找第一個符合的 `Item`，沒找到回 `None`

Args:
    itemType: 物品 ID 整數
    metadata: metadata；不關心傳 `None`
    notFull: `True` 代表只要沒達 stackSize 的那堆

### Window.findContainerItem(itemType, metadata, notFull)
同上但在容器區找

### Chest
繼承 `Window`，`bot.openChest(...)` 的回傳型別

### Chest.deposit(itemType, metadata, count)
從物品欄存入箱子

Args:
    itemType: 物品 ID 整數
    metadata: 選擇特定 metadata，不關心傳 `None`
    count: 要存入的數量

### Chest.withdraw(itemType, metadata, count)
從箱子取出到物品欄

### Chest.close()
關閉這個箱子
等同 `bot.closeWindow(chest)`

### Dispenser
繼承 `Window`，發射器 / 投擲器
方法與 `Chest` 幾乎相同

### Dispenser.deposit(itemType, metadata, count)
從物品欄存入發射器

### Dispenser.withdraw(itemType, metadata, count)
從發射器取出

### Dispenser.close()
關閉這個發射器

### Furnace
繼承 `Window`，`bot.openFurnace(...)` 回傳型別

### Furnace.fuel
目前燃料進度

### Furnace.progress
目前冶煉進度

### Furnace.takeInput()
取出輸入槽的物品

### Furnace.takeFuel()
取出燃料槽的物品

### Furnace.takeOutput()
取出輸出槽的物品

### Furnace.putInput(itemType, metadata, count)
放入指定物品到輸入槽

### Furnace.putFuel(itemType, metadata, count)
放入指定燃料到燃料槽

### Furnace.inputItem()
Returns:
    輸入槽目前的 `Item`

### Furnace.fuelItem()
Returns:
    燃料槽目前的 `Item`

### Furnace.outputItem()
Returns:
    輸出槽目前的 `Item`

### Furnace.close()
關閉熔爐

### EnchantmentTable
繼承 `Window`，附魔台

### EnchantmentTable.enchantments
目前顯示的三個附魔選項陣列，每個元素含 `level` 和 `expected`

### EnchantmentTable.targetItem()
Returns:
    目前放在附魔台上的 `Item`

### EnchantmentTable.enchant(choice)
選擇某個附魔選項進行附魔

Args:
    choice: 選項編號 `0` / `1` / `2`，或對應的字串名稱

### EnchantmentTable.takeTargetItem()
把附魔好的物品拿出來

### EnchantmentTable.putTargetItem(item)
把要附魔的物品放進附魔台

### EnchantmentTable.putLapis(item)
放青金石進去

### EnchantmentTable.close()
關閉附魔台

### Anvil
鐵砧視窗

### Anvil.combine(itemOne, itemTwo, name)
把兩個物品在鐵砧上合併（修復 / 附魔合併），可順便改名

Args:
    itemOne: 左槽物品
    itemTwo: 右槽物品
    name: (選填) 新名稱字串

### Anvil.rename(item, name)
重新命名一個物品

Args:
    item: 要改名的物品
    name: 新名稱

### Villager
繼承 `Window`，村民交易面板

### Villager.trades
村民目前的交易選項陣列，每筆是 `VillagerTrade`

### Villager.close()
關閉交易面板

### Recipe
合成配方物件
由 `bot.recipesFor(...)` 取得

### Recipe.result
合成產出的 `RecipeItem`

### Recipe.inShape
輸入配方的形狀（2D 陣列），空格為 `None`

### Recipe.outShape
輸出配方的形狀

### Recipe.ingredients
合成需要的材料 `RecipeItem` 陣列

### Recipe.delta
合成後物品欄的變化量

### Recipe.requiresTable
是否需要工作台（布林）
`False` 代表玩家 2x2 合成區就能做


---

## Pathfinder（mineflayer-pathfinder，經 `bot.load_plugin` 載入後才可用）

### Pathfinder
尋路插件提供給機器人的執行時 API
載入插件後會自動掛在 `bot.pathfinder` 上

### Pathfinder.setGoal(goal, dynamic)
設定機器人要去的目標；會在背景持續尋路並移動
傳 `None` 可取消當前任務

Args:
    goal: 任一 `Goal` 實例；`None` 代表取消
    dynamic: 預設 `False`。設 `True` 時，目標位置會被持續重新檢查（適合跟隨會移動的實體）

### Pathfinder.setMovements(movements)
套用一套移動規則
通常只需要在初始化或更改規則時呼叫一次

Args:
    movements: `Movements` 實例

### Pathfinder.goto(goal)
阻塞直到抵達目標或失敗
**慎用**：在 JSPyBridge 下會阻塞當前執行緒；若放在事件 handler 裡會卡住 callback 執行緒，通常只建議在主程式使用

### Pathfinder.stop()
取消當前尋路任務並停下移動

### Pathfinder.isMoving()
機器人目前是否正在執行尋路移動

### GoalNear(x, y, z, range)
最常用的目標：抵達 `(x, y, z)` 附近 `range` 格內即算到達

Args:
    x: 目標世界座標
    y: 目標世界座標
    z: 目標世界座標

Args:
    range: 容許的半徑（方塊為單位）

### GoalBlock(x, y, z)
抵達指定整數座標那格方塊上
需要精確落地時使用

### GoalXZ(x, z)
抵達指定 X / Z 平面，Y 不限

### GoalY(y)
爬升 / 下降到指定 Y 高度；X、Z 不限

### GoalFollow(entity, range)
持續跟著某個實體，保持距離在 `range` 格內
搭配 `setGoal(..., dynamic=True)` 使用

Args:
    entity: 要跟隨的 `Entity`
    range: 保持的距離上限

### GoalCompositeAll(goals)
只有全部子目標都滿足時才算達成
通常用來疊加多個空間約束

### GoalCompositeAny(goals)
任一子目標達成就結束
適合「到達任一地標即可」的需求

### GoalInvert(goal)
把一個「抵達某點」目標翻轉成「遠離某點」——會朝讓啟發式最大化的方向移動

### Movements
尋路的移動規則集合
決定機器人能挖、能跳、能游、能跑、允許哪些方塊放置等

### Movements.canDig
是否允許為了開路而挖方塊

### Movements.canOpenDoors
是否允許開門穿過

### Movements.allowSprinting
是否允許跑步（布林）
跑步比較快但耗更多食物

### Movements.allowParkour
是否允許跨越需要跳躍的距離

### Movements.allow1by1towers
是否允許在原地往上疊方塊製作 1x1 高塔

### Movements.allowFreeMotion
是否允許「直線穿越」非方塊化地形

### Movements.allowEntityDetection
是否偵測會阻擋路徑的實體（布林）
開啟後尋路每次會重新掃附近實體，耗一點效能但比較安全

### Movements.digCost
為了開路而挖方塊時加在路徑成本上的懲罰值
預設較大以降低挖路傾向

### Movements.placeCost
為了開路而放置方塊時的成本懲罰

### Movements.maxDropDown
允許直接向下跳躍的最大高度（方塊數）
超過這個值會找別的路或不通

### Pathfinder.thinkTimeout
尋路總思考時間上限（毫秒）
超過會停下來並 emit `path_update` 回報 timeout

### Pathfinder.tickTimeout
每個 tick 內思考時間上限

### Pathfinder.isMining()
機器人是否正在為尋路挖方塊

### Pathfinder.isBuilding()
機器人是否正在為尋路放置方塊

### Pathfinder.bestHarvestTool(block)
Args:
    block: 要挖的 `Block`

Returns:
    物品欄中最適合挖此方塊的 `Item`，沒有合用的工具則回 `None`

### Goal
所有目標類別的基底
學生通常直接用 `GoalNear` 等子類而不是這個

### Goal.hasChanged()
目標參數是否自上次尋路後有改動

### Goal.isValid()
目標是否仍然可以作為有效目標

### GoalNearXZ(x, z, range)
同 `GoalXZ` 但帶距離容許值：抵達 `(x, z)` 平面 `range` 格內即算達成，Y 不限

Args:
    x: 水平座標
    z: 水平座標

Args:
    range: 容許半徑

### GoalGetToBlock(x, y, z)
抵達指定整數座標**旁邊**
適合用來走到箱子前、工作台前這類需要「站旁邊操作」的物件

### "goal_reached"
pathfinder 完成目標時觸發事件
（`bot.pathfinder.setGoal(...)` 後）

Args:
    goal: 已達成的 `Goal`

### "path_update"
每次路徑重算後觸發事件

Args:
    path: `PartiallyComputedPath` 物件，含 `status`、`cost`、`path` 等

### "goal_updated"
目標被更換時觸發事件

Args:
    goal: 新的 `Goal`
    dynamic: 是否為動態目標（會隨 entity 位置更新）

### "path_reset"
路徑需要重置時觸發事件
（例如目標移動、方塊更新、遇到障礙）

Args:
    reason: 原因字串：`"goal_updated"` / `"movements_updated"` / `"block_updated"` / `"chunk_loaded"` / `"goal_moved"` / `"dig_error"` / `"no_scaffolding_blocks"` / `"place_error"` / `"stuck"`

### "path_stop"
pathfinder 明確停下時觸發事件（無參數）
（`bot.pathfinder.stop()` 或任務完成）
