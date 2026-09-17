from typing import Any, Dict, List

import re

from app.services.model_engine.model_router import (
    route_request,
)
from app.services.model_engine.ollama_manager import (
    ollama_manager,
)


class AgentResponseSynthesizer:
    """
    Converts executed NOVA agent results into a clear,
    grounded and user-friendly final response.

    Mission Control evidence-review responses are handled
    deterministically from verified reader results so the
    conversational file-by-file output never becomes a raw
    execution-data dump.
    """

    # ------------------------------------------------------------------
    # EVIDENCE REVIEW TOOL CATEGORIES
    # ------------------------------------------------------------------

    EVIDENCE_READER_TOOLS = {
        "document_reader",
        "file_reader",
        "spreadsheet_reader",
        "ocr",
    }

    EVIDENCE_ANALYSIS_TOOLS = {
        "spreadsheet_analysis",
    }

    EVIDENCE_WRITER_TOOLS = {
        "document_writer",
        "pdf_writer",
        "file_writer",
        "spreadsheet_writer",
        "csv_writer",
        "pptx_writer",
        "visualization_writer",
    }

    # ------------------------------------------------------------------
    # CONTEXT BUILDING
    # ------------------------------------------------------------------

    def _build_context(
        self,
        execution_context: Dict[str, Any],
    ) -> str:
        """
        Convert verified tool outputs into a readable context block.

        Internal execution metadata is excluded.
        """

        sections: List[str] = []

        for step_id, result in execution_context.items():

            if str(step_id).startswith("__"):
                continue

            if not isinstance(
                result,
                dict,
            ):
                sections.append(
                    f"VERIFIED RESULT FOR {step_id}:\n{result}"
                )
                continue

            safe_result = dict(
                result
            )

            for internal_key in (
                "__execution_status",
                "__execution_cancelled",
                "__execution_started_steps",
                "__execution_completed_steps",
            ):
                safe_result.pop(
                    internal_key,
                    None,
                )

            sections.append(
                f"VERIFIED RESULT FOR {step_id}:\n{safe_result}"
            )

        return "\n\n".join(
            sections
        )

    # ------------------------------------------------------------------
    # OBJECTIVE DETECTION
    # ------------------------------------------------------------------

    def _is_evidence_review_request(
        self,
        objective: str,
    ) -> bool:
        """
        Detect NOVA evidence/file-review missions.
        """

        text = str(
            objective or ""
        ).strip().lower()

        if not text:
            return False

        markers = (
            "check every attached file",
            "review every attached file",
            "review all attached files",
            "check all attached files",
            "tell me what each file contains",
            "what each file contains",
            "review the attached files",
            "analyze every attached file",
            "analyse every attached file",
            "analyze all attached files",
            "analyse all attached files",
            "evidence review",
            "file review",
            "mission control evidence review",
            "mandatory evidence review",
            "mandatory mission control evidence review",
            "mandatory mission control evidence review deliverable",
            "output/file_review_report.docx",
            "__evidence_review_report__",
        )

        return any(
            marker in text
            for marker in markers
        )

    # ------------------------------------------------------------------
    # RESULT CLASSIFICATION
    # ------------------------------------------------------------------

    def _result_tool_name(
        self,
        result: Dict[str, Any],
    ) -> str:
        return str(
            result.get(
                "tool",
                "",
            )
        ).strip().lower()

    def _is_reader_result(
        self,
        result: Dict[str, Any],
    ) -> bool:
        """
        True only for source-file reader outputs.

        Generated artifacts and analysis outputs are excluded.
        """

        if not isinstance(
            result,
            dict,
        ):
            return False

        tool = self._result_tool_name(
            result
        )

        if tool in self.EVIDENCE_READER_TOOLS:
            return True

        if tool in self.EVIDENCE_WRITER_TOOLS:
            return False

        if tool in self.EVIDENCE_ANALYSIS_TOOLS:
            return False

        file_path = str(
            result.get(
                "file_path",
                "",
            )
        ).strip().replace(
            "\\",
            "/",
        )

        if file_path.lower().startswith(
            "output/"
        ):
            return False

        return bool(
            result.get("content")
            or result.get("text")
            or result.get("extracted_text")
            or result.get("document_text")
            or isinstance(
                result.get("sheets"),
                list,
            )
        )

    def _is_generated_artifact_result(
        self,
        result: Dict[str, Any],
    ) -> bool:
        """
        Detect actual generated workspace artifacts.
        """

        if not isinstance(
            result,
            dict,
        ):
            return False

        tool = self._result_tool_name(
            result
        )

        if tool not in self.EVIDENCE_WRITER_TOOLS:
            return False

        file_path = str(
            result.get(
                "file_path",
                "",
            )
        ).strip().replace(
            "\\",
            "/",
        )

        return bool(
            result.get("created")
            and (
                file_path.lower().startswith(
                    "output/"
                )
                or result.get("file_name")
            )
        )

    # ------------------------------------------------------------------
    # FILE METADATA HELPERS
    # ------------------------------------------------------------------

    def _get_file_name(
        self,
        result: Dict[str, Any],
        index: int,
    ) -> str:
        """
        Resolve the real source filename from a verified reader result.
        """

        name = (
            result.get("file_name")
            or result.get("filename")
            or result.get("name")
            or ""
        )

        if not str(name).strip():

            file_path = str(
                result.get(
                    "file_path",
                    "",
                )
            ).strip()

            if file_path:
                name = file_path.replace(
                    "\\",
                    "/",
                ).split(
                    "/"
                )[-1]

        if not str(name).strip():
            name = f"file {index}"

        return str(
            name
        ).strip()

    def _get_extension(
        self,
        result: Dict[str, Any],
        file_name: str,
    ) -> str:
        extension = ""

        file_name_path = str(
            file_name
        )

        if "." in file_name_path:
            extension = (
                "."
                + file_name_path.rsplit(
                    ".",
                    1,
                )[1].lower()
            )

        if extension:
            return extension

        file_type = str(
            result.get(
                "file_type",
                "",
            )
        ).strip().lower()

        if file_type in {
            "xlsx",
            "csv",
            "pdf",
            "docx",
            "txt",
            "md",
            "json",
            "png",
            "jpg",
            "jpeg",
        }:
            return "." + file_type

        return ""

    # ------------------------------------------------------------------
    # TEXT CLEANUP
    # ------------------------------------------------------------------

    def _normalize_extracted_text(
        self,
        value: Any,
    ) -> str:
        """
        Remove extractor metadata and excessive whitespace while
        retaining actual source content.
        """

        text = str(
            value or ""
        ).strip()

        if not text:
            return ""

        # Remove common page markers emitted by document extractors.
        text = re.sub(
            r"\[\s*PAGE\s+\d+\s*\]",
            " ",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"(?im)^\s*(?:file|file path|workspace|tool|verification|verification status)\s*:\s*.*$",
            "",
            text,
        )

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        return text.strip()

    def _extract_sentences(
        self,
        text: str,
    ) -> List[str]:
        """
        Extract readable sentences from source text.
        """

        normalized = (
            self._normalize_extracted_text(
                text
            )
        )

        if not normalized:
            return []

        sentences = re.split(
            r"(?<=[.!?])\s+",
            normalized,
        )

        return [
            sentence.strip()
            for sentence in sentences
            if sentence.strip()
        ]

    # ------------------------------------------------------------------
    # SPREADSHEET RESPONSE
    # ------------------------------------------------------------------

    def _build_spreadsheet_file_response(
        self,
        result: Dict[str, Any],
    ) -> List[str]:
        """
        Build a user-facing description from actual spreadsheet metadata.
        """

        lines: List[str] = []

        sheets = result.get(
            "sheets",
            [],
        )

        sheets = [
            sheet
            for sheet in sheets
            if isinstance(
                sheet,
                dict,
            )
        ]

        if not sheets:
            lines.append(
                "What it is: a spreadsheet file containing structured tabular data."
            )

            lines.append(
                "What it contains: no sheet-level details were returned by the local reader."
            )

            return lines

        file_type = str(
            result.get(
                "file_type",
                "",
            )
        ).lower()

        if file_type == "xlsx":
            lines.append(
                "What it is: an Excel workbook containing structured tabular data."
            )
        else:
            lines.append(
                "What it is: a CSV file containing structured tabular data."
            )

        sheet_names = [
            str(
                sheet.get(
                    "sheet_name",
                    "",
                )
            ).strip()
            for sheet in sheets
            if str(
                sheet.get(
                    "sheet_name",
                    "",
                )
            ).strip()
        ]

        if sheet_names:
            lines.append(
                "What it is about: "
                + (
                    "The workbook is organized across "
                    if file_type == "xlsx"
                    else "The tabular data is organized in "
                )
                + ", ".join(
                    sheet_names[:8]
                )
                + "."
            )
        else:
            lines.append(
                "What it is about: the file contains structured tabular information."
            )

        lines.append(
            "What it contains:"
        )

        for sheet in sheets[:8]:

            sheet_name = str(
                sheet.get(
                    "sheet_name",
                    "Sheet",
                )
            ).strip() or "Sheet"

            row_count = sheet.get(
                "row_count"
            )

            column_count = sheet.get(
                "column_count"
            )

            headers = [
                str(
                    header
                ).strip()
                for header in (
                    sheet.get(
                        "headers"
                    )
                    or []
                )
                if str(
                    header
                ).strip()
            ][:8]

            detail = (
                f"- {sheet_name}"
            )

            if (
                row_count is not None
                and column_count is not None
            ):
                detail += (
                    f": {row_count} data rows across "
                    f"{column_count} columns"
                )

            if headers:
                detail += (
                    "; key columns: "
                    + ", ".join(
                        headers
                    )
                )

            detail += "."

            lines.append(
                detail
            )

        return lines

    # ------------------------------------------------------------------
    # DOCUMENT / TEXT / OCR RESPONSE
    # ------------------------------------------------------------------

    def _build_text_file_response(
        self,
        result: Dict[str, Any],
        extension: str,
    ) -> List[str]:
        """
        Build a concise file-by-file explanation from actual extracted text.
        """

        lines: List[str] = []

        if extension == ".pdf":
            file_type = "a PDF document"

        elif extension == ".docx":
            file_type = "a Word document"

        elif extension in {
            ".png",
            ".jpg",
            ".jpeg",
        }:
            file_type = "an image file"

        elif extension == ".txt":
            file_type = "a plain-text file"

        elif extension == ".md":
            file_type = "a Markdown document"

        elif extension == ".json":
            file_type = "a JSON data/configuration file"

        elif extension in {
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
        }:
            file_type = (
                f"a {extension.lstrip('.').upper()} source file"
            )

        else:
            file_type = "a locally read file"

        lines.append(
            f"What it is: {file_type}."
        )

        extracted_text = (
            result.get("content")
            or result.get("text")
            or result.get("extracted_text")
            or result.get("document_text")
            or ""
        )

        sentences = (
            self._extract_sentences(
                extracted_text
            )
        )

        if not sentences:
            lines.append(
                "What it is about: no readable subject could be established from the returned content."
            )

            lines.append(
                "What it contains: the local reader returned no readable text."
            )

            return lines

        about = " ".join(
            sentences[:2]
        ).strip()

        if len(about) > 600:
            about = (
                about[:597]
                .rsplit(
                    " ",
                    1,
                )[0]
                + "..."
            )

        lines.append(
            f"What it is about: {about}"
        )

        lines.append(
            "What it contains:"
        )

        headings: List[str] = []

        for raw_line in str(
            extracted_text
        ).splitlines():

            candidate = raw_line.strip()

            candidate = re.sub(
                r"^\s*#{1,6}\s*",
                "",
                candidate,
            )

            candidate = candidate.strip(
                " -*•"
            )

            if (
                candidate
                and len(candidate) <= 120
                and (
                    raw_line.strip().startswith(
                        "#"
                    )
                    or candidate.endswith(
                        ":"
                    )
                )
                and candidate not in headings
            ):
                headings.append(
                    candidate.rstrip(
                        ":"
                    ).strip()
                )

            if len(headings) >= 6:
                break

        if (
            headings
            and extension in {
                ".pdf",
                ".docx",
                ".md",
            }
        ):
            lines.append(
                "- Major sections/topics: "
                + ", ".join(
                    headings
                )
                + "."
            )

        content_summary = " ".join(
            sentences[:3]
        ).strip()

        if len(content_summary) > 900:
            content_summary = (
                content_summary[:897]
                .rsplit(
                    " ",
                    1,
                )[0]
                + "..."
            )

        lines.append(
            f"- Content summary: {content_summary}"
        )

        return lines

    # ------------------------------------------------------------------
    # DETERMINISTIC EVIDENCE REVIEW RESPONSE
    # ------------------------------------------------------------------

    def _build_evidence_review_response(
        self,
        objective: str,
        execution_context: Dict[str, Any],
    ) -> str:
        """
        Build the conversational Mission Control response directly from
        verified source-reader results.

        This intentionally avoids asking the LLM to serialize internal
        dictionaries, preventing raw execution-data dumps.
        """

        source_results: List[
            Dict[str, Any]
        ] = []

        artifact_results: List[
            Dict[str, Any]
        ] = []

        for _, result in execution_context.items():

            if not isinstance(
                result,
                dict,
            ):
                continue

            if self._is_reader_result(
                result
            ):
                source_results.append(
                    result
                )

            elif self._is_generated_artifact_result(
                result
            ):
                artifact_results.append(
                    result
                )

        if not source_results:
            return (
                "NOVA completed the mission flow, but no verified source-file "
                "reader results were available for the final response."
            )

        response_lines: List[str] = [
            "I reviewed all the attached files and examined their actual contents."
        ]

        for index, result in enumerate(
            source_results,
            start=1,
        ):

            file_name = (
                self._get_file_name(
                    result,
                    index,
                )
            )

            extension = (
                self._get_extension(
                    result,
                    file_name,
                )
            )

            response_lines.extend(
                [
                    "",
                    f"### {index}. {file_name}",
                ]
            )

            if (
                extension in {
                    ".xlsx",
                    ".csv",
                }
                and isinstance(
                    result.get(
                        "sheets"
                    ),
                    list,
                )
            ):
                response_lines.extend(
                    self._build_spreadsheet_file_response(
                        result
                    )
                )

            else:
                response_lines.extend(
                    self._build_text_file_response(
                        result,
                        extension,
                    )
                )

        # ------------------------------------------------------------------
        # VERIFIED OUTPUT
        # ------------------------------------------------------------------

        if artifact_results:

            response_lines.extend(
                [
                    "",
                    "### VERIFIED OUTPUT",
                ]
            )

            for artifact in artifact_results:

                artifact_name = (
                    artifact.get(
                        "file_name"
                    )
                    or "generated file"
                )

                artifact_path = str(
                    artifact.get(
                        "file_path",
                        "",
                    )
                ).replace(
                    "\\",
                    "/",
                )

                size_bytes = artifact.get(
                    "size_bytes"
                )

                response_lines.append(
                    f"- {artifact_name}"
                )

                if artifact_path:
                    response_lines.append(
                        f"  Location: {artifact_path}"
                    )

                if isinstance(
                    size_bytes,
                    int,
                ):
                    response_lines.append(
                        f"  Size: {size_bytes:,} bytes"
                    )

                verification = str(
                    artifact.get(
                        "verification",
                        artifact.get(
                            "verification_status",
                            "",
                        ),
                    )
                ).strip()

                if verification:
                    response_lines.append(
                        f"  Verification: {verification}"
                    )

        return "\n".join(
            response_lines
        ).strip()

    # ------------------------------------------------------------------
    # GENERAL RESPONSE CLEANUP
    # ------------------------------------------------------------------

    def _clean_response(
        self,
        response: str,
    ) -> str:
        """
        Remove accidental placeholders and obvious internal
        response artifacts from the model's final answer.
        """

        cleaned = str(
            response or ""
        ).strip()

        if not cleaned:
            return cleaned

        # Remove accidental Markdown code fences.
        if (
            cleaned.startswith("```")
            and cleaned.endswith("```")
        ):

            lines = cleaned.splitlines()

            if lines:
                lines = lines[1:]

            if (
                lines
                and lines[-1].strip() == "```"
            ):
                lines = lines[:-1]

            cleaned = "\n".join(
                lines
            ).strip()

        # Common placeholder patterns.
        placeholder_patterns = [
            r"\[\s*insert date if available\s*\]",
            r"\[\s*insert date\s*\]",
            r"\[\s*date if available\s*\]",
            r"\[\s*insert filename\s*\]",
            r"\[\s*filename\s*\]",
            r"\[\s*insert file path\s*\]",
            r"\[\s*file path\s*\]",
            r"\[\s*insert details\s*\]",
            r"\[\s*details\s*\]",
        ]

        for pattern in placeholder_patterns:
            cleaned = re.sub(
                pattern,
                "",
                cleaned,
                flags=re.IGNORECASE,
            )

        # Remove internal execution labels.
        cleaned = re.sub(
            r"(?im)^\s*step[-_ ]?\d+\s*:\s*.*$",
            "",
            cleaned,
        )

        cleaned = re.sub(
            r"(?im)^\s*(?:planner|agent execution|tool execution)"
            r"(?:\s+(?:details|metadata))?\s*:\s*.*$",
            "",
            cleaned,
        )

        # Collapse excessive blank lines.
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

        objective = str(
            objective or ""
        ).strip()

        if not objective:
            raise ValueError(
                "Cannot synthesize a response without an objective."
            )

        if not execution_context:
            return (
                "I could not complete the request because "
                "there were no verified results available."
            )

        # Mission Control evidence review gets deterministic output.
        #
        # This is the critical path for file-by-file conversational
        # responses and verified output reporting.
        if self._is_evidence_review_request(
            objective
        ):

            response = (
                self._build_evidence_review_response(
                    objective=objective,
                    execution_context=execution_context,
                )
            )

            response = self._clean_response(
                response
            )

            if not response:
                raise RuntimeError(
                    "NOVA evidence-review synthesizer produced an empty response."
                )

            return response

        routing = route_request(
            objective
        )

        context_text = (
            self._build_context(
                execution_context
            )
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

Done — your cybersecurity document has been created.

File: cybersecurity.docx

Location: output/cybersecurity.docx

Size: 38,320 bytes.

Do NOT expose internal step IDs, planner details, tool
metadata, or execution diagnostics in the main response.

============================================================
WHEN A CALCULATION OR CODE EXECUTION WAS PERFORMED
============================================================

Give the user the useful result directly.

Include important calculated values when they are present.

Do not expose Python source code unless the user explicitly
asked for the code.

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

        response = str(
            result.get(
                "response",
                "",
            )
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


# ---------------------------------------------------------------------------
# SHARED SYNTHESIZER INSTANCE
# ---------------------------------------------------------------------------

agent_response_synthesizer = AgentResponseSynthesizer()