from operator import add
from typing import Annotated, Any

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class CodeReviewState(TypedDict):
    messages: Annotated[list, add_messages]

    # url
    comment_url: str
    diffs_url: str
    pr_url: str
    commits_url: str

    diffs: list[dict[str, str]]
    llm_provider: str
    llm_model: str
    kwargs: dict[str, Any]

    # Results
    review_results: Annotated[list, add]
