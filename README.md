# IT404 Develop Bot

A Python Telegram bot using **TeleBot (pyTelegramBotAPI)** to manage requests for read-only access to the private `Zuno-inc/Zuno` GitHub repository.

## Features

- `/start`, `/help`, `/rules`
- `/access`: collect a GitHub username and create a pending request
- `/status`: show the user's latest request status
- Maintainer-only `/pending`, `/approve ID`, and `/reject ID`
- GitHub App invitations request **pull** permission only
- SQLite storage using Python's built-in `sqlite3`

Requests are reviewed by a maintainer before an invitation is sent. The bot does not grant write or admin access.

## Requirements

- Python 3.11+
- A Telegram bot token from BotFather
- A GitHub App installed on `Zuno-inc/Zuno`
- GitHub App permission: **Repository permissions → Administration: Read and write**
- The GitHub App installation ID
- A Telegram numeric user ID in `ADMIN_TELEGRAM_IDS`

The GitHub App permission is needed because GitHub's collaborator invitation endpoint is an administrative operation. The bot explicitly requests `permission: "pull"` for each invited user. Install the App on the Zuno repository only, not on all repositories.

## Local setup

1. Create and activate a virtual environment.
2. Install dependencies.
3. Copy `.env.example` to `.env` and fill in the values.
4. Start the bot:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python -m src.main
```

The bot uses Telegram long polling, so no public webhook URL is required.

## Render deployment

Deploy this repository as a **Background Worker** (not a Web Service). The included `render.yaml` configures Python, dependency installation, startup, and a persistent disk.

Set these environment variables in Render:

- `BOT_TOKEN`
- `ADMIN_TELEGRAM_IDS`
- `GITHUB_APP_ID`
- `GITHUB_PRIVATE_KEY`
- `GITHUB_INSTALLATION_ID`
- `GITHUB_OWNER=Zuno-inc`
- `GITHUB_REPO=Zuno`
- `DATABASE_PATH=/var/data/requests.sqlite`

The persistent disk is mounted at `/var/data`; SQLite data would otherwise be lost when the worker is redeployed or restarted.

For `GITHUB_PRIVATE_KEY`, paste the PEM private key as a multiline value if Render supports it, or replace line breaks with literal `\\n`. The application converts literal `\\n` sequences back to line breaks.

## Important security notes

- Never put secrets in Git, chat messages, source code, or screenshots.
- Restrict the GitHub App installation to `Zuno-inc/Zuno`.
- Keep the bot administrator list short.
- The GitHub username is supplied by the requester; this MVP does not prove Telegram-to-GitHub identity ownership. The named GitHub account must accept the invitation.
- Private repository forking must be allowed by the Zuno organization/repository settings for contributors to fork privately and open PRs.
- Review every Pull Request before merging.
