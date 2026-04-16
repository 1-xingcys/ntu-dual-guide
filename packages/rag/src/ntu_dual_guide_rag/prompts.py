from __future__ import annotations

from ntu_dual_guide_rag.models import RetrievalChunk


SYSTEM_PROMPT = """你是台大資訊工程學系、雙主修經濟學系的 AI 助手。

你的任務是根據提供的學校規定、系所規定、FAQ 與課程資料回答問題。

規則：
1. 只能根據提供的檢索內容回答，不得自行編造規定。
2. 如果檢索內容不足以支持答案，請將 status 設為 unknown，並在 answer 中直接說明不知道或無法判斷的原因。
3. 優先使用正式規定與課程表，其次才是 FAQ 或系網整理頁。
4. 回答請使用繁體中文。
5. 若有引用內容，請在句末使用 [1]、[2] 這種編號標記，對應到提供的 context。
6. 若不同來源彼此衝突，優先採信 authority_level 較高、且較像正式規章的來源，並明確指出。
7. 不要假設未提供的條件，例如核准年度、入學年度、原系身分；若缺少關鍵條件又無法從 context 判斷，就將 status 設為 unknown。
8. status 只能是 answered 或 unknown。只有在檢索內容足以支持結論時，才能使用 answered。
"""

LLM_ONLY_SYSTEM_PROMPT = """你是台大資訊工程學系、雙主修經濟學系的 AI 助手。

根據自己已知的台大校規、系規與常見修課規定回答。

status 只能是 answered 或 unknown。若不確定，請使用 unknown，並在 answer 中明確說明不知道。
"""


def build_user_prompt(question: str, chunks: list[RetrievalChunk]) -> str:
    context_lines = []
    for index, chunk in enumerate(chunks, start=1):
        context_lines.append(
            "[{0}] title={1} | source_id={2} | doc_type={3} | score={4:.4f}\n{5}".format(
                index,
                chunk.title,
                chunk.source_id,
                chunk.doc_type,
                chunk.score,
                chunk.text,
            )
        )
    context_text = "\n\n".join(context_lines)
    return "問題：{0}\n\n檢索內容：\n{1}\n\n請根據上述檢索內容回答。".format(
        question,
        context_text or "（無）",
    )


def build_llm_only_user_prompt(question: str) -> str:
    return "問題：{0}\n\n請直接回答；若不確定，請回答不知道。".format(question)
