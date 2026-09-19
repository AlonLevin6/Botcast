"""
Telegram front-end for the Daily Commute Podcast Bot.

Send the bot any text message with a topic, and it replies with a
generated MP3 podcast on that topic. Reuses the same generate_script /
synthesize_audio functions as the CLI script (podcast.py). Every
generated episode is kept in podcasts/ and indexed in podcasts/index.db,
and the bot attaches thumbs up/down buttons to collect feedback.

Requires TELEGRAM_BOT_TOKEN in .env (create a bot via @BotFather).
Optionally set ALLOWED_TELEGRAM_USER_ID in .env to restrict the bot to
a single Telegram user (recommended, since anyone who finds the bot
can otherwise burn through your free API quota).
"""

import asyncio
import logging
import os

from dotenv import load_dotenv
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from podcast import create_episode, generate_script, set_rating, synthesize_audio

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# httpx logs full request URLs at INFO level, which include the bot token
# (Telegram's API embeds it in the URL path) - keep it quiet.
logging.getLogger("httpx").setLevel(logging.WARNING)

ALLOWED_USER_ID = os.environ.get("ALLOWED_TELEGRAM_USER_ID")

# Catches accidental greetings ("Hello" sent to test the bot) so they don't
# turn into a pointless podcast about "hello".
GREETINGS = {"hi", "hello", "hey", "yo", "sup", "hola", "test", "start"}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Send me any topic (e.g. \"the history of espresso\") and I'll generate "
        "a short podcast about it."
    )


async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)

    if ALLOWED_USER_ID and user_id != ALLOWED_USER_ID:
        logger.warning("Rejected message from unauthorized user_id=%s", user_id)
        await update.message.reply_text("Sorry, this bot is private.")
        return

    topic = update.message.text.strip()
    if not topic:
        return

    if topic.lower().strip("!.? ") in GREETINGS:
        await update.message.reply_text(
            "That looks like a greeting, not a topic! Send me something like "
            "\"the history of espresso\" and I'll make a podcast about it."
        )
        return

    status = await update.message.reply_text("Writing script...")

    try:
        script = await asyncio.to_thread(generate_script, topic)

        await status.edit_text("Recording audio...")
        episode_id, _, audio_path = create_episode(topic, script)
        await synthesize_audio(script, audio_path)

        await status.edit_text("Uploading...")
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("\U0001F44D", callback_data=f"rate:{episode_id}:up"),
                    InlineKeyboardButton("\U0001F44E", callback_data=f"rate:{episode_id}:down"),
                ]
            ]
        )
        with open(audio_path, "rb") as audio_file:
            await update.message.reply_audio(
                audio=audio_file, title=topic[:60], reply_markup=keyboard
            )

        await status.delete()

    except Exception:
        logger.exception("Failed to generate podcast for topic=%r", topic)
        await status.edit_text("Something went wrong generating that podcast. Try again?")


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    _, episode_id, rating = query.data.split(":")
    set_rating(int(episode_id), rating)

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("Thanks for the feedback!")


async def post_init(app: Application) -> None:
    await app.bot.set_my_commands([BotCommand("start", "How to use this bot")])
    await app.bot.set_my_description(
        "Send me any topic (e.g. \"the history of espresso\") and I'll write a "
        "short script and record it as a podcast for you to listen to."
    )
    await app.bot.set_my_short_description("Send a topic, get back a podcast.")


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN environment variable.")

    app = Application.builder().token(token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_feedback, pattern=r"^rate:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic))

    logger.info("Bot starting (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
