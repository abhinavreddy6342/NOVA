from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import mimetypes
import time

from app.core.database import SessionLocal

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.knowledge.rag import retrieve_context
from app.services.audit.service import (
    audit_service,
    create_request_id,
)
from app.services.chat_files import (
    load_chat_file,
    save_chat_file,
)
from app.services.chat_history import (
    add_attachment,
    add_message,
    create_conversation,
    get_conversation,
)
from app.services.ollama import generate_response


router = APIRouter(
    prefix="/api/chat",
    tags=["chat"],
)


# ---------------------------------------------------------------------------
# NOVA WORKSPACE
# ---------------------------------------------------------------------------

BACKEND_ROOT = (
    Path(__file__).resolve().parents[2]
)

WORKSPACE_ROOT = (
    BACKEND_ROOT
    / "app"
    / "workspace"
).resolve()


# ---------------------------------------------------------------------------
# REQUEST / RESPONSE MODELS
# ---------------------------------------------------------------------------

class AttachmentReference(BaseModel):
    file_id: str
    filename: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = ""

    # None means automatic NOVA model routing.
    model: Optional[str] = None

    conversation_id: Optional[str] = None

    attachments: List[
        AttachmentReference
    ] = Field(
        default_factory=list
    )

    vault_id: Optional[str] = None

    file_ids: List[str] = Field(
        default_factory=list
    )


class ChatResponse(BaseModel):
    response: str
    model: str
    conversation_id: str


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def utc_now():
    return datetime.now(
        timezone.utc
    )


def _safe_audit_success(
    *,
    category: str,
    action: str,
    service: str,
    message: str = "",
    duration_ms: Optional[float] = None,
    model: Optional[str] = None,
    task_type: Optional[str] = None,
    resource: Optional[str] = None,
    resource_id: Optional[str] = None,
    request_id: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    """
    Best-effort audit recording.

    Audit failures must never break the primary NOVA operation.
    """

    try:
        return audit_service.success(
            category=category,
            action=action,
            service=service,
            message=message,
            duration_ms=duration_ms,
            model=model,
            task_type=task_type,
            resource=resource,
            resource_id=resource_id,
            request_id=request_id,
            metadata=metadata or {},
        )
    except Exception as audit_error:
        print(
            "[NOVA AUDIT WARNING] "
            f"Failed to record success event: {audit_error}"
        )
        return None


def _safe_audit_failure(
    *,
    category: str,
    action: str,
    service: str,
    message: str = "",
    duration_ms: Optional[float] = None,
    model: Optional[str] = None,
    task_type: Optional[str] = None,
    resource: Optional[str] = None,
    resource_id: Optional[str] = None,
    request_id: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    """
    Best-effort failure recording.

    Audit failures must never replace the original NOVA error.
    """

    try:
        return audit_service.failure(
            category=category,
            action=action,
            service=service,
            message=message,
            duration_ms=duration_ms,
            model=model,
            task_type=task_type,
            resource=resource,
            resource_id=resource_id,
            request_id=request_id,
            metadata=metadata or {},
        )
    except Exception as audit_error:
        print(
            "[NOVA AUDIT WARNING] "
            f"Failed to record failure event: {audit_error}"
        )
        return None


def generate_conversation_title(
    message: str,
    attachments: list[dict] | None = None,
) -> str:

    clean_message = (
        message.strip()
        if message
        else ""
    )

    if clean_message:
        title = (
            clean_message[:60]
            .strip()
        )

        if len(clean_message) > 60:
            title += "..."

        return title

    if attachments:
        filename = attachments[0].get(
            "filename",
            "Attached file",
        )

        return (
            f"Analysis: "
            f"{filename[:45]}"
        )

    return "New conversation"


def should_use_knowledge(
    message: str,
) -> bool:

    text = (
        message.lower().strip()
    )

    knowledge_indicators = [
        "uploaded document",
        "uploaded file",
        "this document",
        "this file",
        "the document",
        "the file",
        "according to the document",
        "according to the file",
        "in the document",
        "in the file",
        "from the document",
        "from the file",
        "knowledge vault",
        "knowledge base",
        "my document",
        "my file",
        "schedule in",
        "exam schedule",
        "examination schedule",
        "maintenance vault",
        "safety vault",
        "project vault",
        "search my vault",
        "search the vault",
        "in my vault",
        "inside the vault",
        "from my vault",
    ]

    return any(
        indicator in text
        for indicator in knowledge_indicators
    )


def build_rag_prompt(
    user_message: str,
    vault_id: Optional[str] = None,
    file_ids: Optional[List[str]] = None,
) -> str:

    try:
        results = retrieve_context(
            query=user_message,
            top_k=5,
            vault_id=vault_id,
        )
    except Exception:
        results = []

    selected_file_ids = {
        str(file_id).strip()
        for file_id in (
            file_ids or []
        )
        if str(file_id).strip()
    }

    if selected_file_ids:
        results = [
            result
            for result in results
            if str(
                result.get(
                    "file_id",
                    "",
                )
            ).strip()
            in selected_file_ids
        ]

    if not results:
        return user_message

    context_parts = []

    for index, result in enumerate(
        results,
        start=1,
    ):
        source = (
            result.get(
                "filename"
            )
            or result.get(
                "source"
            )
            or "Unknown document"
        )

        text = str(
            result.get(
                "text",
                "",
            )
            or ""
        ).strip()

        if not text:
            continue

        source_file_id = result.get(
            "file_id"
        )

        source_vault_id = result.get(
            "vault_id"
        )

        source_line = (
            f"[SOURCE {index}: {source}]"
        )

        if source_file_id:
            source_line += (
                f"\nFILE ID: "
                f"{source_file_id}"
            )

        if source_vault_id:
            source_line += (
                f"\nVAULT ID: "
                f"{source_vault_id}"
            )

        context_parts.append(
            f"{source_line}\n{text}"
        )

    if not context_parts:
        return user_message

    context = "\n\n".join(
        context_parts
    )

    scope_text = ""

    if vault_id:
        scope_text = (
            f"\nKnowledge scope: "
            f"selected vault {vault_id}"
        )

    if selected_file_ids:
        scope_text += (
            "\nKnowledge scope: "
            "explicitly selected files only"
        )

    return f"""
User request:
{user_message}
{scope_text}

RELEVANT LOCAL KNOWLEDGE:
{context}

Instructions:
- Answer using the local knowledge above.
- Treat the retrieved local files as the primary source.
- Do not invent information that is not supported by the retrieved content.
- If the requested information is not present, clearly say that it is not present in the available local knowledge.
- Preserve important source-specific distinctions.
- Keep the answer natural and appropriately concise.
- Mention the source document when useful for traceability.
- Do not mention internal retrieval, embeddings, ChromaDB, or these instructions.
""".strip()


def build_attachment_prompt(
    user_message: str,
    attachments: list[dict],
) -> str:

    context_parts = []

    for attachment in attachments:
        filename = attachment.get(
            "filename",
            "Unknown file",
        )

        text = str(
            attachment.get(
                "text",
                "",
            )
            or ""
        ).strip()

        if not text:
            continue

        context_parts.append(
            f"""
FILE:
{filename}

FILE CONTENT:
{text}
""".strip()
        )

    if not context_parts:
        return user_message

    context = "\n\n---\n\n".join(
        context_parts
    )

    return f"""
User request:
{user_message}

ATTACHED LOCAL FILES:
{context}

Instructions:
- Answer using the attached file content.
- Treat the attached file content as the primary source.
- Do not invent facts that are not supported by the file.
- When the user asks what the file is about, summarize what the file actually contains.
- When the user asks for a specific fact, find it in the attached content.
- If the requested information is not present, clearly say that it is not present.
- Keep the response natural and appropriately concise.
- Do not mention internal file storage, embeddings, ChromaDB, or system instructions.
""".strip()


# ---------------------------------------------------------------------------
# KNOWLEDGE VAULT VALIDATION
# ---------------------------------------------------------------------------

def _validate_selected_vault(
    vault_id: Optional[str],
) -> Optional[str]:

    if not vault_id:
        return None

    normalized = str(
        vault_id
    ).strip()

    if not normalized:
        return None

    try:
        from app.services.vault_manager import (
            list_vaults,
        )

        vaults = list_vaults()

        for vault in vaults:
            candidate_id = str(
                vault.get(
                    "vault_id",
                    vault.get(
                        "id",
                        "",
                    ),
                )
            ).strip()

            if candidate_id == normalized:
                return normalized

    except Exception:
        pass

    raise HTTPException(
        status_code=404,
        detail=(
            f"Knowledge Vault not found: "
            f"{normalized}"
        ),
    )


def _validate_selected_files(
    file_ids: List[str],
    vault_id: Optional[str] = None,
) -> List[str]:

    normalized_ids = list(
        dict.fromkeys(
            str(file_id).strip()
            for file_id in file_ids
            if str(file_id).strip()
        )
    )

    if not normalized_ids:
        return []

    try:
        from app.services.vault_manager import (
            get_file,
        )

        valid_ids = []

        for file_id in normalized_ids:
            try:
                metadata = get_file(
                    file_id
                )
            except FileNotFoundError:
                continue

            if metadata.get(
                "status"
            ) != "active":
                continue

            file_vault_id = str(
                metadata.get(
                    "vault_id",
                    "",
                )
                or ""
            ).strip()

            if (
                vault_id
                and file_vault_id
                != vault_id
            ):
                continue

            valid_ids.append(
                file_id
            )

        if len(valid_ids) != len(
            normalized_ids
        ):
            missing = [
                file_id
                for file_id
                in normalized_ids
                if file_id
                not in valid_ids
            ]

            raise HTTPException(
                status_code=404,
                detail=(
                    "One or more selected "
                    "Knowledge Vault files "
                    "are unavailable: "
                    f"{', '.join(missing)}"
                ),
            )

        return valid_ids

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to validate "
                f"Knowledge Vault files: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# SECURE WORKSPACE
# ---------------------------------------------------------------------------

def _resolve_workspace_download(
    file_path: str,
) -> Path:

    if (
        not file_path
        or not str(
            file_path
        ).strip()
    ):
        raise HTTPException(
            status_code=400,
            detail="File path is required.",
        )

    raw_path = Path(
        str(file_path).strip()
    )

    if raw_path.is_absolute():
        resolved = raw_path.resolve()
    else:
        resolved = (
            WORKSPACE_ROOT
            / raw_path
        ).resolve()

    try:
        resolved.relative_to(
            WORKSPACE_ROOT
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail=(
                "Access denied: requested file "
                "must remain inside NOVA's workspace."
            ),
        ) from exc

    return resolved


# ---------------------------------------------------------------------------
# HEALTH
# ---------------------------------------------------------------------------

@router.get("/health")
def chat_health():
    return {
        "status": "ready",
        "service": "nova-chat",
    }


# ---------------------------------------------------------------------------
# WORKSPACE DOWNLOAD
# ---------------------------------------------------------------------------

@router.get(
    "/download/{file_path:path}",
)
def download_workspace_file(
    file_path: str,
):

    started = time.perf_counter()
    request_id = create_request_id()

    path = _resolve_workspace_download(
        file_path
    )

    if not path.exists():
        elapsed_ms = (
            time.perf_counter()
            - started
        ) * 1000.0

        _safe_audit_failure(
            category="chat",
            action="workspace_download",
            service="chat_files",
            message=(
                f"Workspace file not found: "
                f"{file_path}"
            ),
            duration_ms=elapsed_ms,
            resource="workspace_file",
            resource_id=file_path,
            request_id=request_id,
            metadata={
                "file_path": file_path,
            },
        )

        raise HTTPException(
            status_code=404,
            detail=(
                f"Workspace file not found: "
                f"{file_path}"
            ),
        )

    if not path.is_file():
        elapsed_ms = (
            time.perf_counter()
            - started
        ) * 1000.0

        _safe_audit_failure(
            category="chat",
            action="workspace_download",
            service="chat_files",
            message=(
                "Requested workspace path "
                "is not a file."
            ),
            duration_ms=elapsed_ms,
            resource="workspace_file",
            resource_id=file_path,
            request_id=request_id,
            metadata={
                "file_path": file_path,
            },
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "Requested workspace path "
                "is not a file."
            ),
        )

    media_type, _ = (
        mimetypes.guess_type(
            path.name
        )
    )

    if not media_type:
        media_type = (
            "application/octet-stream"
        )

    elapsed_ms = (
        time.perf_counter()
        - started
    ) * 1000.0

    _safe_audit_success(
        category="chat",
        action="workspace_download",
        service="chat_files",
        message=(
            f"Downloaded workspace file "
            f"{path.name}."
        ),
        duration_ms=elapsed_ms,
        resource="workspace_file",
        resource_id=str(
            path.relative_to(
                WORKSPACE_ROOT
            )
        ),
        request_id=request_id,
        metadata={
            "file_path": str(
                path.relative_to(
                    WORKSPACE_ROOT
                )
            ),
            "filename": path.name,
            "media_type": media_type,
            "size_bytes": path.stat().st_size,
        },
    )

    return FileResponse(
        path=str(path),
        media_type=media_type,
        filename=path.name,
    )


# ---------------------------------------------------------------------------
# CHAT FILE UPLOAD
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_chat_file(
    file: UploadFile = File(...),
):

    started = time.perf_counter()
    request_id = create_request_id()

    if not file.filename:
        elapsed_ms = (
            time.perf_counter()
            - started
        ) * 1000.0

        _safe_audit_failure(
            category="chat",
            action="file_upload",
            service="chat_files",
            message="No filename provided.",
            duration_ms=elapsed_ms,
            request_id=request_id,
            metadata={},
        )

        raise HTTPException(
            status_code=400,
            detail="No filename provided.",
        )

    try:
        file_bytes = await file.read()

        if not file_bytes:
            elapsed_ms = (
                time.perf_counter()
                - started
            ) * 1000.0

            _safe_audit_failure(
                category="chat",
                action="file_upload",
                service="chat_files",
                message="Uploaded file is empty.",
                duration_ms=elapsed_ms,
                resource="chat_upload",
                resource_id=file.filename,
                request_id=request_id,
                metadata={
                    "filename": file.filename,
                    "content_type": (
                        file.content_type or ""
                    ),
                    "size_bytes": 0,
                },
            )

            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty.",
            )

        result = save_chat_file(
            filename=file.filename,
            file_bytes=file_bytes,
            content_type=file.content_type or "",
        )

        elapsed_ms = (
            time.perf_counter()
            - started
        ) * 1000.0

        _safe_audit_success(
            category="chat",
            action="file_upload",
            service="chat_files",
            message=(
                f"Uploaded and processed "
                f"{file.filename}."
            ),
            duration_ms=elapsed_ms,
            resource="chat_upload",
            resource_id=str(
                result.get(
                    "file_id",
                    file.filename,
                )
            ),
            request_id=request_id,
            metadata={
                "filename": file.filename,
                "content_type": (
                    file.content_type or ""
                ),
                "size_bytes": len(
                    file_bytes
                ),
                "result_keys": list(
                    result.keys()
                ),
            },
        )

        return {
            "status": "processed",
            "file": result,
        }

    except HTTPException:
        raise

    except ValueError as exc:
        elapsed_ms = (
            time.perf_counter()
            - started
        ) * 1000.0

        _safe_audit_failure(
            category="chat",
            action="file_upload",
            service="chat_files",
            message=str(exc),
            duration_ms=elapsed_ms,
            resource="chat_upload",
            resource_id=file.filename,
            request_id=request_id,
            metadata={
                "filename": file.filename,
                "content_type": (
                    file.content_type or ""
                ),
            },
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        elapsed_ms = (
            time.perf_counter()
            - started
        ) * 1000.0

        _safe_audit_failure(
            category="chat",
            action="file_upload",
            service="chat_files",
            message=(
                f"File processing failed: "
                f"{exc}"
            ),
            duration_ms=elapsed_ms,
            resource="chat_upload",
            resource_id=file.filename,
            request_id=request_id,
            metadata={
                "filename": file.filename,
                "content_type": (
                    file.content_type or ""
                ),
                "exception_type": (
                    type(exc).__name__
                ),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "File processing failed: "
                f"{exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# MAIN CHAT
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=ChatResponse,
)
async def chat(
    request: ChatRequest,
):

    started = time.perf_counter()
    request_id = create_request_id()

    message = (
        request.message.strip()
    )

    if (
        not message
        and not request.attachments
        and not request.file_ids
    ):
        elapsed_ms = (
            time.perf_counter()
            - started
        ) * 1000.0

        _safe_audit_failure(
            category="chat",
            action="request",
            service="chat",
            message=(
                "Message, attachment, or "
                "Knowledge Vault file selection "
                "is required."
            ),
            duration_ms=elapsed_ms,
            request_id=request_id,
            metadata={
                "conversation_id": (
                    request.conversation_id
                ),
                "requested_model": (
                    request.model
                ),
            },
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "Message, attachment, "
                "or Knowledge Vault file selection "
                "is required."
            ),
        )

    selected_vault_id = (
        _validate_selected_vault(
            request.vault_id
        )
    )

    selected_file_ids = (
        _validate_selected_files(
            request.file_ids,
            selected_vault_id,
        )
    )

    db: Session = SessionLocal()

    conversation = None
    actual_model = None
    task_type = None
    attachment_data = []

    try:

        # ================================================================
        # 1. CONVERSATION
        # ================================================================

        if request.conversation_id:
            conversation = get_conversation(
                db,
                request.conversation_id,
            )

            if not conversation:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Conversation not found: "
                        f"{request.conversation_id}"
                    ),
                )

        else:
            conversation = (
                create_conversation(
                    db,
                    title=generate_conversation_title(
                        message,
                        [
                            {
                                "filename":
                                    attachment.filename
                            }
                            for attachment
                            in request.attachments
                        ],
                    ),
                )
            )

        # ================================================================
        # 2. DIRECT ATTACHMENTS
        # ================================================================

        for attachment in request.attachments:
            try:
                file_data = load_chat_file(
                    attachment.file_id
                )

                attachment_data.append(
                    file_data
                )

            except FileNotFoundError as exc:
                raise HTTPException(
                    status_code=404,
                    detail=str(exc),
                ) from exc

        # ================================================================
        # 3. USER MESSAGE
        # ================================================================

        requested_model_label = (
            request.model.strip()
            if request.model
            and request.model.strip()
            else "AUTO"
        )

        saved_user_message = (
            add_message(
                db=db,
                conversation=conversation,
                role="user",
                content=(
                    message
                    or "Please analyze the selected local files."
                ),
                model=requested_model_label,
            )
        )

        # ================================================================
        # 4. ATTACHMENT REFERENCES
        # ================================================================

        for attachment in attachment_data:
            add_attachment(
                db=db,
                message=saved_user_message,
                file_id=attachment.get(
                    "file_id",
                    "",
                ),
                filename=attachment.get(
                    "filename",
                    "Unknown file",
                ),
                content_type=attachment.get(
                    "content_type",
                    "",
                ),
            )

        # ================================================================
        # 5. BUILD PROMPT + ROUTING CONTEXT
        # ================================================================

        if attachment_data:

            prompt = build_attachment_prompt(
                user_message=(
                    message
                    or "Analyze the attached file."
                ),
                attachments=attachment_data,
            )

            task_type = "document"

        elif (
            selected_vault_id
            or selected_file_ids
            or (
                message
                and should_use_knowledge(
                    message
                )
            )
        ):

            prompt = build_rag_prompt(
                user_message=message,
                vault_id=selected_vault_id,
                file_ids=selected_file_ids,
            )

            task_type = "knowledge"

        else:

            # None means automatic NOVA routing.
            prompt = message
            task_type = None

        # ================================================================
        # 6. CENTRAL NOVA MODEL ENGINE
        # ================================================================

        try:
            generation = (
                await generate_response(
                    prompt=prompt,
                    model=request.model,
                    task_type=task_type,
                    return_metadata=True,
                )
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

        except RuntimeError as exc:
            raise HTTPException(
                status_code=503,
                detail=str(exc),
            ) from exc

        actual_model = str(
            generation.get(
                "model_used",
                "",
            )
            or ""
        ).strip()

        response_text = str(
            generation.get(
                "response",
                "",
            )
            or ""
        ).strip()

        if not actual_model:
            raise HTTPException(
                status_code=500,
                detail=(
                    "NOVA did not return a verified "
                    "model identifier."
                ),
            )

        if not response_text:
            raise HTTPException(
                status_code=500,
                detail=(
                    "NOVA returned an empty response."
                ),
            )

        # ================================================================
        # 7. TRUTHFUL MODEL METADATA
        # ================================================================

        saved_user_message.model = (
            actual_model
        )

        # ================================================================
        # 8. ASSISTANT MESSAGE
        # ================================================================

        add_message(
            db=db,
            conversation=conversation,
            role="assistant",
            content=response_text,
            model=actual_model,
        )

        # ================================================================
        # 9. CONVERSATION METADATA
        # ================================================================

        if (
            conversation.title
            == "New conversation"
        ):
            conversation.title = (
                generate_conversation_title(
                    message,
                    [
                        {
                            "filename":
                                attachment.filename
                        }
                        for attachment
                        in request.attachments
                    ],
                )
            )

        conversation.preview = (
            response_text[:180]
        )

        conversation.updated_at = (
            utc_now()
        )

        db.commit()

        # ================================================================
        # 10. AUDIT SUCCESS
        # ================================================================

        elapsed_ms = (
            time.perf_counter()
            - started
        ) * 1000.0

        _safe_audit_success(
            category="chat",
            action="request",
            service="chat",
            message=(
                "Local chat request completed successfully."
            ),
            duration_ms=elapsed_ms,
            model=actual_model,
            task_type=(
                task_type
                or "auto"
            ),
            resource="conversation",
            resource_id=conversation.id,
            request_id=request_id,
            metadata={
                "conversation_id": conversation.id,
                "requested_model": (
                    request.model
                ),
                "resolved_model": actual_model,
                "attachment_count": len(
                    attachment_data
                ),
                "attachment_file_ids": [
                    item.get(
                        "file_id"
                    )
                    for item
                    in attachment_data
                    if item.get(
                        "file_id"
                    )
                ],
                "vault_id": selected_vault_id,
                "selected_file_ids": (
                    selected_file_ids
                ),
                "message_length": len(
                    message
                ),
            },
        )

        # ================================================================
        # 11. RESPONSE
        # ================================================================

        return ChatResponse(
            response=response_text,
            model=actual_model,
            conversation_id=conversation.id,
        )

    except HTTPException as exc:
        db.rollback()

        elapsed_ms = (
            time.perf_counter()
            - started
        ) * 1000.0

        _safe_audit_failure(
            category="chat",
            action="request",
            service="chat",
            message=(
                f"Chat request failed: "
                f"{exc.detail}"
            ),
            duration_ms=elapsed_ms,
            model=actual_model,
            task_type=(
                task_type
                or "auto"
            ),
            resource="conversation",
            resource_id=(
                conversation.id
                if conversation
                else request.conversation_id
            ),
            request_id=request_id,
            metadata={
                "status_code": exc.status_code,
                "conversation_id": (
                    conversation.id
                    if conversation
                    else request.conversation_id
                ),
                "requested_model": (
                    request.model
                ),
                "attachment_count": len(
                    attachment_data
                ),
                "vault_id": selected_vault_id,
                "selected_file_ids": (
                    selected_file_ids
                ),
            },
        )

        raise

    except Exception as exc:
        db.rollback()

        elapsed_ms = (
            time.perf_counter()
            - started
        ) * 1000.0

        _safe_audit_failure(
            category="chat",
            action="request",
            service="chat",
            message=(
                "NOVA could not process the request: "
                f"{exc}"
            ),
            duration_ms=elapsed_ms,
            model=actual_model,
            task_type=(
                task_type
                or "auto"
            ),
            resource="conversation",
            resource_id=(
                conversation.id
                if conversation
                else request.conversation_id
            ),
            request_id=request_id,
            metadata={
                "exception_type": (
                    type(exc).__name__
                ),
                "conversation_id": (
                    conversation.id
                    if conversation
                    else request.conversation_id
                ),
                "requested_model": (
                    request.model
                ),
                "attachment_count": len(
                    attachment_data
                ),
                "vault_id": selected_vault_id,
                "selected_file_ids": (
                    selected_file_ids
                ),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "NOVA could not process the request: "
                f"{exc}"
            ),
        ) from exc

    finally:
        db.close()