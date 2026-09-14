from typing import Any, Dict
import re

from app.services.model_engine.model_router import route_request
from app.services.model_engine.ollama_manager import ollama_manager


class AgentResponseSynthesizer:
    """
    Converts executed NOVA agent results into a clear,
    grounded and user-friendly final response.

    The synthesizer is responsible only for the final response
    shown to the user. Internal planning, execution metadata and
    implementation details must never leak into the response.
    """

    # ------------------------------------------------------------------
    # CONTEXT BUILDING
    # ------------------------------------------------------------------

    def _build_context(
        self,
        execution_context: Dict[str, Any],
    ) -> str:
        """
        Convert verified tool outputs into a readable context block.
        """

        sections = []

        for step_id, result in execution_context.items():
            sections.append(
                f"VERIFIED RESULT FOR {step_id}:\n{result}"
            )

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # RESPONSE CLEANUP
    # ------------------------------------------------------------------

    def _clean_response(
        self,
        response: str,
    ) -> str:
        """
        Remove accidental placeholders and obvious internal
        response artifacts from the model's final answer.
        """

        cleaned = str(response or "").strip()

        if not cleaned:
            return cleaned

        # Remove accidental Markdown fences around the final answer.
        if cleaned.startswith("```") and cleaned.endswith("```"):
            lines = cleaned.splitlines()

            if lines:
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            cleaned = "\n".join(lines).strip()

        # Remove common placeholder text that should never reach users.
        placeholder_patterns = [
            r"\[insert date if available\]",
            r"\[insert date\]",
            r"\[date if available\]",
            r"\[insert filename\]",
            r"\[filename\]",
            r"\[insert file path\]",
            r"\[file path\]",
            r"\[insert details\]",
            r"\[details\]",
        ]

        for pattern in placeholder_patterns:
            cleaned = re.sub(
                pattern,
                "",
                cleaned,
                flags=re.IGNORECASE,
            )

        # Remove repeated blank lines created by placeholder removal.
        cleaned = re.sub(
            r"\n{3,}",
            "\n\n",
            cleaned,
        ).strip()

        return cleaned

    # ------------------------------------------------------------------
    # SYNTHESIS
    # ------------------------------------------------------------------

    def synthesize(
        self,
        objective: str,
        execution_context: Dict[str, Any],
    ) -> str:
        """
        Generate a polished, grounded, user-facing response using
        only verified local-agent results.
        """

        objective = objective.strip()

        if not objective:
            raise ValueError(
                "Cannot synthesize a response without an objective."
            )

        if not execution_context:
            return (
                "I could not complete the request because "
                "there were no verified results available."
            )

        routing = route_request(
            objective
        )

        context_text = self._build_context(
            execution_context
        )

        prompt = f"""
You are NOVA's final user-facing response engine.

Your job is to turn the verified local execution results
into a natural, professional response for the user.

USER OBJECTIVE:
{objective}

VERIFIED LOCAL EXECUTION RESULTS:
{context_text}

============================================================
RESPONSE BEHAVIOR
============================================================

Answer the user's request directly.

Use ONLY facts contained in the verified local execution
results above.

Never invent information.

Never guess missing information.

Never create placeholder text.

Never write phrases such as:

- [insert date if available]
- [insert filename]
- [insert details]
- date will be added later
- information unavailable if it is actually present
- any bracketed placeholder

============================================================
WHEN A DOCUMENT OR FILE WAS CREATED
============================================================

When the verified result confirms that a requested document
or file was successfully created:

1. Clearly tell the user that it is done.
2. State the actual filename when available.
3. State the exact local path when available.
4. State the file size when available.
5. Keep the explanation concise.
6. Do not fabricate a creation date.
7. Do not claim information is inside the document unless
   the verified result actually confirms it.

Preferred style:

"Done — your cybersecurity document has been created.

File: cybersecurity.docx
Location: output/cybersecurity.docx
Size: 38,320 bytes."

You may make the wording more natural, but preserve the
same useful information.

Do NOT expose internal step IDs, planner details, tool
metadata, or execution diagnostics in the main response.

Do NOT say:

"STEP: step-1"

"document_writer completed"

"agent execution completed"

"the agent ran successfully"

"the planner selected..."

The interface already displays execution information separately.

============================================================
WHEN A CALCULATION OR CODE EXECUTION WAS PERFORMED
============================================================

Give the user the useful result directly.

Include important calculated values when they are present.

Do not expose Python source code unless the user explicitly
asked for the code.

Example style:

"The calculation is complete.

Result: 42.5

The computation was performed locally."

============================================================
WHEN A SPREADSHEET WAS ANALYZED
============================================================

Summarize the important verified findings clearly.

Include useful totals, averages, minimums, maximums,
counts or other values present in the verified result.

Do not dump raw internal execution data.

============================================================
WHEN KNOWLEDGE WAS SEARCHED
============================================================

Answer the user's question using the retrieved local
knowledge.

Mention the relevant source document name when useful.

If OCR or extracted text is incomplete or damaged, state
that clearly instead of guessing.

============================================================
WHEN A GENERAL MULTI-STEP TASK WAS COMPLETED
============================================================

Provide a natural summary of what NOVA accomplished.

Mention important outputs or files when verified.

Keep the response focused on the user's outcome.

============================================================
STYLE
============================================================

Be:

- clear
- professional
- concise
- helpful
- natural
- confident only when supported by evidence

Use short paragraphs.

Use bullets only when they improve readability.

Do not repeat the user's entire request unnecessarily.

Do not mention:

- prompts
- embeddings
- Chroma
- Ollama
- model routing
- planner internals
- internal implementation details
- hidden system behavior
- execution IDs

Do not use external knowledge.

Return ONLY the final user-facing response.
""".strip()

        result = ollama_manager.generate(
            model=routing.model_name,
            prompt=prompt,
            system=(
                "You are NOVA's final user-facing response engine. "
                "Use only verified local execution results. "
                "Never invent facts or placeholders. "
                "Never expose internal implementation details."
            ),
            temperature=0.1,
            num_predict=1000,
            stream=False,
        )

        response = result.get(
            "response",
            "",
        ).strip()

        if not response:
            raise RuntimeError(
                "NOVA response synthesizer returned an empty response."
            )

        response = self._clean_response(
            response
        )

        if not response:
            raise RuntimeError(
                "NOVA response synthesizer produced an empty cleaned response."
            )

        return response


agent_response_synthesizer = AgentResponseSynthesizer()