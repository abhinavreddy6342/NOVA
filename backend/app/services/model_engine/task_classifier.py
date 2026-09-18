from enum import Enum
import re
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
    MISSION = "mission"


# ---------------------------------------------------------------------------
# KEYWORDS
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

    TaskType.MISSION: [
        "mission",
        "mission control",
        "mission execution",
        "execute this mission",
        "run this mission",
        "start mission",
        "autonomous mission",
        "autonomous multi-step",
        "multi-step mission",
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
# MATCHING
# ---------------------------------------------------------------------------

def _keyword_matches(
    text: str,
    keyword: str,
) -> bool:
    """
    Match complete words/phrases rather than arbitrary substrings.
    """

    escaped = re.escape(
        keyword.strip().lower()
    )

    if not escaped:
        return False

    pattern = (
        rf"(?<!\w){escaped}(?!\w)"
    )

    return re.search(
        pattern,
        text,
        flags=re.IGNORECASE,
    ) is not None


def _score_task(
    text: str,
    keywords: List[str],
) -> int:
    score = 0

    for keyword in keywords:
        if _keyword_matches(
            text,
            keyword,
        ):
            score += 1

    return score


# ---------------------------------------------------------------------------
# CLASSIFICATION
# ---------------------------------------------------------------------------

def classify_task(
    text: str,
) -> TaskType:

    if not text or not text.strip():
        return TaskType.GENERAL

    normalized = (
        " ".join(
            text.lower()
            .strip()
            .split()
        )
    )

    scores = {
        task_type: _score_task(
            normalized,
            keywords,
        )
        for (
            task_type,
            keywords,
        ) in KEYWORDS.items()
    }

    # Mission requests are application-level commands.
    # Give them priority when an explicit mission signal exists.
    if scores.get(
        TaskType.MISSION,
        0,
    ) > 0:
        return TaskType.MISSION

    best_task = max(
        scores,
        key=lambda task: scores[task],
    )

    if scores[best_task] == 0:
        return TaskType.GENERAL

    return best_task


def classify_tasks(
    text: str,
    minimum_score: int = 1,
) -> List[TaskType]:

    if not text or not text.strip():
        return [
            TaskType.GENERAL
        ]

    normalized = (
        " ".join(
            text.lower()
            .strip()
            .split()
        )
    )

    matches = []

    for (
        task_type,
        keywords,
    ) in KEYWORDS.items():

        score = _score_task(
            normalized,
            keywords,
        )

        if score >= minimum_score:
            matches.append(
                task_type
            )

    if not matches:
        return [
            TaskType.GENERAL
        ]

    return matches