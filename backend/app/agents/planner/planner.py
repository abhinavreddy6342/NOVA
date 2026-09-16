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
- pdf_writer
- spreadsheet_writer
- csv_writer
- pptx_writer
- visualization_writer

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

- pdf_writer:
  "inputs": {
      "file_path": "local workspace PDF output path",
      "title": "document title",
      "content": "generated document content"
  }

- spreadsheet_writer:
  "inputs": {
      "file_path": "local workspace XLSX output path",
      "title": "workbook title",
      "content": "generated workbook content"
  }

- csv_writer:
  "inputs": {
      "file_path": "local workspace CSV output path",
      "content": "CSV content"
  }

- pptx_writer:
  "inputs": {
      "file_path": "local workspace PPTX output path",
      "title": "presentation title",
      "subtitle": "presentation subtitle",
      "slides": [
        {
          "title": "slide title",
          "bullets": [
            "bullet point"
          ],
          "image_path": null
        }
      ],
      "content": "presentation content"
  }

- visualization_writer:
  "inputs": {
      "file_path": "local workspace image output path",
      "title": "chart title",
      "chart_type": "bar"
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
- NEVER use a workspace/input path as the output path of a writer tool.
- Writer tools must create files under workspace/output/.
- When a user asks to review, inspect, analyze, summarize, explain, or tell
  what supplied files are about, FIRST READ THE ACTUAL SUPPLIED FILES.
- Never replace actual file reading with generic descriptions.
- Never guess what a file contains from its filename or extension.
- Never say that a file "may contain" something when the actual file can be read.
- For multiple supplied files, create one read/analyze step per real file.
- After reading supplied files, allow the final response layer to synthesize
  the actual results into a file-by-file answer.
- Do not create a report artifact unless the user explicitly requests a
  document, PDF, DOCX, Excel workbook, CSV, PowerPoint, or other output file.
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


# ---------------------------------------------------------------------------
# PRESENTATION CONTENT GENERATOR
# ---------------------------------------------------------------------------

PRESENTATION_CONTENT_GENERATOR_SYSTEM_PROMPT = """
You are NOVA's local PowerPoint presentation content generation engine.

Your job is to transform a user's presentation request into
a professional, structured slide deck specification.

Return ONLY valid JSON.

Required format:

{
  "title": "presentation title",
  "subtitle": "short professional subtitle",
  "slides": [
    {
      "title": "slide title",
      "bullets": [
        "concise presentation point",
        "concise presentation point",
        "concise presentation point"
      ],
      "image_path": null
    }
  ]
}

Requirements:

- Generate 6 to 10 content slides unless the user explicitly asks
  for a different number.
- Do NOT include the title slide inside the "slides" array.
- The title slide is created automatically by NOVA.
- Every content slide must have a clear title.
- Use 3 to 6 concise bullets per slide.
- Keep bullets presentation-friendly rather than paragraph-length.
- Avoid repeating the same information across slides.
- Organize the presentation logically.
- Start with context/problem/definition when appropriate.
- Follow with core concepts, benefits, applications, implementation,
  challenges, and conclusion when appropriate to the topic.
- Use professional business/technical language.
- Do not invent statistics, company facts, case studies, or citations.
- Do not use external services.
- Do not use network access.
- Do not include Markdown fences.
- "image_path" must normally be null unless the user supplied an
  existing NOVA workspace image path.
- Never invent image file paths.
- Do not put explanations outside the JSON.
- The presentation should feel like a real executive/technical
  presentation, not a text outline.
"""


class AgentPlanner:
    """
    Creates validated structured execution plans.

    Python execution requests use the local model to generate
    valid Python source before sandbox execution.

    Artifact-generation requests use the local model to generate
    artifact content before the corresponding writer tool creates
    the actual artifact.

    Evidence-review requests are handled deterministically so that
    actual supplied source files are read before NOVA produces its
    final answer.
    """

    # ------------------------------------------------------------------
    # PROMPT
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        objective: str,
    ) -> str:

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
- Creating PDF -> pdf_writer
- Creating Excel workbook -> spreadsheet_writer
- Creating CSV -> csv_writer
- Creating PowerPoint -> pptx_writer
- Creating charts -> visualization_writer
- Executing Python -> code_executor

For file-review requests:

- Identify every real supplied source file.
- Read every supplied source file first.
- Use document_reader for PDF/DOCX.
- Use spreadsheet_reader for CSV/XLSX.
- Use file_reader for TXT/MD/JSON and other supported text files.
- Do not create a report artifact unless explicitly requested.
- Let the final response synthesize the actual tool results.

IMPORTANT PATH RULE:

- workspace/input/... is for source files only.
- workspace/output/... is for generated files only.
- Never use an input path as the destination of a writer tool.
- Never overwrite a staged input file with generated output.

For writer tools, accepted workspace-relative destination format is:

output/<filename>

The equivalent:

workspace/output/<filename>

must be normalized by NOVA to:

output/<filename>

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
    "file_path": "<workspace/output DOCX path>",
    "title": "<document title>",
    "content": "<generated document content>"
}}

For file_reader:

"inputs": {{
    "file_path": "<workspace file path>"
}}

For file_writer:

"inputs": {{
    "file_path": "<workspace/output file path>",
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

For pdf_writer:

"inputs": {{
    "file_path": "<workspace/output PDF path>",
    "title": "<document title>",
    "content": "<generated document content>"
}}

For spreadsheet_writer:

"inputs": {{
    "file_path": "<workspace/output XLSX path>",
    "title": "<workbook title>",
    "content": "<generated workbook content>"
}}

For csv_writer:

"inputs": {{
    "file_path": "<workspace/output CSV path>",
    "content": "<generated CSV content>"
}}

For pptx_writer:

"inputs": {{
    "file_path": "<workspace/output PPTX path>",
    "title": "<presentation title>",
    "subtitle": "<presentation subtitle>",
    "slides": [
        {{
            "title": "<slide title>",
            "bullets": [
                "<bullet>",
                "<bullet>",
                "<bullet>"
            ],
            "image_path": null
        }}
    ],
    "content": "<optional presentation content>"
}}

For visualization_writer:

"inputs": {{
    "file_path": "<workspace/output image path>",
    "title": "<chart title>",
    "chart_type": "bar"
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
- Never use input/ as a writer destination.
- Writer destinations must resolve to output/<filename>.
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

        cleaned = text.strip()

        if not cleaned:
            raise ValueError(
                "Planner model returned empty output."
            )

        decoder = json.JSONDecoder()

        if "```" in cleaned:

            parts = cleaned.split(
                "```"
            )

            for part in parts:

                candidate = part.strip()

                if candidate.lower().startswith(
                    "json"
                ):
                    candidate = candidate[
                        4:
                    ].strip()

                if not candidate:
                    continue

                try:

                    parsed, _ = (
                        decoder.raw_decode(
                            candidate
                        )
                    )

                    if isinstance(
                        parsed,
                        dict,
                    ):
                        return parsed

                except json.JSONDecodeError:
                    continue

        try:

            parsed, _ = decoder.raw_decode(
                cleaned
            )

            if isinstance(
                parsed,
                dict,
            ):
                return parsed

        except json.JSONDecodeError:
            pass

        for index, character in enumerate(
            cleaned
        ):

            if character != "{":
                continue

            candidate = cleaned[
                index:
            ]

            try:

                parsed, _ = (
                    decoder.raw_decode(
                        candidate
                    )
                )

                if isinstance(
                    parsed,
                    dict,
                ):
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

        cleaned = text.strip()

        if not cleaned:
            raise ValueError(
                "Local code generator returned empty output."
            )

        if "```" in cleaned:

            parts = cleaned.split(
                "```"
            )

            for part in parts:

                candidate = part.strip()

                if not candidate:
                    continue

                lowered = candidate.lower()

                if lowered.startswith(
                    "python"
                ):
                    candidate = candidate[
                        6:
                    ].strip()

                elif lowered.startswith(
                    "py"
                ):
                    candidate = candidate[
                        2:
                    ].strip()

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

        candidate = match.group(
            1
        ).strip()

        candidate = candidate.rstrip(
            ".,;:)"
        )

        return candidate.replace(
            "\\",
            "/",
        )

    def _extract_all_workspace_paths(
        self,
        objective: str,
    ) -> List[str]:
        """
        Extract every real workspace file path from the objective.

        Supports filenames containing spaces, parentheses and other
        normal filename characters.
        """

        text = str(
            objective or ""
        ).strip()

        if not text:
            return []

        paths: List[str] = []
        seen = set()

        def add_path(
            value: str,
        ) -> None:
            candidate = str(
                value or ""
            ).strip()

            if not candidate:
                return

            candidate = (
                candidate
                .replace(
                    "\\",
                    "/",
                )
                .strip()
            )

            candidate = candidate.strip(
                "*`'\""
            )

            candidate = candidate.rstrip(
                ".,;:)>]}*`'\""
            ).strip()

            if candidate.lower().startswith(
                "workspace/"
            ):
                candidate = candidate[
                    len("workspace/"):
                ]

            if not candidate:
                return

            normalized = candidate.lower()

            if not normalized.startswith(
                (
                    "input/",
                    "output/",
                    "temp/",
                )
            ):
                return

            suffix = Path(
                candidate
            ).suffix.lower()

            if suffix not in {
                ".csv",
                ".xlsx",
                ".pdf",
                ".docx",
                ".txt",
                ".md",
                ".json",
                ".png",
                ".jpg",
                ".jpeg",
            }:
                return

            if normalized in seen:
                return

            seen.add(
                normalized
            )

            paths.append(
                candidate
            )

        # Parse explicit SOURCE FILES lines first.
        source_line_pattern = re.compile(
            r"^\s*[-•]\s*"
            r"((?:workspace[\\/])?"
            r"input[\\/]"
            r"[^\r\n]+?\."
            r"(?:csv|xlsx|pdf|docx|txt|md|json|png|jpg|jpeg))"
            r"\s*$",
            flags=re.IGNORECASE
            | re.MULTILINE,
        )

        for match in source_line_pattern.finditer(
            text
        ):
            add_path(
                match.group(1)
            )

        # Parse workspace paths appearing elsewhere.
        broad_pattern = re.compile(
            r"(?i)(?:workspace[\\/])?"
            r"(?:input|output|temp)[\\/]"
            r"[A-Za-z0-9_.()\- ]+?\."
            r"(?:csv|xlsx|pdf|docx|txt|md|json|png|jpg|jpeg)"
            r"(?=$|[\s,;:)>\]}*`'\".])"
        )

        for match in broad_pattern.finditer(
            text
        ):
            add_path(
                match.group(0)
            )

        return paths

    def _extract_output_workspace_path(
        self,
        objective: str,
    ) -> Optional[str]:

        text = objective.strip()

        pattern = (
            r"(?<![A-Za-z0-9_./\\-])"
            r"(?:workspace[\\/])?"
            r"(output"
            r"[\\/]"
            r"[A-Za-z0-9_.\-\\/]+"
            r"\.[A-Za-z0-9]+)"
            r"(?![A-Za-z0-9_.\-])"
        )

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not matches:
            return None

        candidate = matches[-1].strip()

        candidate = candidate.rstrip(
            ".,;:)"
        )

        candidate = candidate.replace(
            "\\",
            "/",
        )

        return (
            candidate
            if candidate.lower().startswith(
                "output/"
            )
            else None
        )

    # ------------------------------------------------------------------
    # OUTPUT PATH NORMALIZATION
    # ------------------------------------------------------------------

    def _normalize_output_path(
        self,
        file_path: str,
    ) -> str:
        """
        Convert accepted workspace-relative output paths to the
        canonical format consumed by writer tools.
        """

        if not file_path:
            raise ValueError(
                "Writer output path cannot be empty."
            )

        normalized = (
            str(file_path)
            .strip()
            .replace("\\", "/")
        )

        normalized = normalized.lstrip(
            "/"
        )

        lower = normalized.lower()

        if lower.startswith(
            "workspace/output/"
        ):
            normalized = normalized[
                len("workspace/")
            ]

        lower = normalized.lower()

        if (
            lower.startswith("workspace/input/")
            or lower.startswith("input/")
            or "/input/" in lower
        ):
            raise ValueError(
                f"Unsafe writer destination '{file_path}'. "
                "Generated artifacts must be written under output/."
            )

        if not lower.startswith(
            "output/"
        ):
            raise ValueError(
                f"Unsafe writer destination '{file_path}'. "
                "Generated artifacts must be written under output/."
            )

        output_relative = normalized[
            len("output/"):
        ]

        if not output_relative:
            raise ValueError(
                "Writer output filename cannot be empty."
            )

        if Path(
            output_relative
        ).is_absolute():
            raise ValueError(
                "Writer output path must be workspace-relative."
            )

        for part in Path(
            output_relative
        ).parts:

            if part == "..":
                raise ValueError(
                    "Writer output path cannot contain '..'."
                )

        return (
            "output/"
            + output_relative
        )

    # ------------------------------------------------------------------
    # GENERATED DOCUMENT OUTPUT PATH
    # ------------------------------------------------------------------

    def _generate_document_output_path(
        self,
        objective: str,
    ) -> str:

        text = objective.strip()

        explicit_output_path = (
            self._extract_output_workspace_path(
                text
            )
        )

        if explicit_output_path:

            if explicit_output_path.lower().endswith(
                ".docx"
            ):
                return explicit_output_path

            return str(
                Path(
                    explicit_output_path
                ).with_suffix(
                    ".docx"
                )
            ).replace(
                "\\",
                "/",
            )

        subject = text

        subject = re.split(
            r"Uploaded workspace attachment\(s\) are available",
            subject,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()

        subject = re.sub(
            r"\b(?:please\s+)?(?:create|generate|write|make|prepare|draft|produce|build)\b",
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

        slug = subject.lower().strip()

        slug = re.sub(
            r"[^a-z0-9]+",
            "-",
            slug,
        )

        slug = re.sub(
            r"-{2,}",
            "-",
            slug,
        ).strip("-")

        if not slug:
            slug = "nova-document"

        slug = slug[
            :80
        ].rstrip(
            "-"
        )

        return (
            f"output/{slug}.docx"
        )

    # ------------------------------------------------------------------
    # TITLE EXTRACTION
    # ------------------------------------------------------------------

    def _extract_document_title(
        self,
        objective: str,
        file_path: str,
    ) -> str:

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

        routing = route_request(
            objective
        )

        prompt = f"""
Generate the exact content for this NOVA workspace file.

User objective:

{objective}

Target file:

{file_path}

File extension:

{Path(file_path).suffix.lower()}

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

        routing = route_request(
            objective
        )

        prompt = f"""
Create the content for a professional document.

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
    # POWERPOINT CONTENT GENERATION
    # ------------------------------------------------------------------

    def _generate_presentation_data(
        self,
        objective: str,
        file_path: str,
    ) -> Dict[str, Any]:

        routing = route_request(
            objective
        )

        prompt = f"""
Create a professional PowerPoint presentation specification.

User objective:

{objective}

Target PPTX:

{file_path}

Return ONLY valid JSON.

Required structure:

{{
  "title": "presentation title",
  "subtitle": "professional subtitle",
  "slides": [
    {{
      "title": "slide title",
      "bullets": [
        "concise point",
        "concise point",
        "concise point"
      ],
      "image_path": null
    }}
  ]
}}

Important requirements:

- Generate 6 to 10 content slides.
- Do NOT include the title slide in the slides array.
- Use 3 to 6 useful bullets per content slide.
- Keep bullets concise enough for PowerPoint.
- Build a logical story from beginning to conclusion.
- Use professional technical/business wording.
- Do not invent statistics or citations.
- Do not use external services.
- Do not invent image paths.
- Set image_path to null unless a real existing NOVA workspace
  image path was provided by the user.
- Return only JSON.
""".strip()

        result = ollama_manager.generate(
            model=routing.model_name,
            prompt=prompt,
            system=PRESENTATION_CONTENT_GENERATOR_SYSTEM_PROMPT,
            temperature=0.1,
            num_predict=3000,
            stream=False,
        )

        response = result.get(
            "response",
            "",
        ).strip()

        if not response:
            raise RuntimeError(
                "Local presentation-content generator returned an empty response."
            )

        data = self._extract_json(
            response
        )

        if not isinstance(
            data,
            dict,
        ):
            raise RuntimeError(
                "Presentation generator returned an invalid JSON structure."
            )

        title = str(
            data.get(
                "title",
                "",
            )
        ).strip()

        subtitle = str(
            data.get(
                "subtitle",
                "",
            )
        ).strip()

        raw_slides = data.get(
            "slides",
            [],
        )

        if not isinstance(
            raw_slides,
            list,
        ):
            raw_slides = []

        slides: List[
            Dict[str, Any]
        ] = []

        for raw_slide in raw_slides:

            if not isinstance(
                raw_slide,
                dict,
            ):
                continue

            slide_title = str(
                raw_slide.get(
                    "title",
                    "",
                )
            ).strip()

            if not slide_title:
                continue

            raw_bullets = raw_slide.get(
                "bullets",
                [],
            )

            if not isinstance(
                raw_bullets,
                list,
            ):
                raw_bullets = [
                    raw_bullets
                ]

            bullets: List[str] = []

            for bullet in raw_bullets:

                clean_bullet = str(
                    bullet
                ).strip()

                if not clean_bullet:
                    continue

                clean_bullet = re.sub(
                    r"^\s*(?:[-*+•·]|\d+[.)])\s+",
                    "",
                    clean_bullet,
                )

                if clean_bullet:
                    bullets.append(
                        clean_bullet
                    )

            image_path = raw_slide.get(
                "image_path"
            )

            if image_path is not None:

                image_path = str(
                    image_path
                ).strip()

                if not image_path:
                    image_path = None

                elif not image_path.lower().startswith(
                    "output/"
                ):

                    image_path = None

            slides.append(
                {
                    "title": slide_title,
                    "bullets": bullets[:6],
                    "image_path": image_path,
                }
            )

        if not title:

            title = self._derive_presentation_title(
                objective
            )

        if not subtitle:

            subtitle = (
                "Sovereign Industrial Intelligence"
            )

        if not slides:

            slides = [
                {
                    "title": "Overview",
                    "bullets": [
                        "Presentation content generated locally by NOVA."
                    ],
                    "image_path": None,
                }
            ]

        return {
            "title": title,
            "subtitle": subtitle,
            "slides": slides,
        }

    # ------------------------------------------------------------------
    # PRESENTATION TITLE
    # ------------------------------------------------------------------

    def _derive_presentation_title(
        self,
        objective: str,
    ) -> str:

        text = objective.strip()

        text = re.split(
            r"Uploaded workspace attachment\(s\) are available",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()

        text = re.sub(
            r"\b(?:please\s+)?(?:create|generate|make|prepare|build|produce|write)\b",
            " ",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\b(?:a|an|the|professional|detailed|technical|formal)\b",
            " ",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\b(?:powerpoint|pptx|presentation|presentations|slide\s+deck|slides?)\b",
            " ",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"^\s*(?:about|on|regarding|concerning)\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        ).strip(
            " .:-"
        )

        if not text:
            return "NOVA Presentation"

        return text[
            :100
        ].strip()

    # ------------------------------------------------------------------
    # MARKDOWN FENCE CLEANUP
    # ------------------------------------------------------------------

    def _strip_markdown_fences(
        self,
        text: str,
    ) -> str:

        cleaned = str(
            text
        ).strip()

        if not cleaned:
            return cleaned

        if (
            cleaned.startswith("```")
            and cleaned.endswith("```")
        ):

            lines = cleaned.splitlines()

            if lines:
                lines = lines[1:]

            if (
                lines
                and lines[-1].strip()
                == "```"
            ):
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

        text = objective.lower().strip()

        document_terms = (
            "create a docx",
            "create docx",
            "generate a docx",
            "generate docx",
            "write a docx",
            "write docx",
            "make a docx",
            "make docx",
            "prepare a docx",
            "prepare docx",
            "draft a docx",
            "draft docx",
            "produce a docx",
            "produce docx",
            "build a docx",
            "build docx",
            "create a word document",
            "create word document",
            "generate a word document",
            "generate word document",
            "write a word document",
            "write word document",
            "make a word document",
            "make word document",
            "prepare a word document",
            "prepare word document",
            "draft a word document",
            "draft word document",
            "produce a word document",
            "produce word document",
            "build a word document",
            "build word document",
            "create a word file",
            "create word file",
            "generate a word file",
            "generate word file",
            "write a word file",
            "write word file",
            "make a word file",
            "make word file",
            "prepare a word file",
            "prepare word file",
            "draft a word file",
            "draft word file",
            "produce a word file",
            "produce word file",
            "build a word file",
            "build word file",
            ".docx",
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
            "produce a document",
            "produce document",
            "build a document",
            "build document",
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
            "draft report",
            "produce a report",
            "produce report",
            "build a report",
            "build report",
        )

        if any(
            term in text
            for term in document_terms
        ):
            return True

        natural_docx_pattern = re.compile(
            r"\b"
            r"(create|generate|write|make|prepare|draft|produce|build)"
            r"\b[\s\S]{0,100}\b"
            r"(docx|word\s+document|word\s+file)\b",
            flags=re.IGNORECASE,
        )

        if natural_docx_pattern.search(
            text
        ):
            return True

        natural_document_pattern = re.compile(
            r"\b"
            r"(create|generate|write|make|prepare|draft|produce|build)"
            r"\b[\s\S]{0,80}\b"
            r"(document|report|proposal|letter|summary|notes|documentation)\b",
            flags=re.IGNORECASE,
        )

        return bool(
            natural_document_pattern.search(
                text
            )
        )

    def _is_file_read_intent(
        self,
        objective: str,
    ) -> bool:

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

    def _is_evidence_review_intent(
        self,
        objective: str,
    ) -> bool:
        """
        Detect requests where NOVA must inspect the actual supplied
        evidence and explain what the files contain.
        """

        text = " ".join(
            str(
                objective or ""
            ).lower().split()
        )

        review_terms = (
            "check the files", "check every file", "check all files", "check every attached file",
            "check all attached files", "check these files", "check the attached files",
            "check the provided files", "check uploaded files", "check each file", "check the file",
            "read every file", "read all files", "read every attached file", "read all attached files",
            "read these files", "read uploaded files", "read each file", "read the file", "read the files",
            "review the files", "review every file", "review all files", "review every attached file",
            "review all attached files", "review the attached files", "review the provided files",
            "review uploaded files", "review each file", "review the evidence", "review all the evidence", "review the file",
            "inspect every file", "inspect all files", "inspect every attached file",
            "inspect all attached files", "inspect the attached files", "inspect each file", "inspect the file", "inspect the files",
            "analyze every file", "analyse every file", "analyze all files", "analyse all files",
            "analyze every attached file", "analyse every attached file", "analyze all attached files",
            "analyse all attached files", "analyze the attached files", "analyse the attached files",
            "analyze the provided files", "analyse the provided files", "analyze each file", "analyse each file",
            "analyze the file", "analyse the file", "analyze the files", "analyse the files",
            "tell me what each file", "tell me what every file", "tell me what each uploaded file",
            "tell me what each attached file", "tell me what each file contains",
            "tell me what every file contains", "tell me what each file is about",
            "tell me what every file is about", "tell me what these files contain",
            "tell me what these files are about", "tell me what each uploaded file contains",
            "tell me what each uploaded file is about", "tell me what each attached file contains",
            "tell me what this file contains", "tell me what this spreadsheet contains", "tell me what this document contains",
            "what each file contains", "what every file contains", "what each file is about",
            "what every file is about", "what does each file contain", "what does every file contain",
            "what are these files about", "what do these files contain", "what each uploaded file contains",
            "what this file contains", "what this spreadsheet contains",
            "explain each file", "explain every file", "explain these files", "explain all files", "explain the file", "explain the files",
            "summarize each file", "summarise each file", "summarize every file", "summarise every file",
            "summarize these files", "summarise these files", "summarize all files", "summarise all files", "summarize the file", "summarise the file",
            "summarize each one", "summarise each one", "explain each one", "explain the contents", "explain what each file contains",
            "understand the files", "understand every file", "understand these files",
            "look through the files", "go through the files",
        )

        has_review_language = any(
            term in text
            for term in review_terms
        )

        workspace_paths = (
            self._extract_all_workspace_paths(
                objective
            )
        )

        source_file_marker = (
            "source files:"
            in text
            or "real user-provided evidence is available" in text
            or "evidence review mode is active" in text
        )

        attachment_language = any(
            phrase in text
            for phrase in (
                "attached file", "attached files", "provided file", "provided files",
                "supplied file", "supplied files", "evidence file", "evidence files",
                "uploaded file", "uploaded files", "these files", "this file",
                "each file", "every file", "all files", "the files",
            )
        )

        if has_review_language and (
            len(workspace_paths) >= 1
            or source_file_marker
            or attachment_language
        ):
            return True

        # Secondary check for action word + file keyword
        action_words = ("check", "review", "read", "analyze", "analyse", "inspect", "explain", "summarize", "summarise", "understand", "tell")
        file_words = ("file", "files", "attachment", "attachments", "upload", "uploads", "evidence", "spreadsheet", "document")
        has_action = any(act in text for act in action_words)
        has_file_kw = any(fw in text for fw in file_words)
        has_scope = any(sc in text for sc in ("each", "every", "all", "these", "this", "attached", "uploaded", "provided", "supplied"))

        return bool(
            has_action and has_file_kw and has_scope and (len(workspace_paths) >= 1 or source_file_marker or attachment_language)
        )

    def _is_evidence_review_with_report_intent(
        self,
        objective: str,
    ) -> bool:
        """
        Detect if user wants both evidence review AND a generated report artifact.
        """
        if not self._is_evidence_review_intent(objective):
            return False

        text = str(objective or "").lower()

        # Check for explicit "do not create any files"
        if "do not create any files" in text or "don't create any files" in text or "no files" in text:
            return False

        report_terms = (
            "create a pdf", "generate a pdf", "make a pdf", "write a pdf", "pdf report",
            "create a docx", "generate a docx", "make a docx", "write a docx", "word document", "word report",
            "create a report", "generate a report", "make a report", "write a report", "report file",
            "create a document", "generate a document", "make a document", "write a document",
            "create an excel", "generate an excel", "excel report", "create a powerpoint", "pptx"
        )

        return any(term in text for term in report_terms)

    def _is_spreadsheet_analysis_intent(
        self,
        objective: str,
    ) -> bool:

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

        return any(
            term in text
            for term in pdf_terms
        )

    def _is_xlsx_write_intent(
        self,
        objective: str,
    ) -> bool:

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

        return any(
            term in text
            for term in xlsx_terms
        )

    def _is_csv_write_intent(
        self,
        objective: str,
    ) -> bool:

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

        return any(
            term in text
            for term in csv_terms
        )

    def _is_pptx_write_intent(
        self,
        objective: str,
    ) -> bool:

        text = objective.lower().strip()

        pptx_terms = (
            "create a powerpoint",
            "create powerpoint",
            "generate a powerpoint",
            "generate powerpoint",
            "create a pptx",
            "generate pptx",
            "powerpoint presentation",
            "pptx presentation",
            "presentation",
            "slide deck",
            "slides",
            ".pptx",
        )

        return any(
            term in text
            for term in pptx_terms
        )

    def _is_visualization_intent(
        self,
        objective: str,
    ) -> bool:

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

        return any(
            term in text
            for term in vis_terms
        )

    # ------------------------------------------------------------------
    # KNOWLEDGE SEARCH PLAN
    # ------------------------------------------------------------------

    def _force_knowledge_search_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:

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
    # FILE REVIEW PLAN
    # ------------------------------------------------------------------

    def _file_reader_tool_for_path(
        self,
        file_path: str,
    ) -> str:

        suffix = Path(
            file_path
        ).suffix.lower()

        if suffix in {
            ".pdf",
            ".docx",
            ".png",
            ".jpg",
            ".jpeg",
        }:
            return "document_reader"

        if suffix in {
            ".xlsx",
            ".csv",
        }:
            return "spreadsheet_reader"

        return "file_reader"

    def _force_evidence_review_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:

        file_paths = (
            self._extract_all_workspace_paths(
                objective
            )
        )

        input_paths = [
            path
            for path in file_paths
            if path.lower().startswith(
                "input/"
            )
        ]

        if input_paths:
            file_paths = input_paths

        if not file_paths:
            return self._build_model_file_read_plan(
                objective
            )

        steps: List[
            Dict[str, Any]
        ] = []

        tools_required: List[str] = []

        expected_outputs: List[str] = []

        for index, file_path in enumerate(
            file_paths
        ):

            tool_name = (
                self._file_reader_tool_for_path(
                    file_path
                )
            )

            suffix = Path(
                file_path
            ).suffix.lower()

            filename = Path(
                file_path
            ).name

            if tool_name == "document_reader":

                if suffix in {".png", ".jpg", ".jpeg"}:
                    type_label = "Image"
                elif suffix == ".pdf":
                    type_label = "PDF"
                else:
                    type_label = "DOCX"

                title = (
                    f"Read {type_label}: "
                    f"{filename}"
                )

                description = (
                    f"Read the actual contents of "
                    f"the supplied {type_label} file "
                    f"'{filename}'. Extract its real "
                    "text and structure so NOVA "
                    "can explain what the file contains."
                )

                expected_output = (
                    f"Actual readable contents of "
                    f"{filename}."
                )

            elif tool_name == "spreadsheet_reader":

                type_label = (
                    "Excel workbook"
                    if suffix == ".xlsx"
                    else "CSV file"
                )

                title = (
                    f"Read {type_label}: "
                    f"{filename}"
                )

                description = (
                    f"Read the actual contents of "
                    f"the supplied {type_label} "
                    f"'{filename}', including available "
                    "sheets, headers, rows and other "
                    "structured information."
                )

                expected_output = (
                    f"Actual structured contents of "
                    f"{filename}."
                )

            else:

                title = (
                    f"Read file: "
                    f"{filename}"
                )

                description = (
                    f"Read the actual contents of "
                    f"the supplied file '{filename}' "
                    "before NOVA answers."
                )

                expected_output = (
                    f"Actual contents of "
                    f"{filename}."
                )

            step_id = (
                f"step-{index + 1}"
            )

            steps.append(
                {
                    "id": step_id,
                    "title": title,
                    "description": description,
                    "tool": tool_name,
                    "dependencies": [],
                    "inputs": {
                        "file_path": file_path,
                    },
                    "expected_output": expected_output,
                }
            )

            if tool_name not in tools_required:
                tools_required.append(
                    tool_name
                )

            expected_outputs.append(
                expected_output
            )

        # ------------------------------------------------------------------
        # PHASE 2 — GENERATED REPORT ARTIFACT (IF REQUESTED)
        # ------------------------------------------------------------------

        if self._is_evidence_review_with_report_intent(objective):
            reader_step_ids = [s["id"] for s in steps]
            writer_tool = "pdf_writer"
            writer_path = "output/file_review_report.pdf"

            obj_lower = objective.lower()
            if "word" in obj_lower or "docx" in obj_lower:
                writer_tool = "document_writer"
                writer_path = "output/file_review_report.docx"

            report_step_id = f"step-{len(steps) + 1}"

            steps.append(
                {
                    "id": report_step_id,
                    "title": "Generate File Review Report",
                    "description": (
                        "Synthesize completed source-reading results "
                        "into a formal review report artifact."
                    ),
                    "tool": writer_tool,
                    "dependencies": reader_step_ids,
                    "inputs": {
                        "file_path": writer_path,
                        "title": "File Review Report",
                        "content": "__EVIDENCE_REVIEW_REPORT__",
                    },
                    "expected_output": (
                        "File review report generated inside the NOVA workspace output directory."
                    ),
                }
            )

            if writer_tool not in tools_required:
                tools_required.append(writer_tool)

            expected_outputs.append("Generated file review report artifact")

        return {
            "objective": objective,
            "steps": steps,
            "tools_required": tools_required,
            "expected_outputs": expected_outputs,
            "verification_required": True,
        }

    # ------------------------------------------------------------------
    # FILE READ PLAN
    # ------------------------------------------------------------------

    def _force_file_read_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:

        file_path = (
            self._extract_workspace_path(
                objective
            )
        )

        if file_path:

            tool_name = self._file_reader_tool_for_path(
                file_path
            )

            if tool_name == "document_reader":

                description = (
                    "Read the requested local PDF/DOCX "
                    "and extract its actual contents."
                )

                expected_output = (
                    "Actual document contents."
                )

            elif tool_name == "spreadsheet_reader":

                description = (
                    "Read the requested local CSV/XLSX "
                    "and extract its actual structured contents."
                )

                expected_output = (
                    "Actual spreadsheet contents."
                )

            else:

                description = (
                    "Read the requested local text file "
                    "and return its actual contents."
                )

                expected_output = (
                    "Actual file contents."
                )

            return {
                "objective": objective,
                "steps": [
                    {
                        "id": "step-1",
                        "title": "Read local file",
                        "description": description,
                        "tool": tool_name,
                        "dependencies": [],
                        "inputs": {
                            "file_path": file_path,
                        },
                        "expected_output": expected_output,
                    }
                ],
                "tools_required": [
                    tool_name
                ],
                "expected_outputs": [
                    expected_output
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

        file_path = (
            self._extract_output_workspace_path(
                objective
            )
        )

        if not file_path:

            raise ValueError(
                "Please provide a workspace output path, "
                "for example output/calculator.py."
            )

        file_path = self._normalize_output_path(
            file_path
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
                        "to the requested NOVA workspace "
                        "output path."
                    ),
                    "tool": "file_writer",
                    "dependencies": [],
                    "inputs": {
                        "file_path": file_path,
                        "content": content,
                    },
                    "expected_output": (
                        "File successfully created in "
                        "the NOVA workspace output directory."
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

        file_path = (
            self._extract_output_workspace_path(
                objective
            )
            or self._generate_document_output_path(
                objective
            )
        )

        file_path = self._normalize_output_path(
            file_path
        )

        if not file_path.lower().endswith(
            ".docx"
        ):

            file_path = str(
                Path(
                    file_path
                ).with_suffix(
                    ".docx"
                )
            ).replace(
                "\\",
                "/",
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
                        "inside the NOVA workspace output directory."
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

        file_path = (
            self._extract_output_workspace_path(
                objective
            )
            or self._generate_document_output_path(
                objective
            ).replace(
                ".docx",
                ".pdf",
            )
        )

        file_path = self._normalize_output_path(
            file_path
        )

        file_path = str(
            Path(
                file_path
            ).with_suffix(
                ".pdf"
            )
        ).replace(
            "\\",
            "/",
        )

        title = self._extract_document_title(
            objective,
            file_path,
        )

        content = self._generate_document_content(
            objective,
            file_path,
            title,
        )

        return {
            "objective": objective,
            "steps": [
                {
                    "id": "step-1",
                    "title": "Create PDF document",
                    "description": (
                        "Generate a formatted PDF document "
                        "using the local ReportLab engine."
                    ),
                    "tool": "pdf_writer",
                    "dependencies": [],
                    "inputs": {
                        "file_path": file_path,
                        "title": title,
                        "content": content,
                    },
                    "expected_output": (
                        "PDF document created and verified."
                    ),
                }
            ],
            "tools_required": [
                "pdf_writer"
            ],
            "expected_outputs": [
                "Created PDF document"
            ],
            "verification_required": True,
        }

    # ------------------------------------------------------------------
    # XLSX WRITE PLAN
    # ------------------------------------------------------------------

    def _force_xlsx_write_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:

        file_path = (
            self._extract_output_workspace_path(
                objective
            )
            or "output/excel_report.xlsx"
        )

        file_path = self._normalize_output_path(
            file_path
        )

        file_path = str(
            Path(
                file_path
            ).with_suffix(
                ".xlsx"
            )
        ).replace(
            "\\",
            "/",
        )

        if not file_path.lower().startswith(
            "output/"
        ):
            file_path = (
                "output/excel_report.xlsx"
            )

        title = self._extract_document_title(
            objective,
            file_path,
        )

        content = self._generate_document_content(
            objective,
            file_path,
            title,
        )

        return {
            "objective": objective,
            "steps": [
                {
                    "id": "step-1",
                    "title": "Create Excel workbook",
                    "description": (
                        "Generate a styled Excel workbook with "
                        "formatted headers and data."
                    ),
                    "tool": "spreadsheet_writer",
                    "dependencies": [],
                    "inputs": {
                        "file_path": file_path,
                        "title": title,
                        "content": content,
                    },
                    "expected_output": (
                        "Excel workbook created and verified "
                        "inside the NOVA workspace output directory."
                    ),
                }
            ],
            "tools_required": [
                "spreadsheet_writer"
            ],
            "expected_outputs": [
                "Created XLSX workbook"
            ],
            "verification_required": True,
        }

    # ------------------------------------------------------------------
    # CSV WRITE PLAN
    # ------------------------------------------------------------------

    def _force_csv_write_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:

        file_path = (
            self._extract_output_workspace_path(
                objective
            )
            or "output/dataset.csv"
        )

        file_path = self._normalize_output_path(
            file_path
        )

        file_path = str(
            Path(
                file_path
            ).with_suffix(
                ".csv"
            )
        ).replace(
            "\\",
            "/",
        )

        if not file_path.lower().startswith(
            "output/"
        ):
            file_path = (
                "output/dataset.csv"
            )

        content = self._generate_file_content(
            objective,
            file_path,
        )

        return {
            "objective": objective,
            "steps": [
                {
                    "id": "step-1",
                    "title": "Create CSV file",
                    "description": (
                        "Generate a clean CSV dataset "
                        "file in the workspace output directory."
                    ),
                    "tool": "csv_writer",
                    "dependencies": [],
                    "inputs": {
                        "file_path": file_path,
                        "content": content,
                    },
                    "expected_output": (
                        "CSV file created and verified."
                    ),
                }
            ],
            "tools_required": [
                "csv_writer"
            ],
            "expected_outputs": [
                "Created CSV file"
            ],
            "verification_required": True,
        }

    # ------------------------------------------------------------------
    # PPTX WRITE PLAN
    # ------------------------------------------------------------------

    def _force_pptx_write_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:

        file_path = (
            self._extract_output_workspace_path(
                objective
            )
            or "output/presentation.pptx"
        )

        file_path = self._normalize_output_path(
            file_path
        )

        file_path = str(
            Path(
                file_path
            ).with_suffix(
                ".pptx"
            )
        ).replace(
            "\\",
            "/",
        )

        if not file_path.lower().startswith(
            "output/"
        ):
            file_path = (
                "output/presentation.pptx"
            )

        presentation_data = (
            self._generate_presentation_data(
                objective=objective,
                file_path=file_path,
            )
        )

        title = str(
            presentation_data.get(
                "title",
                "",
            )
        ).strip()

        subtitle = str(
            presentation_data.get(
                "subtitle",
                "",
            )
        ).strip()

        slides = presentation_data.get(
            "slides",
            [],
        )

        if not isinstance(
            slides,
            list,
        ):
            slides = []

        if not slides:
            slides = [
                {
                    "title": "Overview",
                    "bullets": [
                        "Presentation generated successfully by NOVA."
                    ],
                    "image_path": None,
                }
            ]

        return {
            "objective": objective,
            "steps": [
                {
                    "id": "step-1",
                    "title": "Create PowerPoint deck",
                    "description": (
                        "Generate a professional multi-slide "
                        "PowerPoint presentation from locally "
                        "structured slide content."
                    ),
                    "tool": "pptx_writer",
                    "dependencies": [],
                    "inputs": {
                        "file_path": file_path,
                        "title": (
                            title
                            or self._derive_presentation_title(
                                objective
                            )
                        ),
                        "subtitle": (
                            subtitle
                            or "Sovereign Industrial Intelligence"
                        ),
                        "slides": slides,
                        "content": "",
                    },
                    "expected_output": (
                        "Professional PPTX presentation created "
                        "and verified in the NOVA workspace output directory."
                    ),
                }
            ],
            "tools_required": [
                "pptx_writer"
            ],
            "expected_outputs": [
                "Created PPTX presentation"
            ],
            "verification_required": True,
        }

    # ------------------------------------------------------------------
    # VISUALIZATION PLAN
    # ------------------------------------------------------------------

    def _force_visualization_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:

        file_path = (
            self._extract_output_workspace_path(
                objective
            )
            or "output/data_chart.png"
        )

        file_path = self._normalize_output_path(
            file_path
        )

        suffix = Path(
            file_path
        ).suffix.lower()

        if suffix not in {
            ".png",
            ".jpg",
            ".jpeg",
        }:

            file_path = str(
                Path(
                    file_path
                ).with_suffix(
                    ".png"
                )
            ).replace(
                "\\",
                "/",
            )

        if not file_path.lower().startswith(
            "output/"
        ):

            file_path = (
                "output/data_chart.png"
            )

        chart_type = "bar"

        obj_lower = objective.lower()

        if (
            "line" in obj_lower
            or "trend" in obj_lower
        ):
            chart_type = "line"

        elif (
            "pie" in obj_lower
            or "donut" in obj_lower
        ):
            chart_type = "pie"

        elif "scatter" in obj_lower:
            chart_type = "scatter"

        title = self._extract_document_title(
            objective,
            file_path,
        )

        return {
            "objective": objective,
            "steps": [
                {
                    "id": "step-1",
                    "title": "Generate data visualization",
                    "description": (
                        "Render a high-resolution chart PNG "
                        "using the local Matplotlib engine."
                    ),
                    "tool": "visualization_writer",
                    "dependencies": [],
                    "inputs": {
                        "file_path": file_path,
                        "title": title,
                        "chart_type": chart_type,
                    },
                    "expected_output": (
                        "Chart PNG generated and verified."
                    ),
                }
            ],
            "tools_required": [
                "visualization_writer"
            ],
            "expected_outputs": [
                "Created chart image"
            ],
            "verification_required": True,
        }

    # ------------------------------------------------------------------
    # LOCAL PYTHON GENERATION
    # ------------------------------------------------------------------

    def _generate_python_code(
        self,
        objective: str,
    ) -> str:

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
                normalized_inputs[
                    "query"
                ] = objective.strip()

            else:
                normalized_inputs[
                    "query"
                ] = str(
                    query
                ).strip()

            top_k = normalized_inputs.get(
                "top_k",
                5,
            )

            try:
                top_k = int(
                    top_k
                )
            except (
                TypeError,
                ValueError,
            ):
                top_k = 5

            normalized_inputs[
                "top_k"
            ] = max(
                1,
                min(
                    top_k,
                    10,
                ),
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
                normalized_inputs[
                    "file_path"
                ] = (
                    str(
                        file_path
                    ).strip().replace(
                        "\\",
                        "/",
                    )
                )

        elif tool in {
            "document_writer",
            "pdf_writer",
            "spreadsheet_writer",
            "csv_writer",
            "pptx_writer",
            "visualization_writer",
        }:

            file_path = normalized_inputs.get(
                "file_path"
            )

            if file_path is not None:

                normalized_inputs[
                    "file_path"
                ] = self._normalize_output_path(
                    str(
                        file_path
                    )
                )

            else:

                raise ValueError(
                    f"Writer tool '{tool}' requires a file_path."
                )

            title = normalized_inputs.get(
                "title"
            )

            if title is not None:
                normalized_inputs[
                    "title"
                ] = str(
                    title
                ).strip()

            subtitle = normalized_inputs.get(
                "subtitle"
            )

            if subtitle is not None:
                normalized_inputs[
                    "subtitle"
                ] = str(
                    subtitle
                ).strip()

            content = normalized_inputs.get(
                "content"
            )

            if content is not None:
                normalized_inputs[
                    "content"
                ] = self._strip_markdown_fences(
                    str(
                        content
                    )
                )

            if tool == "pptx_writer":

                raw_slides = normalized_inputs.get(
                    "slides"
                )

                if raw_slides is not None:

                    if not isinstance(
                        raw_slides,
                        list,
                    ):
                        raw_slides = []

                    normalized_slides: List[
                        Dict[str, Any]
                    ] = []

                    for raw_slide in raw_slides:

                        if not isinstance(
                            raw_slide,
                            dict,
                        ):
                            continue

                        slide_title = str(
                            raw_slide.get(
                                "title",
                                "",
                            )
                        ).strip()

                        if not slide_title:
                            continue

                        raw_bullets = raw_slide.get(
                            "bullets",
                            [],
                        )

                        if not isinstance(
                            raw_bullets,
                            list,
                        ):
                            raw_bullets = [
                                raw_bullets
                            ]

                        bullets: List[
                            str
                        ] = []

                        for bullet in raw_bullets:

                            clean_bullet = str(
                                bullet
                            ).strip()

                            if not clean_bullet:
                                continue

                            clean_bullet = re.sub(
                                r"^\s*(?:[-*+•·]|\d+[.)])\s+",
                                "",
                                clean_bullet,
                            )

                            if clean_bullet:
                                bullets.append(
                                    clean_bullet
                                )

                        image_path = raw_slide.get(
                            "image_path"
                        )

                        if image_path is not None:

                            image_path = str(
                                image_path
                            ).strip()

                            if not image_path:

                                image_path = None

                            elif not image_path.lower().startswith(
                                "output/"
                            ):

                                image_path = None

                        normalized_slides.append(
                            {
                                "title": slide_title,
                                "bullets": bullets[:6],
                                "image_path": image_path,
                            }
                        )

                    normalized_inputs[
                        "slides"
                    ] = normalized_slides

        elif tool == "file_writer":

            file_path = normalized_inputs.get(
                "file_path"
            )

            if file_path is not None:

                normalized_inputs[
                    "file_path"
                ] = self._normalize_output_path(
                    str(
                        file_path
                    )
                )

            else:

                raise ValueError(
                    "file_writer requires a file_path."
                )

            content = normalized_inputs.get(
                "content"
            )

            if content is not None:

                normalized_inputs[
                    "content"
                ] = self._strip_markdown_fences(
                    str(
                        content
                    )
                )

        elif tool == "code_executor":

            language = normalized_inputs.get(
                "language",
                "python",
            )

            if not str(
                language
            ).strip():
                language = "python"

            normalized_inputs[
                "language"
            ] = str(
                language
            ).strip().lower()

            code = normalized_inputs.get(
                "code"
            )

            if code is not None:
                normalized_inputs[
                    "code"
                ] = str(
                    code
                )

        return normalized_inputs

    # ------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------

    def _validate_dependencies(
        self,
        steps: List[PlanStep],
    ) -> None:

        step_ids = {
            step.id
            for step in steps
        }

        for step in steps:

            for dependency in (
                step.dependencies
            ):

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
    # DETERMINISTIC FALLBACK PLAN
    # ------------------------------------------------------------------

    def _build_fallback_plan(
        self,
        objective: str,
    ) -> Dict[str, Any]:
        """
        Deterministic safety-net plan.

        For normal non-file tasks it creates a local report.
        Evidence-review requests are handled before this fallback
        and therefore will never reach this generic writer path.
        """

        output_path = (
            "output/"
            "nova_mission_report.docx"
        )

        title = (
            "NOVA Mission Execution Report"
        )

        content = self._generate_document_content(
            objective=objective,
            file_path=output_path,
            title=title,
        )

        return {
            "objective": objective,
            "steps": [
                {
                    "id": "step-1",
                    "title": "Search local mission evidence",
                    "description": (
                        "Search NOVA's local knowledge base "
                        "for information relevant to the mission."
                    ),
                    "tool": "knowledge_search",
                    "dependencies": [],
                    "inputs": {
                        "query": objective,
                        "top_k": 5,
                    },
                    "expected_output": (
                        "Relevant local knowledge and evidence."
                    ),
                },
                {
                    "id": "step-2",
                    "title": "Generate mission report",
                    "description": (
                        "Create a professional mission execution "
                        "report using NOVA's local document engine."
                    ),
                    "tool": "document_writer",
                    "dependencies": [
                        "step-1"
                    ],
                    "inputs": {
                        "file_path": output_path,
                        "title": title,
                        "content": content,
                    },
                    "expected_output": (
                        "Mission execution report generated "
                        "inside the NOVA workspace output directory."
                    ),
                },
            ],
            "tools_required": [
                "knowledge_search",
                "document_writer",
            ],
            "expected_outputs": [
                "Local mission evidence",
                "Generated mission execution report",
            ],
            "verification_required": True,
        }

    # ------------------------------------------------------------------
    # PLAN NORMALIZATION
    # ------------------------------------------------------------------

    def _normalize_plan(
        self,
        objective: str,
        data: Dict[str, Any],
    ) -> AgentPlan:

        raw_steps = data.get(
            "steps",
            [],
        )

        if not isinstance(
            raw_steps,
            list,
        ):
            raw_steps = []

        steps: List[
            PlanStep
        ] = []

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
                step_id = (
                    f"step-{index + 1}"
                )

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

            inputs = (
                self._normalize_tool_inputs(
                    tool=tool,
                    inputs=inputs,
                    objective=objective,
                )
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

        # --------------------------------------------------------------
        # FALLBACK WHEN MODEL RETURNED NO EXECUTABLE STEPS
        # --------------------------------------------------------------

        if not steps:

            if self._is_evidence_review_intent(
                objective
            ):
                return self._normalize_plan(
                    objective,
                    self._force_evidence_review_plan(
                        objective
                    ),
                )

            fallback_plan = (
                self._build_fallback_plan(
                    objective
                )
            )

            return self._normalize_plan(
                objective,
                fallback_plan,
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

        objective = objective.strip()

        if not objective:

            raise ValueError(
                "Agent objective cannot be empty."
            )

        # --------------------------------------------------------------
        # EVIDENCE REVIEW MUST ALWAYS BE CHECKED FIRST
        # --------------------------------------------------------------

        if self._is_evidence_review_intent(
            objective
        ):

            raw_plan = (
                self._force_evidence_review_plan(
                    objective
                )
            )

            return self._normalize_plan(
                objective,
                raw_plan,
            )

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

        if self._is_pdf_write_intent(
            objective
        ):

            raw_plan = (
                self._force_pdf_write_plan(
                    objective
                )
            )

            return self._normalize_plan(
                objective,
                raw_plan,
            )

        if self._is_xlsx_write_intent(
            objective
        ):

            raw_plan = (
                self._force_xlsx_write_plan(
                    objective
                )
            )

            return self._normalize_plan(
                objective,
                raw_plan,
            )

        if self._is_csv_write_intent(
            objective
        ):

            raw_plan = (
                self._force_csv_write_plan(
                    objective
                )
            )

            return self._normalize_plan(
                objective,
                raw_plan,
            )

        if self._is_pptx_write_intent(
            objective
        ):

            raw_plan = (
                self._force_pptx_write_plan(
                    objective
                )
            )

            return self._normalize_plan(
                objective,
                raw_plan,
            )

        if self._is_visualization_intent(
            objective
        ):

            raw_plan = (
                self._force_visualization_plan(
                    objective
                )
            )

            return self._normalize_plan(
                objective,
                raw_plan,
            )

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
        # MODEL PLANNER
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