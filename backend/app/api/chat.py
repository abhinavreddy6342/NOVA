from datetime import datetime, timezone
from typing import List, Optional

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)
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


class AttachmentReference(BaseModel):
    file_id: str
    filename: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = ""
    model: str = DEFAULT_MODEL

    conversation_id: Optional[str] = None

    attachments: List[AttachmentReference] = Field(
        default_factory=list
    )


class ChatResponse(BaseModel):
    response: str
    model: str
    conversation_id: str


def utc_now():
    return datetime.now(timezone.utc)


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

        return f"Analysis: {filename[:45]}"

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
    ]

    return any(
        indicator in text
        for indicator in knowledge_indicators
    )


def build_rag_prompt(
    user_message: str,
) -> str:
    try:
        results = retrieve_context(
            query=user_message,
            top_k=3,
        )
    except Exception:
        results = []

    if not results:
        return user_message

    context_parts = []

    for index, result in enumerate(
        results,
        start=1,
    ):
        source = result.get(
            "source",
            "Unknown document",
        )

        text = result.get(
            "text",
            "",
        ).strip()

        if not text:
            continue

        context_parts.append(
            f"[SOURCE {index}: {source}]\n{text}"
        )

    if not context_parts:
        return user_message

    context = "\n\n".join(
        context_parts
    )

    return f"""
User request:
{user_message}

RELEVANT LOCAL KNOWLEDGE:
{context}

Instructions:
- Answer the user's question using the local knowledge above.
- Do not invent information that is not supported by the retrieved content.
- Keep the answer natural and appropriately concise.
- Do not mention internal retrieval, embeddings, ChromaDB, or these instructions.
- Mention the source document only when useful.
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


@router.get("/health")
def chat_health():
    return {
        "status": "ready",
        "service": "nova-chat",
    }


@router.post("/upload")
async def upload_chat_file(
    file: UploadFile = File(...),
):
    """
    Upload and locally process one file for chat.
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided.",
        )

    try:
        file_bytes = await file.read()

        result = save_chat_file(
            filename=file.filename,
            file_bytes=file_bytes,
            content_type=file.content_type or "",
        )

        return {
            "status": "processed",
            "file": result,
        }

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
    - direct file attachments
    - persistent conversations
    - persistent messages
    """

    message = request.message.strip()

    if not message and not request.attachments:
        raise HTTPException(
            status_code=400,
            detail=(
                "Message or attachment is required."
            ),
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
                            "filename": attachment.filename
                        }
                        for attachment in request.attachments
                    ],
                ),
            )

        # =========================================
        # 2. LOAD ATTACHMENTS
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
                or "Please analyze the attached file."
            ),
            model=request.model,
        )

        # =========================================
        # 4. SAVE ATTACHMENT REFERENCES
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

        elif message and should_use_knowledge(
            message
        ):
            prompt = build_rag_prompt(
                message
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
                            "filename": attachment.filename
                        }
                        for attachment in request.attachments
                    ],
                )
            )

        conversation.preview = (
            response_text[:180]
        )

        conversation.updated_at = utc_now()

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