# 🔗 LinkShareBot

> **Secure private Telegram channel link sharing — powered by PyroFork.**  
> Share your private channels without ever exposing permanent invite URLs, protecting them from copyright strikes.

---

## 🌟 How It Works

1. Admin registers a private channel → bot stores its ID in MongoDB.  
2. Bot generates an **encoded deep-link** like `t.me/YourBot?start=Y2hhbm5lbF8...`.  
3. User clicks the link → bot creates a **fresh, single-use, 5-minute invite link** on the fly.  
4. The permanent channel invite URL is **never exposed** publicly.

---

## 📁 Project Structure

```
LinkShareBot/
├── main.py              # Entrypoint
├── bot.py               # PyroFork Client subclass
├── config.py            # All env-var config + logging
├── helper_func.py       # encode/decode, invite-link helpers, pagination
├── requirements.txt
├── Dockerfile
├── Procfile
├── app.json
├── .env.example
├── database/
│   ├── __init__.py
│   └── mongodb.py       # Async MongoDB layer (CosmicBotz singleton)
└── plugins/
    ├── __init__.py      # aiohttp health-check server
    ├── start.py         # /start + deep-link invite resolution
    ├── channel_mgmt.py  # /addch /delch /channels /links /reqlink /bulklink
    ├── admin.py         # /stats /status /broadcast /cleanup /users
    ├── req_mode.py      # /reqmode /reqtime /approveon /approveoff + auto-approve handler
    └── errors.py        # Disconnect logging
```

---

## 🔑 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `APP_ID` | ✅ | Telegram App ID — [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | ✅ | Telegram API Hash — [my.telegram.org](https://my.telegram.org) |
| `TG_BOT_TOKEN` | ✅ | Bot token from [@BotFather](https://t.me/BotFather) |
| `OWNER_ID` | ✅ | Your Telegram user ID |
| `ADMINS` | ❌ | Space-separated extra admin user IDs |
| `DB_URL` | ✅ | MongoDB Atlas connection string |
| `DB_NAME` | ❌ | Database name (default: `LinkShareBot`) |
| `PORT` | ❌ | Health-check server port (default: `8080`) |
| `FORCE_SUB_CHANNEL` | ❌ | Channel ID to force-subscribe users (`0` = disabled) |
| `LINK_EXPIRY_SECONDS` | ❌ | Invite link TTL in seconds (default: `300`) |

---

## ⚡ Commands

### 👤 User
| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/start <token>` | Resolve a deep-link token → get a temp invite link |

### 🛠️ Admin
| Command | Description |
|---|---|
| `/addch <channel_id>` | Register a channel + get its shareable deep-link |
| `/delch <channel_id>` | Remove a channel |
| `/channels` | Paginated list of all registered channels |
| `/links` | All channels with their deep-links as text |
| `/reqlink` | Generate join-request links for all channels |
| `/bulklink <id1> <id2>...` | Bulk-generate temporary invite links |
| `/reqmode <channel_id>` | Toggle auto-approve join requests ON/OFF |
| `/reqtime <channel_id> <sec>` | Set auto-approve delay in seconds |
| `/approveon <channel_id>` | Enable auto-approve for a channel |
| `/approveoff <channel_id>` | Disable auto-approve for a channel |
| `/status` | Bot uptime + stats |
| `/users` | Total user count |
| `/broadcast` | *(reply to a message)* Send it to all users |
| `/cleanup` | Remove blocked/deactivated users from DB |

### 👑 Owner Only
| Command | Description |
|---|---|
| `/stats` | Full statistics (users, channels, uptime) |

---

## 🚀 Deployment

### VPS / Local

```bash
git clone https://github.com/yourname/LinkShareBot
cd LinkShareBot

# Copy and fill in your env vars
cp .env.example .env
nano .env

pip install -r requirements.txt
python main.py
```

Keep it alive with **tmux** or **screen**:
```bash
tmux new -s linksharebot
python main.py
# Detach: Ctrl+B then D
```

### 🐳 Docker

```bash
docker build -t linksharebot .
docker run -d --name linkshare --env-file .env --restart unless-stopped linksharebot
```

### ☁️ Heroku / Railway

1. Fork this repo.  
2. Set all environment variables in the dashboard.  
3. Deploy — the `Procfile` uses the `worker` dyno.

---

## ⚙️ Setup Checklist

- [ ] Create a bot via [@BotFather](https://t.me/BotFather) — copy the token.
- [ ] Get `APP_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org).
- [ ] Create a free [MongoDB Atlas](https://www.mongodb.com/atlas) cluster — copy the URI.
- [ ] Add the bot as **Admin** to every private channel you want to manage  
      *(needs: Invite Users permission)*.
- [ ] Set `OWNER_ID` to your own Telegram user ID.
- [ ] Run the bot, then use `/addch -100XXXXXXXXXX` to register channels.
- [ ] Share the generated deep-link with your audience — never the raw invite!

---

## 🔒 Security Notes

- Invite links are **single-use** and expire after `LINK_EXPIRY_SECONDS` (default 5 min).
- The permanent channel invite URL is **never sent to any user**.
- Channel IDs are **base64-encoded** in deep-links — not encrypted, but opaque to casual inspection.
- Use `FORCE_SUB_CHANNEL` to gate access behind a subscription wall.

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `pyrofork` | Pyrogram fork — Telegram MTProto client |
| `motor` | Async MongoDB driver |
| `aiohttp` | Lightweight health-check web server |
| `python-dotenv` | Load `.env` file in development |
