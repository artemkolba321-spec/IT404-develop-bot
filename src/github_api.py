import os
import time
import jwt
import requests

API_URL = "https://api.github.com"


def _installation_token():
    app_id = os.getenv("GITHUB_APP_ID")
    private_key = os.getenv("GITHUB_PRIVATE_KEY", "").replace("\\n", "\n")
    installation_id = os.getenv("GITHUB_INSTALLATION_ID")
    if not app_id or not private_key or not installation_id:
        raise RuntimeError("GitHub App credentials are not fully configured.")

    now = int(time.time())
    app_jwt = jwt.encode(
        {"iat": now - 60, "exp": now + 540, "iss": app_id},
        private_key,
        algorithm="RS256",
    )
    response = requests.post(
        f"{API_URL}/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["token"]


def invite_read_only_collaborator(username):
    owner = os.getenv("GITHUB_OWNER", "Zuno-inc")
    repo = os.getenv("GITHUB_REPO", "Zuno")
    token = _installation_token()
    response = requests.put(
        f"{API_URL}/repos/{owner}/{repo}/collaborators/{username}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"permission": "pull"},
        timeout=20,
    )
    if response.status_code not in (201, 204):
        try:
            detail = response.json().get("message", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(f"GitHub API returned HTTP {response.status_code}: {detail}")
    return {"status": response.status_code, "permission": "pull"}
