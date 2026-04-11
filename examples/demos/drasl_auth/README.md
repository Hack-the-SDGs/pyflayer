# Drasl Auth

透過自建 [Drasl](https://github.com/unmojang/drasl) 驗證伺服器連線。

## 功能

- 使用自訂驗證伺服器登入
- 支援 Mojang 驗證協議
- 環境變數設定帳號密碼

## 前置條件

- Minecraft Java Edition 伺服器（設定使用 Drasl 驗證）
- 已部署的 Drasl 驗證伺服器
- Drasl 帳號

## 設定

複製環境變數範本並填入你的資訊：

```bash
cp examples/demos/drasl_auth/.env.example examples/demos/drasl_auth/.env
```

編輯 `.env`：

```env
MC_USERNAME=your_username
MC_PASSWORD=your_password
MC_HOST=mc.example.com
MC_AUTH_SERVER=https://drasl.example.com/auth
MC_SESSION_SERVER=https://drasl.example.com/session
```

## 執行

```bash
uv run --env-file examples/demos/drasl_auth/.env examples/demos/drasl_auth/main.py
```
