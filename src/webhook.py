import hmac
import logging
import os

from flask import Flask, abort, request
import telebot

from src.main import bot

log = logging.getLogger("zuno-webhook")
app = Flask(__name__)

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

if not WEBHOOK_URL:
    raise RuntimeError("Missing required environment variable: WEBHOOK_URL")
if not WEBHOOK_SECRET:
    raise RuntimeError("Missing required environment variable: WEBHOOK_SECRET")

# Register this Render service as the Telegram webhook on startup.
bot.set_webhook(url=WEBHOOK_URL, secret_token=WEBHOOK_SECRET)
log.info("Telegram webhook configured.")


@app.get("/healthz")
def healthcheck():
    return {"status": "ok"}, 200


@app.post("/telegram")
def telegram_webhook():
    supplied_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(supplied_secret, WEBHOOK_SECRET):
        abort(403)

    try:
        update = telebot.types.Update.de_json(request.get_data(as_text=True))
        bot.process_new_updates([update])
    except Exception:
        log.exception("Failed to process Telegram webhook update.")
        return {"status": "error"}, 500

    return {"status": "ok"}, 200
