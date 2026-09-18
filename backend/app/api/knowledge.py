from __future__ import annotations

import inspect
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.knowledge.rag import index_document
from app.services.audit.service import (
    audit_service,
    create_request_id,
)
from app.services.chat_files import (
    MAX_UPLOAD_SIZE,
    save_chat_file,
)
from app.services.knowledge.extractor import (
    extract_document,
)
from app.services.vault_manager import (
    add_existing_file_to_vault,
    create_vault,
    delete_file,
    delete_vault,
    get_file,
    get_stats,
    list_bin,
    list_recent_uploads,
    list_vault_files,
    list_vaults,
    move_file,
    permanent_delete_file,
    permanent_delete_vault,
    register_chat_file,
    reindex_file,
    rename_file,
    rename_vault,
    restore_file,
    restore_vault,
    resolve_file_path,
)


router = APIRouter(
    prefix="/api/knowledge",
    tags=["Knowledge Vault"],
)


# ---------------------------------------------------------------------------
# REQUEST MODELS
# ---------------------------------------------------------------------------

class VaultCreateRequest(BaseModel):
    name: str


class VaultRenameRequest(BaseModel):
    name: str


class FileRenameRequest(BaseModel):
    name: str


class FileMoveRequest(BaseModel):
    vault_id: str


class RestoreRequest(BaseModel):
    item_type: str
    item_id: str


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".docx",
    ".csv",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}


# ---------------------------------------------------------------------------
# AUDIT
# ---------------------------------------------------------------------------

def _safe_audit(
    method_name: str,
    *,
    category: str = "knowledge",
    action: str,
    service: str = "knowledge",
    status: str = "SUCCESS",
    message: str = "",
    request_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    model: Optional[str] = None,
    task_type: Optional[str] = None,
    duration_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Best-effort audit adapter.

    The audit subsystem must never become a dependency that can break
    Knowledge Vault functionality. We also filter keyword arguments against
    the actual audit method signature so this module remains compatible with
    the authoritative audit service implementation.
    """
    try:
        method = getattr(
            audit_service,
            method_name,
            None,
        )

        if method is None:
            return

        payload = {
            "category": category,
            "action": action,
            "service": service,
            "status": status,
            "message": message,
            "request_id": request_id,
            "resource_id": resource_id,
            "model": model,
            "task_type": task_type,
            "duration_ms": duration_ms,
            "metadata": metadata or {},
        }

        try:
            signature = inspect.signature(
                method
            )

            parameters = signature.parameters

            has_var_kwargs = any(
                parameter.kind
                == inspect.Parameter.VAR_KEYWORD
                for parameter in parameters.values()
            )

            if not has_var_kwargs:
                payload = {
                    key: value
                    for key, value in payload.items()
                    if key in parameters
                }

        except Exception:
            pass

        method(
            **payload
        )

    except Exception as exc:
        print(
            "[NOVA AUDIT WARNING] "
            f"Knowledge audit event failed: {exc}"
        )


def _audit_success(
    *,
    action: str,
    message: str,
    request_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    _safe_audit(
        "success",
        action=action,
        status="SUCCESS",
        message=message,
        request_id=request_id,
        resource_id=resource_id,
        duration_ms=duration_ms,
        metadata=metadata,
    )


def _audit_failure(
    *,
    action: str,
    message: str,
    request_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    _safe_audit(
        "failure",
        action=action,
        status="FAILED",
        message=message,
        request_id=request_id,
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
# HELPERS
# ---------------------------------------------------------------------------

def _normalize_id(
    value: str,
    label: str,
) -> str:
    normalized = str(
        value or ""
    ).strip()

    if not normalized:
        raise HTTPException(
            status_code=400,
            detail=f"{label} is required.",
        )

    if (
        "/" in normalized
        or "\\" in normalized
        or normalized in {".", ".."}
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {label}.",
        )

    return normalized


def _validate_filename(
    filename: str,
) -> str:
    value = str(
        filename or ""
    ).strip()

    if not value:
        raise HTTPException(
            status_code=400,
            detail="No filename provided.",
        )

    if (
        "/" in value
        or "\\" in value
        or value in {".", ".."}
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename.",
        )

    value = Path(
        value
    ).name.strip()

    extension = Path(
        value
    ).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. "
                "Use PDF, DOCX, TXT, CSV, XLSX, "
                "PNG, JPG, JPEG, or WEBP."
            ),
        )

    return value


def _validate_upload_size(
    data: bytes,
) -> None:
    if not data:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=(
                "File is too large. "
                "Maximum size is 20 MB."
            ),
        )


def _vault_exists(
    vault_id: str,
) -> bool:
    normalized_id = str(
        vault_id or ""
    ).strip()

    return any(
        str(
            vault.get(
                "vault_id",
                "",
            )
        ).strip()
        == normalized_id
        for vault in list_vaults()
    )


def _ensure_unique_vault_filename(
    vault_id: str,
    filename: str,
    exclude_file_id: str = "",
) -> None:
    normalized_name = str(
        filename or ""
    ).strip().casefold()

    normalized_exclude_id = str(
        exclude_file_id or ""
    ).strip()

    for item in list_vault_files(
        vault_id
    ):
        current_file_id = str(
            item.get(
                "file_id",
                "",
            )
        ).strip()

        current_filename = str(
            item.get(
                "filename",
                "",
            )
        ).strip().casefold()

        if (
            normalized_exclude_id
            and current_file_id
            == normalized_exclude_id
        ):
            continue

        if (
            normalized_name
            and current_filename
            == normalized_name
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    f'A file named "{filename}" '
                    "already exists in this vault."
                ),
            )


def _extract_index_result(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "characters": int(
            result.get(
                "characters",
                0,
            )
            or 0
        ),
        "chunks": int(
            result.get(
                "chunks",
                0,
            )
            or 0
        ),
        "used_ocr": bool(
            result.get(
                "used_ocr",
                False,
            )
        ),
        "pages": int(
            result.get(
                "pages",
                0,
            )
            or 0
        ),
        "indexed": bool(
            result.get(
                "indexed",
                False,
            )
        ),
        "replaced": bool(
            result.get(
                "replaced",
                False,
            )
        ),
    }


def _mark_index_failed(
    file_id: str,
    characters: int = 0,
) -> None:
    try:
        reindex_file(
            file_id=file_id,
            characters=characters,
            chunks=0,
            indexed=False,
        )
    except Exception:
        pass


def _index_and_register_file(
    file_id: str,
    vault_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the real extraction + vector indexing pipeline and then
    synchronize the authoritative registry.

    Chroma remains the search index only. The registry remains the
    file-management source of truth.
    """

    started_at = time.perf_counter()

    normalized_file_id = _normalize_id(
        file_id,
        "file_id",
    )

    normalized_vault_id = (
        str(
            vault_id or ""
        ).strip()
        or None
    )

    if normalized_vault_id:
        normalized_vault_id = _normalize_id(
            normalized_vault_id,
            "vault_id",
        )

        if not _vault_exists(
            normalized_vault_id
        ):
            _audit_failure(
                action="file_index",
                message=(
                    "Knowledge file indexing failed because "
                    "the target vault was not found."
                ),
                request_id=request_id,
                resource_id=normalized_file_id,
                duration_ms=_duration_ms(
                    started_at
                ),
                metadata={
                    "vault_id": normalized_vault_id,
                    "reason": "vault_not_found",
                },
            )

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Vault not found: "
                    f"{normalized_vault_id}"
                ),
            )

    path = resolve_file_path(
        normalized_file_id,
    )

    try:
        result = index_document(
            str(path),
            file_id=normalized_file_id,
            vault_id=normalized_vault_id,
        )
    except Exception as exc:
        current = get_file(
            normalized_file_id,
        )

        _mark_index_failed(
            normalized_file_id,
            characters=int(
                current.get(
                    "characters",
                    0,
                )
                or 0
            ),
        )

        _audit_failure(
            action="file_index",
            message=(
                "Knowledge file extraction or vector "
                "indexing failed."
            ),
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "vault_id": normalized_vault_id,
                "filename": current.get(
                    "filename"
                ),
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise

    updated = reindex_file(
        file_id=normalized_file_id,
        characters=result.get(
            "characters",
            0,
        ),
        chunks=result.get(
            "chunks",
            0,
        ),
        indexed=bool(
            result.get(
                "indexed",
                True,
            )
        ),
    )

    index_summary = _extract_index_result(
        result
    )

    _audit_success(
        action="file_index",
        message=(
            "Knowledge file was extracted and "
            "indexed successfully."
        ),
        request_id=request_id,
        resource_id=normalized_file_id,
        duration_ms=_duration_ms(
            started_at
        ),
        metadata={
            "vault_id": normalized_vault_id,
            "filename": updated.get(
                "filename"
            )
            if isinstance(
                updated,
                dict,
            )
            else None,
            **index_summary,
        },
    )

    return {
        "file": updated,
        "index": index_summary,
    }


def _index_unassigned_file(
    file_id: str,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compatibility pipeline for the original
    POST /api/knowledge/upload endpoint.

    These files remain real local files without being assigned to a
    user-created vault.
    """

    return _index_and_register_file(
        file_id=file_id,
        vault_id=None,
        request_id=request_id,
    )


# ---------------------------------------------------------------------------
# HEALTH
# ---------------------------------------------------------------------------

@router.get("/health")
def knowledge_health() -> Dict[str, Any]:
    try:
        stats = get_stats()

        return {
            "status": "ready",
            "service": "nova-knowledge",
            "vaults": stats.get(
                "vaults",
                0,
            ),
            "files": stats.get(
                "files",
                0,
            ),
            "indexed_files": stats.get(
                "indexed_files",
                0,
            ),
            "chunks": stats.get(
                "total_chunks",
                stats.get(
                    "chunks",
                    0,
                ),
            ),
            "bin_items": stats.get(
                "bin_items",
                0,
            ),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Knowledge health check failed: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# STATS
# ---------------------------------------------------------------------------

@router.get("/stats")
def knowledge_stats() -> Dict[str, Any]:
    try:
        return get_stats()

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Knowledge statistics failed: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# VAULT LIST
# ---------------------------------------------------------------------------

@router.get("/vaults")
def get_vaults() -> Dict[str, Any]:
    try:
        vaults = list_vaults()

        return {
            "vaults": vaults,
            "count": len(vaults),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to load vaults: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# CREATE VAULT
# ---------------------------------------------------------------------------

@router.post("/vaults")
def create_new_vault(
    request: VaultCreateRequest,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    request_id = create_request_id()

    try:
        vault = create_vault(
            request.name,
        )

        vault_id = (
            str(
                vault.get(
                    "vault_id",
                    "",
                )
            ).strip()
            or None
        )

        _audit_success(
            action="vault_create",
            message=(
                "Knowledge Vault created successfully."
            ),
            request_id=request_id,
            resource_id=vault_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "vault_name": vault.get(
                    "name"
                ),
            },
        )

        return {
            "status": "created",
            "vault": vault,
        }

    except ValueError as exc:
        _audit_failure(
            action="vault_create",
            message="Knowledge Vault creation was rejected.",
            request_id=request_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "vault_name": request.name,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        _audit_failure(
            action="vault_create",
            message="Knowledge Vault creation failed.",
            request_id=request_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "vault_name": request.name,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Vault creation failed: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# RENAME VAULT
# ---------------------------------------------------------------------------

@router.patch("/vaults/{vault_id}")
def rename_existing_vault(
    vault_id: str,
    request: VaultRenameRequest,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    request_id = create_request_id()

    normalized_vault_id = _normalize_id(
        vault_id,
        "vault_id",
    )

    try:
        vault = rename_vault(
            normalized_vault_id,
            request.name,
        )

        _audit_success(
            action="vault_rename",
            message=(
                "Knowledge Vault renamed successfully."
            ),
            request_id=request_id,
            resource_id=normalized_vault_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "new_name": request.name,
            },
        )

        return {
            "status": "updated",
            "vault": vault,
        }

    except FileNotFoundError as exc:
        _audit_failure(
            action="vault_rename",
            message="Knowledge Vault rename failed because the vault was not found.",
            request_id=request_id,
            resource_id=normalized_vault_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "new_name": request.name,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        _audit_failure(
            action="vault_rename",
            message="Knowledge Vault rename was rejected.",
            request_id=request_id,
            resource_id=normalized_vault_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "new_name": request.name,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        _audit_failure(
            action="vault_rename",
            message="Knowledge Vault rename failed.",
            request_id=request_id,
            resource_id=normalized_vault_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "new_name": request.name,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Vault rename failed: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# DELETE VAULT → BIN
# ---------------------------------------------------------------------------

@router.delete("/vaults/{vault_id}")
def trash_vault(
    vault_id: str,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    request_id = create_request_id()

    normalized_vault_id = _normalize_id(
        vault_id,
        "vault_id",
    )

    try:
        result = delete_vault(
            normalized_vault_id,
        )

        _audit_success(
            action="vault_delete",
            message=(
                "Knowledge Vault moved to the recovery bin."
            ),
            request_id=request_id,
            resource_id=normalized_vault_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "delete_mode": "soft_delete",
            },
        )

        return {
            "status": "trashed",
            **result,
        }

    except FileNotFoundError as exc:
        _audit_failure(
            action="vault_delete",
            message="Knowledge Vault deletion failed because the vault was not found.",
            request_id=request_id,
            resource_id=normalized_vault_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "delete_mode": "soft_delete",
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        _audit_failure(
            action="vault_delete",
            message="Knowledge Vault deletion failed.",
            request_id=request_id,
            resource_id=normalized_vault_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "delete_mode": "soft_delete",
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Vault deletion failed: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# VAULT FILES
# ---------------------------------------------------------------------------

@router.get("/vaults/{vault_id}/files")
def get_vault_files(
    vault_id: str,
) -> Dict[str, Any]:
    normalized_vault_id = _normalize_id(
        vault_id,
        "vault_id",
    )

    try:
        if not _vault_exists(
            normalized_vault_id
        ):
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Vault not found: "
                    f"{normalized_vault_id}"
                ),
            )

        files = list_vault_files(
            normalized_vault_id,
        )

        return {
            "vault_id": normalized_vault_id,
            "files": files,
            "count": len(files),
        }

    except HTTPException:
        raise

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to load vault files: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# LEGACY / EXISTING KNOWLEDGE UPLOAD
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_knowledge_file(
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    """
    Preserve the original Knowledge Vault upload API.

    This creates a real local file, registers it centrally,
    and indexes it without automatically assigning it to a
    user-created vault.
    """

    started_at = time.perf_counter()
    request_id = create_request_id()

    filename = _validate_filename(
        file.filename or ""
    )

    try:
        data = await file.read()

        _validate_upload_size(
            data
        )

        saved = save_chat_file(
            filename=filename,
            file_bytes=data,
            content_type=file.content_type or "",
        )

        file_id = str(
            saved.get(
                "file_id",
                "",
            )
        ).strip()

        if not file_id:
            raise RuntimeError(
                "Local file storage did not return a file ID."
            )

        registered = register_chat_file(
            file_id=file_id,
            vault_id="",
        )

        try:
            result = _index_unassigned_file(
                file_id,
                request_id=request_id,
            )

            _audit_success(
                action="file_upload",
                message=(
                    "Knowledge file uploaded, registered, "
                    "and indexed successfully."
                ),
                request_id=request_id,
                resource_id=file_id,
                duration_ms=_duration_ms(
                    started_at
                ),
                metadata={
                    "filename": filename,
                    "content_type": (
                        file.content_type or ""
                    ),
                    "size_bytes": len(data),
                    "vault_id": None,
                    "indexed": result[
                        "index"
                    ].get(
                        "indexed",
                        False,
                    ),
                    "chunks": result[
                        "index"
                    ].get(
                        "chunks",
                        0,
                    ),
                    "characters": result[
                        "index"
                    ].get(
                        "characters",
                        0,
                    ),
                    "used_ocr": result[
                        "index"
                    ].get(
                        "used_ocr",
                        False,
                    ),
                },
            )

            return {
                "status": "indexed",
                "file": result["file"],
                "index": result["index"],
            }

        except Exception:
            _mark_index_failed(
                file_id,
                characters=int(
                    registered.get(
                        "characters",
                        0,
                    )
                    or 0
                ),
            )
            raise

    except HTTPException as exc:
        _audit_failure(
            action="file_upload",
            message="Knowledge file upload was rejected.",
            request_id=request_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "filename": filename,
                "status_code": exc.status_code,
                "error": str(
                    exc.detail
                ),
            },
        )

        raise

    except FileNotFoundError as exc:
        _audit_failure(
            action="file_upload",
            message="Knowledge file upload failed because a local source file was not found.",
            request_id=request_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "filename": filename,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        _audit_failure(
            action="file_upload",
            message="Knowledge file upload validation failed.",
            request_id=request_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "filename": filename,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        _audit_failure(
            action="file_upload",
            message="Knowledge file upload failed.",
            request_id=request_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "filename": filename,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Knowledge upload failed: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# UPLOAD DIRECTLY INTO VAULT
# ---------------------------------------------------------------------------

@router.post("/vaults/{vault_id}/files/upload")
async def upload_into_vault(
    vault_id: str,
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    request_id = create_request_id()

    normalized_vault_id = _normalize_id(
        vault_id,
        "vault_id",
    )

    filename = _validate_filename(
        file.filename or ""
    )

    try:
        if not _vault_exists(
            normalized_vault_id
        ):
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Vault not found: "
                    f"{normalized_vault_id}"
                ),
            )

        _ensure_unique_vault_filename(
            normalized_vault_id,
            filename,
        )

        data = await file.read()

        _validate_upload_size(
            data
        )

        saved = save_chat_file(
            filename=filename,
            file_bytes=data,
            content_type=file.content_type or "",
        )

        file_id = str(
            saved.get(
                "file_id",
                "",
            )
        ).strip()

        if not file_id:
            raise RuntimeError(
                "Local file storage did not return a file ID."
            )

        registered = register_chat_file(
            file_id=file_id,
            vault_id=normalized_vault_id,
        )

        try:
            indexed = _index_and_register_file(
                file_id=file_id,
                vault_id=normalized_vault_id,
                request_id=request_id,
            )

            _audit_success(
                action="file_upload",
                message=(
                    "Knowledge file uploaded directly into "
                    "the vault and indexed successfully."
                ),
                request_id=request_id,
                resource_id=file_id,
                duration_ms=_duration_ms(
                    started_at
                ),
                metadata={
                    "filename": filename,
                    "content_type": (
                        file.content_type or ""
                    ),
                    "size_bytes": len(data),
                    "vault_id": normalized_vault_id,
                    "indexed": indexed[
                        "index"
                    ].get(
                        "indexed",
                        False,
                    ),
                    "chunks": indexed[
                        "index"
                    ].get(
                        "chunks",
                        0,
                    ),
                    "characters": indexed[
                        "index"
                    ].get(
                        "characters",
                        0,
                    ),
                    "used_ocr": indexed[
                        "index"
                    ].get(
                        "used_ocr",
                        False,
                    ),
                },
            )

            return {
                "status": "indexed",
                "file": indexed["file"],
                "index": indexed["index"],
            }

        except FileNotFoundError:
            _mark_index_failed(
                file_id,
                characters=int(
                    registered.get(
                        "characters",
                        0,
                    )
                    or 0
                ),
            )
            raise

        except Exception:
            _mark_index_failed(
                file_id,
                characters=int(
                    registered.get(
                        "characters",
                        0,
                    )
                    or 0
                ),
            )
            raise

    except HTTPException as exc:
        _audit_failure(
            action="file_upload",
            message="Vault file upload was rejected.",
            request_id=request_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "filename": filename,
                "vault_id": normalized_vault_id,
                "status_code": exc.status_code,
                "error": str(
                    exc.detail
                ),
            },
        )

        raise

    except FileNotFoundError as exc:
        _audit_failure(
            action="file_upload",
            message="Vault file upload failed because a local source file was not found.",
            request_id=request_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "filename": filename,
                "vault_id": normalized_vault_id,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        _audit_failure(
            action="file_upload",
            message="Vault file upload validation failed.",
            request_id=request_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "filename": filename,
                "vault_id": normalized_vault_id,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        _audit_failure(
            action="file_upload",
            message="Vault file upload failed.",
            request_id=request_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "filename": filename,
                "vault_id": normalized_vault_id,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Vault upload failed: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# ADD EXISTING CHAT UPLOAD TO VAULT
# ---------------------------------------------------------------------------

@router.post(
    "/vaults/{vault_id}/files/{file_id}/add"
)
def add_chat_file_to_vault(
    vault_id: str,
    file_id: str,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    request_id = create_request_id()

    normalized_vault_id = _normalize_id(
        vault_id,
        "vault_id",
    )

    normalized_file_id = _normalize_id(
        file_id,
        "file_id",
    )

    try:
        if not _vault_exists(
            normalized_vault_id
        ):
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Vault not found: "
                    f"{normalized_vault_id}"
                ),
            )

        existing = get_file(
            normalized_file_id
        )

        filename = str(
            existing.get(
                "filename",
                "",
            )
        ).strip()

        if filename:
            _ensure_unique_vault_filename(
                normalized_vault_id,
                filename,
                exclude_file_id=normalized_file_id,
            )

        registered = add_existing_file_to_vault(
            normalized_file_id,
            normalized_vault_id,
        )

        try:
            result = _index_and_register_file(
                file_id=normalized_file_id,
                vault_id=normalized_vault_id,
                request_id=request_id,
            )

            _audit_success(
                action="file_add",
                message=(
                    "Existing knowledge file added to the "
                    "vault and indexed successfully."
                ),
                request_id=request_id,
                resource_id=normalized_file_id,
                duration_ms=_duration_ms(
                    started_at
                ),
                metadata={
                    "filename": filename,
                    "vault_id": normalized_vault_id,
                    "indexed": result[
                        "index"
                    ].get(
                        "indexed",
                        False,
                    ),
                    "chunks": result[
                        "index"
                    ].get(
                        "chunks",
                        0,
                    ),
                    "characters": result[
                        "index"
                    ].get(
                        "characters",
                        0,
                    ),
                },
            )

            return {
                "status": "indexed",
                "file": result["file"] or registered,
                "index": result["index"],
            }

        except Exception:
            _mark_index_failed(
                normalized_file_id,
                characters=int(
                    registered.get(
                        "characters",
                        0,
                    )
                    or 0
                ),
            )
            raise

    except HTTPException as exc:
        _audit_failure(
            action="file_add",
            message="Adding the existing file to the vault was rejected.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "vault_id": normalized_vault_id,
                "status_code": exc.status_code,
                "error": str(
                    exc.detail
                ),
            },
        )

        raise

    except FileNotFoundError as exc:
        _audit_failure(
            action="file_add",
            message="Adding the existing file to the vault failed because the file was not found.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "vault_id": normalized_vault_id,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        _audit_failure(
            action="file_add",
            message="Adding the existing file to the vault failed validation.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "vault_id": normalized_vault_id,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        _audit_failure(
            action="file_add",
            message="Adding the existing file to the vault failed.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "vault_id": normalized_vault_id,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to add file to vault: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# FILE DETAILS
# ---------------------------------------------------------------------------

@router.get("/files/{file_id}")
def get_vault_file(
    file_id: str,
) -> Dict[str, Any]:
    normalized_file_id = _normalize_id(
        file_id,
        "file_id",
    )

    try:
        metadata = get_file(
            normalized_file_id,
        )

        return {
            "file": metadata,
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to load file: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# FILE PREVIEW
# ---------------------------------------------------------------------------

@router.get("/files/{file_id}/preview")
def preview_vault_file(
    file_id: str,
    max_characters: int = Query(
        default=30000,
        ge=1000,
        le=200000,
    ),
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    request_id = create_request_id()

    normalized_file_id = _normalize_id(
        file_id,
        "file_id",
    )

    try:
        metadata = get_file(
            normalized_file_id,
        )

        path = resolve_file_path(
            normalized_file_id,
        )

        extraction = extract_document(
            str(path),
        )

        extracted_text = str(
            extraction.text or ""
        )

        preview_text = extracted_text[
            :max_characters
        ]

        _audit_success(
            action="file_preview",
            message=(
                "Knowledge file preview generated successfully."
            ),
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "filename": metadata.get(
                    "filename"
                ),
                "file_type": extraction.file_type,
                "pages": extraction.pages,
                "used_ocr": extraction.used_ocr,
                "character_count": len(
                    extracted_text
                ),
                "max_characters": max_characters,
                "truncated": (
                    len(extracted_text)
                    > max_characters
                ),
            },
        )

        return {
            "file": metadata,
            "preview": {
                "file_type": extraction.file_type,
                "text": preview_text,
                "pages": extraction.pages,
                "used_ocr": extraction.used_ocr,
                "metadata": extraction.metadata,
                "character_count": len(
                    extracted_text
                ),
                "truncated": (
                    len(extracted_text)
                    > max_characters
                ),
            },
        }

    except FileNotFoundError as exc:
        _audit_failure(
            action="file_preview",
            message="Knowledge file preview failed because the file was not found.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        _audit_failure(
            action="file_preview",
            message="Knowledge file preview validation failed.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        _audit_failure(
            action="file_preview",
            message="Knowledge file preview extraction failed.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        _audit_failure(
            action="file_preview",
            message="Knowledge file preview failed.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"File preview failed: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# RENAME FILE
# ---------------------------------------------------------------------------

@router.patch("/files/{file_id}")
def rename_vault_file(
    file_id: str,
    request: FileRenameRequest,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    request_id = create_request_id()

    normalized_file_id = _normalize_id(
        file_id,
        "file_id",
    )

    new_filename = _validate_filename(
        request.name
    )

    try:
        current = get_file(
            normalized_file_id
        )

        current_vault_id = (
            str(
                current.get(
                    "vault_id",
                    "",
                )
                or ""
            ).strip()
            or None
        )

        old_filename = str(
            current.get(
                "filename",
                "",
            )
        ).strip()

        if current_vault_id:
            _ensure_unique_vault_filename(
                current_vault_id,
                new_filename,
                exclude_file_id=normalized_file_id,
            )

        was_indexed = bool(
            current.get(
                "indexed",
                False,
            )
        )

        file_metadata = rename_file(
            normalized_file_id,
            new_filename,
        )

        # A renamed source must be re-indexed so Chroma carries the
        # current filename/source metadata.
        if was_indexed and file_metadata:
            try:
                synchronized = _index_and_register_file(
                    file_id=normalized_file_id,
                    vault_id=current_vault_id,
                    request_id=request_id,
                )

                _audit_success(
                    action="file_rename",
                    message=(
                        "Knowledge file renamed and its "
                        "search index synchronized."
                    ),
                    request_id=request_id,
                    resource_id=normalized_file_id,
                    duration_ms=_duration_ms(
                        started_at
                    ),
                    metadata={
                        "old_filename": old_filename,
                        "new_filename": new_filename,
                        "vault_id": current_vault_id,
                        "reindexed": True,
                    },
                )

                return {
                    "status": "updated",
                    "file": synchronized["file"],
                    "index": synchronized["index"],
                }

            except Exception:
                _mark_index_failed(
                    normalized_file_id,
                    characters=int(
                        file_metadata.get(
                            "characters",
                            0,
                        )
                        or 0
                    ),
                )
                raise

        _audit_success(
            action="file_rename",
            message="Knowledge file renamed successfully.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "old_filename": old_filename,
                "new_filename": new_filename,
                "vault_id": current_vault_id,
                "reindexed": False,
                "was_indexed": was_indexed,
            },
        )

        return {
            "status": "updated",
            "file": file_metadata,
        }

    except HTTPException as exc:
        _audit_failure(
            action="file_rename",
            message="Knowledge file rename was rejected.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "new_filename": new_filename,
                "status_code": exc.status_code,
                "error": str(
                    exc.detail
                ),
            },
        )

        raise

    except FileNotFoundError as exc:
        _audit_failure(
            action="file_rename",
            message="Knowledge file rename failed because the file was not found.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "new_filename": new_filename,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        _audit_failure(
            action="file_rename",
            message="Knowledge file rename validation failed.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "new_filename": new_filename,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        _audit_failure(
            action="file_rename",
            message="Knowledge file rename failed.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "new_filename": new_filename,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"File rename failed: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# MOVE FILE
# ---------------------------------------------------------------------------

@router.post("/files/{file_id}/move")
def move_vault_file(
    file_id: str,
    request: FileMoveRequest,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    request_id = create_request_id()

    normalized_file_id = _normalize_id(
        file_id,
        "file_id",
    )

    normalized_target_vault_id = _normalize_id(
        request.vault_id,
        "vault_id",
    )

    try:
        if not _vault_exists(
            normalized_target_vault_id
        ):
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Vault not found: "
                    f"{normalized_target_vault_id}"
                ),
            )

        current = get_file(
            normalized_file_id
        )

        current_vault_id = (
            str(
                current.get(
                    "vault_id",
                    "",
                )
                or ""
            ).strip()
            or None
        )

        filename = str(
            current.get(
                "filename",
                "",
            )
        ).strip()

        if (
            current_vault_id
            != normalized_target_vault_id
        ):
            if filename:
                _ensure_unique_vault_filename(
                    normalized_target_vault_id,
                    filename,
                    exclude_file_id=normalized_file_id,
                )

        moved = move_file(
            normalized_file_id,
            normalized_target_vault_id,
        )

        # Moving between vaults changes the vault filter that the
        # Chroma records must carry. Re-index the same physical file
        # under its new vault without creating a duplicate file.
        try:
            synchronized = _index_and_register_file(
                file_id=normalized_file_id,
                vault_id=normalized_target_vault_id,
                request_id=request_id,
            )

            _audit_success(
                action="file_move",
                message=(
                    "Knowledge file moved to the target vault "
                    "and its search index synchronized."
                ),
                request_id=request_id,
                resource_id=normalized_file_id,
                duration_ms=_duration_ms(
                    started_at
                ),
                metadata={
                    "filename": filename,
                    "source_vault_id": current_vault_id,
                    "target_vault_id": normalized_target_vault_id,
                    "reindexed": True,
                },
            )

            return {
                "status": "moved",
                "file": synchronized["file"],
                "index": synchronized["index"],
            }

        except Exception:
            _mark_index_failed(
                normalized_file_id,
                characters=int(
                    moved.get(
                        "characters",
                        0,
                    )
                    or 0
                ),
            )
            raise

    except HTTPException as exc:
        _audit_failure(
            action="file_move",
            message="Knowledge file move was rejected.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "target_vault_id": normalized_target_vault_id,
                "status_code": exc.status_code,
                "error": str(
                    exc.detail
                ),
            },
        )

        raise

    except FileNotFoundError as exc:
        _audit_failure(
            action="file_move",
            message="Knowledge file move failed because the file or vault was not found.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "target_vault_id": normalized_target_vault_id,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        _audit_failure(
            action="file_move",
            message="Knowledge file move validation failed.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "target_vault_id": normalized_target_vault_id,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        _audit_failure(
            action="file_move",
            message="Knowledge file move failed.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "target_vault_id": normalized_target_vault_id,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"File move failed: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# DELETE FILE → BIN
# ---------------------------------------------------------------------------

@router.delete("/files/{file_id}")
def trash_vault_file(
    file_id: str,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    request_id = create_request_id()

    normalized_file_id = _normalize_id(
        file_id,
        "file_id",
    )

    try:
        deleted = delete_file(
            normalized_file_id,
        )

        _audit_success(
            action="file_delete",
            message=(
                "Knowledge file moved to the recovery bin."
            ),
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "delete_mode": "soft_delete",
                "filename": (
                    deleted.get(
                        "filename"
                    )
                    if isinstance(
                        deleted,
                        dict,
                    )
                    else None
                ),
            },
        )

        return {
            "status": "trashed",
            "file": deleted,
        }

    except FileNotFoundError as exc:
        _audit_failure(
            action="file_delete",
            message="Knowledge file deletion failed because the file was not found.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "delete_mode": "soft_delete",
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        _audit_failure(
            action="file_delete",
            message="Knowledge file deletion failed.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "delete_mode": "soft_delete",
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"File deletion failed: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------------------------------

@router.get("/files/{file_id}/download")
def download_vault_file(
    file_id: str,
) -> FileResponse:
    started_at = time.perf_counter()
    request_id = create_request_id()

    normalized_file_id = _normalize_id(
        file_id,
        "file_id",
    )

    try:
        metadata = get_file(
            normalized_file_id,
        )

        path = resolve_file_path(
            normalized_file_id,
        )

        filename = str(
            metadata.get(
                "filename",
                path.name,
            )
        ).strip()

        media_type = str(
            metadata.get(
                "content_type",
                "",
            )
            or "application/octet-stream"
        )

        response = FileResponse(
            path=str(path),
            filename=filename,
            media_type=media_type,
        )

        _audit_success(
            action="file_download",
            message=(
                "Knowledge file download prepared successfully."
            ),
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "filename": filename,
                "media_type": media_type,
            },
        )

        return response

    except FileNotFoundError as exc:
        _audit_failure(
            action="file_download",
            message="Knowledge file download failed because the file was not found.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        _audit_failure(
            action="file_download",
            message="Knowledge file download failed.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"File download failed: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# RE-INDEX
# ---------------------------------------------------------------------------

@router.post("/files/{file_id}/reindex")
def reindex_vault_file(
    file_id: str,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    request_id = create_request_id()

    normalized_file_id = _normalize_id(
        file_id,
        "file_id",
    )

    try:
        metadata = get_file(
            normalized_file_id,
        )

        vault_id = (
            str(
                metadata.get(
                    "vault_id",
                    "",
                )
                or ""
            ).strip()
            or None
        )

        if not vault_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Only files assigned to a Knowledge Vault "
                    "can be re-indexed."
                ),
            )

        if not _vault_exists(
            vault_id
        ):
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Vault not found: "
                    f"{vault_id}"
                ),
            )

        result = _index_and_register_file(
            file_id=normalized_file_id,
            vault_id=vault_id,
            request_id=request_id,
        )

        if not result["index"].get(
            "indexed",
            False,
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "The file could not be indexed. "
                    "Check the local source file and extractor."
                ),
            )

        _audit_success(
            action="file_reindex",
            message=(
                "Knowledge file re-indexed successfully."
            ),
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "vault_id": vault_id,
                "filename": metadata.get(
                    "filename"
                ),
                "chunks": result[
                    "index"
                ].get(
                    "chunks",
                    0,
                ),
                "characters": result[
                    "index"
                ].get(
                    "characters",
                    0,
                ),
                "used_ocr": result[
                    "index"
                ].get(
                    "used_ocr",
                    False,
                ),
            },
        )

        return {
            "status": "indexed",
            "file": result["file"],
            "index": result["index"],
        }

    except HTTPException as exc:
        _audit_failure(
            action="file_reindex",
            message="Knowledge file re-indexing was rejected.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "status_code": exc.status_code,
                "error": str(
                    exc.detail
                ),
            },
        )

        raise

    except FileNotFoundError as exc:
        _audit_failure(
            action="file_reindex",
            message="Knowledge file re-indexing failed because the file was not found.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        _audit_failure(
            action="file_reindex",
            message="Knowledge file re-indexing validation failed.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        _audit_failure(
            action="file_reindex",
            message="Knowledge file re-indexing failed during extraction or indexing.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        _audit_failure(
            action="file_reindex",
            message="Knowledge file re-indexing failed.",
            request_id=request_id,
            resource_id=normalized_file_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"File re-indexing failed: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# RECENT UPLOADS
# ---------------------------------------------------------------------------

@router.get("/recent")
def recent_uploads() -> Dict[str, Any]:
    try:
        files = list_recent_uploads()

        return {
            "files": files,
            "count": len(files),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to load recent uploads: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# BIN
# ---------------------------------------------------------------------------

@router.get("/bin")
def knowledge_bin() -> Dict[str, Any]:
    try:
        items = list_bin()

        return {
            "items": items,
            "count": len(items),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Unable to load Knowledge Vault bin: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# RESTORE
# ---------------------------------------------------------------------------

@router.post("/bin/restore")
def restore_bin_item(
    request: RestoreRequest,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    request_id = create_request_id()

    item_type = (
        str(
            request.item_type
            or ""
        )
        .lower()
        .strip()
    )

    item_id = (
        str(
            request.item_id
            or ""
        )
        .strip()
    )

    if not item_id:
        raise HTTPException(
            status_code=400,
            detail="item_id is required.",
        )

    if item_type not in {
        "file",
        "vault",
    }:
        raise HTTPException(
            status_code=400,
            detail=(
                "item_type must be "
                "'file' or 'vault'."
            ),
        )

    normalized_id = _normalize_id(
        item_id,
        "item_id",
    )

    try:
        if item_type == "file":
            restored = restore_file(
                normalized_id,
            )
        else:
            restored = restore_vault(
                normalized_id,
            )

        _audit_success(
            action="restore",
            message=(
                f"Knowledge {item_type} restored successfully."
            ),
            request_id=request_id,
            resource_id=normalized_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "item_type": item_type,
            },
        )

        return {
            "status": "restored",
            "restored": restored,
        }

    except FileNotFoundError as exc:
        _audit_failure(
            action="restore",
            message=(
                f"Knowledge {item_type} restoration failed "
                "because the item was not found."
            ),
            request_id=request_id,
            resource_id=normalized_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "item_type": item_type,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        _audit_failure(
            action="restore",
            message=(
                f"Knowledge {item_type} restoration failed validation."
            ),
            request_id=request_id,
            resource_id=normalized_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "item_type": item_type,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        _audit_failure(
            action="restore",
            message=(
                f"Knowledge {item_type} restoration failed."
            ),
            request_id=request_id,
            resource_id=normalized_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "item_type": item_type,
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Restore failed: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# PERMANENT DELETE
# ---------------------------------------------------------------------------

@router.delete(
    "/bin/{item_type}/{item_id}"
)
def permanent_delete_bin_item(
    item_type: str,
    item_id: str,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    request_id = create_request_id()

    normalized_type = (
        str(
            item_type
            or ""
        )
        .lower()
        .strip()
    )

    normalized_id = _normalize_id(
        item_id,
        "item_id",
    )

    if normalized_type not in {
        "file",
        "vault",
    }:
        raise HTTPException(
            status_code=400,
            detail=(
                "item_type must be "
                "'file' or 'vault'."
            ),
        )

    try:
        if normalized_type == "file":
            result = permanent_delete_file(
                normalized_id,
            )
        else:
            result = permanent_delete_vault(
                normalized_id,
            )

        _audit_success(
            action="permanent_delete",
            message=(
                f"Knowledge {normalized_type} permanently deleted."
            ),
            request_id=request_id,
            resource_id=normalized_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "item_type": normalized_type,
                "delete_mode": "permanent",
            },
        )

        return {
            "status": "deleted",
            **result,
        }

    except FileNotFoundError as exc:
        _audit_failure(
            action="permanent_delete",
            message=(
                f"Permanent Knowledge {normalized_type} deletion "
                "failed because the item was not found."
            ),
            request_id=request_id,
            resource_id=normalized_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "item_type": normalized_type,
                "delete_mode": "permanent",
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        _audit_failure(
            action="permanent_delete",
            message=(
                f"Permanent Knowledge {normalized_type} deletion "
                "failed validation."
            ),
            request_id=request_id,
            resource_id=normalized_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "item_type": normalized_type,
                "delete_mode": "permanent",
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        _audit_failure(
            action="permanent_delete",
            message=(
                f"Permanent Knowledge {normalized_type} deletion failed."
            ),
            request_id=request_id,
            resource_id=normalized_id,
            duration_ms=_duration_ms(
                started_at
            ),
            metadata={
                "item_type": normalized_type,
                "delete_mode": "permanent",
                "error_type": type(
                    exc
                ).__name__,
                "error": str(exc),
            },
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Permanent deletion failed: {exc}"
            ),
        ) from exc