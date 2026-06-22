#!/usr/bin/env python3
"""
Telegram Bot — Google Sheets Customer Search (GM-Customer-Details)
Searches by First name, Last name, Email, Phone, Campaign, or Notes
and returns the full matching row.

Auth: OAuth2 (token.json + credentials.json — installed app flow)
"""

import logging
import os
import json
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda: None  # Railway uses real env vars; dotenv not needed
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ── Configuration ─────────────────────────────────────────────────────────────
load_dotenv()

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
SPREADSHEET_ID   = os.getenv("SPREADSHEET_ID")
SHEET_NAME       = os.getenv("SHEET_NAME", "Sheet1")

# Google OAuth2 — accept either naming convention
# Railway variables can be named GOOGLE_TOKEN_JSON or TOKEN_FILE (either works)
GOOGLE_TOKEN_JSON       = os.getenv("GOOGLE_TOKEN_JSON") or os.getenv("TOKEN_FILE")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON") or os.getenv("CREDENTIALS_FILE")

# Fallback file paths for local development
TOKEN_FILE       = "token.json"
CREDENTIALS_FILE = "credentials.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Column headers (must match row 1 of your sheet exactly)
COLUMNS = ["First name", "Last name", "Email", "Phone", "Campaign", "Notes"]

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── Google Sheets helpers ─────────────────────────────────────────────────────

def get_credentials() -> Credentials:
    """
    Load OAuth2 credentials from:
      1. GOOGLE_TOKEN_JSON env var (Railway / production), or
      2. token.json file (local development fallback)
    Refreshes automatically if the access token is expired.
    """
    # ── Load token ────────────────────────────────────────────────────────────
    if GOOGLE_TOKEN_JSON:
        logger.info("Loading credentials from GOOGLE_TOKEN_JSON env var")
        token_data = json.loads(GOOGLE_TOKEN_JSON)
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    elif os.path.exists(TOKEN_FILE):
        logger.info(f"Loading credentials from {TOKEN_FILE}")
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    else:
        raise EnvironmentError(
            "No Google credentials found. Set GOOGLE_TOKEN_JSON env var (Railway) "
            f"or place {TOKEN_FILE} next to bot.py (local)."
        )

    # ── Refresh if expired ────────────────────────────────────────────────────
    if creds and creds.expired and creds.refresh_token:
        logger.info("Access token expired — refreshing…")
        creds.refresh(Request())
        logger.info("Token refreshed successfully.")
        # Note: on Railway we cannot write back to a file, but the refreshed
        # token is kept in memory for the lifetime of the process.

    return creds


def fetch_all_data() -> tuple[list[str], list[list[str]]]:
    """Fetch all rows. Returns (headers, data_rows)."""
    creds = get_credentials()
    service = build("sheets", "v4", credentials=creds)
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SPREADSHEET_ID, range=SHEET_NAME)
        .execute()
    )
    values = result.get("values", [])
    if not values:
        return [], []
    headers   = values[0]
    data_rows = values[1:]
    return headers, data_rows


def search_sheet(query: str) -> tuple[list[str], list[list[str]]]:
    """
    Case-insensitive, partial search across every cell.
    Returns (headers, matching_rows).
    """
    headers, data_rows = fetch_all_data()
    q = query.strip().lower()
    matches = [row for row in data_rows if any(q in str(cell).lower() for cell in row)]
    return headers, matches


# ── Formatters ────────────────────────────────────────────────────────────────

def format_row(headers: list[str], row: list[str]) -> str:
    """Render one row as labelled fields."""
    lines = []
    for i, header in enumerate(headers):
        value = row[i] if i < len(row) else ""
        lines.append(f"<b>{header}:</b> {value if value else '—'}")
    return "\n".join(lines)


def format_results(headers: list[str], rows: list[list[str]], query: str) -> str:
    """Build the full reply for a search result set."""
    if not rows:
        return (
            f"🔍 No results found for <b>{query}</b>.\n\n"
            "Try a different spelling or partial value (e.g. just a first name)."
        )

    n   = len(rows)
    sep = "\n" + "─" * 32 + "\n"
    header_line = f'\u2705 <b>{n} result{"s" if n > 1 else ""}</b> for "<b>{query}</b>":\n'

    sections = []
    for idx, row in enumerate(rows, 1):
        label = f"<b>[{idx}]</b>\n" if n > 1 else ""
        sections.append(label + format_row(headers, row))

    return header_line + sep + sep.join(sections)


# ── Bot command handlers ──────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = update.effective_user.first_name or "there"
    await update.message.reply_html(
        f"👋 Hello <b>{name}</b>! I'm the GM Customer Search Bot.\n\n"
        "Send me any value to search across the customer sheet:\n"
        "  • First or last name\n"
        "  • Email address\n"
        "  • Phone number\n"
        "  • Campaign name\n"
        "  • Notes keyword\n\n"
        "I'll return the full record for every match.\n\n"
        "<b>Commands:</b>\n"
        "  /search &lt;value&gt; — explicit search\n"
        "  /columns — show column headers\n"
        "  /help — this message"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(
        "🔎 <b>Search tips:</b>\n\n"
        "• Just <b>type any value</b> and send — no command needed\n"
        "• Searches are <b>partial &amp; case-insensitive</b>\n"
        "  (e.g. <code>joe</code> matches <i>Joe</i>, <i>Joel</i>, <i>joearms@…</i>)\n"
        "• All 6 columns are searched at once\n\n"
        "Use /columns to see what's available."
    )


async def cmd_columns(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        headers, rows = fetch_all_data()
        if not headers:
            await update.message.reply_text("⚠️ The sheet appears to be empty.")
            return
        col_list = "\n".join(f"  {i+1}. {h}" for i, h in enumerate(headers))
        row_count = len(rows)
        await update.message.reply_html(
            f"📋 <b>Columns in GM-Customer-Details:</b>\n\n{col_list}\n\n"
            f"📊 Total customer records: <b>{row_count}</b>"
        )
    except Exception as e:
        logger.exception("Error fetching columns")
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "Usage: /search <value>\nExample: /search Joe"
        )
        return
    query = " ".join(context.args)
    await run_search(update, query)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.message.text.strip()
    if query:
        await run_search(update, query)


async def run_search(update: Update, query: str) -> None:
    status = await update.message.reply_text(f'\U0001f50d Searching for "{query}"\u2026')
    try:
        headers, matches = search_sheet(query)
        reply = format_results(headers, matches, query)

        if len(reply) <= 4096:
            await status.edit_text(reply, parse_mode="HTML")
        else:
            await status.delete()
            for chunk in [reply[i:i+4000] for i in range(0, len(reply), 4000)]:
                await update.message.reply_html(chunk)

    except FileNotFoundError as e:
        await status.edit_text(f"❌ {e}")
    except HttpError as e:
        logger.error("Sheets API error: %s", e)
        await status.edit_text(
            "❌ Google Sheets API error.\n"
            "Check that the sheet is shared and the API is enabled."
        )
    except Exception as e:
        logger.exception("Unexpected error")
        await status.edit_text(f"❌ Unexpected error: {e}")


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    logger.info("Starting GsheetSearchBot…")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("columns", cmd_columns))
    app.add_handler(CommandHandler("search",  cmd_search))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Bot is running. Press Ctrl+C to stop.")

    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("Bot is polling. Press Ctrl+C to stop.")

    # Keep running until Ctrl+C
    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")