const { createAppAuth } = require('@octokit/auth-app');
const { Octokit } = require('@octokit/rest');

let octokitPromise;

function getOctokit() {
  if (!octokitPromise) {
    const appId = process.env.GITHUB_APP_ID;
    const privateKey = process.env.GITHUB_PRIVATE_KEY?.replace(/\\n/g, '\n');
    const installationId = process.env.GITHUB_INSTALLATION_ID;

    if (!appId || !privateKey || !installationId) {
      throw new Error('GitHub App credentials are not fully configured.');
    }

    octokitPromise = (async () => {
      const auth = createAppAuth({
        appId,
        privateKey,
        installationId
      });
      const installationAuth = await auth({ type: 'installation' });
      return new Octokit({ auth: installationAuth.token });
    })();
  }
  return octokitPromise;
}

async function inviteReadOnlyCollaborator(username) {
  const octokit = await getOctokit();
  const owner = process.env.GITHUB_OWNER || 'Zuno-inc';
  const repo = process.env.GITHUB_REPO || 'Zuno';

  const response = await octokit.request(
    'PUT /repos/{owner}/{repo}/collaborators/{username}',
    {
      owner,
      repo,
      username,
      permission: 'pull'
    }
  );

  return {
    status: response.status,
    invitationCreated: response.status === 201,
    permission: 'pull'
  };
}

module.exports = { inviteReadOnlyCollaborator };
