# Zuno Telegram Bot

A lightweight Python Telegram bot using **TeleBot (pyTelegramBotAPI)**. A user starts the bot, sends their GitHub username, and the bot automatically requests read-only access to the private `Zuno-inc/Zuno` repository through a GitHub App.

## User flow

1. The user sends `/start`.
2. The bot greets them and asks for their GitHub username.
3. The user sends the username.
4. The bot calls GitHub and requests collaborator permission `pull`.
5. The bot tells the user whether an invitation was created or access already exists.

No application database, SQLite file, admin approval queue, or persistent request storage is used. The bot keeps only short-lived conversation state and rate-limit data in memory; this resets when the process restarts.

## Important GitHub behavior

When GitHub returns HTTP 201, it has created an invitation. The recipient must still accept that invitation in GitHub before repository access becomes active. HTTP 204 means the account already has access.

The bot trusts the GitHub username supplied in Telegram. It does not verify that the Telegram user owns that GitHub account. Anyone who knows another person's GitHub username could submit it, so this fully automatic flow should only be used if that risk is acceptable.

The GitHub App needs **Repository permissions → Administration: Read and write** for GitHub's collaborator invitation endpoint, even though this bot requests only `pull` access for each user. Install the App only on `Zuno-inc/Zuno`, not on all repositories. The resulting collaborator permission requested by the bot is read-only.

Private repository forking must be enabled in the Zuno organization/repository settings if contributors are expected to fork privately and open Pull Requests.

## Render deployment (free Web Service + Telegram webhook)

This repository is configured as a Render **Web Service**, not a Background Worker. Telegram sends updates to the HTTPS webhook endpoint at `/telegram`. The service exposes `/healthz` for health checks.

1. In Render, choose **New → Blueprint**, connect this GitHub repository, and apply the `render.yaml` blueprint.
2. In the service's Environment settings, add the required secrets:
   - `BOT_TOKEN`
   - `GITHUB_APP_ID`
   - `GITHUB_PRIVATE_KEY`
   - `GITHUB_INSTALLATION_ID`
3. Render automatically generates `WEBHOOK_SECRET` from the Blueprint. The app detects the public service URL through Render's `RENDER_EXTERNAL_URL` variable and registers `https://YOUR-SERVICE.onrender.com/telegram` with Telegram at startup. You do not need to enter `WEBHOOK_URL` manually.

Also set `GITHUB_OWNER=Zuno-inc` and `GITHUB_REPO=Zuno` (already supplied by the Blueprint), and optionally `PROJECT_URL`.

**Free-tier caveat:** Render's free Web Services can spin down after inactivity and may take time to wake up. Telegram will retry webhook deliveries when it does not receive a successful response, but delivery can be delayed. This is not an always-on service.

Do not run a second polling instance of this bot while the webhook is active. Never paste secrets into chat or commit them to GitHub.

## Local development

Install dependencies with `pip install -r requirements.txt`. To run the existing long-polling entry point locally, set the Telegram and GitHub App variables in your local `.env` file and run:

```bash
python -m src.main
```

For local webhook testing, expose the Flask app in `src.webhook:app` through an HTTPS tunnel and set `WEBHOOK_URL` and `WEBHOOK_SECRET` accordingly.

## Requirements

- Python 3.11+
- Telegram bot token from BotFather
- GitHub App installed on `Zuno-inc/Zuno`
- GitHub App ID, private key, and installation ID

For `GITHUB_PRIVATE_KEY`, use a multiline PEM value or literal `\\n` line breaks; the application converts literal `\\n` sequences to newlines.
