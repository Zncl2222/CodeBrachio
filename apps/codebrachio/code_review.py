from typing import Literal, Optional

import httpx
from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langfuse.callback import CallbackHandler
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from configs import LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY

from .prompts import GITHUB_CODE_REVIEW_PROMPT
from .states import CodeReviewState
from .utils import parse_diff


class BaseGraph:
    def _get_llm_model(
        self,
        model_provider: Optional[Literal['google', 'groq']] = None,
        model: Optional[str] = None,
        **kwargs,
    ):
        if model_provider == 'google':
            model = 'gemini-1.5-pro' if not model else model
            return ChatGoogleGenerativeAI(model=model, **kwargs)

        if model_provider == 'groq':
            model = 'llama-3.3-70b-versatile' if not model else model
            return ChatGroq(model=model, **kwargs)

        return ChatGoogleGenerativeAI(model='gemini-1.5-pro', **kwargs)


class CodeReview(BaseGraph):
    def _get_code_diffs(self, state: CodeReviewState) -> dict:
        response = httpx.get(
            state['diffs_url'],
            headers={
                'Authorization': f'Bearer {self.access_token}',
                'Accept': 'application/vnd.github.v3.diff',
            },
        )
        diffs = parse_diff(response.text)
        return {'diffs': diffs}

    def _get_all_pr_commits(self, state: CodeReviewState) -> dict:
        pull_request_url = state['pr_url']
        commits_url = f'{pull_request_url}/commits'
        commits = httpx.get(
            commits_url,
            headers={
                'Accept': 'application/vnd.github+json',
                'Authorization': f'Bearer {self.access_token}',
            },
        ).json()

        commits = sorted(commits, key=lambda x: x['commit']['author']['date'], reverse=True)
        # latest_commit_id = commits[0]['sha']
        commits = [x['sha'] for x in commits]
        return {'commits': commits}

    def _create_comment(self, state: CodeReviewState) -> dict:
        response = httpx.post(
            state['comment_url'],
            headers={
                'Accept': 'application/vnd.github+json',
                'Authorization': f'Bearer {self.access_token}',
            },
            json={
                'body': state['messages'][-1].content,
            },
        )
        return {'messages': [response.text]}

    def _create_review(self, state: CodeReviewState) -> dict:
        for diff in state['diffs']:
            for commit in state['commits']:
                resp = httpx.post(
                    f"{state['pr_url']}/comments",
                    headers={
                        'Accept': 'application/vnd.github+json',
                        'Authorization': f'Bearer {self.access_token}',
                    },
                    json={
                        'body': "Hello I'm Brachio",
                        'commit_id': commit,
                        'path': diff['file'],
                        'start_line': diff['start_line'] + 3,
                        'line': diff['end_line'] - 3,
                        'start_side': 'RIGHT',
                        'side': 'RIGHT',
                    },
                )
                if resp.status_code == 201:
                    break
        return {'messages': []}

    def _code_review(self, state: CodeReviewState) -> dict:
        model_name = state['llm_model']
        kwargs = state.get('kwargs', {})
        provider = state.get('llm_provider', None)
        system_message = SystemMessage(GITHUB_CODE_REVIEW_PROMPT)
        llm_model = self._get_llm_model(model_provider=provider, model=model_name, **kwargs)
        message = f"{state['diffs']}\n{state['messages']}"
        resp = llm_model.invoke([system_message, message])
        return {'messages': [resp]}

    def _create_graph(self) -> CompiledStateGraph:
        graph = StateGraph(CodeReviewState)

        graph.add_node('get_code_diffs', self._get_code_diffs)
        graph.add_node('code_review', self._code_review)
        graph.add_node('get_commits', self._get_all_pr_commits)
        graph.add_node('create_review', self._create_review)
        graph.add_node('create_comment', self._create_comment)

        graph.add_edge(START, 'get_code_diffs')
        graph.add_edge('get_code_diffs', 'code_review')
        graph.add_edge('code_review', 'create_comment')
        graph.add_edge('create_comment', 'get_commits')
        graph.add_edge('get_commits', 'create_review')
        graph.add_edge('create_review', END)

        return graph.compile()

    def run(self, access_token: str, json_payload: dict) -> str:
        graph = self._create_graph()
        self.access_token = access_token

        langfuse_handler = CallbackHandler(
            secret_key=LANGFUSE_SECRET_KEY,
            public_key=LANGFUSE_PUBLIC_KEY,
            host=LANGFUSE_HOST,
        )

        data = {
            'llm_model': None,
            'llm_provider': 'groq',
            'messages': json_payload['comment']['body'],
            'diffs_url': json_payload['issue']['pull_request']['url'],
            'comment_url': json_payload['issue']['comments_url'],
            'pr_url': json_payload['issue']['pull_request']['url'],
        }

        graph.invoke(data, config={'callbacks': [langfuse_handler]})
