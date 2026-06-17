# GsheetSearchBot — Setup Guide

Searches GM-Customer-Details (First name, Last name, Email, Phone, Campaign, Notes)
and returns the full matching row via Telegram.

---

## Folder structure

```
your-folder/
├── bot.py
├── requirements.txt
├── token.json          ← paste your token.json content here
└── credentials.json    ← paste your credentials.json content here
```

---

## Step 1 — Create the two credential files

**token.json** — create this file and paste your token JSON into it:
```json
{"token": "ya29.a0AT...", "refresh_token": "1//0g...", ...}
```

**credentials.json** — create this file and paste your credentials JSON into it:
```json
{"installed": {"client_id": "...", "client_secret": "...", ...}}
```

The bot auto-refreshes the access token whenever it expires — you won't need
to update token.json manually again.

---

## Step 2 — Install dependencies

```bash
pip install -r requirements.txt
```

---

## Step 3 — Run the bot

```bash
python bot.py
```

---

## Telegram usage

| What to send | What happens |
|---|---|
| `Joe` | Finds all rows where any cell contains "joe" |
| `joearms@email.com` | Looks up by email |
| `404343434` | Looks up by phone |
| `Hybrid SUV` | Looks up by campaign |
| `/search Arms` | Same as typing "Arms" |
| `/columns` | Shows column list + total record count |
| `/help` | Usage tips |

Searches are **partial and case-insensitive** — `joe` matches `Joe`, `Joel`, `joearms@…`

---

## Keeping it running 24/7

```bash
# Simple background process
nohup python bot.py &

# Or with screen
screen -S gsheetbot
python bot.py
# Ctrl+A then D to detach
```
