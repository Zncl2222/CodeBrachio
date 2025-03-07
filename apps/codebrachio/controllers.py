import re

from litestar import Controller, Request, Response
from litestar.exceptions import HTTPException
from litestar.handlers import post

from configs import GITHUB_CLIENT_ID

from .auth import (
    generate_jwt,
    get_github_app_installations,
    get_installation_access_token,
    verify_webhook_signature,
)
from .code_review import CodeReview


class GitHubController(Controller):
    path = '/github'

    MODEL_CHOICES = ['google', 'groq', 'xai']
    DEFAULT_MODEL = 'xai'
    MODEL_REGEX = re.compile(r'@CodeBrachio\s*\[(google|groq|xai)\]', re.IGNORECASE)

    def _extract_model_provider(self, body: str) -> str:
        """Extract LLM provider from comment body, fallback to default."""
        match = self.MODEL_REGEX.search(body)
        if match:
            return match.group(1).lower()
        return self.DEFAULT_MODEL

    @post('/code_review')
    async def code_review(self, request: Request) -> Response:
        jwt_token = generate_jwt(GITHUB_CLIENT_ID)

        response = await get_github_app_installations(jwt_token)

        installations = response.json()
        installations_id = installations[0]['id']

        access_token = get_installation_access_token(jwt_token, installations_id)
        signature = request.headers.get('x-hub-signature-256', '')
        payload = await request.body()
        if not verify_webhook_signature(payload, signature):
            raise HTTPException(status_code=401, detail='Invalid webhook signature')

        json_payload = await request.json()
        if json_payload['action'] != 'created':
            return Response({'status': 'ok'}, status_code=200)

        user = json_payload['comment']['user']['login']
        body = json_payload['comment']['body']

        if user != 'codebrachio[bot]' and '@CodeBrachio' in body:
            model_provider = self._extract_model_provider(body)
            json_payload['llm_provider'] = model_provider
            CodeReview().run(access_token, json_payload)

        return Response({'status': 'ok'}, status_code=200)
