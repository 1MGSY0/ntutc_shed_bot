import os
import json
import datetime
import logging
import gspread
import asyncio 
import uvicorn
import base64
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    CallbackContext,
)
from quart import Quart, request, jsonify  

# Load environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")
PROJECT_ID = os.environ.get("PROJECT_ID")
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME")
TOPIC_THREAD_ID = os.getenv("TOPIC_THREAD_ID")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(PROJECT_ID)

# Telegram Bot Setup
application = ApplicationBuilder().token(TOKEN).build()

# Flask Setup
app = Quart(__name__)

# Suggested purposes
SUGGESTED_PURPOSES = ["Weekly sessions"]

# User state tracking
user_states = {}

# Google Sheets Setup
def authenticate_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    logger = logging.getLogger(PROJECT_ID)

    try:
        decoded_json = base64.b64decode(GOOGLE_CREDENTIALS_JSON).decode("utf-8")
        creds_dict = json.loads(decoded_json)
        print("Decoded preview:", decoded_json[:100])
    except Exception as e:
        logger.error("❌ Failed to decode GOOGLE_CREDENTIALS_JSON: %s", e)
        creds_dict = {}
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(credentials)
    return client.open_by_key(SPREADSHEET_ID).sheet1

# Telegram Handlers
async def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Open & Close", callback_data='open & close')],
        [InlineKeyboardButton("Open", callback_data='open')],
        [InlineKeyboardButton("Close", callback_data='close')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select your action:", reply_markup=reply_markup)

async def action_selected(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    action = query.data.capitalize()
    user_states[query.from_user.id] = {"action": action}

    keyboard = [[purpose] for purpose in SUGGESTED_PURPOSES]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await query.message.reply_text(f"Enter purpose of {action} Shed:", reply_markup=reply_markup)

async def purpose_entered(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    purpose = update.message.text.strip()

    if user_id not in user_states:
        await update.message.reply_text("❌ Please start the process again using /start.")
        return

    user_states[user_id]["purpose"] = purpose

    keyboard = [
    [InlineKeyboardButton(f"{hour + i:02}", callback_data=f"hour_{hour + i}") for i in range(6)]
    for hour in range(0, 24, 6)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🕒 Select the time *hour* (24-hour format):", parse_mode="Markdown", reply_markup=reply_markup)

async def hour_selected(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    hour = int(query.data.split("_")[1])
    user_states[query.from_user.id]["hour"] = hour

    keyboard = [
        [InlineKeyboardButton(f"{m:02}", callback_data=f"minute_{m}") for m in range(row, row + 30, 5)]
        for row in range(0, 60, 30)
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("⏳ Select the time *minutes*:", parse_mode="Markdown", reply_markup=reply_markup)

async def minute_selected(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    minute = int(query.data.split("_")[1])
    state = user_states[user_id]

    action = state["action"]
    purpose = state["purpose"]
    hour = state["hour"]
    action_time = f"{hour:02}:{minute:02}"
    now = datetime.datetime.now()
    date = now.strftime("%Y-%m-%d")
    submitted_at = now.strftime("%Y-%m-%d %H:%M:%S")

    try:
        sheet = authenticate_google_sheets()
        log_message = (
            f"Shed Activity Log\n"
            f"👤 {query.from_user.username or query.from_user.full_name}\n"
            f"📌 {action}\n"
            f"🎯 {purpose}\n"
            f"🕒 {action_time}"
        )
        chat_id = int(CHANNEL_USERNAME) if CHANNEL_USERNAME.startswith("-") else CHANNEL_USERNAME
        if TOPIC_THREAD_ID:
            await context.bot.send_message(chat_id=chat_id, text=log_message, message_thread_id=int(TOPIC_THREAD_ID))
        else:
            await context.bot.send_message(chat_id=chat_id, text=log_message)

        sheet.append_row([
            query.from_user.username or query.from_user.full_name,
            action, purpose, date, action_time, submitted_at,
            str(query.message.message_id if query.message else "N/A")
        ])
        await query.message.reply_text(f"✅ {action} shed for '{purpose}' at {action_time}.")
        del user_states[user_id]
    except Exception as e:
        logger.error(f"Google Sheets Error: {e}")
        await query.message.reply_text("❌ Error logging data. Try again later.")

async def guideline(update: Update, context: CallbackContext) -> None:
    guideline_text = (
        "Please read the guideline for the shed usage.\n\n"
        "These guidelines ensure the responsible and secure use of the SRC tennis court shed. "
        "Compliance is mandatory for all authorized users.\n\n"
        "SHED USAGE GUIDELINE: "
        "https://docs.google.com/document/d/1-lut9Nqr645IN6kR7awaQG4txnc8U-Vh3uoJg5xcRgM/edit?usp=sharing"
    )
    await update.message.reply_text(guideline_text)

#Set bot commands
async def set_bot_commands(application):
    commands = [
        BotCommand("start", "Start the shed usage logger"),
        BotCommand("guideline", "View shed usage guidelines"),
    ]
    await application.bot.set_my_commands(commands)

async def start_bot():
    print("Starting Telegram bot...")
    await application.initialize()
    await application.start()
    await asyncio.Event().wait()

#Temporary functions for obtaining chat_id and message_thread_id
# async def debug_log_ids(update: Update, context: CallbackContext):
#     if update.message:
#         print("Chat ID:", update.effective_chat.id)
#         print("Message Thread ID:", update.message.message_thread_id)

# application.add_handler(MessageHandler(filters.ALL, debug_log_ids))

#Register Handlers once
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("guideline", guideline))
application.add_handler(CallbackQueryHandler(action_selected, pattern="^(open|close|open & close)$"))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, purpose_entered))
application.add_handler(CallbackQueryHandler(hour_selected, pattern="^hour_\\d+$"))
application.add_handler(CallbackQueryHandler(minute_selected, pattern="^minute_\\d+$"))


@app.route(f"/{TOKEN}", methods=["POST"])
async def telegram_webhook():
    data = await request.get_json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return "OK"


#Health check endpoint
@app.route("/health", methods=["GET"])
async def health():
    return jsonify({"status": "Bot is running"}), 200


if __name__ == "__main__":

    async def run_all():
        await application.initialize()
        await set_bot_commands(application)
        await application.start()
        print("✅ Bot initialized and handlers registered.")

        config = uvicorn.Config(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
        server = uvicorn.Server(config)
        await server.serve()

    asyncio.run(run_all())


