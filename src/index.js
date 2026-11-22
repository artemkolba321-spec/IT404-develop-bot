require('dotenv').config();

const TeleBot = require('telebot');
const db = require('./db');
const { inviteReadOnlyCollaborator } = require('./github');

const required = ['BOT_TOKEN', 'ADMIN_TELEGRAM_IDS'];
for (const key of required) {
  if (!process.env[key]) {
    throw new Error(`Missing required environment variable: ${key}`);
  }
}

const admins = new Set(
  process.env.ADMIN_TELEGRAM_IDS.split(',').map((id) => id.trim()).filter(Boolean)
);
const bot = new TeleBot({
  token: process.env.BOT_TOKEN,
  usePlugins: ['commandButton']
});

const waitingForGithub = new Set();
const rateLimit = new Map();

const mainKeyboard = {
  reply_markup: {
    keyboard: [
      [{ text: '/access' }, { text: '/status' }],
      [{ text: '/rules' }, { text: '/help' }]
    ],
    resize_keyboard: true
  }
};

function isAdmin(userId) {
  return admins.has(String(userId));
}

function isRateLimited(userId) {
  const now = Date.now();
  const previous = rateLimit.get(String(userId)) || 0;
  if (now - previous < 60_000) return true;
  rateLimit.set(String(userId), now);
  return false;
}

bot.on('/start', (msg) => {
  waitingForGithub.delete(String(msg.from.id));
  return bot.sendMessage(
    msg.chat.id,
    'Welcome to the Zuno Developer Bot!\n\nUse /access to request read-only access to the private Zuno repository. A maintainer will review your request.',
    mainKeyboard
  );
});

bot.on('/help', (msg) => bot.sendMessage(
  msg.chat.id,
  'Commands:\n/access — request repository access\n/status — check your latest request\n/rules — contributor rules\n/help — show this help\n\nMaintainers: /pending, /approve REQUEST_ID, /reject REQUEST_ID',
  mainKeyboard
));

bot.on('/rules', (msg) => {
  const projectUrl = process.env.PROJECT_URL || 'https://zuno-com.onrender.com/';
  return bot.sendMessage(
    msg.chat.id,
    'Zuno contributor rules:\n\n1. Access is read-only. Do not expect direct push access.\n2. Make changes in your own fork and submit a Pull Request.\n3. Keep PRs focused and explain what you changed.\n4. Never commit secrets, tokens, passwords, or private user data.\n5. Be respectful and follow the project license.\n\nProject: ' + projectUrl,
    mainKeyboard
  );
});

bot.on('/access', (msg) => {
  waitingForGithub.add(String(msg.from.id));
  return bot.sendMessage(
    msg.chat.id,
    'Please send your GitHub username (for example: octocat).\n\nThe maintainer will review the request. If approved, GitHub will send an invitation to that GitHub account with read-only access.'
  );
});

bot.on('/status', (msg) => {
  const request = db.getLatestForTelegram(msg.from.id);
  if (!request) {
    return bot.sendMessage(msg.chat.id, 'You have not submitted an access request yet. Use /access to begin.');
  }

  const labels = {
    pending: 'Waiting for maintainer review.',
    approved: 'Invitation sent by GitHub. Please check GitHub notifications and email, then accept it.',
    rejected: 'Your request was declined. Contact a maintainer if you think this is a mistake.'
  };
  return bot.sendMessage(
    msg.chat.id,
    `Request #${request.id} for GitHub user @${request.github_username}\nStatus: ${labels[request.status] || request.status}`
  );
});

bot.on('/pending', (msg) => {
  if (!isAdmin(msg.from.id)) return bot.sendMessage(msg.chat.id, 'This command is for maintainers only.');
  const requests = db.listPending();
  if (!requests.length) return bot.sendMessage(msg.chat.id, 'There are no pending requests.');
  const lines = requests.map((r) =>
    `#${r.id} — @${r.github_username} (Telegram ID: ${r.telegram_id})`
  );
  return bot.sendMessage(msg.chat.id, 'Pending requests:\n' + lines.join('\n') +
    '\n\nApprove with /approve ID or reject with /reject ID.');
});

bot.on(/^\/approve(?:\s+(\d+))?$/, async (msg, props) => {
  if (!isAdmin(msg.from.id)) return bot.sendMessage(msg.chat.id, 'This command is for maintainers only.');
  const id = Number(props.match[1]);
  if (!id) return bot.sendMessage(msg.chat.id, 'Usage: /approve REQUEST_ID');
  const request = db.getRequest(id);
  if (!request) return bot.sendMessage(msg.chat.id, 'Request not found.');
  if (request.status !== 'pending') return bot.sendMessage(msg.chat.id, `Request is already ${request.status}.`);

  try {
    const result = await inviteReadOnlyCollaborator(request.github_username);
    db.setStatus(id, 'approved', msg.from.id, true);
    await bot.sendMessage(
      msg.chat.id,
      `GitHub accepted the invitation request for @${request.github_username}. Permission requested: pull (read-only). HTTP ${result.status}.`
    );
    await bot.sendMessage(
      request.telegram_id,
      `Your request was approved. GitHub has sent an invitation to @${request.github_username}. Please accept it on GitHub to access the repository.\n\nYou have read-only access; submit changes through Pull Requests.`
    );
  } catch (error) {
    console.error('GitHub invitation failed:', error.message);
    await bot.sendMessage(msg.chat.id, `Could not send the invitation: ${error.message}`);
  }
});

bot.on(/^\/reject(?:\s+(\d+))?$/, async (msg, props) => {
  if (!isAdmin(msg.from.id)) return bot.sendMessage(msg.chat.id, 'This command is for maintainers only.');
  const id = Number(props.match[1]);
  if (!id) return bot.sendMessage(msg.chat.id, 'Usage: /reject REQUEST_ID');
  const request = db.getRequest(id);
  if (!request) return bot.sendMessage(msg.chat.id, 'Request not found.');
  if (request.status !== 'pending') return bot.sendMessage(msg.chat.id, `Request is already ${request.status}.`);
  db.setStatus(id, 'rejected', msg.from.id);
  await bot.sendMessage(msg.chat.id, `Request #${id} rejected.`);
  await bot.sendMessage(request.telegram_id, 'Your Zuno repository access request was declined. You can contact a maintainer for more information.');
});

bot.on('text', async (msg) => {
  const telegramId = String(msg.from.id);
  if (!waitingForGithub.has(telegramId) || msg.text.startsWith('/')) return;
  waitingForGithub.delete(telegramId);

  if (isRateLimited(telegramId)) {
    return bot.sendMessage(msg.chat.id, 'Please wait a minute before submitting another request.');
  }

  const username = msg.text.trim().replace(/^@/, '');
  if (!/^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$/.test(username)) {
    return bot.sendMessage(msg.chat.id, 'That does not look like a valid GitHub username. Use /access to try again.');
  }

  try {
    const request = db.createRequest({
      telegramId,
      telegramUsername: msg.from.username || null,
      githubUsername: username
    });
    await bot.sendMessage(
      msg.chat.id,
      `Request #${request.id} submitted for @${username}. A maintainer will review it. Use /status to check progress.`
    );

    for (const adminId of admins) {
      await bot.sendMessage(
        adminId,
        `New Zuno access request #${request.id}\nGitHub: @${username}\nTelegram ID: ${telegramId}\nApprove: /approve ${request.id}\nReject: /reject ${request.id}`
      );
    }
  } catch (error) {
    console.error('Could not save access request:', error.message);
    await bot.sendMessage(msg.chat.id, 'Sorry, I could not save your request. Please try again later.');
  }
});

bot.on('polling_error', (error) => console.error('Telegram polling error:', error.message));

bot.start()
  .then(() => console.log('IT404 Develop Bot is running (long polling).'))
  .catch((error) => {
    console.error('Could not start Telegram bot:', error);
    process.exitCode = 1;
  });

process.on('SIGINT', () => {
  bot.stop();
  db.close();
  process.exit(0);
});
process.on('SIGTERM', () => {
  bot.stop();
  db.close();
  process.exit(0);
});
