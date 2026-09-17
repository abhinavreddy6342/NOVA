from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import mimetypes

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.ai_config import DEFAULT_MODEL
from app.core.database import SessionLocal
from app.knowledge.rag import retrieve_context
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

BACKEND_ROOT = Path(__file__).resolve().parents[2]

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
    model: str = DEFAULT_MODEL

    conversation_id: Optional[str] = None

    attachments: List[
        AttachmentReference
    ] = Field(
        default_factory=list
    )

    # Optional Knowledge Vault context.
    # Existing requests remain fully compatible because
    # both fields are optional.
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


def generate_conversation_title(
    message: str,
    attachments: list[dict] | None = None,
) -> str:
    """
    Generate a deterministic conversation title
    without calling the LLM.
    """

    clean_message = (
        message.strip()
        if message
        else ""
    )

    if clean_message:
        title = clean_message[:60].strip()

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
    text = message.lower().strip()

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
    """
    Retrieve local Knowledge Vault context.

    vault_id:
        Restricts retrieval to one real vault.

    file_ids:
        Restricts retrieved sources to explicitly selected files.

    The vector layer remains the source for semantic retrieval;
    this function only prepares grounded context for the LLM.
    """

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
        source = result.get(
            "filename"
        ) or result.get(
            "source"
        ) or "Unknown document"

        text = result.get(
            "text",
            "",
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

        text = attachment.get(
            "text",
            "",
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
# KNOWLEDGE VAULT HELPERS
# ---------------------------------------------------------------------------

def _validate_selected_vault(
    vault_id: Optional[str],
) -> Optional[str]:
    """
    Validate an explicitly selected vault against the real
    Knowledge Vault registry.

    Returns the normalized vault ID or None.
    """

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
    """
    Validate explicitly selected registry file IDs.

    Only active registered files are accepted.
    When a vault is selected, files must belong to that vault.
    """

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

            file_vault_id = (
                str(
                    metadata.get(
                        "vault_id",
                        "",
                    )
                    or ""
                ).strip()
            )

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
                for file_id in normalized_ids
                if file_id
                not in valid_ids
            ]

            raise HTTPException(
                status_code=404,
                detail=(
                    "One or more selected "
                    f"Knowledge Vault files "
                    f"are unavailable: "
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
# SECURE WORKSPACE PATH RESOLUTION
# ---------------------------------------------------------------------------

def _resolve_workspace_download(
    file_path: str,
) -> Path:
    """
    Resolve a requested workspace file while preventing
    path traversal outside NOVA's workspace.
    """

    if (
        not file_path
        or not str(file_path).strip()
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
            WORKSPACE_ROOT / raw_path
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
# FILE DOWNLOAD
# ---------------------------------------------------------------------------

@router.get(
    "/download/{file_path:path}",
)
def download_workspace_file(
    file_path: str,
):
    """
    Download a generated or existing file from
    NOVA's controlled workspace.

    Example:

    /api/chat/download/output/agent_test_report.docx

    Only files inside app/workspace are accessible.
    """

    path = _resolve_workspace_download(
        file_path
    )

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Workspace file not found: "
                f"{file_path}"
            ),
        )

    if not path.is_file():
        raise HTTPException(
            status_code=400,
            detail=(
                "Requested workspace path "
                "is not a file."
            ),
        )

    media_type, _ = mimetypes.guess_type(
        path.name
    )

    if not media_type:
        media_type = (
            "application/octet-stream"
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
    """
    Upload and locally process one file for chat.

    Chat uploads remain temporary local files until
    the user explicitly adds them to a Knowledge Vault.
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided.",
        )

    try:
        file_bytes = await file.read()

        if not file_bytes:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty.",
            )

        result = save_chat_file(
            filename=file.filename,
            file_bytes=file_bytes,
            content_type=file.content_type or "",
        )

        return {
            "status": "processed",
            "file": result,
        }

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
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
    """
    Main NOVA chat endpoint.

    Supports:
    - normal text chat
    - Knowledge Vault retrieval
    - selected Knowledge Vault files
    - direct file attachments
    - persistent conversations
    - persistent messages
    """

    message = request.message.strip()

    if (
        not message
        and not request.attachments
        and not request.file_ids
    ):
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

    try:
        # =========================================
        # 1. GET OR CREATE CONVERSATION
        # =========================================

        conversation = None

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
            conversation = create_conversation(
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

        # =========================================
        # 2. LOAD DIRECT CHAT ATTACHMENTS
        # =========================================

        attachment_data = []

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

        # =========================================
        # 3. SAVE USER MESSAGE
        # =========================================

        saved_user_message = add_message(
            db=db,
            conversation=conversation,
            role="user",
            content=(
                message
                or "Please analyze the selected local files."
            ),
            model=request.model,
        )

        # =========================================
        # 4. SAVE CHAT ATTACHMENT REFERENCES
        # =========================================

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

        # =========================================
        # 5. BUILD AI PROMPT
        # =========================================

        if attachment_data:
            prompt = build_attachment_prompt(
                user_message=(
                    message
                    or "Analyze the attached file."
                ),
                attachments=attachment_data,
            )

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

        else:
            prompt = message

        # =========================================
        # 6. GENERATE NOVA RESPONSE
        # =========================================

        response = await generate_response(
            prompt=prompt,
            model=request.model,
        )

        response_text = str(
            response
        ).strip()

        if not response_text:
            raise HTTPException(
                status_code=500,
                detail=(
                    "NOVA returned an empty response."
                ),
            )

        # =========================================
        # 7. SAVE NOVA RESPONSE
        # =========================================

        add_message(
            db=db,
            conversation=conversation,
            role="assistant",
            content=response_text,
            model=request.model,
        )

        # =========================================
        # 8. UPDATE CONVERSATION METADATA
        # =========================================

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

        # =========================================
        # 9. RETURN RESPONSE
        # =========================================

        return ChatResponse(
            response=response_text,
            model=request.model,
            conversation_id=conversation.id,
        )

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "NOVA could not process the request: "
                f"{exc}"
            ),
        ) from exc

    finally:
        db.close()