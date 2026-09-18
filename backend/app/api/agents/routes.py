from pathlib import Path
import json
import shutil
import re
import uuid
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.execution.executor import (
    AgentExecutor,
    set_mission_cancelled,
)
from app.agents.planner.planner import agent_planner
from app.agents.response.synthesizer import (
    agent_response_synthesizer,
)
from app.core.database import get_db
from app.services.chat_files import load_chat_file
from app.services.chat_history import (
    add_attachment,
    add_message,
    create_conversation,
    get_conversation,
)
from app.services.audit.service import (
    audit_service,
    create_request_id,
)


router = APIRouter(
    prefix="/api/agents",
    tags=["Agents"],
)


# ---------------------------------------------------------------------------
# AUDIT ADAPTER
# ---------------------------------------------------------------------------

def _safe_audit(
    *,
    category: str,
    action: str,
    service: str,
    status: str,
    message: str,
    request_id: Optional[str] = None,
    model: Optional[str] = None,
    task_type: Optional[str] = None,
    resource: Optional[str] = None,
    resource_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Best-effort audit adapter.

    Audit persistence must never break the actual NOVA
    agent / mission execution path.
    """

    try:
        audit_service.record_event(
            category=category,
            action=action,
            service=service,
            status=status,
            message=message,
            request_id=request_id,
            model=model,
            task_type=task_type,
            resource=resource,
            resource_id=resource_id,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )
    except Exception as exc:
        print(
            "[NOVA AUDIT] "
            f"{type(exc).__name__}: {exc}"
        )


def _audit_success(
    *,
    category: str,
    action: str,
    service: str,
    message: str,
    request_id: Optional[str] = None,
    model: Optional[str] = None,
    task_type: Optional[str] = None,
    resource: Optional[str] = None,
    resource_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    _safe_audit(
        category=category,
        action=action,
        service=service,
        status="success",
        message=message,
        request_id=request_id,
        model=model,
        task_type=task_type,
        resource=resource,
        resource_id=resource_id,
        duration_ms=duration_ms,
        metadata=metadata,
    )


def _audit_failure(
    *,
    category: str,
    action: str,
    service: str,
    message: str,
    request_id: Optional[str] = None,
    model: Optional[str] = None,
    task_type: Optional[str] = None,
    resource: Optional[str] = None,
    resource_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    _safe_audit(
        category=category,
        action=action,
        service=service,
        status="failed",
        message=message,
        request_id=request_id,
        model=model,
        task_type=task_type,
        resource=resource,
        resource_id=resource_id,
        duration_ms=duration_ms,
        metadata=metadata,
    )


def _duration_ms(
    started_at: float,
) -> float:
    return round(
        (
            time.perf_counter()
            - started_at
        )
        * 1000,
        2,
    )


# ---------------------------------------------------------------------------
# NOVA WORKSPACE
# ---------------------------------------------------------------------------

APP_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

BACKEND_ROOT = (
    APP_ROOT.parent
).resolve()

WORKSPACE_ROOT = (
    APP_ROOT / "workspace"
).resolve()

WORKSPACE_INPUT_DIR = (
    WORKSPACE_ROOT / "input"
).resolve()

WORKSPACE_OUTPUT_DIR = (
    WORKSPACE_ROOT / "output"
).resolve()

CHAT_UPLOADS_DIR = (
    APP_ROOT
    / "knowledge"
    / "chat_uploads"
).resolve()


# ---------------------------------------------------------------------------
# REQUEST / RESPONSE MODELS
# ---------------------------------------------------------------------------

class AgentRunRequest(BaseModel):
    objective: str = Field(
        ...,
        min_length=1,
    )

    context: Optional[
        Dict[str, Any]
    ] = None

    auto_confirm: bool = False


class MissionRunRequest(BaseModel):
    """
    Dedicated Mission Control execution request.

    Mission Control uses the same sovereign planner/executor
    pipeline as Local Chat while attaching mission-specific
    metadata and evidence references.
    """

    mission_id: Optional[str] = None

    title: str = Field(
        ...,
        min_length=1,
    )

    objective: str = Field(
        ...,
        min_length=1,
    )

    context: Optional[
        Dict[str, Any]
    ] = None

    auto_confirm: bool = False


class AgentRunResponse(BaseModel):
    conversation_id: Optional[str] = None

    plan: Dict[str, Any]

    execution: Dict[str, Any]

    response: str

    artifacts: List[
        Dict[str, Any]
    ] = Field(
        default_factory=list
    )


class MissionRunResponse(BaseModel):
    mission_id: Optional[str] = None

    title: str

    status: str

    conversation_id: Optional[str] = None

    plan: Dict[str, Any]

    execution: Dict[str, Any]

    response: str

    artifacts: List[
        Dict[str, Any]
    ] = Field(
        default_factory=list
    )

    sovereignty: Dict[str, Any]


# ---------------------------------------------------------------------------
# ATTACHMENT HELPERS
# ---------------------------------------------------------------------------

ALLOWED_ATTACHMENT_EXTENSIONS = {
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
    ".webp",
}


def _get_context_attachments(
    context: Optional[
        Dict[str, Any]
    ],
) -> List[
    Dict[str, Any]
]:
    """
    Extract normalized uploaded-file references from agent context.

    These are normal chat-upload references. Knowledge Vault
    selections are handled separately below.
    """

    if not context:
        return []

    attachments = context.get(
        "attachments",
        [],
    )

    if not isinstance(
        attachments,
        list,
    ):
        return []

    normalized: List[
        Dict[str, Any]
    ] = []

    for attachment in attachments:
        if not isinstance(
            attachment,
            dict,
        ):
            continue

        file_id = str(
            attachment.get(
                "file_id",
                "",
            )
        ).strip()

        if not file_id:
            continue

        filename = str(
            attachment.get(
                "filename",
                "",
            )
        ).strip()

        content_type = str(
            attachment.get(
                "content_type",
                "",
            )
        ).strip()

        normalized.append(
            {
                "file_id": file_id,
                "filename": filename,
                "content_type": content_type,
                "source_type": "chat",
            }
        )

    return normalized


def _get_context_vault_file_ids(
    context: Optional[
        Dict[str, Any]
    ],
) -> List[str]:
    """
    Read explicitly selected Knowledge Vault file IDs.

    Supported context keys:
    - vault_file_ids
    - knowledge_file_ids
    - selected_file_ids
    """

    if not context:
        return []

    candidate_keys = (
        "vault_file_ids",
        "knowledge_file_ids",
        "selected_file_ids",
    )

    combined: List[str] = []

    for key in candidate_keys:
        value = context.get(
            key,
            [],
        )

        if isinstance(
            value,
            str,
        ):
            value = [
                value
            ]

        if not isinstance(
            value,
            list,
        ):
            continue

        combined.extend(
            value
        )

    return list(
        dict.fromkeys(
            str(
                file_id
            ).strip()
            for file_id in combined
            if str(
                file_id
            ).strip()
        )
    )


def _get_context_vault_id(
    context: Optional[
        Dict[str, Any]
    ],
) -> Optional[str]:
    """
    Return the selected Knowledge Vault ID when supplied.
    """

    if not context:
        return None

    for key in (
        "vault_id",
        "knowledge_vault_id",
        "selected_vault_id",
    ):
        value = str(
            context.get(
                key,
                "",
            )
        ).strip()

        if value:
            return value

    return None


def _resolve_chat_upload_path(
    file_id: str,
) -> Path:
    """
    Resolve a previously uploaded file inside NOVA's
    controlled chat-upload directory.
    """

    metadata = load_chat_file(
        file_id
    )

    if not isinstance(
        metadata,
        dict,
    ):
        raise ValueError(
            f"Invalid uploaded-file metadata: {file_id}"
        )

    stored_name = str(
        metadata.get(
            "stored_name",
            "",
        )
    ).strip()

    if not stored_name:
        raise ValueError(
            "Uploaded file metadata does not contain a stored filename."
        )

    source_path = (
        CHAT_UPLOADS_DIR
        / Path(
            stored_name
        ).name
    ).resolve()

    try:
        source_path.relative_to(
            CHAT_UPLOADS_DIR
        )
    except ValueError as exc:
        raise PermissionError(
            "Access denied: uploaded file is outside "
            "NOVA's controlled attachment directory."
        ) from exc

    if not source_path.exists():
        raise FileNotFoundError(
            f"Uploaded file not found: {file_id}"
        )

    if not source_path.is_file():
        raise ValueError(
            "Uploaded attachment is not a file."
        )

    return source_path


def _resolve_vault_file(
    file_id: str,
    vault_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Resolve one real active Knowledge Vault file.

    The file registry is authoritative.
    Chroma is never used to resolve filesystem state.
    """

    from app.services.vault_manager import (
        get_file,
        resolve_file_path,
    )

    normalized_file_id = str(
        file_id or ""
    ).strip()

    if not normalized_file_id:
        raise ValueError(
            "Knowledge Vault file ID is required."
        )

    metadata = get_file(
        normalized_file_id
    )

    status = str(
        metadata.get(
            "status",
            "",
        )
    ).strip().lower()

    if status != "active":
        raise FileNotFoundError(
            f"Knowledge Vault file is not active: {normalized_file_id}"
        )

    registered_vault_id = str(
        metadata.get(
            "vault_id",
            "",
        )
        or ""
    ).strip()

    if not registered_vault_id:
        raise ValueError(
            f"Knowledge Vault file is not assigned to a vault: {normalized_file_id}"
        )

    normalized_vault_id = str(
        vault_id or ""
    ).strip()

    if (
        normalized_vault_id
        and registered_vault_id
        != normalized_vault_id
    ):
        raise PermissionError(
            f"File {normalized_file_id} does not belong to "
            f"selected vault {normalized_vault_id}."
        )

    source_path = resolve_file_path(
        normalized_file_id
    )

    vault_name = str(
        metadata.get(
            "vault_name",
            "",
        )
    ).strip()

    if not vault_name:
        try:
            from app.services.vault_manager import (
                list_vaults,
            )

            for vault in list_vaults():
                if str(
                    vault.get(
                        "vault_id",
                        "",
                    )
                ).strip() == registered_vault_id:
                    vault_name = str(
                        vault.get(
                            "name",
                            "",
                        )
                    ).strip()
                    break
        except Exception:
            vault_name = ""

    return {
        "file_id": normalized_file_id,
        "filename": metadata.get(
            "filename",
            source_path.name,
        ),
        "content_type": metadata.get(
            "content_type",
            "",
        ),
        "vault_id": registered_vault_id,
        "vault_name": vault_name,
        "stored_name": metadata.get(
            "stored_name",
            "",
        ),
        "source_path": source_path,
        "registry": metadata,
    }


def _get_context_source_references(
    context: Optional[
        Dict[str, Any]
    ],
) -> List[
    Dict[str, Any]
]:
    """
    Return real file references attached to an agent request.

    This combines:
    - normal Local Chat uploads
    - explicit Knowledge Vault selections

    Duplicate file IDs are emitted only once.
    """

    references: List[
        Dict[str, Any]
    ] = []

    seen_ids = set()

    for attachment in _get_context_attachments(
        context
    ):
        file_id = str(
            attachment.get(
                "file_id",
                "",
            )
        ).strip()

        if not file_id:
            continue

        if file_id in seen_ids:
            continue

        seen_ids.add(
            file_id
        )

        references.append(
            dict(
                attachment
            )
        )

    vault_id = _get_context_vault_id(
        context
    )

    for file_id in _get_context_vault_file_ids(
        context
    ):
        normalized_file_id = str(
            file_id or ""
        ).strip()

        if not normalized_file_id:
            continue

        if normalized_file_id in seen_ids:
            continue

        try:
            vault_file = _resolve_vault_file(
                file_id=normalized_file_id,
                vault_id=vault_id,
            )

            references.append(
                {
                    "file_id": normalized_file_id,
                    "filename": str(
                        vault_file.get(
                            "filename",
                            "Unknown file",
                        )
                    ),
                    "content_type": str(
                        vault_file.get(
                            "content_type",
                            "",
                        )
                    ),
                    "source_type": "knowledge-vault",
                    "vault_id": vault_file.get(
                        "vault_id"
                    ),
                    "vault_name": vault_file.get(
                        "vault_name",
                        "",
                    ),
                }
            )

            seen_ids.add(
                normalized_file_id
            )

        except Exception as exc:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Selected Knowledge Vault file "
                    f"is unavailable: {normalized_file_id}. "
                    f"{exc}"
                ),
            ) from exc

    return references


# ---------------------------------------------------------------------------
# STAGE SOURCE ATTACHMENT
# ---------------------------------------------------------------------------

def _stage_attachment(
    attachment: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Stage one real source file into workspace/input.

    The staged file is a temporary execution input.
    It is never treated as a generated artifact.
    """

    file_id = str(
        attachment.get(
            "file_id",
            "",
        )
    ).strip()

    if not file_id:
        raise ValueError(
            "Attachment is missing file_id."
        )

    source_type = str(
        attachment.get(
            "source_type",
            "chat",
        )
    ).strip().lower()

    source_path: Path
    original_filename: str
    content_type: str
    resolved_vault_id: Optional[str] = None
    resolved_vault_name = ""

    if source_type == "knowledge-vault":
        vault_id = str(
            attachment.get(
                "vault_id",
                "",
            )
            or ""
        ).strip()

        vault_file = _resolve_vault_file(
            file_id=file_id,
            vault_id=(
                vault_id
                or None
            ),
        )

        source_path = Path(
            vault_file[
                "source_path"
            ]
        )

        original_filename = str(
            vault_file.get(
                "filename",
                source_path.name,
            )
        ).strip()

        content_type = str(
            vault_file.get(
                "content_type",
                attachment.get(
                    "content_type",
                    "",
                ),
            )
        ).strip()

        resolved_vault_id = str(
            vault_file.get(
                "vault_id",
                "",
            )
            or ""
        ).strip() or None

        resolved_vault_name = str(
            vault_file.get(
                "vault_name",
                "",
            )
        ).strip()

    else:
        source_path = _resolve_chat_upload_path(
            file_id
        )

        original_filename = str(
            attachment.get(
                "filename"
            )
            or source_path.name
        ).strip()

        content_type = str(
            attachment.get(
                "content_type",
                "",
            )
        ).strip()

    extension = (
        source_path.suffix.lower()
    )

    if extension not in (
        ALLOWED_ATTACHMENT_EXTENSIONS
    ):
        raise ValueError(
            f"Unsupported attachment extension: {extension}. "
            "Supported formats are CSV, XLSX, PDF, DOCX, TXT, "
            "MD, JSON, PNG, JPEG and WEBP."
        )

    original_filename = Path(
        original_filename
    ).name

    if not original_filename:
        original_filename = (
            source_path.name
        )

    safe_filename = (
        f"{file_id}_{original_filename}"
    )

    destination_path = (
        WORKSPACE_INPUT_DIR
        / safe_filename
    ).resolve()

    try:
        destination_path.relative_to(
            WORKSPACE_INPUT_DIR
        )
    except ValueError as exc:
        raise PermissionError(
            "Access denied: staged attachment must remain "
            "inside NOVA's workspace input directory."
        ) from exc

    WORKSPACE_INPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        source_path,
        destination_path,
    )

    if not destination_path.exists():
        raise RuntimeError(
            "Uploaded attachment could not be staged "
            "into the NOVA workspace."
        )

    return {
        "file_id": file_id,
        "original_filename": original_filename,
        "content_type": content_type,
        "source_type": source_type,
        "vault_id": resolved_vault_id,
        "vault_name": resolved_vault_name,
        "workspace_file_path": str(
            destination_path.relative_to(
                WORKSPACE_ROOT
            )
        ).replace(
            "\\",
            "/",
        ),
        "workspace_absolute_path": str(
            destination_path
        ),
        "extension": extension,
    }


# ---------------------------------------------------------------------------
# EVIDENCE REVIEW DETECTION
# ---------------------------------------------------------------------------

def _is_evidence_review_request(
    objective: str,
) -> bool:
    """
    Detect missions where the user wants NOVA to understand and explain
    the supplied evidence.
    """

    text = " ".join(
        str(
            objective or ""
        ).lower().split()
    )

    review_terms = (
        "check the files",
        "check every file",
        "check all files",
        "check every attached file",
        "check all attached files",
        "check these files",
        "check the attached files",
        "check the provided files",
        "check uploaded files",
        "check each file",
        "check the file",
        "read every file",
        "read all files",
        "read every attached file",
        "read all attached files",
        "read these files",
        "read uploaded files",
        "read each file",
        "read the file",
        "read the files",
        "review the files",
        "review every file",
        "review all files",
        "review every attached file",
        "review all attached files",
        "review the attached files",
        "review the provided files",
        "review uploaded files",
        "review each file",
        "review the evidence",
        "review all the evidence",
        "review the file",
        "inspect every file",
        "inspect all files",
        "inspect every attached file",
        "inspect all attached files",
        "inspect the attached files",
        "inspect each file",
        "inspect the file",
        "inspect the files",
        "analyze every file",
        "analyse every file",
        "analyze all files",
        "analyse all files",
        "analyze every attached file",
        "analyse every attached file",
        "analyze all attached files",
        "analyse all attached files",
        "analyze the attached files",
        "analyse the attached files",
        "analyze the provided files",
        "analyse the provided files",
        "analyze each file",
        "analyse each file",
        "analyze the file",
        "analyse the file",
        "analyze the files",
        "analyse the files",
        "tell me what each file",
        "tell me what every file",
        "tell me what each uploaded file",
        "tell me what each attached file",
        "tell me what each file contains",
        "tell me what every file contains",
        "tell me what each file is about",
        "tell me what every file is about",
        "tell me what these files contain",
        "tell me what these files are about",
        "tell me what each uploaded file contains",
        "tell me what each uploaded file is about",
        "tell me what each attached file contains",
        "tell me what this file contains",
        "tell me what this spreadsheet contains",
        "tell me what this document contains",
        "what each file contains",
        "what every file contains",
        "what each file is about",
        "what every file is about",
        "what are these files about",
        "what do these files contain",
        "what each uploaded file contains",
        "what this file contains",
        "what this spreadsheet contains",
        "explain each file",
        "explain every file",
        "explain these files",
        "explain all files",
        "explain the file",
        "explain the files",
        "summarize each file",
        "summarise each file",
        "summarize every file",
        "summarise every file",
        "summarize these files",
        "summarise these files",
        "summarize all files",
        "summarise all files",
        "summarize the file",
        "summarise the file",
        "summarize each one",
        "summarise each one",
        "explain each one",
        "explain the contents",
        "explain what each file contains",
        "understand the files",
        "understand every file",
        "understand these files",
        "look through the files",
        "go through the files",
    )

    if any(
        term in text
        for term in review_terms
    ):
        return True

    action_words = (
        "check",
        "review",
        "read",
        "analyze",
        "analyse",
        "inspect",
        "explain",
        "summarize",
        "summarise",
        "understand",
        "tell",
    )

    file_words = (
        "file",
        "files",
        "attachment",
        "attachments",
        "upload",
        "uploads",
        "evidence",
        "spreadsheet",
        "document",
    )

    has_action = any(
        act in text
        for act in action_words
    )

    has_file = any(
        f in text
        for f in file_words
    )

    has_scope = any(
        sc in text
        for sc in (
            "each",
            "every",
            "all",
            "these",
            "this",
            "attached",
            "uploaded",
            "provided",
            "supplied",
        )
    )

    return bool(
        has_action
        and has_file
        and has_scope
    )


def _is_evidence_review_report_request(
    objective: str,
) -> bool:
    """
    Detect an evidence review request.

    Mission Control controls whether a DOCX report is mandatory.
    """

    return _is_evidence_review_request(
        objective
    )


# ---------------------------------------------------------------------------
# AGENT CONTEXT PREPARATION
# ---------------------------------------------------------------------------

def _prepare_agent_context(
    context: Optional[
        Dict[str, Any]
    ],
    objective: str,
) -> tuple[
    Dict[str, Any],
    List[
        Dict[str, Any]
    ],
]:
    """
    Prepare a complete sovereign runtime context.

    Supports:
    - direct Local Chat uploads
    - Knowledge Vault file selections
    - selected vault scope
    - mission evidence
    """

    prepared_context: Dict[
        str,
        Any,
    ] = dict(
        context or {}
    )

    source_references = (
        _get_context_source_references(
            context
        )
    )

    prepared_context[
        "source_references"
    ] = source_references

    prepared_context[
        "selected_vault_id"
    ] = _get_context_vault_id(
        context
    )

    prepared_context[
        "selected_vault_file_ids"
    ] = _get_context_vault_file_ids(
        context
    )

    chat_attachments = (
        _get_context_attachments(
            context
        )
    )

    prepared_context[
        "mission_attachments"
    ] = source_references

    staged_attachments: List[
        Dict[str, Any]
    ] = []

    try:
        for attachment in source_references:
            staged = _stage_attachment(
                attachment
            )

            staged_attachments.append(
                staged
            )

            request_id = str(
                prepared_context.get(
                    "audit_request_id",
                    "",
                )
            ).strip() or None

            mission_context = prepared_context.get(
                "mission",
                {},
            )

            mission_id = None

            if isinstance(
                mission_context,
                dict,
            ):
                mission_id = str(
                    mission_context.get(
                        "mission_id",
                        "",
                    )
                ).strip() or None

            category = (
                "mission"
                if prepared_context.get(
                    "mission_control",
                    False,
                )
                else "agent"
            )

            action = (
                "mission_evidence_staged"
                if category == "mission"
                else "agent_evidence_staged"
            )

            filename = str(
                staged.get(
                    "original_filename",
                    attachment.get(
                        "filename",
                        "source file",
                    ),
                )
            ).strip()

            _audit_success(
                category=category,
                action=action,
                service="agents",
                message=(
                    f"Staged source evidence: {filename}"
                ),
                request_id=request_id,
                task_type=(
                    "mission"
                    if category == "mission"
                    else "agent"
                ),
                resource="file",
                resource_id=str(
                    attachment.get(
                        "file_id",
                        "",
                    )
                ).strip() or None,
                metadata={
                    "mission_id": mission_id,
                    "file_id": str(
                        attachment.get(
                            "file_id",
                            "",
                        )
                    ).strip(),
                    "filename": filename,
                    "source_type": str(
                        attachment.get(
                            "source_type",
                            "chat",
                        )
                    ).strip(),
                    "vault_id": staged.get(
                        "vault_id"
                    ),
                    "vault_name": staged.get(
                        "vault_name",
                        "",
                    ),
                    "workspace_file_path": staged.get(
                        "workspace_file_path",
                        "",
                    ),
                },
            )

    except Exception:
        _cleanup_staged_files(
            staged_attachments
        )
        raise

    staged_paths = [
        item[
            "workspace_file_path"
        ]
        for item in staged_attachments
    ]

    spreadsheet_paths = [
        path
        for path in staged_paths
        if path.lower().endswith(
            (
                ".csv",
                ".xlsx",
            )
        )
    ]

    document_paths = [
        path
        for path in staged_paths
        if path.lower().endswith(
            (
                ".pdf",
                ".docx",
                ".txt",
                ".md",
                ".json",
            )
        )
    ]

    image_paths = [
        path
        for path in staged_paths
        if path.lower().endswith(
            (
                ".png",
                ".jpg",
                ".jpeg",
                ".webp",
            )
        )
    ]

    prepared_context[
        "attachments"
    ] = staged_attachments

    prepared_context[
        "chat_attachments"
    ] = chat_attachments

    prepared_context[
        "staged_files"
    ] = staged_paths

    prepared_context[
        "spreadsheet_files"
    ] = spreadsheet_paths

    prepared_context[
        "document_files"
    ] = document_paths

    prepared_context[
        "image_files"
    ] = image_paths

    prepared_context[
        "evidence_review"
    ] = _is_evidence_review_request(
        objective
    )

    prepared_context[
        "mission_control"
    ] = bool(
        prepared_context.get(
            "mission_control",
            False,
        )
    )

    prepared_context[
        "evidence_review_report"
    ] = bool(
        prepared_context.get(
            "mission_control",
            False,
        )
        and prepared_context.get(
            "evidence_review",
            False,
        )
    )

    # -----------------------------------------------------------------------
    # PREVIOUS MISSION CONVERSATION
    # -----------------------------------------------------------------------

    conversation_history = prepared_context.get(
        "conversation_history",
        [],
    )

    if isinstance(
        conversation_history,
        list,
    ) and conversation_history:

        history_lines: List[str] = []

        for item in conversation_history[-12:]:
            if not isinstance(
                item,
                dict,
            ):
                continue

            role = str(
                item.get(
                    "role",
                    "",
                )
            ).strip().lower()

            content = str(
                item.get(
                    "content",
                    "",
                )
            ).strip()

            if not content:
                continue

            if role not in {
                "user",
                "assistant",
            }:
                continue

            history_lines.append(
                f"{role.upper()}: {content}"
            )

        if history_lines:
            prepared_context[
                "conversation_history_text"
            ] = "\n".join(
                history_lines
            )

    # -----------------------------------------------------------------------
    # SOURCE EVIDENCE INSTRUCTIONS
    # -----------------------------------------------------------------------

    attachment_instruction = ""

    if staged_paths:
        attachment_instruction = (
            "\n\nREAL USER-PROVIDED EVIDENCE IS AVAILABLE "
            "INSIDE THE NOVA WORKSPACE.\n"
            "SOURCE FILES:\n"
            + "\n".join(
                f"- {path}"
                for path in staged_paths
            )
            + "\n\nIMPORTANT SOURCE RULES:\n"
            "- These files are the authoritative source inputs.\n"
            "- Read the ACTUAL CONTENT of every supplied file before answering.\n"
            "- Do not infer a file's contents from its filename.\n"
            "- Do not invent missing measurements, records, observations or facts.\n"
            "- Do not overwrite or modify source files.\n"
        )

    selected_vault_id = (
        prepared_context.get(
            "selected_vault_id"
        )
    )

    selected_vault_file_ids = (
        prepared_context.get(
            "selected_vault_file_ids",
            [],
        )
    )

    if (
        selected_vault_id
        or selected_vault_file_ids
    ):
        attachment_instruction += (
            "\n\nKNOWLEDGE VAULT SOURCE SCOPE:\n"
            f"- Selected vault: "
            f"{selected_vault_id or 'ALL SELECTED VAULT SOURCES'}\n"
            f"- Selected file count: "
            f"{len(selected_vault_file_ids)}\n"
            "- The selected Knowledge Vault files are real registry files.\n"
            "- Treat their actual contents as authoritative source material.\n"
            "- Do not substitute unrelated files from other vaults.\n"
        )

    if prepared_context.get(
        "evidence_review"
    ):
        attachment_instruction += (
            "\n\nEVIDENCE REVIEW MODE IS ACTIVE.\n"
            "The user's goal is to understand the supplied files.\n"
            "You MUST inspect every supplied source file.\n"
            "There must be one reading step for every supplied source file.\n"
            "After all files are read, synthesize a conversational answer.\n"
            "\n"
            "MISSION CONTROL DELIVERABLE RULE:\n"
            "When this workflow is running from Mission Control, "
            "a DOCX review report is mandatory after all supplied files "
            "have been successfully read.\n"
            "The DOCX must be based only on actual completed reader results.\n"
            "The DOCX must be created inside the NOVA workspace output directory.\n"
            "The report-generation step must occur after all source-reading steps.\n"
            "The report must not modify the source input files.\n"
            "The final conversational response must still explain what each "
            "file is about and what it contains.\n"
            "Do not expose internal storage paths or execution metadata "
            "in the conversational answer.\n"
        )

    # -----------------------------------------------------------------------
    # CURRENT MISSION CONTEXT
    # -----------------------------------------------------------------------

    history_text = str(
        prepared_context.get(
            "conversation_history_text",
            "",
        )
    ).strip()

    mission_context = prepared_context.get(
        "mission",
        {},
    )

    mission_context_text = ""

    if isinstance(
        mission_context,
        dict,
    ):
        mission_title = str(
            mission_context.get(
                "title",
                "",
            )
        ).strip()

        mission_id = str(
            mission_context.get(
                "mission_id",
                "",
            )
        ).strip()

        mission_type = str(
            mission_context.get(
                "type",
                mission_context.get(
                    "mission_type",
                    "",
                ),
            )
        ).strip()

        mission_priority = str(
            mission_context.get(
                "priority",
                "",
            )
        ).strip()

        mission_autonomy = str(
            mission_context.get(
                "autonomy",
                "",
            )
        ).strip()

        if (
            mission_title
            or mission_id
            or mission_type
            or mission_priority
            or mission_autonomy
        ):
            mission_context_text = (
                "\n\nCURRENT MISSION CONTEXT:\n"
                f"- Mission ID: {mission_id}\n"
                f"- Mission: {mission_title}\n"
                f"- Type: {mission_type}\n"
                f"- Priority: {mission_priority}\n"
                f"- Autonomy: {mission_autonomy}\n"
            )

    # -----------------------------------------------------------------------
    # PREVIOUS CONVERSATION CONTEXT
    # -----------------------------------------------------------------------

    conversation_context_text = ""

    if history_text:
        conversation_context_text = (
            "\n\nPREVIOUS MISSION CONVERSATION:\n"
            f"{history_text}\n"
            "\nUse the previous conversation only as context. "
            "Do not treat unsupported statements as facts. "
            "Use supplied evidence as the authoritative source."
        )

    prepared_context[
        "conversation_history_text"
    ] = history_text

    prepared_context[
        "agent_objective"
    ] = (
        objective
        + mission_context_text
        + conversation_context_text
        + attachment_instruction
    )

    return (
        prepared_context,
        staged_attachments,
    )


# ---------------------------------------------------------------------------
# CLEANUP
# ---------------------------------------------------------------------------

def _cleanup_staged_files(
    staged_attachments: List[
        Dict[str, Any]
    ],
) -> None:
    """
    Remove temporary staged copies created for an execution.
    """

    for attachment in staged_attachments:
        path_value = attachment.get(
            "workspace_absolute_path"
        )

        if not path_value:
            continue

        path = Path(
            str(path_value)
        ).resolve()

        try:
            path.relative_to(
                WORKSPACE_INPUT_DIR
            )
        except ValueError:
            continue

        try:
            if (
                path.exists()
                and path.is_file()
            ):
                path.unlink()
        except OSError:
            continue


# ---------------------------------------------------------------------------
# EXECUTION SERIALIZATION
# ---------------------------------------------------------------------------

def serialize_execution(
    execution: Any,
) -> Dict[str, Any]:
    """
    Convert the existing ExecutionResult object
    into JSON-safe response data.
    """

    if hasattr(
        execution,
        "to_dict",
    ):
        result = execution.to_dict()

        if isinstance(
            result,
            dict,
        ):
            return result

    result: Dict[
        str,
        Any,
    ] = {}

    for attribute in (
        "completed_steps",
        "failed_steps",
        "blocked_steps",
    ):
        if hasattr(
            execution,
            attribute,
        ):
            result[
                attribute
            ] = getattr(
                execution,
                attribute,
            )

    if hasattr(
        execution,
        "plan",
    ):
        plan = execution.plan

        if hasattr(
            plan,
            "status",
        ):
            status = plan.status

            result[
                "status"
            ] = (
                status.value
                if hasattr(
                    status,
                    "value",
                )
                else str(
                    status
                )
            )

    return result


def build_synthesis_context(
    execution: Any,
) -> Dict[str, Any]:
    """
    Extract successful step results from the executed plan
    for final response synthesis.
    """

    context: Dict[
        str,
        Any
    ] = {}

    if not hasattr(
        execution,
        "plan",
    ):
        return context

    plan = execution.plan

    for step in plan.steps:
        status_value = getattr(
            step.status,
            "value",
            str(
                step.status
            ),
        )

        if (
            status_value
            == "completed"
            and step.result is not None
        ):
            context[
                step.id
            ] = step.result

    return context


# ---------------------------------------------------------------------------
# EVIDENCE CONTENT EXTRACTION
# ---------------------------------------------------------------------------

def _humanize_source_name(
    value: Any,
) -> str:
    """
    Convert a workspace path or filename into
    a clean user-facing file name.
    """

    text = str(
        value or ""
    ).strip()

    if not text:
        return "Supplied file"

    return Path(
        text
    ).name


def _json_safe_preview(
    value: Any,
    max_chars: int = 8000,
) -> str:
    """
    Convert structured reader data into bounded readable text.
    """

    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    except Exception:
        serialized = str(
            value
        )

    serialized = serialized.strip()

    if len(serialized) <= max_chars:
        return serialized

    return (
        serialized[
            : max_chars - 3
        ].rstrip()
        + "..."
    )


def _extract_result_text(
    result: Any,
) -> str:
    """
    Extract useful readable content from common reader result structures.

    Spreadsheet reader output is structured under sheets/headers/rows,
    so it is explicitly converted into a readable evidence representation.
    """

    if result is None:
        return ""

    if isinstance(
        result,
        str,
    ):
        return result.strip()

    if isinstance(
        result,
        list,
    ):
        parts: List[str] = []

        for item in result:
            text = _extract_result_text(
                item
            )

            if text:
                parts.append(
                    text
                )

        return "\n".join(
            parts
        ).strip()

    if not isinstance(
        result,
        dict,
    ):
        return str(
            result
        ).strip()

    if isinstance(
        result.get(
            "sheets"
        ),
        list,
    ):
        spreadsheet_lines: List[str] = []

        file_name = str(
            result.get(
                "file_name",
                "",
            )
        ).strip()

        file_type = str(
            result.get(
                "file_type",
                "",
            )
        ).strip()

        sheet_count = result.get(
            "sheet_count"
        )

        if file_name:
            spreadsheet_lines.append(
                f"File: {file_name}"
            )

        if file_type:
            spreadsheet_lines.append(
                f"Type: {file_type.upper()}"
            )

        if sheet_count is not None:
            spreadsheet_lines.append(
                f"Sheets: {sheet_count}"
            )

        spreadsheet_lines.append(
            ""
        )

        for sheet_index, sheet in enumerate(
            result.get(
                "sheets",
                [],
            )
        ):
            if not isinstance(
                sheet,
                dict,
            ):
                continue

            sheet_name = str(
                sheet.get(
                    "sheet_name",
                    f"Sheet {sheet_index + 1}",
                )
            ).strip()

            headers = sheet.get(
                "headers",
                [],
            )

            rows = sheet.get(
                "rows",
                [],
            )

            row_count = sheet.get(
                "row_count",
                len(
                    rows
                    if isinstance(
                        rows,
                        list,
                    )
                    else []
                ),
            )

            column_count = sheet.get(
                "column_count",
                len(
                    headers
                    if isinstance(
                        headers,
                        list,
                    )
                    else []
                ),
            )

            spreadsheet_lines.append(
                f"Sheet: {sheet_name}"
            )

            spreadsheet_lines.append(
                f"Dimensions: {row_count} data rows × {column_count} columns"
            )

            if isinstance(
                headers,
                list,
            ) and headers:

                header_text = ", ".join(
                    str(
                        header
                    )
                    for header in headers
                )

                spreadsheet_lines.append(
                    f"Columns: {header_text}"
                )

            if isinstance(
                rows,
                list,
            ) and rows:

                spreadsheet_lines.append(
                    "Sample data:"
                )

                for row in rows[:8]:
                    if not isinstance(
                        row,
                        (
                            list,
                            tuple,
                        ),
                    ):
                        row = [
                            row
                        ]

                    row_text = " | ".join(
                        "" if value is None
                        else str(value)
                        for value in row
                    )

                    spreadsheet_lines.append(
                        f"- {row_text}"
                    )

            else:
                spreadsheet_lines.append(
                    "Sample data: no data rows returned"
                )

            spreadsheet_lines.append(
                ""
            )

        return "\n".join(
            spreadsheet_lines
        ).strip()

    preferred_keys = (
        "text",
        "content",
        "extracted_text",
        "document_text",
        "summary",
        "description",
        "analysis",
    )

    for key in preferred_keys:
        value = result.get(
            key
        )

        if isinstance(
            value,
            str,
        ) and value.strip():
            return value.strip()

    nested_keys = (
        "data",
        "document",
        "extraction",
        "output",
        "result",
    )

    for key in nested_keys:
        nested = result.get(
            key
        )

        if nested is result:
            continue

        nested_text = _extract_result_text(
            nested
        )

        if nested_text:
            return nested_text

    useful = {
        key: value
        for key, value in result.items()
        if key not in {
            "size_bytes",
            "workspace",
            "tool",
            "verification",
            "verification_status",
            "created",
        }
    }

    if useful:
        return _json_safe_preview(
            useful
        )

    return ""


def _summarize_source_code_file(
    file_name: str,
    text: str,
) -> str:
    ext = Path(
        file_name
    ).suffix.lower()

    lines = [
        line
        for line in text.splitlines()
        if line.strip()
    ]

    total_lines = len(lines)

    if ext == ".css":
        selectors = re.findall(
            r"([.#a-zA-Z0-9_\-\s,]+)\s*\{",
            text,
        )

        clean_sel = [
            s.strip()
            for s in selectors
            if s.strip()
            and not s.strip().startswith("@")
        ][:12]

        sel_text = (
            f"Key selectors/components: {', '.join(clean_sel)}"
            if clean_sel
            else ""
        )

        return (
            f"File: {file_name} "
            f"(Frontend CSS Stylesheet, {total_lines} lines)\n"
            "Purpose: Defines UI styling, dark theme, layout structure, "
            "typography, colors, panels, buttons, and animations.\n"
            f"{sel_text}\n"
            "Summary: Contains styling declarations covering visual layout "
            "and responsive UI design."
        )

    if ext == ".json":
        try:
            parsed = json.loads(
                text
            )

            if isinstance(
                parsed,
                dict,
            ):
                keys = list(
                    parsed.keys()
                )

                return (
                    f"File: {file_name} "
                    f"(JSON Data/Configuration, {total_lines} lines)\n"
                    "Purpose: Structured JSON data containing key fields: "
                    f"{', '.join(keys[:15])}.\n"
                    f"Key fields count: {len(keys)}"
                )

            if isinstance(
                parsed,
                list,
            ):
                return (
                    f"File: {file_name} "
                    f"(JSON Array, {len(parsed)} items, {total_lines} lines)\n"
                    "Sample record: "
                    f"{json.dumps(parsed[0]) if parsed else '[]'}"
                )

        except Exception:
            pass

        return (
            f"File: {file_name} "
            f"(JSON data, {total_lines} lines)\n"
            f"Content preview: {text[:500]}"
        )

    if ext in {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
    }:
        symbols = re.findall(
            r"(?:def|function|const|class)\s+([a-zA-Z0-9_]+)",
            text,
        )

        clean_symbols = sorted(
            list(
                set(
                    symbols
                )
            )
        )[:12]

        sym_text = (
            "Declared functions/classes: "
            f"{', '.join(clean_symbols)}"
            if clean_symbols
            else "Main script execution"
        )

        return (
            f"File: {file_name} "
            f"({ext.lstrip('.').upper()} Source Module, {total_lines} lines)\n"
            "Purpose: Program source code implementing application logic.\n"
            f"{sym_text}"
        )

    if ext == ".md":
        headings = re.findall(
            r"^\s*#{1,6}\s+(.+)$",
            text,
            flags=re.MULTILINE,
        )

        h_text = (
            "Major sections: "
            + ", ".join(
                h.strip()
                for h in headings[:10]
            )
            if headings
            else ""
        )

        return (
            f"File: {file_name} "
            f"(Markdown Document, {total_lines} lines)\n"
            f"{h_text}\n"
            f"Summary: {text[:600]}"
        )

    if ext == ".txt":
        non_empty = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        css_like = (
            ":root" in text
            or (
                "{" in text
                and "}" in text
                and "--" in text
            )
        )

        json_like = text.lstrip().startswith(
            (
                "{",
                "[",
            )
        )

        code_like = bool(
            re.search(
                r"\b(?:def|class|function|import|from|const|let|var|return)\b",
                text
            )
        )

        if css_like:
            selectors = re.findall(
                r"([.#a-zA-Z0-9_\-\s,]+)\s*\{",
                text,
            )

            clean_sel = [
                s.strip()
                for s in selectors
                if s.strip()
                and not s.strip().startswith("@")
            ][:10]

            selector_text = (
                f"Key selectors/components: {', '.join(clean_sel)}\n"
                if clean_sel
                else ""
            )

            return (
                f"File: {file_name} "
                f"(Plain-text stylesheet/source extract, "
                f"{total_lines} non-empty lines)\n"
                "Purpose: Contains CSS-style UI definitions such as variables, "
                "selectors, layout, colors, and component styling.\n"
                f"{selector_text}"
                "The file was interpreted from its actual text rather than "
                "returned verbatim."
            )

        if json_like:
            try:
                parsed = json.loads(
                    text
                )

                if isinstance(
                    parsed,
                    dict,
                ):
                    keys = list(
                        parsed.keys()
                    )

                    return (
                        f"File: {file_name} "
                        f"(Text file containing JSON structure, "
                        f"{total_lines} non-empty lines)\n"
                        "Key fields: "
                        + ", ".join(
                            str(k)
                            for k in keys[:15]
                        )
                    )

                if isinstance(
                    parsed,
                    list,
                ):
                    return (
                        f"File: {file_name} "
                        f"(Text file containing a JSON array, "
                        f"{len(parsed)} items)\n"
                        "The file contains structured records rather than prose."
                    )

            except Exception:
                pass

        if code_like:
            symbols = re.findall(
                r"(?:def|function|class|const|let|var)\s+([a-zA-Z0-9_]+)",
                text,
            )

            symbols = sorted(
                list(
                    set(
                        symbols
                    )
                )
            )[:10]

            symbol_text = (
                f"Declared symbols: {', '.join(symbols)}\n"
                if symbols
                else ""
            )

            return (
                f"File: {file_name} "
                f"(Plain-text source/code extract, "
                f"{total_lines} non-empty lines)\n"
                "Purpose: Contains program or configuration logic "
                "represented as plain text.\n"
                f"{symbol_text}"
                "The raw source is intentionally summarized instead of "
                "dumped into the chat."
            )

        first_lines = non_empty[:3]

        preview = " | ".join(
            first_lines
        )

        if len(preview) > 420:
            preview = (
                preview[:417]
                .rstrip()
                + "..."
            )

        return (
            f"File: {file_name} "
            f"(Plain Text, {total_lines} non-empty lines)\n"
            "Purpose: Text content supplied by the user for review.\n"
            f"Opening content: "
            f"{preview or 'No readable text extracted.'}"
        )

    if ext == ".log":
        return (
            f"File: {file_name} "
            f"(Log File, {total_lines} lines)\n"
            f"First entry: {lines[0] if lines else ''}\n"
            f"Latest entry: {lines[-1] if lines else ''}"
        )

    preview_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ][:4]

    preview = " | ".join(
        preview_lines
    )

    if len(preview) > 700:
        preview = (
            preview[:697]
            .rstrip()
            + "..."
        )

    return (
        f"File: {file_name} "
        f"({ext.lstrip('.') or 'UNKNOWN'} File, "
        f"{total_lines} non-empty lines)\n"
        f"Summary: "
        f"{preview or 'No readable text extracted.'}"
    )


def _clean_evidence_text(
    text: str,
    max_chars: int = 6500,
) -> str:
    """
    Clean source text while preserving useful code/document content.
    """

    value = str(
        text or ""
    ).replace(
        "\r\n",
        "\n",
    ).replace(
        "\r",
        "\n",
    ).strip()

    if not value:
        return ""

    value = re.sub(
        r"\n{3,}",
        "\n\n",
        value,
    )

    if len(value) <= max_chars:
        return value

    return (
        value[
            : max_chars - 3
        ].rstrip()
        + "..."
    )


def _build_evidence_source_packet(
    execution: Any,
    prepared_context: Dict[str, Any],
) -> List[
    Dict[str, Any]
]:
    """
    Build a bounded, structured source packet for NOVA's
    local evidence-review language model.
    """

    if not hasattr(
        execution,
        "plan",
    ):
        return []

    staged_attachments = (
        prepared_context.get(
            "attachments",
            [],
        )
    )

    filename_by_path: Dict[
        str,
        str,
    ] = {}

    if isinstance(
        staged_attachments,
        list,
    ):
        for attachment in staged_attachments:
            if not isinstance(
                attachment,
                dict,
            ):
                continue

            path_value = str(
                attachment.get(
                    "workspace_file_path",
                    "",
                )
            ).strip().replace(
                "\\",
                "/",
            )

            original_filename = str(
                attachment.get(
                    "original_filename",
                    "",
                )
            ).strip()

            if path_value:
                filename_by_path[
                    path_value
                ] = (
                    original_filename
                    or _humanize_source_name(
                        path_value
                    )
                )

    packet: List[
        Dict[str, Any]
    ] = []

    for step in execution.plan.steps:
        status_value = getattr(
            step.status,
            "value",
            str(
                step.status
            ),
        )

        if status_value != "completed":
            continue

        result = step.result

        if result is None:
            continue

        tool_name = str(
            getattr(
                step,
                "tool",
                "",
            )
        ).strip().lower()

        if tool_name not in {
            "file_reader",
            "document_reader",
            "spreadsheet_reader",
            "spreadsheet_analysis",
            "ocr",
            "image_reader",
        }:
            continue

        source_path = ""

        if isinstance(
            result,
            dict,
        ):
            for key in (
                "file_path",
                "source_file",
                "source_path",
                "workspace_file_path",
                "path",
            ):
                candidate = str(
                    result.get(
                        key,
                        "",
                    )
                ).strip()

                if candidate:
                    source_path = (
                        candidate
                        .replace(
                            "\\",
                            "/",
                        )
                    )
                    break

        source_name = (
            filename_by_path.get(
                source_path
            )
            or (
                str(
                    result.get(
                        "file_name",
                        "",
                    )
                ).strip()
                if isinstance(
                    result,
                    dict,
                )
                else ""
            )
        )

        if not source_name:
            step_description = str(
                getattr(
                    step,
                    "description",
                    "",
                )
            ).strip()

            for (
                candidate_path,
                candidate_name,
            ) in filename_by_path.items():

                if (
                    Path(
                        candidate_path
                    ).name.lower()
                    in step_description.lower()
                ):
                    source_name = candidate_name
                    source_path = candidate_path
                    break

        if not source_name:
            source_name = _humanize_source_name(
                source_path
            )

        extracted_text = _extract_result_text(
            result
        )

        ext = Path(
            source_name
        ).suffix.lower()

        if ext in {
            ".txt",
            ".css",
            ".json",
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".html",
            ".xml",
            ".yaml",
            ".yml",
            ".log",
        }:
            extracted_text = _summarize_source_code_file(
                source_name,
                extracted_text,
            )

        else:
            extracted_text = _clean_evidence_text(
                extracted_text,
                max_chars=6500,
            )

        if not extracted_text:
            extracted_text = (
                f"File '{source_name}' was opened, "
                "but no readable text was extracted."
            )

        packet.append(
            {
                "file_name": source_name,
                "file_path": source_path,
                "reader": tool_name,
                "actual_content": extracted_text,
            }
        )

    return packet


# ---------------------------------------------------------------------------
# LOCAL EVIDENCE REVIEW RESPONSE
# ---------------------------------------------------------------------------

EVIDENCE_REVIEW_SYSTEM_PROMPT = """
You are NOVA's local evidence-review assistant.

Your job is to answer the user's request using ONLY the actual extracted evidence in the packet.

Required output format:

I reviewed all the attached files and examined their actual contents.

### 1. filename
What it is:
...

What it contains / Sheets & Data:
...

Key information / Important visible patterns:
...

Rules:
- Do not dump raw source code or long text blocks for CSS, JS, PY, JSON, etc. Summarize what the code or stylesheet does.
- For spreadsheets, explain sheets, column names, data dimensions, and representative sample records based on actual rows.
- For PDF/Word documents, summarize document subject, major sections, and key findings.
- For images, summarize readable text or visible properties.
- Do not report internal file paths, storage locations, or verification metadata unless explicitly asked.
- Do not invent facts that are not supported by the extracted evidence.
"""


def _generate_evidence_review_response(
    objective: str,
    execution: Any,
    prepared_context: Dict[str, Any],
) -> str:
    """
    Use the local NOVA model to turn actual reader results into
    a natural conversational file-by-file answer.
    """

    packet = _build_evidence_source_packet(
        execution=execution,
        prepared_context=prepared_context,
    )

    if not packet:
        return (
            "I could not complete the evidence review because "
            "no source-reading results were completed."
        )

    evidence_sections: List[str] = []

    for index, item in enumerate(
        packet,
        start=1,
    ):
        evidence_sections.append(
            (
                f"SOURCE {index}\n"
                f"FILE NAME: {item['file_name']}\n"
                f"FILE TYPE / READER: {item['reader']}\n"
                f"ACTUAL EXTRACTED CONTENT:\n"
                f"{item['actual_content']}\n"
            )
        )

    evidence_packet = (
        "\n".join(
            evidence_sections
        )
    )

    prompt = f"""
USER REQUEST:

{objective}

ACTUAL LOCAL EVIDENCE:

{evidence_packet}

Produce the final conversational answer now.

The answer MUST contain a separate section for every supplied source file.
Do not repeat raw source code verbatim.
""".strip()

    try:
        from app.services.model_engine.model_router import (
            route_request,
        )
        from app.services.model_engine.ollama_manager import (
            ollama_manager,
        )

        routing = route_request(
            objective
        )

        result = ollama_manager.generate(
            model=routing.model_name,
            prompt=prompt,
            system=EVIDENCE_REVIEW_SYSTEM_PROMPT,
            temperature=0.1,
            num_predict=2200,
            stream=False,
        )

        response = str(
            result.get(
                "response",
                "",
            )
        ).strip()

        if response:
            lower_response = response.lower()

            raw_dump_signals = (
                "/* ========================================================="
                in response
                or response.count(";") > 120
            )

            required_sections = sum(
                1
                for item in packet
                if item.get(
                    "file_name",
                    "",
                ).lower()
                in lower_response
            )

            if (
                required_sections
                >= max(
                    1,
                    len(packet) - 1,
                )
                and not raw_dump_signals
            ):
                return response

    except Exception as exc:
        print(
            "[NOVA EVIDENCE REVIEW MODEL FALLBACK] "
            f"{type(exc).__name__}: {exc}"
        )

    lines: List[str] = [
        "I reviewed all the attached files and examined their actual contents."
    ]

    for index, item in enumerate(
        packet,
        start=1,
    ):
        file_name = item[
            "file_name"
        ]

        lines.append(
            f"\n### {index}. {file_name}"
        )

        text = item.get(
            "actual_content",
            "",
        ).strip()

        lines.append(
            "What it is:"
        )

        ext = Path(
            file_name
        ).suffix.lower()

        if ext in {
            ".xlsx",
            ".csv",
        }:
            lines.append(
                "Spreadsheet workbook containing structured data tables."
            )

        elif ext in {
            ".pdf",
            ".docx",
        }:
            lines.append(
                "Document containing formatted text and section headings."
            )

        elif ext in {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        }:
            lines.append(
                "Image file analyzed via local OCR / vision processing."
            )

        elif ext in {
            ".css",
            ".json",
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".md",
            ".log",
            ".txt",
        }:
            lines.append(
                f"Text/Source file "
                f"({ext.lstrip('.').upper()} format)."
            )

        else:
            lines.append(
                "Supplied file attachment."
            )

        lines.append(
            "\nWhat it contains:"
        )

        lines.append(
            text
            if text
            else
            "The local extraction returned no readable text for this file."
        )

    return "\n".join(
        lines
    ).strip()


# ---------------------------------------------------------------------------
# EVIDENCE REVIEW RESPONSE
# ---------------------------------------------------------------------------

def _build_evidence_review_response(
    execution: Any,
    prepared_context: Dict[str, Any],
) -> str:
    """
    Build a natural file-by-file evidence review from actual
    completed reader results.
    """

    return _generate_evidence_review_response(
        objective=str(
            prepared_context.get(
                "original_objective",
                prepared_context.get(
                    "agent_objective",
                    "Review the supplied files.",
                ),
            )
        ),
        execution=execution,
        prepared_context=prepared_context,
    )


# ---------------------------------------------------------------------------
# ARTIFACT EXTRACTION
# ---------------------------------------------------------------------------

def _normalize_artifact_path(
    raw_path: Any,
) -> Optional[str]:
    """
    Normalize only workspace/output/... paths.

    Source input files can never become artifacts.
    """

    if not raw_path:
        return None

    raw = (
        str(raw_path)
        .replace(
            "\\",
            "/",
        )
        .strip()
        .lstrip("/")
    )

    if not raw:
        return None

    try:
        path = Path(
            raw
        )

        if path.is_absolute():
            resolved = path.resolve()

            relative = (
                resolved.relative_to(
                    WORKSPACE_ROOT
                )
            )

            normalized = str(
                relative
            ).replace(
                "\\",
                "/",
            )

        else:
            normalized = raw

            if normalized.startswith(
                "workspace/"
            ):
                normalized = normalized[
                    len(
                        "workspace/"
                    ):
                ]

    except Exception:
        return None

    normalized = (
        normalized
        .strip("/")
    )

    if not normalized:
        return None

    normalized_lower = (
        normalized.lower()
    )

    if (
        normalized_lower.startswith(
            "input/"
        )
        or normalized_lower.startswith(
            "workspace/input/"
        )
        or "/input/" in normalized_lower
    ):
        return None

    if not normalized_lower.startswith(
        "output/"
    ):
        return None

    resolved_path = (
        WORKSPACE_ROOT
        / normalized
    ).resolve()

    try:
        resolved_path.relative_to(
            WORKSPACE_OUTPUT_DIR
        )
    except ValueError:
        return None

    return normalized


def extract_artifacts(
    execution_dump: Dict[str, Any],
) -> List[
    Dict[str, Any]
]:
    """
    Extract only real generated artifacts that physically exist
    below workspace/output/.
    """

    context = execution_dump.get(
        "context",
        {},
    )

    if not isinstance(
        context,
        dict,
    ):
        return []

    artifacts: List[
        Dict[str, Any]
    ] = []

    seen_paths = set()

    for step_id, result in context.items():
        if not isinstance(
            result,
            dict,
        ):
            continue

        raw_file_path = result.get(
            "file_path"
        )

        if not raw_file_path:
            continue

        relative_path = (
            _normalize_artifact_path(
                raw_file_path
            )
        )

        if not relative_path:
            continue

        if relative_path in seen_paths:
            continue

        resolved_path = (
            WORKSPACE_ROOT
            / relative_path
        ).resolve()

        try:
            resolved_path.relative_to(
                WORKSPACE_OUTPUT_DIR
            )
        except ValueError:
            continue

        if not (
            resolved_path.exists()
            and resolved_path.is_file()
        ):
            continue

        seen_paths.add(
            relative_path
        )

        file_name = (
            result.get(
                "file_name"
            )
            or resolved_path.name
        )

        extension = (
            result.get(
                "extension"
            )
            or resolved_path.suffix
        )

        extension = str(
            extension or ""
        )

        if (
            extension
            and not extension.startswith(
                "."
            )
        ):
            extension = (
                f".{extension}"
            )

        extension = extension.lower()

        artifact_type = (
            extension.lstrip(".")
            if extension
            else ""
        )

        size_bytes = result.get(
            "size_bytes"
        )

        if not isinstance(
            size_bytes,
            int,
        ):
            try:
                size_bytes = (
                    resolved_path
                    .stat()
                    .st_size
                )
            except OSError:
                size_bytes = None

        verification_status = (
            result.get(
                "verification"
            )
            or result.get(
                "verification_status"
            )
            or (
                "VERIFIED"
                if result.get(
                    "verified"
                )
                else "COMPLETED"
            )
        )

        artifacts.append(
            {
                "step_id": str(
                    step_id
                ),
                "file_name": str(
                    file_name
                ),
                "file_path": relative_path,
                "extension": extension,
                "artifact_type": artifact_type,
                "size_bytes": size_bytes,
                "verification_status": str(
                    verification_status
                ),
                "available": True,
            }
        )

    return artifacts


def _audit_generated_artifacts(
    *,
    artifacts: List[Dict[str, Any]],
    request_id: Optional[str],
    category: str,
    task_type: str,
    mission_id: Optional[str] = None,
) -> None:
    """
    Persist one real audit event per physically verified artifact.
    """

    if not artifacts:
        return

    for artifact in artifacts:
        file_name = str(
            artifact.get(
                "file_name",
                "Generated artifact",
            )
        ).strip()

        file_path = str(
            artifact.get(
                "file_path",
                "",
            )
        ).strip()

        _audit_success(
            category="artifact",
            action="artifact_generated",
            service="agents",
            message=(
                f"Generated artifact: {file_name}"
            ),
            request_id=request_id,
            task_type=task_type,
            resource="artifact",
            resource_id=file_path or file_name,
            metadata={
                "source_category": category,
                "mission_id": mission_id,
                "step_id": str(
                    artifact.get(
                        "step_id",
                        "",
                    )
                ),
                "file_name": file_name,
                "file_path": file_path,
                "extension": artifact.get(
                    "extension",
                    "",
                ),
                "artifact_type": artifact.get(
                    "artifact_type",
                    "",
                ),
                "size_bytes": artifact.get(
                    "size_bytes"
                ),
                "verification_status": artifact.get(
                    "verification_status",
                    "",
                ),
                "available": bool(
                    artifact.get(
                        "available",
                        False,
                    )
                ),
            },
        )


# ---------------------------------------------------------------------------
# ARTIFACT RESPONSE
# ---------------------------------------------------------------------------

def _format_artifact_size(
    size_bytes: Any,
) -> str:
    if not isinstance(
        size_bytes,
        int,
    ) or size_bytes < 0:
        return ""

    if size_bytes < 1024:
        return (
            f"{size_bytes} bytes"
        )

    if size_bytes < 1024 * 1024:
        return (
            f"{size_bytes:,} bytes "
            f"({size_bytes / 1024:.1f} KB)"
        )

    return (
        f"{size_bytes:,} bytes "
        f"({size_bytes / (1024 * 1024):.2f} MB)"
    )


def _artifact_label(
    extension: str,
) -> str:
    mapping = {
        ".xlsx": "Excel report",
        ".csv": "CSV file",
        ".docx": "Word document",
        ".pdf": "PDF document",
        ".pptx": "PowerPoint presentation",
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".webp": "image",
        ".txt": "text file",
        ".md": "Markdown file",
        ".json": "JSON file",
        ".py": "Python file",
        ".js": "JavaScript file",
        ".jsx": "React file",
        ".ts": "TypeScript file",
        ".tsx": "TypeScript React file",
    }

    return mapping.get(
        str(
            extension
        ).lower(),
        "file",
    )


def _build_deterministic_artifact_response(
    artifacts: List[
        Dict[str, Any]
    ],
) -> str:
    if not artifacts:
        return ""

    if len(artifacts) == 1:
        artifact = artifacts[0]

        label = _artifact_label(
            artifact.get(
                "extension",
                "",
            )
        )

        lines = [
            f"Done — your {label} has been created.",
            "",
            (
                "File: "
                f"{artifact.get('file_name', 'Generated artifact')}"
            ),
            (
                "Location: "
                f"{artifact.get('file_path', '')}"
            ),
        ]

        size_text = (
            _format_artifact_size(
                artifact.get(
                    "size_bytes"
                )
            )
        )

        if size_text:
            lines.append(
                f"Size: {size_text}"
            )

        verification = str(
            artifact.get(
                "verification_status",
                "",
            )
        ).strip()

        if verification:
            lines.append(
                f"Verification: {verification}"
            )

        return "\n".join(
            lines
        )

    lines = [
        "Done — NOVA generated the requested artifacts.",
        "",
    ]

    for artifact in artifacts:
        file_name = artifact.get(
            "file_name",
            "Generated artifact",
        )

        file_path = artifact.get(
            "file_path",
            "",
        )

        lines.append(
            f"- {file_name}"
        )

        if file_path:
            lines.append(
                f"  Location: {file_path}"
            )

        size_text = (
            _format_artifact_size(
                artifact.get(
                    "size_bytes"
                )
            )
        )

        if size_text:
            lines.append(
                f"  Size: {size_text}"
            )

    return "\n".join(
        lines
    )


# ---------------------------------------------------------------------------
# CONVERSATION HELPERS
# ---------------------------------------------------------------------------

def build_conversation_title(
    objective: str,
) -> str:
    cleaned = " ".join(
        objective.strip().split()
    )

    if not cleaned:
        return "NOVA Agent Chat"

    if len(cleaned) <= 70:
        return cleaned

    return (
        cleaned[:67].rstrip()
        + "..."
    )


# ---------------------------------------------------------------------------
# SHARED AGENT EXECUTION
# ---------------------------------------------------------------------------

def _execute_agent_workflow(
    objective: str,
    context: Optional[
        Dict[str, Any]
    ],
    auto_confirm: bool,
) -> tuple[
    Dict[str, Any],
    Dict[str, Any],
    List[
        Dict[str, Any]
    ],
    str,
]:
    """
    Shared sovereign Planner -> Executor -> Response pipeline.
    """

    workflow_started_at = time.perf_counter()

    (
        prepared_context,
        staged_attachments,
    ) = _prepare_agent_context(
        context=context,
        objective=objective,
    )

    prepared_context[
        "original_objective"
    ] = objective

    request_id = str(
        prepared_context.get(
            "audit_request_id",
            "",
        )
    ).strip() or None

    mission_control = bool(
        prepared_context.get(
            "mission_control",
            False,
        )
    )

    task_type = (
        "mission"
        if mission_control
        else "agent"
    )

    mission_id = None

    mission_context_for_audit = prepared_context.get(
        "mission",
        {},
    )

    if isinstance(
        mission_context_for_audit,
        dict,
    ):
        mission_id = str(
            mission_context_for_audit.get(
                "mission_id",
                "",
            )
        ).strip() or None

    category = (
        "mission"
        if mission_control
        else "agent"
    )

    try:
        planner_objective = str(
            prepared_context.get(
                "agent_objective",
                objective,
            )
        ).strip()

        evidence_review = bool(
            prepared_context.get(
                "evidence_review",
                False,
            )
        )

        if (
            mission_control
            and evidence_review
        ):
            planner_objective = (
                planner_objective
                + "\n\n"
                + "MANDATORY MISSION CONTROL EVIDENCE REVIEW DELIVERABLE:\n"
                + "After ALL supplied evidence files have been successfully "
                + "read, generate a DOCX review report.\n"
                + "This DOCX report is mandatory for this Mission Control "
                + "evidence-review workflow.\n"
                + "The original user wording must not disable this Mission "
                + "Control deliverable requirement.\n"
                + "The report MUST use only actual completed reader results.\n"
                + "Use the existing NOVA document_writer tool.\n"
                + "Create the report at:\n"
                + "output/file_review_report.docx\n"
                + "The report-generation step MUST depend on every source "
                + "reading step.\n"
                + "Do not generate the report before all source files have "
                + "been read successfully.\n"
                + "Return the generated DOCX as a real workspace artifact."
            )

        plan_started_at = time.perf_counter()

        plan = (
            agent_planner.create_plan(
                objective=planner_objective,
            )
        )

        _audit_success(
            category=category,
            action=(
                "mission_plan_created"
                if mission_control
                else "agent_plan_created"
            ),
            service="agents.planner",
            message=(
                "Mission plan created."
                if mission_control
                else "Agent plan created."
            ),
            request_id=request_id,
            task_type=task_type,
            resource=(
                "mission"
                if mission_control
                else "agent"
            ),
            resource_id=mission_id,
            duration_ms=_duration_ms(
                plan_started_at
            ),
            metadata={
                "mission_id": mission_id,
                "objective_length": len(
                    objective
                ),
                "evidence_review": evidence_review,
                "evidence_count": len(
                    prepared_context.get(
                        "source_references",
                        [],
                    )
                    if isinstance(
                        prepared_context.get(
                            "source_references",
                            [],
                        ),
                        list,
                    )
                    else []
                ),
            },
        )

        effective_auto_confirm = (
            True
            if (
                mission_control
                and evidence_review
            )
            else bool(
                auto_confirm
            )
        )

        executor = AgentExecutor(
            auto_confirm=effective_auto_confirm,
        )

        execution_mission_id = None

        if mission_control:
            mission_context = prepared_context.get(
                "mission",
                {},
            )

            if isinstance(
                mission_context,
                dict,
            ):
                execution_mission_id = str(
                    mission_context.get(
                        "mission_id",
                        "",
                    )
                ).strip()

            if not execution_mission_id:
                execution_mission_id = str(
                    prepared_context.get(
                        "mission_id",
                        "",
                    )
                ).strip()

        execution_started_at = time.perf_counter()

        execution = executor.execute(
            plan=plan,
            context=prepared_context,
            mission_id=(
                execution_mission_id
                if execution_mission_id
                else None
            ),
        )

        execution_dump = (
            serialize_execution(
                execution
            )
        )

        execution_status = str(
            execution_dump.get(
                "status",
                "",
            )
        ).strip().lower()

        failed_steps_for_audit = (
            execution_dump.get(
                "failed_steps"
            ) or []
        )

        blocked_steps_for_audit = (
            execution_dump.get(
                "blocked_steps"
            ) or []
        )

        execution_audit_status = (
            "failed"
            if (
                execution_status
                in {
                    "failed",
                    "failure",
                    "error",
                }
                or failed_steps_for_audit
            )
            else "success"
        )

        execution_message = (
            "Mission execution completed."
            if mission_control
            else "Agent execution completed."
        )

        if execution_status in {
            "cancelled",
            "canceled",
        }:
            execution_message = (
                "Mission execution stopped cooperatively."
            )

        elif failed_steps_for_audit:
            execution_message = (
                "Agent execution completed with failed steps."
            )

        elif blocked_steps_for_audit:
            execution_message = (
                "Agent execution completed with blocked steps."
            )

        _safe_audit(
            category=category,
            action=(
                "mission_execution"
                if mission_control
                else "agent_execution"
            ),
            service="agents.executor",
            status=execution_audit_status,
            message=execution_message,
            request_id=request_id,
            task_type=task_type,
            resource=(
                "mission"
                if mission_control
                else "agent"
            ),
            resource_id=(
                execution_mission_id
                or mission_id
            ),
            duration_ms=_duration_ms(
                execution_started_at
            ),
            metadata={
                "mission_id": (
                    execution_mission_id
                    or mission_id
                ),
                "execution_status": execution_status,
                "completed_steps": len(
                    execution_dump.get(
                        "completed_steps",
                        [],
                    )
                    or []
                ),
                "failed_steps": len(
                    failed_steps_for_audit
                ),
                "blocked_steps": len(
                    blocked_steps_for_audit
                ),
                "mission_cancelled": bool(
                    execution_dump.get(
                        "mission_cancelled",
                        False,
                    )
                ),
            },
        )

        plan_dump = plan.model_dump(
            mode="json"
        )

        if evidence_review:
            response = (
                _build_evidence_review_response(
                    execution=execution,
                    prepared_context=prepared_context,
                )
            )

            is_report_requested = bool(
                prepared_context.get(
                    "evidence_review_report",
                    False,
                )
            )

            artifacts_dump = (
                extract_artifacts(
                    execution_dump
                )
                if is_report_requested
                else []
            )

            execution_status = str(
                execution_dump.get(
                    "status",
                    "",
                )
            ).lower().strip()

            if execution_status in {
                "cancelled",
                "canceled",
            }:
                execution_dump[
                    "mission_cancelled"
                ] = True

            elif (
                is_report_requested
                and not artifacts_dump
            ):
                print(
                    "[NOVA MISSION CONTROL] "
                    "Mandatory evidence-review DOCX was not created "
                    "or could not be found in workspace/output/."
                )

                execution_dump[
                    "mission_deliverable_error"
                ] = (
                    "Mandatory evidence-review DOCX was not created "
                    "or could not be verified in the NOVA workspace output directory."
                )

            _audit_generated_artifacts(
                artifacts=artifacts_dump,
                request_id=request_id,
                category=category,
                task_type=task_type,
                mission_id=mission_id,
            )

            return (
                plan_dump,
                execution_dump,
                artifacts_dump,
                response,
            )

        artifacts_dump = (
            extract_artifacts(
                execution_dump
            )
        )

        _audit_generated_artifacts(
            artifacts=artifacts_dump,
            request_id=request_id,
            category=category,
            task_type=task_type,
            mission_id=mission_id,
        )

        if artifacts_dump:
            response = (
                _build_deterministic_artifact_response(
                    artifacts_dump
                )
            )

        else:
            synthesis_context = (
                build_synthesis_context(
                    execution
                )
            )

            if synthesis_context:
                response = (
                    agent_response_synthesizer.synthesize(
                        objective=objective,
                        execution_context=synthesis_context,
                    )
                )

            else:
                response = (
                    "NOVA could not produce a final answer "
                    "because the agent execution did not "
                    "produce any completed results."
                )

        _audit_success(
            category=category,
            action=(
                "mission_workflow_response_ready"
                if mission_control
                else "agent_workflow_response_ready"
            ),
            service="agents",
            message=(
                "Mission response synthesized."
                if mission_control
                else "Agent response synthesized."
            ),
            request_id=request_id,
            task_type=task_type,
            resource=(
                "mission"
                if mission_control
                else "agent"
            ),
            resource_id=mission_id,
            duration_ms=_duration_ms(
                workflow_started_at
            ),
            metadata={
                "mission_id": mission_id,
                "artifact_count": len(
                    artifacts_dump
                ),
                "evidence_review": evidence_review,
                "response_length": len(
                    response
                ),
            },
        )

        return (
            plan_dump,
            execution_dump,
            artifacts_dump,
            response,
        )

    except Exception as exc:
        _audit_failure(
            category=category,
            action=(
                "mission_workflow"
                if mission_control
                else "agent_workflow"
            ),
            service="agents",
            message=(
                "Mission workflow failed."
                if mission_control
                else "Agent workflow failed."
            ),
            request_id=request_id,
            task_type=task_type,
            resource=(
                "mission"
                if mission_control
                else "agent"
            ),
            resource_id=mission_id,
            duration_ms=_duration_ms(
                workflow_started_at
            ),
            metadata={
                "mission_id": mission_id,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(
                    exc
                )[:1200],
            },
        )

        raise

    finally:
        _cleanup_staged_files(
            staged_attachments
        )


# ---------------------------------------------------------------------------
# SAVE CHAT EXECUTION
# ---------------------------------------------------------------------------

def _save_agent_conversation(
    db: Session,
    objective: str,
    plan_dump: Dict[str, Any],
    execution_dump: Dict[str, Any],
    artifacts_dump: List[
        Dict[str, Any]
    ],
    response: str,
    request_context: Optional[
        Dict[str, Any]
    ],
) -> str:
    supplied_conversation_id = None

    if request_context:
        supplied_conversation_id = (
            request_context.get(
                "conversation_id"
            )
        )

    conversation = None

    if supplied_conversation_id:
        conversation = get_conversation(
            db,
            str(
                supplied_conversation_id
            ),
        )

    if conversation is None:
        conversation = (
            create_conversation(
                db,
                title=build_conversation_title(
                    objective
                ),
            )
        )

    saved_user_message = add_message(
        db=db,
        conversation=conversation,
        role="user",
        content=objective,
        model=None,
    )

    is_mission_chat = bool(
        request_context
        and request_context.get(
            "source"
        ) == "nova-mission-chat"
    )

    if not is_mission_chat:
        source_references = (
            _get_context_source_references(
                request_context
            )
        )

        for attachment in source_references:
            file_id = attachment.get(
                "file_id"
            )

            if not file_id:
                continue

            try:
                file_data = load_chat_file(
                    file_id
                )
            except Exception:
                file_data = None

            if isinstance(
                file_data,
                dict,
            ):
                filename = file_data.get(
                    "filename",
                    attachment.get(
                        "filename",
                        "Unknown file",
                    ),
                )

                content_type = file_data.get(
                    "content_type",
                    attachment.get(
                        "content_type",
                        "",
                    ),
                )
            else:
                filename = attachment.get(
                    "filename",
                    "Unknown file",
                )

                content_type = attachment.get(
                    "content_type",
                    "",
                )

            add_attachment(
                db=db,
                message=saved_user_message,
                file_id=file_id,
                filename=filename,
                content_type=content_type,
            )

    agent_data_to_save = {
        "plan": plan_dump,
        "execution": execution_dump,
        "artifacts": artifacts_dump,
    }

    add_message(
        db=db,
        conversation=conversation,
        role="assistant",
        content=response,
        model="NOVA Agent",
        agent_data=agent_data_to_save,
    )

    return conversation.id


# ---------------------------------------------------------------------------
# STANDARD AGENT RUN
# ---------------------------------------------------------------------------

@router.post(
    "/run",
    response_model=AgentRunResponse,
)
def run_agent(
    request: AgentRunRequest,
    db: Session = Depends(get_db),
) -> AgentRunResponse:

    started_at = time.perf_counter()
    request_id = create_request_id()

    objective = request.objective.strip()

    if not objective:
        _audit_failure(
            category="agent",
            action="agent_run_validation",
            service="agents",
            message="Agent objective cannot be empty.",
            request_id=request_id,
            task_type="agent",
            metadata={
                "reason": "empty_objective",
            },
        )

        raise HTTPException(
            status_code=400,
            detail="Objective cannot be empty.",
        )

    request_context: Dict[
        str,
        Any,
    ] = dict(
        request.context or {}
    )

    request_context[
        "audit_request_id"
    ] = request_id

    _audit_success(
        category="agent",
        action="agent_run_started",
        service="agents",
        message="Agent workflow started.",
        request_id=request_id,
        task_type="agent",
        resource="agent",
        metadata={
            "objective_length": len(
                objective
            ),
            "auto_confirm": bool(
                request.auto_confirm
            ),
            "attachment_count": len(
                _get_context_attachments(
                    request_context
                )
            ),
            "vault_file_count": len(
                _get_context_vault_file_ids(
                    request_context
                )
            ),
        },
    )

    try:
        (
            plan_dump,
            execution_dump,
            artifacts_dump,
            response,
        ) = _execute_agent_workflow(
            objective=objective,
            context=request_context,
            auto_confirm=request.auto_confirm,
        )

        conversation_id = (
            _save_agent_conversation(
                db=db,
                objective=objective,
                plan_dump=plan_dump,
                execution_dump=execution_dump,
                artifacts_dump=artifacts_dump,
                response=response,
                request_context=request_context,
            )
        )

        _audit_success(
            category="agent",
            action="agent_run_completed",
            service="agents",
            message="Agent workflow completed successfully.",
            request_id=request_id,
            task_type="agent",
            resource="agent",
            resource_id=conversation_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "conversation_id": conversation_id,
                "artifact_count": len(
                    artifacts_dump
                ),
                "execution_status": str(
                    execution_dump.get(
                        "status",
                        "",
                    )
                ),
                "completed_steps": len(
                    execution_dump.get(
                        "completed_steps",
                        [],
                    )
                    or []
                ),
                "failed_steps": len(
                    execution_dump.get(
                        "failed_steps",
                        [],
                    )
                    or []
                ),
                "blocked_steps": len(
                    execution_dump.get(
                        "blocked_steps",
                        [],
                    )
                    or []
                ),
            },
        )

        return AgentRunResponse(
            conversation_id=conversation_id,
            plan=plan_dump,
            execution=execution_dump,
            response=response,
            artifacts=artifacts_dump,
        )

    except HTTPException:
        raise

    except Exception as exc:
        _audit_failure(
            category="agent",
            action="agent_run_failed",
            service="agents",
            message="Agent workflow failed.",
            request_id=request_id,
            task_type="agent",
            resource="agent",
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(
                    exc
                )[:1200],
            },
        )

        print(
            f"NOVA Agent execution internal error: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "NOVA COULD NOT COMPLETE THIS TASK: "
                "The requested agent workflow encountered an error."
            ),
        ) from exc


# ---------------------------------------------------------------------------
# MISSION RUN
# ---------------------------------------------------------------------------

@router.post(
    "/mission/run",
    response_model=MissionRunResponse,
)
def run_mission(
    request: MissionRunRequest,
    db: Session = Depends(get_db),
) -> MissionRunResponse:
    """
    Execute one real Mission Control workflow.

    Evidence can come from:
    - normal chat uploads
    - Knowledge Vault file selections
    """

    started_at = time.perf_counter()
    request_id = create_request_id()

    title = request.title.strip()
    objective = request.objective.strip()

    if not title:
        _audit_failure(
            category="mission",
            action="mission_run_validation",
            service="agents",
            message="Mission title cannot be empty.",
            request_id=request_id,
            task_type="mission",
            metadata={
                "reason": "empty_title",
            },
        )

        raise HTTPException(
            status_code=400,
            detail="Mission title cannot be empty.",
        )

    if not objective:
        _audit_failure(
            category="mission",
            action="mission_run_validation",
            service="agents",
            message="Mission objective cannot be empty.",
            request_id=request_id,
            task_type="mission",
            metadata={
                "reason": "empty_objective",
            },
        )

        raise HTTPException(
            status_code=400,
            detail="Mission objective cannot be empty.",
        )

    # -----------------------------------------------------------------------
    # GUARANTEE A REAL MISSION ID
    # -----------------------------------------------------------------------

    mission_id = str(
        request.mission_id or ""
    ).strip()

    if not mission_id:
        mission_id = (
            f"mission-{uuid.uuid4().hex[:12]}"
        )

    mission_context: Dict[
        str,
        Any,
    ] = dict(
        request.context or {}
    )

    mission_context[
        "audit_request_id"
    ] = request_id

    mission_context[
        "mission_control"
    ] = True

    mission_context[
        "mission_id"
    ] = mission_id

    source_references = (
        _get_context_source_references(
            mission_context
        )
    )

    _audit_success(
        category="mission",
        action="mission_run_started",
        service="agents",
        message=(
            f"Mission '{title}' started."
        ),
        request_id=request_id,
        task_type="mission",
        resource="mission",
        resource_id=mission_id,
        metadata={
            "mission_id": mission_id,
            "title": title,
            "objective_length": len(
                objective
            ),
            "auto_confirm": bool(
                request.auto_confirm
            ),
            "evidence_count": len(
                source_references
            ),
            "knowledge_vault_evidence_count": sum(
                1
                for reference in source_references
                if reference.get(
                    "source_type"
                ) == "knowledge-vault"
            ),
        },
    )

    # -----------------------------------------------------------------------
    # REAL EVIDENCE REQUIREMENT
    # -----------------------------------------------------------------------

    if not source_references:
        _audit_failure(
            category="mission",
            action="mission_run_validation",
            service="agents",
            message=(
                "Mission rejected because no real evidence file was supplied."
            ),
            request_id=request_id,
            task_type="mission",
            resource="mission",
            resource_id=mission_id,
            metadata={
                "reason": "no_evidence",
                "mission_id": mission_id,
                "title": title,
            },
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "MISSION REQUIRES AT LEAST ONE REAL "
                "EVIDENCE FILE OR KNOWLEDGE VAULT FILE."
            ),
        )

    # -----------------------------------------------------------------------
    # VALIDATE EVERY REAL SOURCE
    # -----------------------------------------------------------------------

    for reference in source_references:
        file_id = str(
            reference.get(
                "file_id",
                "",
            )
        ).strip()

        if not file_id:
            continue

        source_type = str(
            reference.get(
                "source_type",
                "chat",
            )
        ).strip().lower()

        try:
            if source_type == "knowledge-vault":
                vault_id = str(
                    reference.get(
                        "vault_id",
                        "",
                    )
                    or ""
                ).strip()

                source_path = (
                    _resolve_vault_file(
                        file_id=file_id,
                        vault_id=(
                            vault_id
                            or None
                        ),
                    )[
                        "source_path"
                    ]
                )

            else:
                source_path = (
                    _resolve_chat_upload_path(
                        file_id
                    )
                )

        except FileNotFoundError as exc:
            _audit_failure(
                category="mission",
                action="mission_evidence_validation",
                service="agents",
                message=(
                    "Mission evidence file is unavailable."
                ),
                request_id=request_id,
                task_type="mission",
                resource="file",
                resource_id=file_id,
                metadata={
                    "mission_id": mission_id,
                    "filename": reference.get(
                        "filename"
                    ),
                    "source_type": source_type,
                    "reason": "file_not_found",
                },
            )

            raise HTTPException(
                status_code=400,
                detail=(
                    "MISSION EVIDENCE FILE IS NOT AVAILABLE: "
                    f"{reference.get('filename') or file_id}"
                ),
            ) from exc

        except Exception as exc:
            _audit_failure(
                category="mission",
                action="mission_evidence_validation",
                service="agents",
                message=(
                    "Mission evidence validation failed."
                ),
                request_id=request_id,
                task_type="mission",
                resource="file",
                resource_id=file_id,
                metadata={
                    "mission_id": mission_id,
                    "filename": reference.get(
                        "filename"
                    ),
                    "source_type": source_type,
                    "error_type": type(
                        exc
                    ).__name__,
                    "error": str(
                        exc
                    )[:1200],
                },
            )

            raise HTTPException(
                status_code=400,
                detail=(
                    "MISSION EVIDENCE VALIDATION FAILED: "
                    f"{reference.get('filename') or file_id}. "
                    f"{exc}"
                ),
            ) from exc

        extension = (
            source_path.suffix.lower()
        )

        if extension not in (
            ALLOWED_ATTACHMENT_EXTENSIONS
        ):
            _audit_failure(
                category="mission",
                action="mission_evidence_validation",
                service="agents",
                message=(
                    "Mission contains an unsupported evidence file."
                ),
                request_id=request_id,
                task_type="mission",
                resource="file",
                resource_id=file_id,
                metadata={
                    "mission_id": mission_id,
                    "filename": source_path.name,
                    "extension": extension,
                    "reason": "unsupported_extension",
                },
            )

            raise HTTPException(
                status_code=400,
                detail=(
                    "MISSION CONTAINS AN UNSUPPORTED "
                    f"EVIDENCE FILE: {source_path.name}"
                ),
            )

    # -----------------------------------------------------------------------
    # NORMALIZE CONTEXT
    # -----------------------------------------------------------------------

    mission_context[
        "source_references"
    ] = source_references

    mission_context[
        "mission_attachments"
    ] = source_references

    mission_context[
        "vault_file_ids"
    ] = [
        reference[
            "file_id"
        ]
        for reference in source_references
        if reference.get(
            "source_type"
        ) == "knowledge-vault"
    ]

    mission_context[
        "selected_vault_id"
    ] = _get_context_vault_id(
        mission_context
    )

    mission_context[
        "mission"
    ] = {
        **(
            mission_context.get(
                "mission",
                {}
            )
            if isinstance(
                mission_context.get(
                    "mission",
                    {}
                ),
                dict,
            )
            else {}
        ),
        "mission_id": mission_id,
        "title": title,
        "execution_boundary": (
            "LOCAL / AIR-GAPPED"
        ),
        "external_ai_calls": 0,
        "evidence_count": len(
            source_references
        ),
        "knowledge_vault_evidence_count": sum(
            1
            for reference in source_references
            if reference.get(
                "source_type"
            ) == "knowledge-vault"
        ),
    }

    mission_objective = (
        f"MISSION: {title}\n\n"
        f"OBJECTIVE:\n{objective}"
    )

    try:
        (
            plan_dump,
            execution_dump,
            artifacts_dump,
            response,
        ) = _execute_agent_workflow(
            objective=mission_objective,
            context=mission_context,
            auto_confirm=request.auto_confirm,
        )

        conversation_id = (
            _save_agent_conversation(
                db=db,
                objective=mission_objective,
                plan_dump=plan_dump,
                execution_dump=execution_dump,
                artifacts_dump=artifacts_dump,
                response=response,
                request_context=mission_context,
            )
        )

        execution_status = str(
            execution_dump.get(
                "status",
                "",
            )
        ).lower().strip()

        failed_steps = (
            execution_dump.get(
                "failed_steps"
            ) or []
        )

        blocked_steps = (
            execution_dump.get(
                "blocked_steps"
            ) or []
        )

        mission_deliverable_error = (
            execution_dump.get(
                "mission_deliverable_error"
            )
        )

        mission_cancelled = (
            execution_status
            in {
                "cancelled",
                "canceled",
            }
            or bool(
                execution_dump.get(
                    "mission_cancelled",
                    False,
                )
            )
        )

        if mission_cancelled:
            mission_status = "STOPPED"

        elif execution_status in {
            "failed",
            "error",
            "failure",
        }:
            mission_status = "FAILED"

        elif failed_steps:
            mission_status = "FAILED"

        elif blocked_steps:
            mission_status = "BLOCKED"

        elif mission_deliverable_error:
            mission_status = "FAILED"

        elif (
            mission_context.get(
                "mission_control",
                False,
            )
            and _is_evidence_review_request(
                mission_objective
            )
            and not artifacts_dump
        ):
            mission_status = "FAILED"

        elif execution_status in {
            "completed",
            "complete",
            "success",
            "successful",
        }:
            mission_status = "COMPLETED"

        else:
            mission_status = "COMPLETED"

        sovereignty = {
            "execution_mode": "LOCAL",
            "network_mode": "AIR-GAPPED",
            "external_ai_calls": 0,
            "local_reasoning": True,
            "local_tool_execution": True,
            "artifact_directory": (
                "workspace/output/"
            ),
            "knowledge_vault_sources": sum(
                1
                for reference in source_references
                if reference.get(
                    "source_type"
                ) == "knowledge-vault"
            ),
        }

        terminal_audit_status = (
            "success"
            if mission_status
            == "COMPLETED"
            else "failed"
        )

        terminal_message_map = {
            "COMPLETED": (
                f"Mission '{title}' completed successfully."
            ),
            "STOPPED": (
                f"Mission '{title}' was stopped."
            ),
            "FAILED": (
                f"Mission '{title}' failed."
            ),
            "BLOCKED": (
                f"Mission '{title}' is blocked."
            ),
        }

        _safe_audit(
            category="mission",
            action="mission_run_completed",
            service="agents",
            status=terminal_audit_status,
            message=terminal_message_map.get(
                mission_status,
                f"Mission '{title}' finished with status {mission_status}.",
            ),
            request_id=request_id,
            task_type="mission",
            resource="mission",
            resource_id=mission_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "mission_id": mission_id,
                "title": title,
                "mission_status": mission_status,
                "execution_status": execution_status,
                "conversation_id": conversation_id,
                "artifact_count": len(
                    artifacts_dump
                ),
                "evidence_count": len(
                    source_references
                ),
                "knowledge_vault_evidence_count": sum(
                    1
                    for reference in source_references
                    if reference.get(
                        "source_type"
                    ) == "knowledge-vault"
                ),
                "failed_steps": len(
                    failed_steps
                ),
                "blocked_steps": len(
                    blocked_steps
                ),
                "mission_cancelled": mission_cancelled,
                "mission_deliverable_error": bool(
                    mission_deliverable_error
                ),
            },
        )

        return MissionRunResponse(
            mission_id=mission_id,
            title=title,
            status=mission_status,
            conversation_id=conversation_id,
            plan=plan_dump,
            execution=execution_dump,
            response=response,
            artifacts=artifacts_dump,
            sovereignty=sovereignty,
        )

    except HTTPException:
        raise

    except Exception as exc:
        _audit_failure(
            category="mission",
            action="mission_run_failed",
            service="agents",
            message=(
                f"Mission '{title}' encountered an internal execution error."
            ),
            request_id=request_id,
            task_type="mission",
            resource="mission",
            resource_id=mission_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "mission_id": mission_id,
                "title": title,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(
                    exc
                )[:1200],
            },
        )

        print(
            f"NOVA Mission execution internal error: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "NOVA COULD NOT EXECUTE THIS MISSION: "
                "The sovereign mission workflow encountered an error."
            ),
        ) from exc


# ---------------------------------------------------------------------------
# MISSION STOP
# ---------------------------------------------------------------------------

@router.post(
    "/mission/{mission_id}/stop",
)
def stop_mission(
    mission_id: str,
) -> Dict[str, Any]:
    """
    Request cooperative cancellation of a running Mission Control mission.

    The currently executing tool is allowed to finish. The executor then
    stops before starting remaining steps.
    """

    started_at = time.perf_counter()

    normalized_mission_id = str(
        mission_id or ""
    ).strip()

    request_id = create_request_id()

    if not normalized_mission_id:
        _audit_failure(
            category="mission",
            action="mission_stop_validation",
            service="agents",
            message="Mission ID cannot be empty.",
            request_id=request_id,
            task_type="mission",
            metadata={
                "reason": "empty_mission_id",
            },
        )

        raise HTTPException(
            status_code=400,
            detail="Mission ID cannot be empty.",
        )

    accepted = set_mission_cancelled(
        normalized_mission_id
    )

    if not accepted:
        _audit_failure(
            category="mission",
            action="mission_stop_request",
            service="agents",
            message=(
                "Mission stop request was rejected because the mission ID is invalid."
            ),
            request_id=request_id,
            task_type="mission",
            resource="mission",
            resource_id=normalized_mission_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "mission_id": normalized_mission_id,
                "accepted": False,
            },
        )

        raise HTTPException(
            status_code=400,
            detail="Invalid mission ID.",
        )

    _audit_success(
        category="mission",
        action="mission_stop_requested",
        service="agents.executor",
        message=(
            f"Mission stop requested for {normalized_mission_id}."
        ),
        request_id=request_id,
        task_type="mission",
        resource="mission",
        resource_id=normalized_mission_id,
        duration_ms=_duration_ms(
            started_at
        ),
        metadata={
            "mission_id": normalized_mission_id,
            "accepted": True,
            "stop_mode": "cooperative",
        },
    )

    return {
        "mission_id": normalized_mission_id,
        "status": "STOP_REQUESTED",
        "message": (
            "Mission stop request accepted. "
            "The executor will stop before starting the next step."
        ),
    }


# ---------------------------------------------------------------------------
# MISSION DELETE
# ---------------------------------------------------------------------------

@router.delete(
    "/mission/{mission_id}",
)
def delete_mission(
    mission_id: str,
) -> Dict[str, Any]:
    """
    Remove a Mission Control mission from active backend execution state.

    Source files, including Knowledge Vault files, remain untouched.
    """

    started_at = time.perf_counter()

    normalized_mission_id = str(
        mission_id or ""
    ).strip()

    request_id = create_request_id()

    if not normalized_mission_id:
        _audit_failure(
            category="mission",
            action="mission_delete_validation",
            service="agents",
            message="Mission ID cannot be empty.",
            request_id=request_id,
            task_type="mission",
            metadata={
                "reason": "empty_mission_id",
            },
        )

        raise HTTPException(
            status_code=400,
            detail="Mission ID cannot be empty.",
        )

    cancellation_requested = set_mission_cancelled(
        normalized_mission_id
    )

    _audit_success(
        category="mission",
        action="mission_delete_requested",
        service="agents",
        message=(
            f"Mission deletion request accepted for {normalized_mission_id}."
        ),
        request_id=request_id,
        task_type="mission",
        resource="mission",
        resource_id=normalized_mission_id,
        duration_ms=_duration_ms(
            started_at
        ),
        metadata={
            "mission_id": normalized_mission_id,
            "cancel_requested": bool(
                cancellation_requested
            ),
            "source_files_preserved": True,
        },
    )

    return {
        "mission_id": normalized_mission_id,
        "status": "DELETE_REQUESTED",
        "cancel_requested": bool(
            cancellation_requested
        ),
        "message": (
            "Mission deletion request accepted. "
            "Any in-flight execution will be cooperatively stopped, "
            "while user source evidence remains untouched."
        ),
    }