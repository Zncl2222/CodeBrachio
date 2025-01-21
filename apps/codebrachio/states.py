from typing import Annotated, Any

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class CodeReviewState(TypedDict):
    messages: Annotated[list, add_messages]

    # url
    comment_url: str
    diffs_url: str

    diffs: str
    llm_provider: str
    llm_model: str
    kwargs: dict[str, Any]
