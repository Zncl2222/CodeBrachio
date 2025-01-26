import httpx
from litestar import Controller, Request, Response
from litestar.exceptions import HTTPException
from litestar.handlers import post

from configs import GITHUB_CLIENT_ID

from .auth import generate_jwt, get_installation_access_token, verify_webhook_signature
from .code_review import CodeReview


class GitHubController(Controller):
    path = '/github'

    @post('/code_review')
    async def code_review(self, request: Request) -> Response:
        jwt_token = generate_jwt(GITHUB_CLIENT_ID)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                'https://api.github.com/app/installations',
                headers={
                    'Authorization': f'Bearer {jwt_token}',
                    'Accept': 'application/vnd.github+json',
                },
            )

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)

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
            CodeReview().run(access_token, json_payload)

        return Response({'status': 'ok'}, status_code=200)
