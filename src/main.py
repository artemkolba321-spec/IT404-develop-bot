import logging
import os
import re
import time

from dotenv import load_dotenv

load_dotenv()

import telebot

from src.github_api import invite_read_only_collaborator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("zuno-bot")

for key in ("BOT_TOKEN", "GITHUB_APP_ID", "GITHUB_PRIVATE_KEY", "GITHUB_INSTALLATION_ID"):
    if not os.getenv(key):
        raise RuntimeError(f"Missing required environment variable: {key}")

bot = telebot.TeleBot(os.environ["BOT_TOKEN"], parse_mode=None)
waiting_for_github = set()
last_request_at = {}
USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
REQUEST_COOLDOWN_SECONDS = 30


def ask_for_username(chat_id, user_id):
    waiting_for_github.add(user_id)
    bot.send_message(
        chat_id,
        "Welcome to Zuno! 👋\n\n"
        "Send your GitHub username and I’ll automatically request read-only "
        "access to the Zuno repository.",
    )


@bot.message_handler(commands=["start", "access"])
def start_or_access(message):
    ask_for_username(message.chat.id, str(message.from_user.id))


@bot.message_handler(commands=["help"])
def help_command(message):
    bot.send_message(
        message.chat.id,
        "Send /start and then your GitHub username to receive an automatic "
        "read-only access invitation.\n"
        "Use /rules to read the contributor guidelines.",
    )


@bot.message_handler(commands=["rules"])
def rules(message):
    project_url = os.getenv("PROJECT_URL", "https://zuno-com.onrender.com/")
    bot.send_message(
        message.chat.id,
        "Zuno contributor rules:\n\n"
        "1. Access is read-only: make changes in your own fork.\n"
        "2. Submit your changes through a Pull Request.\n"
        "3. Never commit tokens, passwords, secrets, or private user data.\n"
        "4. Be respectful and explain your changes clearly.\n\n"
        f"Project: {project_url}",
    )


@bot.message_handler(content_types=["text"], func=lambda message: not (message.text or "").startswith("/"))
def receive_github_username(message):
    telegram_id = str(message.from_user.id)
    if telegram_id not in waiting_for_github:
        return

    username = (message.text or "").strip().removeprefix("@")
    if not USERNAME_RE.fullmatch(username):
        bot.send_message(
            message.chat.id,
            "That username format doesn’t look valid. Send your GitHub username "
            "using letters, numbers, or hyphens, or use /start to try again.",
        )
        return

    now = time.monotonic()
    previous = last_request_at.get(telegram_id, 0)
    if now - previous < REQUEST_COOLDOWN_SECONDS:
        remaining = int(REQUEST_COOLDOWN_SECONDS - (now - previous))
        bot.send_message(message.chat.id, f"Please wait {remaining} seconds before trying again.")
        return

    waiting_for_github.discard(telegram_id)
    last_request_at[telegram_id] = now
    bot.send_message(message.chat.id, f"Thanks! Contacting GitHub for @{username}…")

    try:
        result = invite_read_only_collaborator(username)
        if result["invitation_created"]:
            bot.send_message(
                message.chat.id,
                f"✅ GitHub invitation sent to @{username} for the Zuno repository.\n\n"
                "Please accept the invitation in your GitHub notifications or email. "
                "Your access will be read-only (pull). You can then fork the project "
                "and contribute through Pull Requests.",
            )
        else:
            bot.send_message(
                message.chat.id,
                f"✅ The GitHub account @{username} already has access to Zuno. "
                "You can contribute through Pull Requests.",
            )
    except Exception:
        log.exception("Could not invite GitHub user %s", username)
        bot.send_message(
            message.chat.id,
            "❌ GitHub could not create the invitation. Check that the username "
            "is correct, then use /start to try again later. If the problem "
            "continues, contact the Zuno maintainers.",
        )


def main():
    log.info("Zuno Telegram bot is starting (long polling).")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)


if __name__ == "__main__":
    main()
