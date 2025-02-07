import logging
from collections import defaultdict
from typing import Any, Dict, List, Literal, Optional

import httpx
from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_xai import ChatXAI
from langfuse.callback import CallbackHandler
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from configs import LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, XAI_API_KEY

from .prompts import GITHUB_CODE_REVIEW_PROMPT
from .states import CodeReviewState
from .utils import parse_diff

logger = logging.getLogger(__name__)


class BaseGraph:
    def _get_llm_model(
        self,
        model_provider: Optional[Literal['google', 'groq', 'xai']] = None,
        model: Optional[str] = None,
        **kwargs,
    ):
        """Return an instance of the LLM model based on the provider."""
        if model_provider == 'google':
            model = model or 'gemini-1.5-pro'
            return ChatGoogleGenerativeAI(model=model, **kwargs)
        elif model_provider == 'groq':
            model = model or 'llama-3.3-70b-versatile'
            return ChatGroq(model=model, **kwargs)
        elif model_provider == 'xai':
            return ChatXAI(model='grok-2-latest', api_key=XAI_API_KEY, **kwargs)
        else:
            return ChatGoogleGenerativeAI(model='gemini-1.5-pro', **kwargs)


class CodeReview(BaseGraph):
    def __init__(self):
        self.access_token: Optional[str] = None
        self.headers: Dict[str, str] = {}

    def _get_all_pr_commits_and_diffs(self, state: CodeReviewState) -> Dict[str, Any]:
        """
        Fetch commits and associated diffs for a pull request.
        Note: The repository URL is currently hardcoded and may be parameterized.
        """
        pull_request_url = state['pr_url']
        commits_url = f'{pull_request_url}/commits'
        try:
            with httpx.Client(timeout=30) as client:
                commits_resp = client.get(commits_url, headers=self.headers)
                commits_resp.raise_for_status()
                commits = commits_resp.json()
                commits = sorted(commits, key=lambda x: x['commit']['author']['date'], reverse=True)

                diffs = []
                for commit in commits:
                    commit_sha = commit['sha']
                    diffs_url = state['commits_url'].replace('{/sha}', f'/{commit_sha}')
                    diff_resp = client.get(diffs_url, headers=self.headers)
                    diff_resp.raise_for_status()
                    diff_data = diff_resp.json()
                    code_diffs: List[Any] = []
                    for file_info in diff_data.get('files', []):
                        patch = file_info.get('patch')
                        if patch:
                            code_diffs.extend(
                                parse_diff(patch, commit_sha, file_info.get('filename'))
                            )
                    diffs.append({'commit': commit, 'diffs': code_diffs})

            return {'diffs': diffs}
        except httpx.HTTPError as e:
            logger.error(f'Error fetching commits or diffs: {e}')
            raise

    def _create_comment(self, state: CodeReviewState) -> Dict[str, Any]:
        """Post a comment on the pull request using the latest message."""
        try:
            response = httpx.post(
                state['comment_url'],
                headers={
                    'Accept': 'application/vnd.github+json',
                    'Authorization': f'Bearer {self.access_token}',
                },
                json={'body': state['messages'][-1].content},
                timeout=180,
            )
            response.raise_for_status()
            return {'messages': [response.text]}
        except httpx.HTTPError as e:
            logger.error(f'Error creating comment: {e}')
            raise

    def _create_review(self, state: CodeReviewState) -> Dict[str, Any]:
        """
        Create a code review by grouping review results by commit and posting them.
        """
        merged_results = defaultdict(list)
        for item in state['review_results']:
            commit_id = item['meta_data']['commit_id']
            merged_results[commit_id].append(item)

        try:
            for commit_id, results in merged_results.items():
                comments = []
                for result in results:
                    meta = result['meta_data']
                    comments.append(
                        {
                            'body': result['results'],
                            'path': meta['file'],
                            'start_line': meta['start_line'],
                            'line': meta['end_line'],
                            'start_side': 'RIGHT',
                            'side': 'RIGHT',
                        }
                    )
                # Create the review
                review_resp = httpx.post(
                    f"{state['pr_url']}/reviews",
                    headers=self.headers,
                    json={
                        'body': "Hello I'm Brachio",
                        'commit_id': commit_id,
                        'comments': comments,
                    },
                )
                review_resp.raise_for_status()
                review_id = review_resp.json().get('id')
                if review_id:
                    event_resp = httpx.post(
                        f"{state['pr_url']}/reviews/{review_id}/events",
                        headers=self.headers,
                        json={
                            'body': 'CodeBrachioTest',
                            'event': 'COMMENT',
                        },
                    )
                    event_resp.raise_for_status()
            return {'messages': []}
        except httpx.HTTPError as e:
            logger.error(f'Error creating review: {e}')
            raise

    def _map_review(self, state: CodeReviewState) -> List[Send]:
        """
        Map diffs into individual review tasks.
        Each diff is wrapped into a Send object for further processing.
        """
        map_params = []
        common_props = {k: v for k, v in state.items() if k != 'diffs'}
        for commit_data in state.get('diffs', []):
            for diff_item in commit_data.get('diffs', []):
                map_params.append(
                    Send(
                        'code_review',
                        {'diffs': diff_item, **common_props},
                    )
                )
        return map_params

    def _code_review(self, state: CodeReviewState) -> Dict[str, Any]:
        """
        Perform code review on a diff using an LLM.
        Note: This function assumes that state['diffs'] is a dict containing a 'code_snippet'.
        Adjust as needed based on your data structure.
        """
        logger.info('-------------- Call Code Review --------------')
        model_name = state.get('llm_model')
        provider = state.get('llm_provider')
        kwargs = state.get('kwargs', {})
        system_message = SystemMessage(GITHUB_CODE_REVIEW_PROMPT)
        llm_model = self._get_llm_model(model_provider=provider, model=model_name, **kwargs)

        code_snippet = state.get('diffs', {}).get('code_snippet', '')
        user_question = state.get('messages', '')
        message = f'{code_snippet}\n User Question: {user_question}'

        try:
            response = llm_model.invoke([system_message, message])
            content = response.content
        except Exception as e:
            logger.error(f'Error during code review LLM invocation: {e}')
            content = 'Error'

        return {'review_results': [{'meta_data': state.get('diffs', {}), 'results': content}]}

    def _create_graph(self) -> CompiledStateGraph:
        """
        Create and compile the state graph for the code review workflow.
        """
        graph = StateGraph(CodeReviewState)
        graph.add_node('code_review', self._code_review)
        graph.add_node('get_commits', self._get_all_pr_commits_and_diffs)
        graph.add_node('create_review', self._create_review)
        graph.add_node('create_comment', self._create_comment)

        graph.add_edge(START, 'get_commits')
        graph.add_edge('code_review', 'create_comment')
        graph.add_edge('create_comment', 'create_review')
        graph.add_edge('create_review', END)

        graph.add_conditional_edges(
            'get_commits',
            self._map_review,
            {'continue': 'code_review'},
        )

        return graph.compile()

    def run(self, access_token: str, json_payload: dict) -> str:
        """
        Run the complete code review workflow.
        This method sets up authentication headers, initializes the workflow state,
        and invokes the state graph.
        """
        self.access_token = access_token
        self.headers = {
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {self.access_token}',
        }

        langfuse_handler = CallbackHandler(
            secret_key=LANGFUSE_SECRET_KEY,
            public_key=LANGFUSE_PUBLIC_KEY,
            host=LANGFUSE_HOST,
        )

        data = {
            'llm_model': None,
            'llm_provider': 'xai',
            'messages': json_payload['comment']['body'],
            'diffs_url': json_payload['issue']['pull_request']['url'],
            'comment_url': json_payload['issue']['comments_url'],
            'pr_url': json_payload['issue']['pull_request']['url'],
            'commits_url': json_payload['repository']['commits_url'],
        }

        graph = self._create_graph()
        graph.invoke(data, config={'callbacks': [langfuse_handler]})
        return 'Workflow executed successfully'
