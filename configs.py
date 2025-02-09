import os

import dotenv

dotenv.load_dotenv('.env')

os.environ['GOOGLE_API_KEY'] = os.getenv('GOOGLE_API_KEY', default='')
os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', default='')
os.environ['LANGCHAIN_TRACING_V2'] = os.getenv('LANGCHAIN_TRACING_V2', default='')
os.environ['LANGCHAIN_PROJECT'] = os.getenv('LANGCHAIN_PROJECT', default='')
os.environ['LANGCHAIN_ENDPOINT'] = os.getenv('LANGCHAIN_ENDPOINT', default='')
os.environ['LANGCHAIN_API_KEY'] = os.getenv('LANGCHAIN_API_KEY', default='')
os.environ['GROQ_API_KEY'] = os.getenv('GROQ_API_KEY', default='')

# Configuration for the GitHub App
GITHUB_APP_ID = os.getenv('GITHUB_APP_ID', default='')
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID', default='')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET', default='')
GITHUB_WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET', default='')
GITHUB_PEM_FILE_NAME = os.getenv('GITHUB_PEM_FILE_NAME', default='')
GITHUB_JWT_SIGNING_KEY: str = ''

with open(GITHUB_PEM_FILE_NAME, 'rb') as pem_file:
    GITHUB_JWT_SIGNING_KEY = pem_file.read()

# Langfuse
LANGFUSE_SECRET_KEY = os.getenv('LANGFUSE_SECRET_KEY', default='')
LANGFUSE_PUBLIC_KEY = os.getenv('LANGFUSE_PUBLIC_KEY', default='')
LANGFUSE_HOST = os.getenv('LANGFUSE_HOST', default='')

XAI_API_KEY = os.getenv('XAI_API_KEY')
