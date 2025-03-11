import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, CallbackContext
import datetime
import requests
import pandas as pd

# Telegram Bot Config
TOKEN = "7868047897:AAG1Fk3bcJQteZDD8mhj3tzqdyNrKJSdr98"
CHANNEL_USERNAME = "@ntutc_shed_bot"  # Your Telegram channel where logs are posted

# Google Sheets Setup
SPREADSHEET_ID = "1LUImOcGIkUa3r_8pssFkRay_f47nY8EqUzlK07cS4Kw"
SHEET_NAME = "ShedLogAY2425"

# Suggested purposes
SUGGESTED_PURPOSES = ["Weekly sessions"]

# User state tracking for purpose input
user_states = {}

# Authenticate Google Sheets
def authenticate_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_name("google_credentials.json", scope)
    client = gspread.authorize(credentials)
    return client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

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

    action = user_states.pop(user_id)  # Retrieve and remove user action

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

# Main Function
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(action_selected, pattern="^(open|close)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_entry))

    app.run_polling()

if __name__ == '__main__':
    main()