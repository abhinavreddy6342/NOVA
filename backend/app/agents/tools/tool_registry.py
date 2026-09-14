from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from app.agents.tools.handlers import (
    code_executor_handler,
    document_reader_handler,
    document_writer_handler,
    file_reader_handler,
    file_writer_handler,
    knowledge_search_handler,
    spreadsheet_analysis_handler,
    spreadsheet_reader_handler,
)


@dataclass
class ToolDefinition:
    """
    Describes a tool that NOVA's agent can use.
    """

    name: str
    description: str
    category: str

    enabled: bool = True
    requires_confirmation: bool = False

    input_schema: Dict[str, str] = field(
        default_factory=dict
    )

    handler: Optional[Callable] = None


class ToolRegistry:
    """
    Central registry of tools available to NOVA agents.

    The registry acts as an explicit allow-list.
    A tool must be registered before an agent can use it.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}

    def register(
        self,
        tool: ToolDefinition,
    ) -> None:
        """
        Register or replace a tool.
        """

        if not tool.name.strip():
            raise ValueError(
                "Tool name cannot be empty."
            )

        self._tools[tool.name] = tool

    def get(
        self,
        tool_name: str,
    ) -> Optional[ToolDefinition]:
        """
        Return a registered tool.
        """

        return self._tools.get(
            tool_name
        )

    def exists(
        self,
        tool_name: str,
    ) -> bool:
        """
        Check whether a tool is registered.
        """

        return tool_name in self._tools

    def list_tools(
        self,
        enabled_only: bool = True,
    ) -> List[ToolDefinition]:
        """
        Return registered tools.
        """

        tools = list(
            self._tools.values()
        )

        if enabled_only:
            tools = [
                tool
                for tool in tools
                if tool.enabled
            ]

        return sorted(
            tools,
            key=lambda tool: tool.name,
        )

    def enable(
        self,
        tool_name: str,
    ) -> bool:
        """
        Enable a registered tool.
        """

        tool = self.get(
            tool_name
        )

        if not tool:
            return False

        tool.enabled = True

        return True

    def disable(
        self,
        tool_name: str,
    ) -> bool:
        """
        Disable a registered tool.
        """

        tool = self.get(
            tool_name
        )

        if not tool:
            return False

        tool.enabled = False

        return True

    def remove(
        self,
        tool_name: str,
    ) -> bool:
        """
        Remove a tool from the registry.
        """

        if tool_name not in self._tools:
            return False

        del self._tools[tool_name]

        return True


# ---------------------------------------------------------------------------
# NOVA TOOL REGISTRY
# ---------------------------------------------------------------------------

tool_registry = ToolRegistry()


# ---------------------------------------------------------------------------
# DOCUMENT READER
# ---------------------------------------------------------------------------

tool_registry.register(
    ToolDefinition(
        name="document_reader",
        description=(
            "Read and extract text from supported "
            "local documents such as PDF, TXT and DOCX."
        ),
        category="document",
        requires_confirmation=False,
        input_schema={
            "file_path": "string",
        },
        handler=document_reader_handler,
    )
)


# ---------------------------------------------------------------------------
# DOCUMENT WRITER
# ---------------------------------------------------------------------------

tool_registry.register(
    ToolDefinition(
        name="document_writer",
        description=(
            "Create a formatted DOCX document from "
            "locally generated content and save it "
            "inside the NOVA workspace."
        ),
        category="document",
        requires_confirmation=True,
        input_schema={
            "file_path": "string",
            "title": "string",
            "content": "string",
        },
        handler=document_writer_handler,
    )
)


# ---------------------------------------------------------------------------
# KNOWLEDGE SEARCH
# ---------------------------------------------------------------------------

tool_registry.register(
    ToolDefinition(
        name="knowledge_search",
        description=(
            "Search NOVA's local ChromaDB knowledge base "
            "for relevant indexed information."
        ),
        category="knowledge",
        requires_confirmation=False,
        input_schema={
            "query": "string",
            "top_k": "integer",
        },
        handler=knowledge_search_handler,
    )
)


# ---------------------------------------------------------------------------
# FILE READER
# ---------------------------------------------------------------------------

tool_registry.register(
    ToolDefinition(
        name="file_reader",
        description=(
            "Safely read a permitted local text or structured "
            "file inside the NOVA workspace."
        ),
        category="filesystem",
        requires_confirmation=False,
        input_schema={
            "file_path": "string",
        },
        handler=file_reader_handler,
    )
)


# ---------------------------------------------------------------------------
# FILE WRITER
# ---------------------------------------------------------------------------

tool_registry.register(
    ToolDefinition(
        name="file_writer",
        description=(
            "Safely write generated content to a permitted "
            "NOVA workspace location."
        ),
        category="filesystem",
        requires_confirmation=True,
        input_schema={
            "file_path": "string",
            "content": "string",
        },
        handler=file_writer_handler,
    )
)


# ---------------------------------------------------------------------------
# CODE EXECUTOR
# ---------------------------------------------------------------------------

tool_registry.register(
    ToolDefinition(
        name="code_executor",
        description=(
            "Execute Python code inside NOVA's isolated "
            "Docker sandbox with disabled network access."
        ),
        category="execution",
        requires_confirmation=True,
        input_schema={
            "language": "string",
            "code": "string",
            "timeout": "integer",
        },
        handler=code_executor_handler,
    )
)


# ---------------------------------------------------------------------------
# SPREADSHEET READER
# ---------------------------------------------------------------------------

tool_registry.register(
    ToolDefinition(
        name="spreadsheet_reader",
        description=(
            "Read and inspect permitted local CSV and XLSX "
            "spreadsheet files and return structured data."
        ),
        category="spreadsheet",
        requires_confirmation=False,
        input_schema={
            "file_path": "string",
        },
        handler=spreadsheet_reader_handler,
    )
)


# ---------------------------------------------------------------------------
# SPREADSHEET ANALYSIS
# ---------------------------------------------------------------------------

tool_registry.register(
    ToolDefinition(
        name="spreadsheet_analysis",
        description=(
            "Read and analyze permitted local CSV and XLSX "
            "files and calculate deterministic numeric summaries."
        ),
        category="spreadsheet",
        requires_confirmation=False,
        input_schema={
            "file_path": "string",
        },
        handler=spreadsheet_analysis_handler,
    )
)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def get_tool(
    tool_name: str,
) -> Optional[ToolDefinition]:
    """
    Convenience function for retrieving a tool.
    """

    return tool_registry.get(
        tool_name
    )


def get_enabled_tools() -> List[ToolDefinition]:
    """
    Return all enabled NOVA tools.
    """

    return tool_registry.list_tools(
        enabled_only=True
    )


def get_tool_names() -> List[str]:
    """
    Return enabled tool names.
    """

    return [
        tool.name
        for tool in get_enabled_tools()
    ]