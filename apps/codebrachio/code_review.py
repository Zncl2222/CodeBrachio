from typing import Literal, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .states import CodeReviewState


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


class CodeReview(BaseGraph):
    def _code_review(self, state: CodeReviewState) -> dict:
        model_name = state['llm_model']
        kwargs = state['kwargs']
        provider = state['model_provider']
        llm_model = self._get_llm_model(model_provider=provider, model=model_name, **kwargs)
        resp = llm_model.invoke(state['input'])
        return {'messages': [resp]}

    def _create_graph(self) -> CompiledStateGraph:
        graph = StateGraph(CodeReviewState)

        graph.add_node(START, 'start')
        graph.add_node('code_review', self._code_review)
        graph.add_node('end', END)

        graph.add_edge(START, 'code_review')
        graph.add_edge('code_review', 'end')

        return graph.compile()

    def run(self, input: dict) -> str:
        graph = self._create_graph()
        graph.invoke(input)
