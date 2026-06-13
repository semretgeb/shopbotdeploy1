# ShopBot Ethiopia 🤖

An AI-powered Telegram chatbot for Ethiopian small businesses.
Replies to customers 24/7 in Amharic and English.

---

## Setup Instructions (Windows)

### Step 1 — Install Python
1. Go to https://www.python.org/downloads
2. Download and install Python
3. ⚠️ Check "Add Python to PATH" before installing

### Step 2 — Open terminal in this folder
1. Open the shopbot folder
2. Hold Shift + Right-click inside the folder
3. Click "Open PowerShell window here"

### Step 3 — Create virtual environment
```
python -m venv venv
venv\Scripts\activate
```

### Step 4 — Install libraries
```
pip install -r requirements.txt
```

### Step 5 — Add your API keys
1. Rename .env.example to .env
2. Open .env and fill in:
   - TELEGRAM_TOKEN → get from @BotFather on Telegram
   - ANTHROPIC_API_KEY → get from https://console.anthropic.com
   - OWNER_TELEGRAM_ID → get from @userinfobot on Telegram

### Step 6 — Run the bot
```
python main.py
```

---

## How to use

### As shop owner:
- /start — Welcome message
- /setup — Set up your shop (name, products, prices, delivery)
- /myshop — View your current shop details
- /resetshop — Reset and start over

### As customer:
- Just send a message and the AI replies automatically!

---

## Project Structure
```
shopbot/
├── main.py          # Bot entry point
├── setup_flow.py    # Shop owner onboarding conversation
├── chat_handler.py  # Customer AI reply handler
├── database.py      # SQLite database functions
├── claude_api.py    # Claude AI integration
├── .env             # Your API keys (never share this!)
└── requirements.txt # Python libraries needed
```
