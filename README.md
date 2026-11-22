# Zuno Telegram Bot

A lightweight Python Telegram bot using **TeleBot (pyTelegramBotAPI)**. A user starts the bot, sends their GitHub username, and the bot automatically requests read-only access to the private `Zuno-inc/Zuno` repository through a GitHub App.

## Flow

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

## Requirements

- Python 3.11+
- Telegram bot token from BotFather
- GitHub App installed on `Zuno-inc/Zuno`
- GitHub App ID, private key, and installation ID

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
python -m src.main
```

The bot uses Telegram long polling; no webhook or public web service is needed.

## Render deployment

Deploy as a **Background Worker**. Set these environment variables in Render:

- `BOT_TOKEN`
- `GITHUB_APP_ID`
- `GITHUB_PRIVATE_KEY`
- `GITHUB_INSTALLATION_ID`
- `GITHUB_OWNER=Zuno-inc`
- `GITHUB_REPO=Zuno`
- `PROJECT_URL=https://zuno-com.onrender.com/` (optional)

No persistent disk or database is required. The worker uses memory only.

Never commit real tokens or private keys. For `GITHUB_PRIVATE_KEY`, use a multiline PEM value or literal `\\n` line breaks; the application converts literal `\\n` sequences to newlines.
