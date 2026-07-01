# 钉钉企业内部应用 + Stream 模式接入指南

> **推荐方案**，对比企业微信：**不需公网 URL、不需 callback 验证、不需 ngrok**。

## 总览

```
你的 Mac 运行: app/dingtalk/bot.py
   ↓ WebSocket 长连接（由我们主动连出去）
钉钉 Stream 服务器
   ↓ 推送用户消息
我们收到 → 跑 pipeline → 通过 API 主动回复
```

**跟企业微信的核心区别**：
- 企业微信是 WeChat **主动推**给我们 → 需要 callback URL
- 钉钉 Stream 是**我们主动连**到钉钉 → **不需要任何公网 URL**

## Step 1: 注册钉钉开发者账号

1. 去 https://open-dev.dingtalk.com/ 注册（用手机号 + 邮箱）
2. 创建一个"企业内部应用"
3. 进入应用 → **机器人** → 开启"机器人能力" → 选择"Stream 模式"
4. 在"基础信息"页拿：
   - **AppKey**（`AppKey_xxxxxxxxxxxx`）
   - **AppSecret**（点"查看"获取）
   - **AgentId**（`1234567890` 这种数字）

## Step 2: 把凭证填到 `.env`

```bash
vim .env
# 找到这几行，填入：
DINGTALK_APP_KEY=你的AppKey
DINGTALK_APP_SECRET=你的AppSecret
DINGTALK_AGENT_ID=你的AgentId（纯数字）
```

## Step 3: 启动 bot

```bash
# 先测试（前台跑，看日志）
.venv/bin/python -m app.dingtalk.bot

# 看到 "Starting DingTalk bot (agent_id=xxx)" 说明连接成功
# Ctrl+C 退出
```

## Step 4: launchd 守护（自动重启 + 开机自启）

```bash
# 装服务
launchctl load -w ~/Library/LaunchAgents/com.mothercare.dingtalk.plist

# 验证
launchctl list | grep dingtalk
# 看 pid 是不是在跑
```

## Step 5: 在钉钉里跟机器人对话

1. 用手机/电脑登录**钉钉**（不是企业微信）
2. 搜索"母婴助手"应用
3. 直接发消息："新生儿黄疸多少算危险？"
4. 应该几秒内收到回复

## Step 6: 邀请家人（可选）

- 钉钉支持**企业内部群**
- 把老婆/妈妈/月嫂/你**全部**加到钉钉，搜索应用后都能用
- 不像企业微信那样有可见范围限制

## 故障排查

**bot 起不来**：
- 看 `data/dingtalk.err.log`
- 90% 是 `DINGTALK_APP_KEY/SECRET/AGENT_ID` 配错了

**bot 起来但收不到消息**：
- 检查"应用 → 机器人"是否开启了 **Stream 模式**
- 检查"权限管理"里"机器人"是否给了"接收消息"权限

**收到消息但没回复**：
- 看 `data/dingtalk.log` 有没有 pipeline 错误
- 看 KB 检索是不是不命中（用 `python -m app.eval.run_eval` 验证 KB 质量）

## 跟企业微信的对比

| | 企业微信 | 钉钉 Stream |
|---|---|---|
| 公网 URL | 必填 | **不需要** |
| Callback 验证 | AES 加密握手 | **不需要** |
| VPN 友好 | 差 | **好**（长连接） |
| 重试机制 | 一次失败就报错 | 自动重连（我们代码里） |
| 公网域名 | 需要 ngrok / 服务器 | **不需要** |
| 单聊支持 | 需要创建可见 | 应用名搜索即可 |
| 群聊 | 不支持 | 支持（企业内部群） |

## 不再需要的东西

- ngrok / cloudflared
- 公网 IP / 域名 / HTTPS 证书
- 企业微信后台的 callback URL 配置
- AesKey / Token / 签名验证

## 保留（如果想用企业微信）

企业微信代码还在 `app/wechat/` 里。等你以后买云服务器（30 块/月）部署了，可以一键切回企业微信。代码、配置、文档都在，不丢。
