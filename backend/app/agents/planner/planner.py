import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agents.planner.plan_models import (
    AgentPlan,
    PlanStep,
)
from app.agents.tools.tool_registry import (
    get_tool,
    get_tool_names,
)
from app.services.model_engine.model_router import (
    route_request,
)
from app.services.model_engine.ollama_manager import (
    ollama_manager,
)


# ---------------------------------------------------------------------------
# PLANNER PROMPTS
# ---------------------------------------------------------------------------

PLANNER_SYSTEM_PROMPT = """
You are NOVA's local agent planning engine.

Your job is to convert a user's objective into a safe,
structured execution plan.

Return ONLY valid JSON.

Required JSON format:

{
  "objective": "string",
  "steps": [
    {
      "id": "step-1",
      "title": "string",
      "description": "string",
      "tool": null,
      "dependencies": [],
      "inputs": {},
      "expected_output": "string"
    }
  ],
  "tools_required": [],
  "expected_outputs": [],
  "verification_required": true
}

Available NOVA tools are:

- document_reader
- document_writer
- knowledge_search
- file_reader
- file_writer
- code_executor
- spreadsheet_reader
- spreadsheet_analysis

IMPORTANT TOOL INPUT RULES:

- knowledge_search:
  "inputs": {
      "query": "search query",
      "top_k": 5
  }

- document_reader:
  "inputs": {
      "file_path": "local document path"
  }

- document_writer:
  "inputs": {
      "file_path": "local workspace DOCX output path",
      "title": "document title",
      "content": "document content"
  }

- file_reader:
  "inputs": {
      "file_path": "local workspace file path"
  }

- file_writer:
  "inputs": {
      "file_path": "local workspace output path",
      "content": "generated content"
  }

- spreadsheet_reader:
  "inputs": {
      "file_path": "local workspace spreadsheet path"
  }

- spreadsheet_analysis:
  "inputs": {
      "file_path": "local workspace spreadsheet path"
  }

- code_executor:
  "inputs": {
      "language": "python",
      "code": "valid Python source code"
  }

Rules:

- Use only the tools listed above.
- Do not invent tool names.
- Keep plans practical and minimal.
- Dependencies must reference step IDs only.
- Never put filenames in dependencies.
- Never use external services.
- Never leave required tool inputs empty.
- Return only valid JSON.
"""


CODE_GENERATOR_SYSTEM_PROMPT = """
You are NOVA's local Python code generation engine.

Generate safe Python code for the user's requested task.

Requirements:

- Return ONLY executable Python source code.
- Do not use Markdown fences.
- Do not explain the code.
- Do not use network access.
- Do not make HTTP requests.
- Do not access external services.
- Do not use subprocess.
- Do not use os.system.
- Do not install packages.
- Prefer Python standard library.
- Print the final useful result clearly.
- Keep the code minimal and deterministic.
"""


FILE_CONTENT_GENERATOR_SYSTEM_PROMPT = """
You are NOVA's local file-content generation engine.

Generate the exact content that should be written into
a requested workspace file.

Requirements:

- Return ONLY the file content.
- Do not use Markdown fences unless the requested file
  itself is Markdown.
- Do not explain your answer outside the file content.
- Do not use external services.
- Do not include imaginary data.
- Follow the user's requested file format.
- Keep the generated content practical and usable.
"""


DOCUMENT_CONTENT_GENERATOR_SYSTEM_PROMPT = """
You are NOVA's local document-content generation engine.

Generate professional content for a DOCX document.

Requirements:

- Return ONLY the document content.
- Do not use Markdown code fences.
- Do not explain the generation process.
- Do not mention that you are an AI model.
- Do not use external services or external data.
- Do not invent facts that were not provided by the user.
- Use clear headings and well-structured paragraphs.
- Use bullet points when useful.
- Keep the document professional and readable.
- Follow the user's requested purpose exactly.
"""


class AgentPlanner:
    """
    Creates validated structured execution plans.

    Critical tool intents are resolved deterministically.

    Python execution requests use the local model to generate
    valid Python source before sandbox execution.

    DOCX requests use the local model to generate document content
    before the document_writer tool creates the actual DOCX file.
    """

    # ------------------------------------------------------------------
    # PROMPT
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        objective: str,
    ) -> str:
        """
        Build the planner prompt.
        """

        available_tools = ", ".join(
            get_tool_names()
        )

        return f"""
Create an execution plan for this NOVA objective:

{objective}

Available tools:

{available_tools}

Important:

- Local knowledge search/retrieval -> knowledge_search
- Reading a PDF/DOCX document -> document_reader
- Creating a DOCX/Word document -> document_writer
- Reading a local text/code/structured file -> file_reader
- Reading CSV/XLSX -> spreadsheet_reader
- Analyzing CSV/XLSX -> spreadsheet_analysis
- Writing plain file content -> file_writer
- Executing Python -> code_executor

Required tool inputs must always be populated.

For knowledge_search:

"inputs": {{
    "query": "<search question>",
    "top_k": 5
}}

For document_reader:

"inputs": {{
    "file_path": "<document path>"
}}

For document_writer:

"inputs": {{
    "file_path": "<workspace DOCX output path>",
    "title": "<document title>",
    "content": "<generated document content>"
}}

For file_reader:

"inputs": {{
    "file_path": "<workspace file path>"
}}

For file_writer:

"inputs": {{
    "file_path": "<workspace output path>",
    "content": "<generated content>"
}}

For spreadsheet_reader:

"inputs": {{
    "file_path": "<workspace spreadsheet path>"
}}

For spreadsheet_analysis:

"inputs": {{
    "file_path": "<workspace spreadsheet path>"
}}

For code_executor:

"inputs": {{
    "language": "python",
    "code": "<valid Python source code>"
}}

Rules:

- Use only available tools.
- Dependencies must contain step IDs only.
- Never invent filenames as dependencies.
- Prefer local NOVA capabilities.
- Never use external services.
- Keep the plan practical and minimal.
- Return only valid JSON.
""".strip()

    # ------------------------------------------------------------------
    # JSON EXTRACTION
    # ------------------------------------------------------------------

    def _extract_json(
        self,
        text: str,
    ) -> Dict[str, Any]:
        """
        Extract the first valid JSON object from model output.
        """

        cleaned = text.strip()

        if not cleaned:
            raise ValueError(
                "Planner model returned empty output."
            )

        decoder = json.JSONDecoder()

        if "```" in cleaned:
            parts = cleaned.split("```")

            for part in parts:
                candidate = part.strip()

                if candidate.lower().startswith("json"):
                    candidate = candidate[4:].strip()

                if not candidate:
                    continue

                try:
                    parsed, _ = decoder.raw_decode(
                        candidate
                    )

                    if isinstance(parsed, dict):
                        return parsed

                except json.JSONDecodeError:
                    continue

        try:
            parsed, _ = decoder.raw_decode(
                cleaned
            )

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            pass

        for index, character in enumerate(
            cleaned
        ):
            if character != "{":
                continue

            candidate = cleaned[index:]

            try:
                parsed, _ = decoder.raw_decode(
                    candidate
                )

                if isinstance(parsed, dict):
                    return parsed

            except json.JSONDecodeError:
                continue

        raise ValueError(
            "Planner model did not return a valid JSON object."
        )

    # ------------------------------------------------------------------
    # PYTHON EXTRACTION
    # ------------------------------------------------------------------

    def _extract_python_code(
        self,
        text: str,
    ) -> str:
        """
        Extract executable Python from local model output.
        """

        cleaned = text.strip()

        if not cleaned:
            raise ValueError(
                "Local code generator returned empty output."
            )

        if "```" in cleaned:
            parts = cleaned.split("```")

            for part in parts:
                candidate = part.strip()

                if not candidate:
                    continue

                lowered = candidate.lower()

                if lowered.startswith("python"):
                    candidate = candidate[6:].strip()

                elif lowered.startswith("py"):
                    candidate = candidate[2:].strip()

                if candidate:
                    return candidate

        return cleaned

    # ------------------------------------------------------------------
    # WORKSPACE PATH EXTRACTION
    # ------------------------------------------------------------------

    def _extract_workspace_path(
        self,
        objective: str,
    ) -> Optional[str]:
        """
        Extract an explicit workspace-relative file path.

        Examples:

        output/calculator.py
        input/data.xlsx
        output/report.txt
        output/report.docx
        temp/test.json
        """

        text = objective.strip()

        pattern = (
            r"(?<![A-Za-z0-9_./\\-])"
            r"((?:output|input|temp)"
            r"[\\/]"
            r"[A-Za-z0-9_.\-\\/]+"
            r"\.[A-Za-z0-9]+)"
            r"(?![A-Za-z0-9_.\-])"
        )

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            return None

        candidate = match.group(1).strip()

        candidate = candidate.rstrip(
            ".,;:)"
        )

        return candidate.replace(
            "\\",
            "/",
        )

    # ------------------------------------------------------------------
    # GENERATED DOCUMENT OUTPUT PATH
    # ------------------------------------------------------------------

    def _generate_document_output_path(
        self,
        objective: str,
    ) -> str:
        """
        Generate a deterministic workspace-relative DOCX output path when
        the user did not explicitly provide one.

        Examples:

        Create a document about cybersecurity
            -> output/cybersecurity.docx

        Generate a report on campus placement analytics
            -> output/campus-placement-analytics.docx
        """

        text = objective.strip()

        # Remove an explicitly supplied workspace path first so the generated
        # slug is based on the document subject rather than the filename.
        explicit_path = self._extract_workspace_path(text)

        if explicit_path:
            return explicit_path

        subject = text

        # Remove common request verbs and document/report words.
        subject = re.sub(
            r"\b(?:please\s+)?(?:create|generate|write|make|prepare|draft)\b",
            " ",
            subject,
            flags=re.IGNORECASE,
        )

        subject = re.sub(
            r"\b(?:a|an|the)\b",
            " ",
            subject,
            flags=re.IGNORECASE,
        )

        subject = re.sub(
            r"\b(?:document|docx|word\s+document|word\s+file|report)\b",
            " ",
            subject,
            flags=re.IGNORECASE,
        )

        subject = re.sub(
            r"\b(?:about|on|regarding|concerning|for|of)\b",
            " ",
            subject,
            flags=re.IGNORECASE,
        )

        # Keep the slug filesystem-safe and readable.
        slug = subject.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = re.sub(r"-{2,}", "-", slug).strip("-")

        if not slug:
            slug = "nova-document"

        # Keep generated filenames reasonably short.
        slug = slug[:80].rstrip("-")

        return f"output/{slug}.docx"

    # ------------------------------------------------------------------
    # TITLE EXTRACTION
    # ------------------------------------------------------------------

    def _extract_document_title(
        self,
        objective: str,
        file_path: str,
    ) -> str:
        """
        Build a deterministic document title.
        """

        path_stem = Path(
            file_path
        ).stem.strip()

        if path_stem:
            title = path_stem.replace(
                "_",
                " ",
            ).replace(
                "-",
                " ",
            )

            return title.title()

        return "NOVA Generated Document"

    # ------------------------------------------------------------------
    # FILE CONTENT GENERATION
    # ------------------------------------------------------------------

    def _generate_file_content(
        self,
        objective: str,
        file_path: str,
    ) -> str:
        """
        Generate plain file content locally using Ollama.
        """

        routing = route_request(
            objective
        )

        extension = Path(
            file_path
        ).suffix.lower()

        prompt = f"""
Generate the exact content for this NOVA workspace file.

User objective:

{objective}

Target file:

{file_path}

File extension:

{extension}

Return ONLY the file content.

Do not include explanations before or after the content.

Do not wrap the content in Markdown fences.
""".strip()

        result = ollama_manager.generate(
            model=routing.model_name,
            prompt=prompt,
            system=FILE_CONTENT_GENERATOR_SYSTEM_PROMPT,
            temperature=0.1,
            num_predict=1500,
            stream=False,
        )

        response = result.get(
            "response",
            "",
        ).strip()

        if not response:
            raise RuntimeError(
                "Local file-content generator returned an empty response."
            )

        return self._strip_markdown_fences(
            response
        )

    # ------------------------------------------------------------------
    # DOCUMENT CONTENT GENERATION
    # ------------------------------------------------------------------

    def _generate_document_content(
        self,
        objective: str,
        file_path: str,
        title: str,
    ) -> str:
        """
        Generate professional DOCX content locally using Ollama.
        """

        routing = route_request(
            objective
        )

        prompt = f"""
Create the content for a professional Word document.

User objective:

{objective}

Target file:

{file_path}

Document title:

{title}

Create useful, well-structured content for the requested document.

Use simple document structure such as:

Heading
Paragraphs

## Section
Paragraphs

- Important point
- Important point

Do not return JSON.

Do not return Python code.

Do not return Markdown code fences.

Return ONLY the document content.
""".strip()

        result = ollama_manager.generate(
            model=routing.model_name,
            prompt=prompt,
            system=DOCUMENT_CONTENT_GENERATOR_SYSTEM_PROMPT,
            temperature=0.1,
            num_predict=1800,
            stream=False,
        )

        response = result.get(
            "response",
            "",
        ).strip()

        if not response:
            raise RuntimeError(
                "Local document-content generator returned an empty response."
            )

        return self._strip_markdown_fences(
            response
        )

    # ------------------------------------------------------------------
    # MARKDOWN FENCE CLEANUP
    # ------------------------------------------------------------------

    def _strip_markdown_fences(
        self,
        text: str,
    ) -> str:
        """
        Remove accidental Markdown code fences from generated content.
        """

        cleaned = str(
            text
        ).strip()

        if not cleaned:
            return cleaned

        if cleaned.startswith("```") and cleaned.endswith("```"):
            lines = cleaned.splitlines()

            if lines:
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            cleaned = "\n".join(
                lines
            ).strip()

        return cleaned

    # ------------------------------------------------------------------
    # INTENT DETECTION
    # ------------------------------------------------------------------

    def _is_knowledge_search_intent(
        self,
        objective: str,
    ) -> bool:
        """
        Detect explicit local knowledge-base requests.
        """

        text = objective.lower().strip()

        knowledge_terms = (
            "knowledge base",
            "knowledge vault",
            "local knowledge",
            "search knowledge",
            "search the knowledge",
            "search local",
            "search the local",
            "retrieve from knowledge",
            "query knowledge",
            "look up in knowledge",
            "find in knowledge",
            "search my documents",
            "search the documents",
            "find in my documents",
        )

        return any(
            term in text
            for term in knowledge_terms
        )

    def _is_code_execution_intent(
        self,
        objective: str,
    ) -> bool:
        """
        Detect explicit requests to execute Python/code.
        """

        text = objective.lower().strip()

        execution_terms = (
            "execute python",
            "run python",
            "execute this python",
            "run this python",
            "execute the code",
            "run the code",
            "execute code",
            "run code",
            "calculate using python",
            "python calculation",
            "run this program",
            "execute this program",
            "code executor",
            "using python",
        )

        return any(
            term in text
            for term in execution_terms
        )

    def _is_document_write_intent(
        self,
        objective: str,
    ) -> bool:
        """
        Detect requests that should create a professional DOCX document.

        This intentionally supports both explicit Word/DOCX wording and
        natural-language requests such as "create a report" or
        "make a document about cybersecurity".
        """

        text = objective.lower().strip()

        document_terms = (
            # Explicit DOCX / Word requests
            "create a docx",
            "create docx",
            "generate a docx",
            "generate docx",
            "write a docx",
            "write docx",
            "make a docx",
            "make docx",
            "create a word document",
            "create word document",
            "generate a word document",
            "generate word document",
            "write a word document",
            "write word document",
            "make a word document",
            "make word document",
            "create a word file",
            "create word file",
            "generate a word file",
            "generate word file",
            "write a word file",
            "write word file",
            "make a word file",
            "make word file",
            ".docx",

            # Natural-language document requests
            "create a document",
            "create document",
            "generate a document",
            "generate document",
            "write a document",
            "write document",
            "make a document",
            "make document",
            "prepare a document",
            "prepare document",
            "draft a document",
            "draft document",

            # Report requests
            "create a report",
            "create report",
            "generate a report",
            "generate report",
            "write a report",
            "write report",
            "make a report",
            "make report",
            "prepare a report",
            "prepare report",
            "draft a report",
            "draft report",
        )

        return any(
            term in text
            for term in document_terms
        )

    def _is_file_read_intent(
        self,
        objective: str,
    ) -> bool:
        """
        Detect requests to inspect local workspace files.
        """

        text = objective.lower().strip()

        file_terms = (
            "read file",
            "read the file",
            "open file",
            "open the file",
            "inspect file",
            "inspect the file",
            "read input/",
            "read output/",
            "read temp/",
            "analyze file",
            "analyse file",
            "analyze the file",
            "analyse the file",
            "view file",
            "show file",
        )

        return any(
            term in text
            for term in file_terms
        )

    def _is_spreadsheet_analysis_intent(
        self,
        objective: str,
    ) -> bool:
        """
        Detect requests requiring spreadsheet analysis.
        """

        text = objective.lower().strip()

        analysis_terms = (
            "analyze spreadsheet",
            "analyse spreadsheet",
            "analyze the spreadsheet",
            "analyse the spreadsheet",
            "analyze excel",
            "analyse excel",
            "analyze the excel",
            "analyse the excel",
            "calculate from spreadsheet",
            "calculate from excel",
            "calculate spreadsheet",
            "spreadsheet statistics",
            "spreadsheet analysis",
            "excel analysis",
            "sales analysis",
            "analyze sales",
            "analyse sales",
        )

        return any(
            term in text
            for term in analysis_terms
        )

    def _is_spreadsheet_intent(
        self,
        objective: str,
    ) -> bool:
        """
        Detect basic spreadsheet-reading requests.
        """

        text = objective.lower().strip()

        spreadsheet_terms = (
            ".xlsx",
            ".csv",
            ".xls",
            "spreadsheet",
            "excel file",
            "excel sheet",
            "excel workbook",
            "workbook",
            "worksheet",
            "read excel",
            "inspect excel",
        )

        return any(
            term in text
            for term in spreadsheet_terms
        )

    def _is_file_write_intent(
        self,
        objective: str,
    ) -> bool:
        """
        Detect explicit plain-file generation requests.

        DOCX requests are handled separately by
        _is_document_write_intent().
        """

        text = objective.lower().strip()

        write_terms = (
            "create a file",
            "create file",
            "write a file",
            "write file",
            "save this to",
            "save it to",
            "save the file",
            "generate a file",
            "generate file",
            "create a python file",
            "create a text file",
            "create a json file",
            "create a csv file",
            "create a javascript file",
            "create a html file",
            "create a css file",
            "create a markdown file",
        )

        return any(
            term in text
            for term in write_terms
        )

    def _is_pdf_write_intent(
        self,
        objective: str,
    ) -> bool:
        """Detect requests to create a PDF document."""
        text = objective.lower().strip()
        pdf_terms = (
            "create a pdf",
            "create pdf",
            "generate a pdf",
            "generate pdf",
            "write a pdf",
            "write pdf",
            "make a pdf",
            "make pdf",
            ".pdf",
            "pdf summary",
            "pdf report",
        )
        return any(term in text for term in pdf_terms)

    def _is_xlsx_write_intent(
        self,
        objective: str,
    ) -> bool:
        """Detect requests to generate an Excel workbook."""
        text = objective.lower().strip()
        xlsx_terms = (
            "create an excel",
            "create excel",
            "generate an excel",
            "generate excel",
            "create xlsx",
            "generate xlsx",
            "excel report",
            "excel workbook",
            "make an excel",
            "make excel",
            "create an excel report",
            "create excel report",
        )
        return any(term in text for term in xlsx_terms)

    def _is_csv_write_intent(
        self,
        objective: str,
    ) -> bool:
        """Detect requests to generate a CSV file."""
        text = objective.lower().strip()
        csv_terms = (
            "create a csv",
            "create csv",
            "generate a csv",
            "generate csv",
            "export csv",
            "export a csv",
            "save as csv",
        )
        return any(term in text for term in csv_terms)

    def _is_pptx_write_intent(
        self,
        objective: str,
    ) -> bool:
        """Detect requests to generate a PowerPoint presentation."""
        text = objective.lower().strip()
        pptx_terms = (
            "create a powerpoint",
            "create powerpoint",
            "generate a powerpoint",
            "generate powerpoint",
            "create a pptx",
            "generate pptx",
            "presentation",
            "slide deck",
            "slides",
            ".pptx",
        )
        return any(term in text for term in pptx_terms)

    def _is_visualization_intent(
        self,
        objective: str,
    ) -> bool:
        """Detect requests to generate data visualizations or charts."""
        text = objective.lower().strip()
        vis_terms = (
            "create a chart",
            "create chart",
            "generate a chart",
            "generate chart",
            "bar chart",
            "line chart",
            "pie chart",
            "scatter plot",
            "visual summary",
            "plot the data",
            "visualize",
            "visualise",
        )
        return any(term in text for term in vis_terms)

    # ------------------------------------------------------------------
    # KNOWLEDGE SEARCH PLAN
    # ------------------------------------------------------------------

    def _force_knowledge_search_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:
        """
        Build a deterministic knowledge-search plan.
        """

        return {
            "objective": objective,
            "steps": [
                {
                    "id": "step-1",
                    "title": "Search local knowledge base",
                    "description": (
                        "Search NOVA's local knowledge base "
                        "for information relevant to the "
                        "user's objective."
                    ),
                    "tool": "knowledge_search",
                    "dependencies": [],
                    "inputs": {
                        "query": objective,
                        "top_k": 5,
                    },
                    "expected_output": (
                        "Relevant local knowledge results."
                    ),
                }
            ],
            "tools_required": [
                "knowledge_search"
            ],
            "expected_outputs": [
                "Relevant local knowledge results"
            ],
            "verification_required": True,
        }

    # ------------------------------------------------------------------
    # CODE EXECUTION PLAN
    # ------------------------------------------------------------------

    def _force_code_execution_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:
        """
        Build a deterministic Python execution plan.
        """

        code = self._generate_python_code(
            objective
        )

        return {
            "objective": objective,
            "steps": [
                {
                    "id": "step-1",
                    "title": "Execute Python code",
                    "description": (
                        "Execute locally generated Python "
                        "inside NOVA's isolated sandbox."
                    ),
                    "tool": "code_executor",
                    "dependencies": [],
                    "inputs": {
                        "language": "python",
                        "code": code,
                    },
                    "expected_output": (
                        "Successful local Python execution result."
                    ),
                }
            ],
            "tools_required": [
                "code_executor"
            ],
            "expected_outputs": [
                "Python execution result"
            ],
            "verification_required": True,
        }

    # ------------------------------------------------------------------
    # FILE READ PLAN
    # ------------------------------------------------------------------

    def _force_file_read_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:
        """
        Build a file-reader plan using the explicitly
        supplied workspace path when available.
        """

        file_path = (
            self._extract_workspace_path(
                objective
            )
        )

        if file_path:
            return {
                "objective": objective,
                "steps": [
                    {
                        "id": "step-1",
                        "title": "Read local file",
                        "description": (
                            "Read the requested NOVA "
                            "workspace file."
                        ),
                        "tool": "file_reader",
                        "dependencies": [],
                        "inputs": {
                            "file_path": file_path,
                        },
                        "expected_output": (
                            "Contents of the requested file."
                        ),
                    }
                ],
                "tools_required": [
                    "file_reader"
                ],
                "expected_outputs": [
                    "File contents"
                ],
                "verification_required": True,
            }

        return self._build_model_file_read_plan(
            objective
        )

    def _build_model_file_read_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:
        """
        Fallback to the local model when no explicit
        workspace path can be extracted.
        """

        routing = route_request(
            objective
        )

        prompt = f"""
Create a one-step NOVA file-reader plan.

User objective:

{objective}

Use ONLY:

file_reader

The required input is:

"inputs": {{
    "file_path": "<local NOVA workspace file path>"
}}

Return ONLY valid JSON.
""".strip()

        result = ollama_manager.generate(
            model=routing.model_name,
            prompt=prompt,
            system=PLANNER_SYSTEM_PROMPT,
            temperature=0.0,
            num_predict=512,
            stream=False,
        )

        response = result.get(
            "response",
            "",
        ).strip()

        if not response:
            raise RuntimeError(
                "File-reader planner returned an empty response."
            )

        return self._extract_json(
            response
        )

    # ------------------------------------------------------------------
    # SPREADSHEET READING PLAN
    # ------------------------------------------------------------------

    def _force_spreadsheet_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:
        """
        Build a spreadsheet-reader plan.
        """

        file_path = (
            self._extract_workspace_path(
                objective
            )
        )

        if file_path:
            return {
                "objective": objective,
                "steps": [
                    {
                        "id": "step-1",
                        "title": "Read spreadsheet",
                        "description": (
                            "Read the requested local "
                            "spreadsheet."
                        ),
                        "tool": "spreadsheet_reader",
                        "dependencies": [],
                        "inputs": {
                            "file_path": file_path,
                        },
                        "expected_output": (
                            "Structured spreadsheet data."
                        ),
                    }
                ],
                "tools_required": [
                    "spreadsheet_reader"
                ],
                "expected_outputs": [
                    "Structured spreadsheet data"
                ],
                "verification_required": True,
            }

        return self._build_model_spreadsheet_plan(
            objective
        )

    def _build_model_spreadsheet_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:
        """
        Fallback spreadsheet plan using local model.
        """

        routing = route_request(
            objective
        )

        prompt = f"""
Create a one-step NOVA spreadsheet-reader plan.

User objective:

{objective}

Use ONLY:

spreadsheet_reader

The required input is:

"inputs": {{
    "file_path": "<local NOVA workspace .xlsx or .csv path>"
}}

Return ONLY valid JSON.
""".strip()

        result = ollama_manager.generate(
            model=routing.model_name,
            prompt=prompt,
            system=PLANNER_SYSTEM_PROMPT,
            temperature=0.0,
            num_predict=512,
            stream=False,
        )

        response = result.get(
            "response",
            "",
        ).strip()

        if not response:
            raise RuntimeError(
                "Spreadsheet planner returned an empty response."
            )

        return self._extract_json(
            response
        )

    # ------------------------------------------------------------------
    # SPREADSHEET ANALYSIS PLAN
    # ------------------------------------------------------------------

    def _force_spreadsheet_analysis_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:
        """
        Build a spreadsheet-analysis plan.
        """

        file_path = (
            self._extract_workspace_path(
                objective
            )
        )

        if file_path:
            return {
                "objective": objective,
                "steps": [
                    {
                        "id": "step-1",
                        "title": "Analyze spreadsheet",
                        "description": (
                            "Analyze the requested local "
                            "spreadsheet."
                        ),
                        "tool": "spreadsheet_analysis",
                        "dependencies": [],
                        "inputs": {
                            "file_path": file_path,
                        },
                        "expected_output": (
                            "Deterministic spreadsheet analysis."
                        ),
                    }
                ],
                "tools_required": [
                    "spreadsheet_analysis"
                ],
                "expected_outputs": [
                    "Spreadsheet analysis"
                ],
                "verification_required": True,
            }

        return self._build_model_spreadsheet_analysis_plan(
            objective
        )

    def _build_model_spreadsheet_analysis_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:
        """
        Fallback spreadsheet-analysis plan using local model.
        """

        routing = route_request(
            objective
        )

        prompt = f"""
Create a one-step NOVA spreadsheet-analysis plan.

User objective:

{objective}

Use ONLY:

spreadsheet_analysis

The required input is:

"inputs": {{
    "file_path": "<local NOVA workspace .xlsx or .csv path>"
}}

Return ONLY valid JSON.
""".strip()

        result = ollama_manager.generate(
            model=routing.model_name,
            prompt=prompt,
            system=PLANNER_SYSTEM_PROMPT,
            temperature=0.0,
            num_predict=512,
            stream=False,
        )

        response = result.get(
            "response",
            "",
        ).strip()

        if not response:
            raise RuntimeError(
                "Spreadsheet-analysis planner returned an empty response."
            )

        return self._extract_json(
            response
        )

    # ------------------------------------------------------------------
    # FILE WRITE PLAN
    # ------------------------------------------------------------------

    def _force_file_write_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:
        """
        Build a deterministic file-writer plan.

        The output path is extracted directly from the
        user's objective.
        """

        file_path = (
            self._extract_workspace_path(
                objective
            )
        )

        if not file_path:
            raise ValueError(
                "Please provide a workspace output path, "
                "for example output/calculator.py."
            )

        content = self._generate_file_content(
            objective=objective,
            file_path=file_path,
        )

        return {
            "objective": objective,
            "steps": [
                {
                    "id": "step-1",
                    "title": "Write local file",
                    "description": (
                        "Write locally generated content "
                        "to the requested NOVA workspace path."
                    ),
                    "tool": "file_writer",
                    "dependencies": [],
                    "inputs": {
                        "file_path": file_path,
                        "content": content,
                    },
                    "expected_output": (
                        "File successfully created in "
                        "the NOVA workspace."
                    ),
                }
            ],
            "tools_required": [
                "file_writer"
            ],
            "expected_outputs": [
                "Created workspace file"
            ],
            "verification_required": True,
        }

    # ------------------------------------------------------------------
    # DOCUMENT WRITE PLAN
    # ------------------------------------------------------------------

    def _force_document_write_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:
        """
        Build a deterministic DOCX document-writer plan.

        The target path is extracted directly from the user's
        objective. The document content is generated locally
        before execution.
        """

        file_path = (
            self._extract_workspace_path(
                objective
            )
            or self._generate_document_output_path(
                objective
            )
        )

        extension = Path(
            file_path
        ).suffix.lower()

        if extension != ".docx":
            raise ValueError(
                "document_writer requires a .docx output path."
            )

        title = self._extract_document_title(
            objective=objective,
            file_path=file_path,
        )

        content = self._generate_document_content(
            objective=objective,
            file_path=file_path,
            title=title,
        )

        return {
            "objective": objective,
            "steps": [
                {
                    "id": "step-1",
                    "title": "Create DOCX document",
                    "description": (
                        "Generate a professional Word document "
                        "using locally generated content."
                    ),
                    "tool": "document_writer",
                    "dependencies": [],
                    "inputs": {
                        "file_path": file_path,
                        "title": title,
                        "content": content,
                    },
                    "expected_output": (
                        "DOCX document successfully created "
                        "inside the NOVA workspace."
                    ),
                }
            ],
            "tools_required": [
                "document_writer"
            ],
            "expected_outputs": [
                "Created DOCX document"
            ],
            "verification_required": True,
        }

    # ------------------------------------------------------------------
    # PDF WRITE PLAN
    # ------------------------------------------------------------------

    def _force_pdf_write_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:
        """Build a deterministic PDF writer plan."""
        file_path = (
            self._extract_workspace_path(objective)
            or self._generate_document_output_path(objective).replace(".docx", ".pdf")
        )
        if not file_path.endswith(".pdf"):
            file_path = str(Path(file_path).with_suffix(".pdf")).replace("\\", "/")

        title = self._extract_document_title(objective, file_path)
        content = self._generate_document_content(objective, file_path, title)

        return {
            "objective": objective,
            "steps": [
                {
                    "id": "step-1",
                    "title": "Create PDF document",
                    "description": "Generate a formatted PDF document using local ReportLab engine.",
                    "tool": "pdf_writer",
                    "dependencies": [],
                    "inputs": {
                        "file_path": file_path,
                        "title": title,
                        "content": content,
                    },
                    "expected_output": "PDF document created and verified.",
                }
            ],
            "tools_required": ["pdf_writer"],
            "expected_outputs": ["Created PDF document"],
            "verification_required": True,
        }

    # ------------------------------------------------------------------
    # XLSX WRITE PLAN
    # ------------------------------------------------------------------

    def _force_xlsx_write_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:
        """Build a deterministic Excel workbook plan."""
        file_path = (
            self._extract_workspace_path(objective)
            or "output/excel_report.xlsx"
        )
        if not file_path.endswith(".xlsx"):
            file_path = str(Path(file_path).with_suffix(".xlsx")).replace("\\", "/")

        title = self._extract_document_title(objective, file_path)
        content = self._generate_document_content(objective, file_path, title)

        return {
            "objective": objective,
            "steps": [
                {
                    "id": "step-1",
                    "title": "Create Excel workbook",
                    "description": "Generate a styled Excel workbook with formatted headers and data.",
                    "tool": "spreadsheet_writer",
                    "dependencies": [],
                    "inputs": {
                        "file_path": file_path,
                        "title": title,
                        "content": content,
                    },
                    "expected_output": "Excel workbook created and verified.",
                }
            ],
            "tools_required": ["spreadsheet_writer"],
            "expected_outputs": ["Created XLSX workbook"],
            "verification_required": True,
        }

    # ------------------------------------------------------------------
    # CSV WRITE PLAN
    # ------------------------------------------------------------------

    def _force_csv_write_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:
        """Build a deterministic CSV generation plan."""
        file_path = (
            self._extract_workspace_path(objective)
            or "output/dataset.csv"
        )
        if not file_path.endswith(".csv"):
            file_path = str(Path(file_path).with_suffix(".csv")).replace("\\", "/")

        content = self._generate_file_content(objective, file_path)

        return {
            "objective": objective,
            "steps": [
                {
                    "id": "step-1",
                    "title": "Create CSV file",
                    "description": "Generate a clean CSV dataset file in the workspace.",
                    "tool": "csv_writer",
                    "dependencies": [],
                    "inputs": {
                        "file_path": file_path,
                        "content": content,
                    },
                    "expected_output": "CSV file created and verified.",
                }
            ],
            "tools_required": ["csv_writer"],
            "expected_outputs": ["Created CSV file"],
            "verification_required": True,
        }

    # ------------------------------------------------------------------
    # PPTX WRITE PLAN
    # ------------------------------------------------------------------

    def _force_pptx_write_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:
        """Build a deterministic PowerPoint presentation plan."""
        file_path = (
            self._extract_workspace_path(objective)
            or "output/presentation.pptx"
        )
        if not file_path.endswith(".pptx"):
            file_path = str(Path(file_path).with_suffix(".pptx")).replace("\\", "/")

        title = self._extract_document_title(objective, file_path)
        content = self._generate_document_content(objective, file_path, title)

        return {
            "objective": objective,
            "steps": [
                {
                    "id": "step-1",
                    "title": "Create PowerPoint deck",
                    "description": "Generate a styled PPTX presentation in NOVA dark theme.",
                    "tool": "pptx_writer",
                    "dependencies": [],
                    "inputs": {
                        "file_path": file_path,
                        "title": title,
                        "content": content,
                    },
                    "expected_output": "PPTX presentation created and verified.",
                }
            ],
            "tools_required": ["pptx_writer"],
            "expected_outputs": ["Created PPTX presentation"],
            "verification_required": True,
        }

    # ------------------------------------------------------------------
    # VISUALIZATION PLAN
    # ------------------------------------------------------------------

    def _force_visualization_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:
        """Build a deterministic data visualization plan."""
        file_path = (
            self._extract_workspace_path(objective)
            or "output/data_chart.png"
        )
        if not file_path.endswith((".png", ".jpg", ".jpeg")):
            file_path = str(Path(file_path).with_suffix(".png")).replace("\\", "/")

        chart_type = "bar"
        obj_lower = objective.lower()
        if "line" in obj_lower or "trend" in obj_lower:
            chart_type = "line"
        elif "pie" in obj_lower or "donut" in obj_lower:
            chart_type = "pie"
        elif "scatter" in obj_lower:
            chart_type = "scatter"

        title = self._extract_document_title(objective, file_path)

        return {
            "objective": objective,
            "steps": [
                {
                    "id": "step-1",
                    "title": "Generate data visualization",
                    "description": "Render a high-resolution chart PNG using local Matplotlib engine.",
                    "tool": "visualization_writer",
                    "dependencies": [],
                    "inputs": {
                        "file_path": file_path,
                        "title": title,
                        "chart_type": chart_type,
                    },
                    "expected_output": "Chart PNG generated and verified.",
                }
            ],
            "tools_required": ["visualization_writer"],
            "expected_outputs": ["Created chart image"],
            "verification_required": True,
        }

    # ------------------------------------------------------------------
    # LOCAL PYTHON GENERATION
    # ------------------------------------------------------------------

    def _generate_python_code(
        self,
        objective: str,
    ) -> str:
        """
        Use NOVA's local Ollama model to convert
        natural language into valid Python source.
        """

        routing = route_request(
            objective
        )

        prompt = f"""
Convert this user request into executable Python:

{objective}

Return only the Python source code.

The Python program must:

- perform the requested calculation or operation
- print the useful final result
- avoid network access
- avoid external services
- avoid subprocess/system commands
- use only safe local Python operations
""".strip()

        result = ollama_manager.generate(
            model=routing.model_name,
            prompt=prompt,
            system=CODE_GENERATOR_SYSTEM_PROMPT,
            temperature=0.0,
            num_predict=800,
            stream=False,
        )

        response = result.get(
            "response",
            "",
        ).strip()

        if not response:
            raise RuntimeError(
                "Local Python code generator returned an empty response."
            )

        code = self._extract_python_code(
            response
        ).strip()

        if not code:
            raise RuntimeError(
                "Local Python code generator produced empty code."
            )

        return code

    # ------------------------------------------------------------------
    # INPUT NORMALIZATION
    # ------------------------------------------------------------------

    def _normalize_tool_inputs(
        self,
        tool: str | None,
        inputs: Dict[str, Any],
        objective: str,
    ) -> Dict[str, Any]:
        """
        Normalize required inputs for known tools.
        """

        normalized_inputs = dict(
            inputs
        )

        if not tool:
            return normalized_inputs

        if tool == "knowledge_search":
            query = normalized_inputs.get(
                "query"
            )

            if (
                query is None
                or not str(query).strip()
            ):
                normalized_inputs["query"] = (
                    objective.strip()
                )
            else:
                normalized_inputs["query"] = (
                    str(query).strip()
                )

            top_k = normalized_inputs.get(
                "top_k",
                5,
            )

            try:
                top_k = int(top_k)
            except (
                TypeError,
                ValueError,
            ):
                top_k = 5

            normalized_inputs["top_k"] = max(
                1,
                min(top_k, 10),
            )

        elif tool in {
            "document_reader",
            "file_reader",
            "spreadsheet_reader",
            "spreadsheet_analysis",
        }:
            file_path = normalized_inputs.get(
                "file_path"
            )

            if file_path is not None:
                normalized_inputs["file_path"] = (
                    str(file_path).strip()
                )

        elif tool == "document_writer":
            file_path = normalized_inputs.get(
                "file_path"
            )

            if file_path is not None:
                normalized_inputs["file_path"] = (
                    str(file_path).strip()
                )

            title = normalized_inputs.get(
                "title"
            )

            if title is not None:
                normalized_inputs["title"] = (
                    str(title).strip()
                )

            content = normalized_inputs.get(
                "content"
            )

            if content is not None:
                normalized_inputs["content"] = (
                    self._strip_markdown_fences(
                        str(content)
                    )
                )

        elif tool == "file_writer":
            file_path = normalized_inputs.get(
                "file_path"
            )

            if file_path is not None:
                normalized_inputs["file_path"] = (
                    str(file_path).strip()
                )

            content = normalized_inputs.get(
                "content"
            )

            if content is not None:
                normalized_inputs["content"] = (
                    self._strip_markdown_fences(
                        str(content)
                    )
                )

        elif tool == "code_executor":
            language = normalized_inputs.get(
                "language",
                "python",
            )

            if not str(language).strip():
                language = "python"

            normalized_inputs["language"] = (
                str(language).strip().lower()
            )

            code = normalized_inputs.get(
                "code"
            )

            if code is not None:
                normalized_inputs["code"] = (
                    str(code)
                )

        return normalized_inputs

    # ------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------

    def _validate_dependencies(
        self,
        steps: List[PlanStep],
    ) -> None:
        """
        Ensure every dependency references an existing step ID.
        """

        step_ids = {
            step.id
            for step in steps
        }

        for step in steps:
            for dependency in step.dependencies:
                if dependency not in step_ids:
                    raise ValueError(
                        f"Invalid dependency '{dependency}' "
                        f"in step '{step.id}'. "
                        "Dependencies must reference "
                        "existing step IDs."
                    )

    def _validate_tools(
        self,
        steps: List[PlanStep],
        tools_required: List[str],
    ) -> List[str]:
        """
        Validate all requested tools against NOVA's allow-list.
        """

        discovered_tools = set(
            tools_required
        )

        for step in steps:
            if step.tool:
                discovered_tools.add(
                    step.tool
                )

        valid_tools = []

        for tool_name in discovered_tools:
            tool_name = str(
                tool_name
            ).strip()

            if not tool_name:
                continue

            tool = get_tool(
                tool_name
            )

            if not tool:
                raise ValueError(
                    f"Planner requested unknown tool "
                    f"'{tool_name}'."
                )

            if not tool.enabled:
                raise ValueError(
                    f"Planner requested disabled tool "
                    f"'{tool_name}'."
                )

            valid_tools.append(
                tool_name
            )

        return sorted(
            valid_tools
        )

    # ------------------------------------------------------------------
    # PLAN NORMALIZATION
    # ------------------------------------------------------------------

    def _normalize_plan(
        self,
        objective: str,
        data: Dict[str, Any],
    ) -> AgentPlan:
        """
        Convert raw planner JSON into a validated AgentPlan.
        """

        raw_steps = data.get(
            "steps",
            [],
        )

        if not isinstance(
            raw_steps,
            list,
        ):
            raw_steps = []

        steps: List[PlanStep] = []

        for index, raw_step in enumerate(
            raw_steps
        ):
            if not isinstance(
                raw_step,
                dict,
            ):
                continue

            step_id = str(
                raw_step.get(
                    "id",
                    f"step-{index + 1}",
                )
            ).strip()

            if not step_id:
                step_id = f"step-{index + 1}"

            title = str(
                raw_step.get(
                    "title",
                    f"Step {index + 1}",
                )
            ).strip()

            description = str(
                raw_step.get(
                    "description",
                    "",
                )
            ).strip()

            tool = raw_step.get(
                "tool"
            )

            if tool is not None:
                tool = str(
                    tool
                ).strip()

                if not tool:
                    tool = None

            dependencies = raw_step.get(
                "dependencies",
                [],
            )

            if not isinstance(
                dependencies,
                list,
            ):
                dependencies = []

            normalized_dependencies = [
                str(item).strip()
                for item in dependencies
                if str(item).strip()
            ]

            inputs = raw_step.get(
                "inputs",
                {},
            )

            if not isinstance(
                inputs,
                dict,
            ):
                inputs = {}

            inputs = self._normalize_tool_inputs(
                tool=tool,
                inputs=inputs,
                objective=objective,
            )

            expected_output = raw_step.get(
                "expected_output"
            )

            if expected_output is not None:
                expected_output = str(
                    expected_output
                ).strip()

            steps.append(
                PlanStep(
                    id=step_id,
                    title=title,
                    description=description,
                    tool=tool,
                    dependencies=(
                        normalized_dependencies
                    ),
                    inputs=inputs,
                    expected_output=(
                        expected_output
                    ),
                )
            )

        if not steps:
            raise ValueError(
                "Planner returned no executable steps."
            )

        tools_required = data.get(
            "tools_required",
            [],
        )

        if not isinstance(
            tools_required,
            list,
        ):
            tools_required = []

        tools_required = [
            str(tool).strip()
            for tool in tools_required
            if str(tool).strip()
        ]

        expected_outputs = data.get(
            "expected_outputs",
            [],
        )

        if not isinstance(
            expected_outputs,
            list,
        ):
            expected_outputs = []

        expected_outputs = [
            str(output).strip()
            for output in expected_outputs
            if str(output).strip()
        ]

        validated_tools = (
            self._validate_tools(
                steps,
                tools_required,
            )
        )

        plan = AgentPlan(
            id=(
                f"plan-"
                f"{uuid.uuid4().hex[:12]}"
            ),
            objective=objective,
            steps=steps,
            tools_required=(
                validated_tools
            ),
            expected_outputs=(
                expected_outputs
            ),
            verification_required=bool(
                data.get(
                    "verification_required",
                    True,
                )
            ),
        )

        self._validate_dependencies(
            plan.steps
        )

        return plan

    # ------------------------------------------------------------------
    # PLAN CREATION
    # ------------------------------------------------------------------

    def create_plan(
        self,
        objective: str,
    ) -> AgentPlan:
        """
        Generate and validate an AgentPlan.

        Critical intents are handled deterministically
        before general local LLM planning.
        """

        objective = objective.strip()

        if not objective:
            raise ValueError(
                "Agent objective cannot be empty."
            )

        # --------------------------------------------------------------
        # KNOWLEDGE SEARCH
        # --------------------------------------------------------------

        if self._is_knowledge_search_intent(
            objective
        ):
            raw_plan = (
                self._force_knowledge_search_plan(
                    objective
                )
            )

            return self._normalize_plan(
                objective,
                raw_plan,
            )

        # --------------------------------------------------------------
        # CODE EXECUTION
        # --------------------------------------------------------------

        if self._is_code_execution_intent(
            objective
        ):
            raw_plan = (
                self._force_code_execution_plan(
                    objective
                )
            )

            return self._normalize_plan(
                objective,
                raw_plan,
            )

        # --------------------------------------------------------------
        # PDF DOCUMENT WRITING
        # --------------------------------------------------------------

        if self._is_pdf_write_intent(objective):
            raw_plan = self._force_pdf_write_plan(objective)
            return self._normalize_plan(objective, raw_plan)

        # --------------------------------------------------------------
        # XLSX SPREADSHEET WRITING
        # --------------------------------------------------------------

        if self._is_xlsx_write_intent(objective):
            raw_plan = self._force_xlsx_write_plan(objective)
            return self._normalize_plan(objective, raw_plan)

        # --------------------------------------------------------------
        # CSV FILE WRITING
        # --------------------------------------------------------------

        if self._is_csv_write_intent(objective):
            raw_plan = self._force_csv_write_plan(objective)
            return self._normalize_plan(objective, raw_plan)

        # --------------------------------------------------------------
        # PPTX PRESENTATION WRITING
        # --------------------------------------------------------------

        if self._is_pptx_write_intent(objective):
            raw_plan = self._force_pptx_write_plan(objective)
            return self._normalize_plan(objective, raw_plan)

        # --------------------------------------------------------------
        # VISUALIZATION / CHART GENERATION
        # --------------------------------------------------------------

        if self._is_visualization_intent(objective):
            raw_plan = self._force_visualization_plan(objective)
            return self._normalize_plan(objective, raw_plan)

        # --------------------------------------------------------------
        # DOCX DOCUMENT WRITING
        # --------------------------------------------------------------

        if self._is_document_write_intent(
            objective
        ):
            raw_plan = (
                self._force_document_write_plan(
                    objective
                )
            )

            return self._normalize_plan(
                objective,
                raw_plan,
            )

        # --------------------------------------------------------------
        # PLAIN FILE WRITING
        # --------------------------------------------------------------

        if self._is_file_write_intent(
            objective
        ):
            raw_plan = (
                self._force_file_write_plan(
                    objective
                )
            )

            return self._normalize_plan(
                objective,
                raw_plan,
            )

        # --------------------------------------------------------------
        # SPREADSHEET ANALYSIS
        # --------------------------------------------------------------

        if self._is_spreadsheet_analysis_intent(
            objective
        ):
            raw_plan = (
                self._force_spreadsheet_analysis_plan(
                    objective
                )
            )

            return self._normalize_plan(
                objective,
                raw_plan,
            )

        # --------------------------------------------------------------
        # SPREADSHEET READING
        # --------------------------------------------------------------

        if self._is_spreadsheet_intent(
            objective
        ):
            raw_plan = (
                self._force_spreadsheet_plan(
                    objective
                )
            )

            return self._normalize_plan(
                objective,
                raw_plan,
            )

        # --------------------------------------------------------------
        # LOCAL FILE READING
        # --------------------------------------------------------------

        if self._is_file_read_intent(
            objective
        ):
            raw_plan = (
                self._force_file_read_plan(
                    objective
                )
            )

            return self._normalize_plan(
                objective,
                raw_plan,
            )

        # --------------------------------------------------------------
        # GENERAL LOCAL MODEL PLANNING
        # --------------------------------------------------------------

        routing = route_request(
            objective
        )

        prompt = self._build_prompt(
            objective
        )

        result = ollama_manager.generate(
            model=routing.model_name,
            prompt=prompt,
            system=PLANNER_SYSTEM_PROMPT,
            temperature=0.2,
            num_predict=1024,
            stream=False,
        )

        response = result.get(
            "response",
            "",
        ).strip()

        if not response:
            raise RuntimeError(
                "Planner model returned an empty response."
            )

        raw_plan = self._extract_json(
            response
        )

        return self._normalize_plan(
            objective,
            raw_plan,
        )


# ---------------------------------------------------------------------------
# SHARED PLANNER INSTANCE
# ---------------------------------------------------------------------------

agent_planner = AgentPlanner()