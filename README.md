# DL Slot Booking Telegram Bot

Automated Telegram bot for booking DL test slots on sarathi.parivahan.gov.in with AI-powered captcha solving.

## 🏗️ Architecture

### **Technology Stack:**
- **Framework**: `python-telegram-bot` (async polling bot)
- **HTTP Client**: `requests` library (NO Selenium, NO browser needed)
- **AI Captcha**: `google-generativeai` (optional, for Gemini API)
- **Image Processing**: `Pillow` (PIL)
- **State Management**: In-memory dictionary (no database required)
- **Runtime**: Python 3.8+ with async/await

### **Key Characteristics:**
✅ **Lightweight** - Just HTTP requests, no browser automation  
✅ **Simple Dependencies** - Standard Python libraries  
✅ **No Special Requirements** - Works on any Python environment  
✅ **Long-Running Process** - Needs 24/7 persistent execution  
✅ **Polling-Based** - Uses Telegram polling (not webhooks)

## 🚀 Free 24/7 Hosting

Based on your bot's architecture (lightweight Python bot with HTTP requests), here are **truly free options**:

### ⭐ **Option 1: Render** (RECOMMENDED - Truly Free)

**Why it's good:**
- ✅ **100% Free** - No credit card, no charges
- ✅ **Easy GitHub deployment** - Auto-deploy on push
- ✅ **Simple setup** - Good for beginners
- ⚠️ **Sleeps after 15 min inactivity** - Use UptimeRobot (free) to keep alive

**Free Tier:**
- Free forever (no credit card required)
- 512MB RAM
- Apps sleep after 15 minutes of inactivity
- Use UptimeRobot (free) to ping every 5 minutes

**Setup Steps:**

1. Push code to GitHub
2. Go to https://render.com and sign up (free, no credit card)
3. Click **"New"** → **"Web Service"**
4. Connect your GitHub repository
5. Set **Start Command**: `python telegram_bot.py`
6. **Set Environment Variables** (if using .env method):
   - Go to Environment tab
   - Add: `BOT_TOKEN`, `AUTHORIZED_USERS`, `APPLICATION_NUMBER`, `DOB`, `GEMINI_API_KEY`
7. Click **"Create Web Service"**
8. **Set up UptimeRobot** (to prevent sleep):
   - Go to https://uptimerobot.com (free)
   - Add monitor for your Render URL
   - Set interval to 5 minutes
   - Your bot stays awake 24/7!

**Link**: https://render.com

---

### ⭐ **Option 2: Fly.io** (Free Tier - Always On)

**Why it's good:**
- ✅ **Free tier available** - 3 shared-CPU VMs, 256MB RAM each
- ✅ **Always-on** - No sleep, truly 24/7
- ✅ **160GB bandwidth** - More than enough
- ✅ **GitHub integration** - Auto-deploy

**Free Tier:**
- 3 shared-CPU 256MB VMs (free)
- 160GB outbound data transfer
- Always-on (no sleep)
- Persistent storage

**Setup Steps:**

1. Install Fly.io CLI: https://fly.io/docs/getting-started/installing-flyctl/
2. Sign up at https://fly.io (free tier available)
3. Run: `fly launch` in your project directory
4. Follow prompts to deploy
5. Your bot runs 24/7!

**Link**: https://fly.io

---

### ⭐ **Option 3: PythonAnywhere** (Free Tier - Always On)

**Why it's good:**
- ✅ **Free tier available** - Perfect for Python bots
- ✅ **Always-on** - No sleep
- ✅ **Simple setup** - Web-based interface
- ✅ **No GitHub needed** - Direct file upload

**Free Tier:**
- Always-on Python web app
- 512MB disk space
- Limited CPU time (enough for small bots)
- Web-based console

**Setup Steps:**

1. Sign up at https://www.pythonanywhere.com (free account)
2. Go to "Web" tab → "Add a new web app"
3. Choose "Manual configuration" → Python 3.11
4. Upload your files via Files tab
5. Set up scheduled task or web app to run your bot
6. Your bot runs 24/7!

**Link**: https://www.pythonanywhere.com

---

### ⚠️ **Important Notes**

**Your Bot's Architecture:**
- ✅ Uses `requests` library (HTTP client) - **NO Selenium needed**
- ✅ Lightweight Python bot - works on any Python 3.8+ environment
- ✅ In-memory state - no database required
- ✅ Async polling bot - needs persistent process

**Security:**
- Your bot token is hardcoded in `telegram_bot.py` (line 29)
- This is fine for personal use
- For production, consider using environment variables

**File Structure for Deployment:**
```
your-bot/
├── telegram_bot.py          (main bot file)
├── dl_booking_automation.py  (automation module)
├── requirements.txt          (dependencies)
├── Procfile                  (for some platforms - already created)
└── runtime.txt               (for some platforms - already created)
├── .env                      (your credentials - NOT committed to git)
└── .gitignore                (ensures .env is not committed)
```

**Security Best Practices:**
- ✅ **Use `.env` file** - Credentials stay local, never committed to git
- ✅ **`.gitignore` included** - Automatically ignores `.env` file
- ✅ **Works with public repos** - Safe to share code without exposing secrets
- ⚠️ **If hardcoding**: Only safe if repository is **private**

## Quick Setup

### 1. Create Virtual Environment
```bash
# Windows 
python -m venv venv
venv\Scripts\Activate.ps1

# Android (Termux)
python -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Bot (SECURE METHOD - Recommended)

**Option A: Using Environment Variables (Recommended for Public Repos)**

1. Create a `.env` file in the project root:
   ```bash
   # .env file
   BOT_TOKEN=your_bot_token_here
   AUTHORIZED_USERS=your_telegram_user_id_here
   APPLICATION_NUMBER=your_application_number
   DOB=DD-MM-YYYY
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

2. The `.env` file is automatically ignored by git (already in `.gitignore`)
3. Your credentials stay secure and won't be committed to the repository

**Option B: Hardcode in Code (Only for Private Repos)**

If your repository is **private**, you can hardcode credentials directly in `telegram_bot.py`:
- Set `BOT_TOKEN` (line 29) - Get from @BotFather
- Set `AUTHORIZED_USERS` (line 33) - Your Telegram user ID
- (Optional) Set `DEFAULT_GEMINI_API_KEY` (line 52) - Get from https://makersuite.google.com/app/apikey

**⚠️ Security Note:**
- **Public Repo**: Always use `.env` file (credentials will be exposed if hardcoded)
- **Private Repo**: Either method works, but `.env` is still recommended

### 4. Run Bot
```bash
python telegram_bot.py
```

## Commands

| Command | Description |
|---------|-------------|
| `/setup [app_no] [dob]` | Set application number and DOB (DD-MM-YYYY) |
| `/check` | Check slot availability once |
| `/monitor` | Start continuous monitoring |
| `/stop` | Stop monitoring |
| `/interval [minutes]` | Set check interval (default: 30 min) |
| `/captcha_method [manual/ai]` | Set captcha solving method |
| `/set_gemini_key [key]` | Set Gemini API key for AI solving |
| `/status` | Check current status |

## Usage Example

```
/setup 3209941425 04-03-1974
/set_gemini_key YOUR_API_KEY
/captcha_method ai
/interval 30
/monitor
```

## Captcha Solving

- **Manual**: Bot sends image, you enter code
- **AI**: Auto-solves using Gemini (requires API key, not 100% accurate)

## Running in Background

**Windows:**
```powershell
.\venv\Scripts\Activate.ps1
python telegram_bot.py
```

**Android (Termux):**
```bash
# Using tmux (recommended)
pkg install tmux
tmux new -s bot
source venv/bin/activate
python telegram_bot.py
# Detach: Ctrl+B, then D
# Reattach: tmux attach -t bot

# Or using nohup
source venv/bin/activate
nohup python telegram_bot.py > bot.log 2>&1 &
```

## 🆘 Troubleshooting

### **Bot not responding?**
1. Check logs on your hosting platform
2. Verify bot token is correct in `telegram_bot.py`
3. Ensure all dependencies are installed (check `requirements.txt`)

### **Import errors?**
- Verify `requirements.txt` has all packages:
  - `python-telegram-bot>=21.0`
  - `requests>=2.31.0`
  - `google-generativeai>=0.3.0` (optional)
  - `Pillow>=10.0.0`

### **Bot stops after inactivity?**
- ⚠️ Render: Sleeps after 15 min - Use UptimeRobot (free) to keep alive
- ✅ Fly.io: Always-on on free tier
- ✅ PythonAnywhere: Always-on on free tier

### **Deployment fails?**
- Check Python version (needs 3.8+)
- Verify all files are included in ZIP/GitHub
- Check platform logs for specific errors

### **Missing dl_booking_automation.py?**
- Make sure this file exists in your project
- It's required for the bot to work
- Include it in your ZIP file or GitHub repo

### **Local Bot Issues:**
- **Bot not starting**: Check internet, verify bot token
- **AI fails**: Check API key/quota, use manual mode
- **Connection timeout**: Check firewall, verify Telegram access
- **Termux bot stops**: Use `tmux` or `nohup` to keep running in background

## 📝 Quick Start Checklist

### **For Render (Recommended):**
- [ ] Push code to GitHub
- [ ] Sign up at https://render.com (free, no credit card)
- [ ] Create Web Service from GitHub repo
- [ ] Set start command: `python telegram_bot.py`
- [ ] Set environment variables
- [ ] Set up UptimeRobot (free) to prevent sleep

### **For Fly.io:**
- [ ] Install Fly.io CLI
- [ ] Sign up at https://fly.io (free tier available)
- [ ] Deploy using CLI or GitHub integration
- [ ] Verify bot is running

## Requirements

- Python 3.8+
- Telegram Bot Token
- (Optional) Gemini API Key for AI captcha solving

## 📚 Additional Resources

- **Render Docs**: https://render.com/docs
- **Fly.io Docs**: https://fly.io/docs
- **PythonAnywhere Docs**: https://help.pythonanywhere.com
- **Python Telegram Bot Docs**: https://python-telegram-bot.org
- **UptimeRobot** (for Render keep-alive): https://uptimerobot.com
