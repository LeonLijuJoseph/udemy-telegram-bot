from telegram.ext import (Updater, CommandHandler, ConversationHandler, MessageHandler, Filters, CallbackContext)
import os
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from data_source import DataSource
import threading
import time
import datetime
import logging
import sys

MODE = os.getenv("MODE")

API_KEY = os.getenv('API_KEY')
ENTER_MESSAGE, ENTER_TIME = range(2)
ADD_REMINDER_TEXT = 'Add a reminder ⏰'
INTERVAL = 30

dataSource = DataSource(os.environ.get('DATABASE_URL'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

if MODE == "dev":
    def run():
        logger.info("Start in DEV mode")
        updater.start_polling()
elif MODE == "prod":
    def run():
        logger.info("Start in PROD mode")
        updater.start_webhook(listen="0.0.0.0", port=int(os.getenv("PORT", "8443")), url_path=API_KEY,
                              webhook_url="https://{}.herokuapp.com/{}".format(os.environ.get("APP_NAME"), API_KEY))
else:
    logger.error("No mode specified!")
    sys.exit(1)


def start_handler(update, context):
    update.message.reply_text("Hello Leon", reply_markup=add_reminder_button())


def add_reminder_button():
    keyboard = [[KeyboardButton(ADD_REMINDER_TEXT)]]
    return ReplyKeyboardMarkup(keyboard)


def add_reminder_handler(update: Update, context: CallbackContext):
    update.message.reply_text("Please enter the reminder name")
    return ENTER_MESSAGE


def enter_message_handler(update: Update, context: CallbackContext):
    update.message.reply_text("Please enter a time for the reminder")
    context.user_data["message_text"] = update.message.text
    return ENTER_TIME


def enter_time_handler(update: Update, context: CallbackContext):
    message_text = context.user_data["message_text"]
    time = datetime.datetime.strptime(update.message.text, "%d/%m/%Y %H:%M")
    message_data = dataSource.create_reminder(update.message.chat_id, message_text, time)
    update.message.reply_text("Your reminder: " + message_data.__repr__())
    return ConversationHandler.END


def start_check_reminders_task():
    thread = threading.Thread(target=check_reminders, args=())
    thread.daemon = True
    thread.start()


def check_reminders():
    while True:
        for reminder_data in dataSource.get_all_reminders():
            if reminder_data.should_be_fired():
                dataSource.fire_reminder(reminder_data.reminder_id)
                updater.bot.send_message(reminder_data.chat_id, reminder_data.message)
        time.sleep(INTERVAL)



if __name__ == '__main__':
    updater = Updater(API_KEY, use_context=True)
    updater.dispatcher.add_handler(CommandHandler("start", start_handler))
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex(ADD_REMINDER_TEXT), add_reminder_handler)],
        states={
            ENTER_MESSAGE: [MessageHandler(Filters.all, enter_message_handler)],
            ENTER_TIME: [MessageHandler(Filters.all, enter_time_handler)]
        },
        fallbacks=[]
    )

    updater.dispatcher.add_handler(conv_handler)
    dataSource.create_tables()
    run()
    start_check_reminders_task()
