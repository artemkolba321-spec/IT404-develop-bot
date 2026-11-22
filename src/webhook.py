import hashlib
import hmac
import logging
import os

from flask import Flask, abort, request
import telebot

from src.main import bot

log = logging.getLogger("zuno-webhook")
app = Flask(__name__)

# Render provides RENDER_EXTERNAL_URL automatically for Web Services.
# WEBHOOK_URL can override it for local testing or a custom domain.
service_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip() or (
    f"{service_url}/telegram" if service_url else ""
)
raw_webhook_secret = os.getenv("WEBHOOK_SECRET", "")
if not WEBHOOK_URL:
    raise RuntimeError(
        "Could not determine webhook URL. Set WEBHOOK_URL or deploy as a Render Web Service."
    )
if not raw_webhook_secret:
    raise RuntimeError("Missing required environment variable: WEBHOOK_SECRET")

# Telegram accepts only URL-safe characters in secret_token. Hashing also
# normalizes any generated secret into a fixed-length, valid token.
WEBHOOK_SECRET = hashlib.sha256(raw_webhook_secret.encode("utf-8")).hexdigest()

# Register this Render service as the Telegram webhook on startup.
bot.set_webhook(url=WEBHOOK_URL, secret_token=WEBHOOK_SECRET)
log.info("Telegram webhook configured at %s", WEBHOOK_URL)


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
