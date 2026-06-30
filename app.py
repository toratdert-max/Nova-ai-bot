import os
import logging
import asyncio
from collections import defaultdict, deque

from flask import Flask
from threading import Thread

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import google.generativeai as genai


# =======================
# CONFIG
# =======================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN is not set")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set")

genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-1.5-flash"

model = genai.GenerativeModel(MODEL_NAME)

# =======================
# LOGGING
# =======================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =======================
# MEMORY (per user)
# =======================
user_memory = defaultdict(lambda: deque(maxlen=10))

# =======================
# FLASK HEALTH CHECK
# =======================
app = Flask(__name__)

@app.get("/")
def home():
    return "Bot is alive", 200

def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

# =======================
# GEMINI FUNCTION
# =======================
async def ask_gemini(user_id: int, text: str) -> str:
    history = user_memory[user_id]

    context = "\n".join(history)
    prompt = f"""
Ты Telegram-бот. Отвечай кратко и понятно.

История диалога:
{context}

Пользователь:
{text}
"""

    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return "Ошибка Gemini API. Попробуй позже."


# =======================
# COMMANDS
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот на Gemini API.\nНапиши сообщение, и я отвечу."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start - запуск\n"
        "/help - помощь\n\n"
        "Просто напиши сообщение, и я отвечу через Gemini."
    )


# =======================
# MESSAGE HANDLER
# =======================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    user_memory[user_id].append(f"User: {text}")

    response = await ask_gemini(user_id, text)

    user_memory[user_id].append(f"Bot: {response}")

    await update.message.reply_text(response)


# =======================
# MAIN
# =======================
def main():
    # start flask in background
    Thread(target=run_flask).start()

    app_bot = Application.builder().token(TELEGRAM_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("help", help_command))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is running...")
    app_bot.run_polling()


if __name__ == "__main__":
    main()
