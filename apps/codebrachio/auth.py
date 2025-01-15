import hmac
import time
from hashlib import sha256

import httpx
import jwt

from configs import GITHUB_JWT_SIGNING_KEY, GITHUB_WEBHOOK_SECRET


def generate_jwt(app_id: str) -> str:
    payload = {
        'iat': int(time.time()),
        'exp': int(time.time()) + 60,
        'iss': app_id,
    }
    token = jwt.encode(payload, GITHUB_JWT_SIGNING_KEY, algorithm='RS256')
    return token


def get_installation_access_token(jwt_token: str, installation_id: int) -> str:
    url = f'https://api.github.com/app/installations/{installation_id}/access_tokens'
    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'Accept': 'application/vnd.github+json',
    }
    response = httpx.post(url, headers=headers)
    response.raise_for_status()
    return response.json()['token']


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    computed_hmac = hmac.new(GITHUB_WEBHOOK_SECRET.encode(), payload, sha256).hexdigest()
    expected_signature = f'sha256={computed_hmac}'
    return hmac.compare_digest(expected_signature, signature)
