import logging
import os
import re
import time

import telebot
from dotenv import load_dotenv

from src import database as db
from src.github_api import invite_read_only_collaborator

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("it404-bot")

required = ("BOT_TOKEN", "ADMIN_TELEGRAM_IDS")
for key in required:
    if not os.getenv(key):
        raise RuntimeError(f"Missing required environment variable: {key}")

admins = {
    item.strip()
    for item in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",")
    if item.strip()
}
bot = telebot.TeleBot(os.environ["BOT_TOKEN"], parse_mode=None)
waiting_for_github = set()
last_request_at = {}
USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")

MAIN_KEYBOARD = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
MAIN_KEYBOARD.row("/access", "/status")
MAIN_KEYBOARD.row("/rules", "/help")


def is_admin(user_id):
    return str(user_id) in admins


def admin_only(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "This command is for maintainers only.")
        return False
    return True


@bot.message_handler(commands=["start"])
def start(message):
    waiting_for_github.discard(str(message.from_user.id))
    bot.send_message(
        message.chat.id,
        "Welcome to the Zuno Developer Bot!\n\n"
        "Use /access to request read-only access to the private Zuno repository. "
        "A maintainer will review your request.",
        reply_markup=MAIN_KEYBOARD,
    )


@bot.message_handler(commands=["help"])
def help_command(message):
    bot.send_message(
        message.chat.id,
        "Commands:\n"
        "/access — request repository access\n"
        "/status — check your latest request\n"
        "/rules — contributor rules\n"
        "/help — show this help\n\n"
        "Maintainers: /pending, /approve REQUEST_ID, /reject REQUEST_ID",
        reply_markup=MAIN_KEYBOARD,
    )


@bot.message_handler(commands=["rules"])
def rules(message):
    project_url = os.getenv("PROJECT_URL", "https://zuno-com.onrender.com/")
    bot.send_message(
        message.chat.id,
        "Zuno contributor rules:\n\n"
        "1. Access is read-only. Do not expect direct push access.\n"
        "2. Make changes in your own fork and submit a Pull Request.\n"
        "3. Keep PRs focused and explain what you changed.\n"
        "4. Never commit secrets, tokens, passwords, or private user data.\n"
        "5. Be respectful and follow the project license.\n\n"
        f"Project: {project_url}",
        reply_markup=MAIN_KEYBOARD,
    )


@bot.message_handler(commands=["access"])
def access(message):
    waiting_for_github.add(str(message.from_user.id))
    bot.send_message(
        message.chat.id,
        "Please send your GitHub username (for example: octocat).\n\n"
        "The maintainer will review the request. If approved, GitHub will send "
        "an invitation to that GitHub account with read-only access.",
    )


@bot.message_handler(commands=["status"])
def status(message):
    request = db.get_latest_for_telegram(message.from_user.id)
    if not request:
        bot.send_message(
            message.chat.id,
            "You have not submitted an access request yet. Use /access to begin.",
        )
        return
    labels = {
        "pending": "Waiting for maintainer review.",
        "approved": "GitHub invitation request sent. Check GitHub notifications/email and accept it.",
        "rejected": "Your request was declined. Contact a maintainer if you think this is a mistake.",
    }
    bot.send_message(
        message.chat.id,
        f"Request #{request['id']} for GitHub user @{request['github_username']}\n"
        f"Status: {labels.get(request['status'], request['status'])}",
    )


@bot.message_handler(commands=["pending"])
def pending(message):
    if not admin_only(message):
        return
    requests = db.list_pending()
    if not requests:
        bot.send_message(message.chat.id, "There are no pending requests.")
        return
    lines = [
        f"#{item['id']} — @{item['github_username']} (Telegram ID: {item['telegram_id']})"
        for item in requests
    ]
    bot.send_message(
        message.chat.id,
        "Pending requests:\n" + "\n".join(lines)
        + "\n\nApprove with /approve ID or reject with /reject ID.",
    )


@bot.message_handler(commands=["approve"])
def approve(message):
    if not admin_only(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        bot.send_message(message.chat.id, "Usage: /approve REQUEST_ID")
        return
    request_id = int(parts[1])
    request = db.get_request(request_id)
    if not request:
        bot.send_message(message.chat.id, "Request not found.")
        return
    if request["status"] != "pending":
        bot.send_message(message.chat.id, f"Request is already {request['status']}.")
        return
    try:
        result = invite_read_only_collaborator(request["github_username"])
        db.set_status(request_id, "approved", message.from_user.id, invitation_sent=True)
        bot.send_message(
            message.chat.id,
            f"GitHub accepted the invitation request for @{request['github_username']}. "
            f"Permission requested: pull (read-only). HTTP {result['status']}.",
        )
        try:
            bot.send_message(
                request["telegram_id"],
                f"Your request was approved. GitHub has sent an invitation to "
                f"@{request['github_username']}. Please accept it on GitHub.\n\n"
                "You have read-only access; submit changes through Pull Requests.",
            )
        except Exception:
            log.exception("Could not notify requester for request #%s", request_id)
    except Exception as exc:
        log.exception("GitHub invitation failed for request #%s", request_id)
        bot.send_message(message.chat.id, f"Could not send the invitation: {exc}")


@bot.message_handler(commands=["reject"])
def reject(message):
    if not admin_only(message):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        bot.send_message(message.chat.id, "Usage: /reject REQUEST_ID")
        return
    request_id = int(parts[1])
    request = db.get_request(request_id)
    if not request:
        bot.send_message(message.chat.id, "Request not found.")
        return
    if request["status"] != "pending":
        bot.send_message(message.chat.id, f"Request is already {request['status']}.")
        return
    db.set_status(request_id, "rejected", message.from_user.id)
    bot.send_message(message.chat.id, f"Request #{request_id} rejected.")
    try:
        bot.send_message(
            request["telegram_id"],
            "Your Zuno repository access request was declined. "
            "You can contact a maintainer for more information.",
        )
    except Exception:
        log.exception("Could not notify requester for rejected request #%s", request_id)


@bot.message_handler(content_types=["text"], func=lambda message: not (message.text or "").startswith("/"))
def collect_github_username(message):
    telegram_id = str(message.from_user.id)
    if telegram_id not in waiting_for_github:
        return
    waiting_for_github.discard(telegram_id)

    now = time.monotonic()
    if now - last_request_at.get(telegram_id, 0) < 60:
        bot.send_message(message.chat.id, "Please wait a minute before submitting another request.")
        return

    username = (message.text or "").strip().removeprefix("@")
    if not USERNAME_RE.fullmatch(username):
        bot.send_message(
            message.chat.id,
            "That does not look like a valid GitHub username. Use /access to try again.",
        )
        return

    last_request_at[telegram_id] = now
    try:
        request = db.create_request(
            telegram_id,
            message.from_user.username,
            username,
        )
        bot.send_message(
            message.chat.id,
            f"Request #{request['id']} submitted for @{username}. "
            "A maintainer will review it. Use /status to check progress.",
        )
        for admin_id in admins:
            try:
                bot.send_message(
                    admin_id,
                    f"New Zuno access request #{request['id']}\n"
                    f"GitHub: @{username}\nTelegram ID: {telegram_id}\n"
                    f"Approve: /approve {request['id']}\nReject: /reject {request['id']}",
                )
            except Exception:
                log.exception("Could not notify admin %s", admin_id)
    except Exception:
        log.exception("Could not save access request")
        bot.send_message(
            message.chat.id,
            "Sorry, I could not save your request. Please try again later.",
        )


def main():
    db.init_db()
    log.info("IT404 Develop Bot is starting (long polling).")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)


if __name__ == "__main__":
    main()
