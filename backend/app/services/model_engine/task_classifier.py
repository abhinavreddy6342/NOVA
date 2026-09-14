from enum import Enum
from typing import List


class TaskType(str, Enum):
    """
    High-level task categories understood by NOVA.
    """

    GENERAL = "general"
    CONVERSATION = "conversation"
    CODING = "coding"
    REASONING = "reasoning"
    DOCUMENT = "document"
    SUMMARIZATION = "summarization"
    DATA_ANALYSIS = "data_analysis"
    SPREADSHEET = "spreadsheet"
    VISION = "vision"
    CREATIVE = "creative"


# ---------------------------------------------------------------------------
# KEYWORD GROUPS
# ---------------------------------------------------------------------------

KEYWORDS = {
    TaskType.CODING: [
        "code",
        "coding",
        "program",
        "programming",
        "python",
        "javascript",
        "typescript",
        "java",
        "c++",
        "sql",
        "api",
        "debug",
        "debugging",
        "function",
        "class",
        "algorithm",
        "github",
        "script",
        "developer",
        "software",
    ],

    TaskType.DOCUMENT: [
        "document",
        "pdf",
        "report",
        "file",
        "document analysis",
        "read this",
        "extract",
        "approval note",
        "office note",
        "technical report",
    ],

    TaskType.SUMMARIZATION: [
        "summarize",
        "summary",
        "summarise",
        "brief",
        "shorten",
        "key points",
        "main points",
        "tldr",
    ],

    TaskType.DATA_ANALYSIS: [
        "analyze data",
        "analyse data",
        "data analysis",
        "dataset",
        "statistics",
        "trend",
        "trends",
        "correlation",
        "calculate",
        "calculation",
        "average",
        "median",
        "percentage",
        "forecast",
    ],

    TaskType.SPREADSHEET: [
        "spreadsheet",
        "excel",
        "xlsx",
        "csv",
        "cell",
        "worksheet",
        "workbook",
        "formula",
        "pivot table",
        "column",
        "row",
    ],

    TaskType.VISION: [
        "image",
        "photo",
        "picture",
        "drawing",
        "diagram",
        "scan",
        "scanned",
        "handwritten",
        "handwriting",
        "engineering drawing",
        "visual",
    ],

    TaskType.REASONING: [
        "why",
        "reason",
        "reasoning",
        "logic",
        "solve",
        "problem",
        "compare",
        "evaluate",
        "calculate",
        "step by step",
        "decision",
        "explain why",
    ],

    TaskType.CREATIVE: [
        "write a story",
        "story",
        "poem",
        "creative",
        "brainstorm",
        "ideas",
        "caption",
        "marketing",
        "slogan",
        "design concept",
    ],

    TaskType.CONVERSATION: [
        "hello",
        "hi",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "thanks",
        "thank you",
        "bye",
        "who are you",
        "what are you",
    ],
}


# ---------------------------------------------------------------------------
# CLASSIFICATION
# ---------------------------------------------------------------------------

def _score_task(
    text: str,
    keywords: List[str],
) -> int:
    """
    Calculate a simple keyword score.
    """

    score = 0

    for keyword in keywords:
        if keyword in text:
            score += 1

    return score


def classify_task(
    text: str,
) -> TaskType:
    """
    Classify a user request into the most likely NOVA task type.

    This is intentionally deterministic and local.
    No external model or API is used.
    """

    if not text or not text.strip():
        return TaskType.GENERAL

    normalized = " ".join(
        text.lower().strip().split()
    )

    scores = {
        task_type: _score_task(
            normalized,
            keywords,
        )
        for task_type, keywords in KEYWORDS.items()
    }

    best_task = max(
        scores,
        key=scores.get,
    )

    best_score = scores[best_task]

    if best_score == 0:
        return TaskType.GENERAL

    return best_task


def classify_tasks(
    text: str,
    minimum_score: int = 1,
) -> List[TaskType]:
    """
    Return all matching task categories.

    Useful when a request contains multiple task types,
    such as document analysis + reasoning.
    """

    if not text or not text.strip():
        return [TaskType.GENERAL]

    normalized = " ".join(
        text.lower().strip().split()
    )

    matches = []

    for task_type, keywords in KEYWORDS.items():
        score = _score_task(
            normalized,
            keywords,
        )

        if score >= minimum_score:
            matches.append(task_type)

    if not matches:
        return [TaskType.GENERAL]

    return matches