from litestar.openapi.config import OpenAPIConfig
from litestar.openapi.plugins import SwaggerRenderPlugin

from litestar import Litestar, Controller, Response, Request
from litestar.handlers import post, get
from litestar.exceptions import HTTPException
from hashlib import sha256
import dotenv
import hmac
import jwt  # PyJWT
import time
import os
import httpx


import os

dotenv.load_dotenv('.env')

os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")


# Configuration for the GitHub App
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "YOUR_APP_ID")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
# GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY", "YOUR_PRIVATE_KEY")  # PEM format
with open('codebrachy.2025-01-04.private-key.pem', 'rb') as pem_file:
    signing_key = pem_file.read()

GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "YOUR_WEBHOOK_SECRET")


# # Utility: Generate a JWT for GitHub API
# def generate_jwt():
#     now = int(time.time())
#     payload = {
#         "iat": now,
#         "exp": now + 600,  # Token expires after 10 minutes
#         "iss": GITHUB_CLIENT_ID,
#     }
#     headers = {"alg": "RS256"}
#     return jwt.encode(payload, signing_key, algorithm="RS256", headers=headers)


# Utility: Verify webhook payload signature
def verify_webhook_signature(secret, payload, signature):
    computed_hmac = hmac.new(secret.encode(), payload, sha256).hexdigest()
    expected_signature = f"sha256={computed_hmac}"
    return hmac.compare_digest(expected_signature, signature)


# Step 1: Generate a JWT
def generate_jwt(app_id):
    payload = {
        "iat": int(time.time()),  # Issued at time
        "exp": int(time.time()) + 60,  # Expiration time (10 minutes)
        "iss": app_id,  # GitHub App's ID
    }
    token = jwt.encode(payload, signing_key, algorithm="RS256")
    return token

# Step 2: Obtain an Installation Access Token
def get_installation_access_token(jwt_token, installation_id):
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
    }
    response = httpx.post(url, headers=headers)
    response.raise_for_status()  # Raise an error for bad status codes
    return response.json()["token"]


# Controller: Handle GitHub-related endpoints
class GitHubController(Controller):
    path = "/github"

    @post("/installations")
    async def list_installations(self, request: Request) -> Response:
        # Generate JWT
        jwt_token = generate_jwt(GITHUB_CLIENT_ID)

        # Use JWT to fetch installations
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/app/installations",
                headers={"Authorization": f"Bearer {jwt_token}", "Accept": "application/vnd.github+json"},
            )

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        installations = response.json()
        return Response(content={"installations": installations}, status_code=200)

    @post("/webhook")
    async def github_webhook(self, request: Request) -> Response:
        jwt_token = generate_jwt(GITHUB_CLIENT_ID)

        # Use JWT to fetch installations
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/app/installations",
                headers={"Authorization": f"Bearer {jwt_token}", "Accept": "application/vnd.github+json"},
            )

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        installations = response.json()
        installations_id = installations[0]['id']

        access_token = get_installation_access_token(jwt_token, installations_id)
        # signature = request.headers.get("x-hub-signature-256", "")
        payload = await request.json()
        # print(payload)
        # if not verify_webhook_signature(GITHUB_WEBHOOK_SECRET, payload, signature):
        #     raise HTTPException(status_code=401, detail="Invalid webhook signature")
        print(payload['action'])
        print(payload['comment'])
        print(payload['issue']['pull_request']['diff_url'])
        url = payload['issue']['pull_request']['url']
        # # Log the webhook payload
        # print(f"Webhook received: {payload.decode('utf-8')}")
        resp = httpx.get(
            url,
            headers={'Authorization': f"Bearer {access_token}",  "Accept": "application/vnd.github.v3.diff"}
        )
        print(resp.text)

        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",  # Specify the desired model version
            temperature=0.7,        # Adjust the temperature for creativity
            max_tokens=1000,        # Set the maximum number of tokens per response
            timeout=60,             # Set a timeout for API requests
            max_retries=3           # Number of retries for failed requests
        )

        messages = [
            ("system", "You are a helpful assistant."),
            ("human", "How can I integrate Google Gemini with LangChain?")
        ]

        response = llm.invoke(messages)
        print(response.content)


        return Response({'status': 'ok'}, status_code=200)

# Controller: Handle general routes
class GeneralController(Controller):
    path = "/"

    @get("/hello")
    async def say_hello(self) -> Response:
        return Response(content={"message": "Hello from the class-based view!"})


# Create the Litestar app with controllers
app = Litestar(
    route_handlers=[
        GitHubController,  # GitHub-related routes
        GeneralController,  # General routes
    ],
    openapi_config=OpenAPIConfig(
        title="Litestar Example",
        description="Example of litestar",
        version="0.0.1",
        render_plugins=[SwaggerRenderPlugin()],
    ),
)
