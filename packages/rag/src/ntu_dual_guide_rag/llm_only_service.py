from __future__ import annotations

from pathlib import Path

from ntu_dual_guide_rag.models import ChatAnswer
from ntu_dual_guide_rag.openai_responses import create_structured_answer
from ntu_dual_guide_rag.prompts import LLM_ONLY_SYSTEM_PROMPT
from ntu_dual_guide_rag.prompts import build_llm_only_user_prompt
from ntu_dual_guide_rag.settings import RagSettings


class LlmOnlyService:
    def __init__(self, settings: RagSettings) -> None:
        self.settings = settings

    @classmethod
    def from_repo_root(cls, repo_root: Path) -> "LlmOnlyService":
        settings = RagSettings.from_env(repo_root)
        return cls(settings)

    def answer(self, question: str) -> ChatAnswer:
        structured_answer = create_structured_answer(
            api_key=self.settings.openai_api_key,
            model=self.settings.openai_model,
            instructions=LLM_ONLY_SYSTEM_PROMPT,
            user_input=build_llm_only_user_prompt(question),
        )

        return ChatAnswer(
            answer=structured_answer.answer,
            status=structured_answer.status,
            model=self.settings.openai_model,
            dataset_version=self.settings.dataset_version,
            namespace=self.settings.namespace,
            citations=[],
            retrieved_chunks=[],
        )
