# 企业微信自建应用接入指南

把你的 `mother-care` 服务挂到企业微信上，让自家人（老婆、月嫂）能在微信里直接问问题。

## 总览

```
家人微信消息 → 企业微信服务器 → 你的回调URL（公网HTTPS） → 你的服务器
                                                              ↓
                                                     LLM 生成回复
                                                              ↓
家人微信收到 ← 企业微信服务器 ← ← ← 主动 send 或被动回复 ← ←
```

你需要做的：
1. **企业微信管理后台**：创建一个自建应用，拿 5 个凭证
2. **本地网络**：把服务暴露到公网 HTTPS（用 cloudflared 或 ngrok）
3. **填 .env**：把 5 个凭证填到 `.env`
4. **启动服务 + 验证**：测试 URL 握手 + 收发消息

预计 15-30 分钟搞定。

---

## Step 1: 企业微信管理后台

### 1.1 注册 / 登录企业微信

- 没企业微信的话：去 https://work.weixin.qq.com/ 用手机号注册一个企业（免费，1 分钟）
- 已有：直接登录管理后台 https://work.weixin.qq.com/wework_admin/

### 1.2 拿 CorpID（企业 ID）

- 我的企业 → 企业信息 → **企业 ID**
- 形如 `ww` 开头的一串字母数字
- **填到 `.env`**：`WECHAT_CORP_ID=你的企业ID`

### 1.3 创建自建应用

- 应用管理 → 自建 → 创建应用
- 名称：`母婴助手`（显示在微信里）
- 可见范围：选你自己（先只给自己/家人用）
- 创建后记下 **AgentId**（形如 `1000002`）和 **Secret**（点"查看"获取）
- **填到 `.env`**：
  ```
  WECHAT_AGENT_ID=1000002
  WECHAT_CORP_SECRET=xxx-xxx-xxx-xxx
  ```

### 1.4 配置回调（关键！）

- 进入刚创建的应用 → **接收消息** → **设置 API 接收**
- 三个字段：
  - **URL**：你的公网 HTTPS 地址 + `/wechat/callback`
    - 例：`https://abc-xyz.trycloudflare.com/wechat/callback`
    - 等 Step 2 暴露完公网再填
  - **Token**：自定义字符串，自己起一个，比如 `MC_TOKEN_2026`
    - **填到 `.env`**：`WECHAT_CALLBACK_TOKEN=MC_TOKEN_2026`
  - **EncodingAESKey**：**点"随机生成"**（WeChat 自动生成一个 43 字符的 key）
    - **复制下来**，填到 `.env**：`WECHAT_CALLBACK_AES_KEY=<43字符key>`
- 点"保存"——这时 WeChat 会向你配置的 URL 发一个 GET 请求做验证（需要你的服务已经能公网访问）

### 1.5 把家人加进企业

- 我的企业 → 成员管理 → 邀请家人（用微信扫码）
- 家人需要下载"企业微信"app（不是普通微信）

---

## Step 2: 把本地服务暴露到公网 HTTPS

企业微信的回调必须是公网 HTTPS URL。本地 `localhost:8000` 不行。

### 推荐方案：cloudflared（无需注册）

```bash
brew install cloudflared   # 一次性
```

启动你的 FastAPI 服务（一个 terminal）：
```bash
bash scripts/run_dev.sh
# 看到 Uvicorn running on http://0.0.0.0:8000
```

启动 tunnel（另一个 terminal）：
```bash
bash scripts/expose_dev.sh cloudflared
# 输出形如：
# https://random-words-1234.trycloudflare.com
```

**把这个 URL 复制下来**，填到 Step 1.4 的回调 URL，例如：
```
https://random-words-1234.trycloudflare.com/wechat/callback
```

⚠️ **重要**：cloudflared 的 URL 是临时的，重启会变。如果你想要稳定的 URL，需要：
- 买个域名 + 部署到云服务器（生产方案）
- 或者用 ngrok 免费账号绑定固定子域名

### 备选方案：ngrok

```bash
brew install ngrok
# 注册 https://dashboard.ngrok.com 拿 authtoken
ngrok config add-authtoken <你的token>
ngrok http 8000
```

---

## Step 3: 验证配置

启动服务后，跑：

```bash
.venv/bin/python scripts/test_wechat_e2e.py
```

应该看到：
```
=== Test 1: URL verification (encrypted) ===
  HTTP 200
  body = 'test_echo_string_for_url_verification'
  ✓ URL verification PASSED

=== Test 2: Incoming encrypted message ===
  HTTP 200
  body = {...}
  ✓ Message callback PASSED
```

---

## Step 4: 实际收发消息测试

1. **在企业微信管理后台保存回调配置**（前面 1.4 那步）
   - 如果保存时报"URL 校验失败"，说明：
     - 服务没起来 → 检查 uvicorn 日志
     - 公网 URL 不通 → 在浏览器直接访问那个 URL 看能不能看到你的服务
     - Token 不一致 → 检查 .env 和管理后台完全一致

2. **用企业微信 app 发消息给自建应用**
   - 打开企业微信 app → 找到"母婴助手"应用
   - 发消息："新生儿黄疸多少算危险？"
   - 应该几秒内收到回复

---

## 常见问题

### "URL 校验失败" 

最常见原因：
1. **Token 不一致**：管理后台填的 Token 和 `.env` 里 `WECHAT_CALLBACK_TOKEN` 必须完全一样
2. **EncodingAESKey 不一致**：43 字符，不能多空格/换行
3. **回调 URL 不通**：在浏览器直接访问那个 URL，应该看到 `{"name":"Mother & Baby AI Assistant",...}`
4. **服务没起来**：检查 uvicorn 日志

### "消息发出去了但收不到回复"

1. 看 uvicorn 日志有没有收到 POST 请求
2. 看 `/tmp/uvicorn.log` 或 console 里有没有 `[wechat:callback] pipeline failed`
3. 看 access_token 是不是过期（会自动重试一次）

### "收到了但内容是错的"

跑 `python -m app.eval.run_eval --report md` 看检索质量。Hit@1 应该 ≥ 60%。

---

## 生产部署（可选）

cloudflared 是开发期方案，URL 会变。生产推荐：
- 买个域名（几十块/年）
- 部署到云服务器（阿里云/腾讯云轻量应用服务器，几十块/月）
- 用 nginx + certbot 自动 HTTPS
- 配合 systemd 或 supervisor 守护进程

需要我帮你写部署脚本的话告诉我。