import os
import json
import datetime
import logging
import gspread
from flask import Flask, request
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, filters, CallbackContext, Application, AIORateLimiter, ExtBot

# Load environment variables (Cloud Run doesn’t store local files)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

# Set up Flask app
app = Flask(__name__)

# Google Sheets Authentication
def authenticate_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(credentials)
    return client.open_by_key(SPREADSHEET_ID).sheet1

# Suggested purposes
SUGGESTED_PURPOSES = ["Weekly sessions"]

# User state tracking for purpose input
user_states = {}

# Initialize Telegram bot
bot = ExtBot(token=TOKEN)
dispatcher = Dispatcher(bot=bot, update_queue=None, use_context=True, rate_limiter=AIORateLimiter())

# Start Command
async def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Open Shed", callback_data='open')],
        [InlineKeyboardButton("Close Shed", callback_data='close')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome! Select an option:", reply_markup=reply_markup)

# Handle Shed Open/Close Selection and Ask for Purpose
async def action_selected(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    action = query.data.capitalize()

    # Store action in user state
    user_states[query.from_user.id] = action

    # Show suggested purposes with a reply keyboard
    keyboard = [[purpose] for purpose in SUGGESTED_PURPOSES]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await query.message.reply_text(f"Please enter the purpose for {action}:\n(You can type your own or choose a suggestion below)", reply_markup=reply_markup)

# Log Entry and Send to Telegram Channel
async def log_entry(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user = update.message.from_user.username or update.message.from_user.full_name
    purpose = update.message.text.strip()

    if user_id not in user_states:
        await update.message.reply_text("❌ Please start the process again using /start.")
        return

    action = user_states.pop(user_id)

    now = datetime.datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")
    submitted_at = now.strftime("%Y-%m-%d %H:%M:%S")

    try:
        sheet = authenticate_google_sheets()

        # Send log message to the Telegram Channel
        log_message = (
            f"📌 *Shed Activity Log*\n"
            f"👤 *User:* {user}\n"
            f"📌 *Action:* {action}\n"
            f"🎯 *Purpose:* {purpose}\n"
            f"🕒 *Time:* {submitted_at}"
        )

        message = await context.bot.send_message(chat_id=CHANNEL_USERNAME, text=log_message, parse_mode="Markdown")

        # Store log entry in Google Sheets
        sheet.append_row([user, action, purpose, date, time, submitted_at, str(message.message_id)])

        await update.message.reply_text(f"✅ {action} logged for '{purpose}' at {time}.")
    except Exception as e:
        await update.message.reply_text("❌ Error logging data. Try again later.")
        print("Google Sheets Error:", e)

# Webhook route for Telegram updates
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(), bot)
    dispatcher.process_update(update)
    return "OK", 200

# Health check route for UptimeRobot
@app.route("/")
def index():
    return "Bot is running!", 200

# Run Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
