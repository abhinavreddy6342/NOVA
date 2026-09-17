from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


# ---------------------------------------------------------------------------
# PATHS / STORAGE
# ---------------------------------------------------------------------------

BASE_DIR = Path(
    __file__
).resolve().parent.parent

KNOWLEDGE_DIR = (
    BASE_DIR / "knowledge"
).resolve()

VAULT_REGISTRY_PATH = (
    KNOWLEDGE_DIR / "vault_registry.json"
).resolve()

CHAT_UPLOADS_DIR = (
    KNOWLEDGE_DIR / "chat_uploads"
).resolve()


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

MAX_UPLOAD_SIZE = 20 * 1024 * 1024

REGISTRY_VERSION = 5


# ---------------------------------------------------------------------------
# TIME
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


# ---------------------------------------------------------------------------
# PATH SECURITY
# ---------------------------------------------------------------------------

def _safe_name(
    name: str,
) -> str:
    value = Path(
        str(
            name or ""
        )
    ).name.strip()

    if not value:
        raise ValueError(
            "A valid filename is required."
        )

    if value in {
        ".",
        "..",
    }:
        raise ValueError(
            "Invalid filename."
        )

    return value


def _safe_id(
    value: str,
    label: str,
) -> str:
    normalized = str(
        value or ""
    ).strip()

    if not normalized:
        raise ValueError(
            f"{label} is required."
        )

    safe = Path(
        normalized
    ).name

    if safe != normalized:
        raise ValueError(
            f"Invalid {label}."
        )

    if normalized in {
        ".",
        "..",
    }:
        raise ValueError(
            f"Invalid {label}."
        )

    return normalized


def _safe_chat_file_path(
    stored_name: str,
) -> Path:
    safe_stored_name = _safe_name(
        stored_name
    )

    path = (
        CHAT_UPLOADS_DIR
        / safe_stored_name
    ).resolve()

    try:
        path.relative_to(
            CHAT_UPLOADS_DIR
        )
    except ValueError as exc:
        raise PermissionError(
            "File is outside the controlled NOVA upload directory."
        ) from exc

    return path


def _safe_metadata_path(
    file_id: str,
) -> Path:
    safe_id = _safe_id(
        file_id,
        "File ID",
    )

    path = (
        CHAT_UPLOADS_DIR
        / f"{safe_id}.json"
    ).resolve()

    try:
        path.relative_to(
            CHAT_UPLOADS_DIR
        )
    except ValueError as exc:
        raise PermissionError(
            "Metadata file is outside the controlled NOVA upload directory."
        ) from exc

    return path


# ---------------------------------------------------------------------------
# INDEX / RAG
# ---------------------------------------------------------------------------

def _delete_index(
    file_id: str,
    filename: str = "",
) -> bool:
    """
    Remove all Chroma chunks associated with a file.

    The Chroma layer is treated as a secondary index.
    The registry remains authoritative.
    """

    normalized_file_id = str(
        file_id or ""
    ).strip()

    if not normalized_file_id:
        return False

    try:
        from app.knowledge.vector_store import (
            delete_document,
        )

        delete_document(
            filename=filename,
            file_id=normalized_file_id,
        )

        return True

    except Exception as exc:
        print(
            "[NOVA VAULT INDEX DELETE] "
            f"{type(exc).__name__}: {exc}"
        )
        return False


def _reindex_file(
    file_id: str,
    vault_id: Optional[str],
    path: Path,
) -> Dict[str, Any]:
    """
    Re-index one real local file.
    """

    try:
        if not path.exists():
            raise FileNotFoundError(
                f"Source file does not exist: {path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Source path is not a file: {path}"
            )

        from app.knowledge.rag import (
            index_document,
        )

        result = index_document(
            str(path),
            file_id=file_id,
            vault_id=vault_id,
        )

        return {
            "success": bool(
                result.get(
                    "indexed",
                    False,
                )
            ),
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
            "indexed_at": str(
                result.get(
                    "indexed_at",
                    "",
                )
                or ""
            ),
            "content_sha256": str(
                result.get(
                    "content_sha256",
                    "",
                )
                or ""
            ),
        }

    except Exception as exc:
        print(
            "[NOVA VAULT INDEX REBUILD] "
            f"{type(exc).__name__}: {exc}"
        )

        return {
            "success": False,
            "characters": 0,
            "chunks": 0,
            "used_ocr": False,
            "indexed_at": "",
            "content_sha256": "",
            "error": str(exc),
        }


def _apply_index_result(
    item: Dict[str, Any],
    result: Dict[str, Any],
) -> None:
    success = bool(
        result.get(
            "success",
            False,
        )
    )

    item["indexed"] = success

    item["chunks"] = (
        max(
            0,
            int(
                result.get(
                    "chunks",
                    0,
                )
                or 0
            ),
        )
        if success
        else 0
    )

    item["characters"] = (
        max(
            0,
            int(
                result.get(
                    "characters",
                    0,
                )
                or 0
            ),
        )
        if success
        else 0
    )

    if success:
        indexed_at = str(
            result.get(
                "indexed_at",
                "",
            )
            or ""
        ).strip()

        content_sha256 = str(
            result.get(
                "content_sha256",
                "",
            )
            or ""
        ).strip()

        if indexed_at:
            item["indexed_at"] = indexed_at

        if content_sha256:
            item["content_sha256"] = (
                content_sha256
            )

    else:
        item["indexed_at"] = (
            item.get(
                "indexed_at",
                None,
            )
            if item.get("indexed_at")
            else None
        )


def _reindex_item(
    item: Dict[str, Any],
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Re-index using current registry metadata.
    """

    file_id = str(
        item.get(
            "file_id",
            "",
        )
    ).strip()

    if not file_id:
        item["indexed"] = False
        item["chunks"] = 0
        item["characters"] = 0

        return {
            "indexed": False,
            "chunks": 0,
            "characters": 0,
        }

    try:
        current_path = (
            path
            if path is not None
            else _safe_chat_file_path(
                str(
                    item.get(
                        "stored_name",
                        "",
                    )
                )
            )
        )

        current_path = Path(
            current_path
        ).resolve()

        if not current_path.exists():
            item["indexed"] = False
            item["chunks"] = 0

            return {
                "indexed": False,
                "chunks": 0,
                "characters": int(
                    item.get(
                        "characters",
                        0,
                    )
                    or 0
                ),
                "error": (
                    "Stored source file does not exist."
                ),
            }

        if not current_path.is_file():
            item["indexed"] = False
            item["chunks"] = 0

            return {
                "indexed": False,
                "chunks": 0,
                "characters": int(
                    item.get(
                        "characters",
                        0,
                    )
                    or 0
                ),
                "error": (
                    "Stored source path is not a file."
                ),
            }

        result = _reindex_file(
            file_id=file_id,
            vault_id=item.get(
                "vault_id"
            ),
            path=current_path,
        )

        _apply_index_result(
            item,
            result,
        )

        response = {
            "indexed": bool(
                result.get(
                    "success",
                    False,
                )
            ),
            "chunks": int(
                result.get(
                    "chunks",
                    0,
                )
                or 0
            ),
            "characters": int(
                result.get(
                    "characters",
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
        }

        if result.get(
            "indexed_at"
        ):
            response["indexed_at"] = (
                result["indexed_at"]
            )

        if result.get(
            "content_sha256"
        ):
            response["content_sha256"] = (
                result["content_sha256"]
            )

        if result.get(
            "error"
        ):
            response["error"] = result[
                "error"
            ]

        return response

    except Exception as exc:
        item["indexed"] = False
        item["chunks"] = 0

        return {
            "indexed": False,
            "chunks": 0,
            "characters": int(
                item.get(
                    "characters",
                    0,
                )
                or 0
            ),
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# REGISTRY
# ---------------------------------------------------------------------------

def _empty_registry() -> Dict[str, Any]:
    return {
        "version": REGISTRY_VERSION,
        "updated_at": _now(),
        "vaults": [],
        "files": [],
        "bin": [],
    }


def _ensure_registry() -> None:
    KNOWLEDGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    CHAT_UPLOADS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not VAULT_REGISTRY_PATH.exists():
        _atomic_write(
            _empty_registry()
        )


def _normalize_registry(
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Normalize older registry versions without destroying
    existing data.
    """

    if not isinstance(
        data,
        dict,
    ):
        data = _empty_registry()

    if not isinstance(
        data.get("vaults"),
        list,
    ):
        data["vaults"] = []

    if not isinstance(
        data.get("files"),
        list,
    ):
        data["files"] = []

    if not isinstance(
        data.get("bin"),
        list,
    ):
        data["bin"] = []

    data["version"] = (
        REGISTRY_VERSION
    )

    data.setdefault(
        "updated_at",
        _now(),
    )

    # -----------------------------------------------------------------------
    # VAULTS
    # -----------------------------------------------------------------------

    normalized_vaults: List[
        Dict[str, Any]
    ] = []

    for vault in data["vaults"]:
        if not isinstance(
            vault,
            dict,
        ):
            continue

        vault.setdefault(
            "vault_id",
            uuid4().hex,
        )

        vault.setdefault(
            "name",
            "Untitled Vault",
        )

        vault.setdefault(
            "status",
            "active",
        )

        vault.setdefault(
            "created_at",
            _now(),
        )

        vault.setdefault(
            "updated_at",
            vault["created_at"],
        )

        vault.setdefault(
            "deleted_at",
            None,
        )

        normalized_vaults.append(
            vault
        )

    data["vaults"] = (
        normalized_vaults
    )

    # -----------------------------------------------------------------------
    # FILES
    # -----------------------------------------------------------------------

    normalized_files: List[
        Dict[str, Any]
    ] = []

    for item in data["files"]:
        if not isinstance(
            item,
            dict,
        ):
            continue

        file_id = str(
            item.get(
                "file_id",
                "",
            )
        ).strip()

        if not file_id:
            continue

        item.setdefault(
            "vault_id",
            None,
        )

        item.setdefault(
            "filename",
            item.get(
                "original_filename",
                "Unknown file",
            ),
        )

        item.setdefault(
            "original_filename",
            item.get(
                "filename",
                "Unknown file",
            ),
        )

        item.setdefault(
            "stored_name",
            "",
        )

        item.setdefault(
            "stored_relative_path",
            "",
        )

        item.setdefault(
            "content_type",
            "",
        )

        item.setdefault(
            "extension",
            "",
        )

        item.setdefault(
            "file_type",
            "document",
        )

        if "size" not in item:
            item["size"] = int(
                item.get(
                    "size_bytes",
                    0,
                )
                or 0
            )

        item.setdefault(
            "characters",
            0,
        )

        item.setdefault(
            "chunks",
            0,
        )

        item.setdefault(
            "indexed",
            False,
        )

        item.setdefault(
            "indexed_at",
            None,
        )

        item.setdefault(
            "content_sha256",
            "",
        )

        item.setdefault(
            "status",
            "active",
        )

        item.setdefault(
            "created_at",
            _now(),
        )

        item.setdefault(
            "updated_at",
            item.get(
                "created_at",
                _now(),
            ),
        )

        item.setdefault(
            "deleted_at",
            None,
        )

        item.setdefault(
            "deleted_from_vault_id",
            None,
        )

        item.setdefault(
            "deleted_from_vault_name",
            "",
        )

        item.setdefault(
            "source",
            "chat",
        )

        normalized_files.append(
            item
        )

    data["files"] = (
        normalized_files
    )

    # -----------------------------------------------------------------------
    # BIN
    # -----------------------------------------------------------------------

    normalized_bin: List[
        Dict[str, Any]
    ] = []

    for entry in data["bin"]:
        if not isinstance(
            entry,
            dict,
        ):
            continue

        item_type = str(
            entry.get(
                "item_type",
                "",
            )
        ).strip()

        item_id = str(
            entry.get(
                "item_id",
                "",
            )
        ).strip()

        if not item_type or not item_id:
            continue

        entry.setdefault(
            "deleted_at",
            _now(),
        )

        normalized_bin.append(
            entry
        )

    data["bin"] = (
        normalized_bin
    )

    return data


def _load_registry() -> Dict[str, Any]:
    _ensure_registry()

    try:
        data = json.loads(
            VAULT_REGISTRY_PATH.read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        json.JSONDecodeError,
    ):
        print(
            "[NOVA VAULT REGISTRY] "
            "Registry could not be parsed; rebuilding registry structure."
        )

        data = _empty_registry()

    return _normalize_registry(
        data
    )


def _atomic_write(
    data: Dict[str, Any],
) -> None:
    KNOWLEDGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    fd, temp_name = tempfile.mkstemp(
        prefix=".nova-vault-",
        suffix=".json",
        dir=str(
            KNOWLEDGE_DIR
        ),
    )

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                data,
                handle,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(
            temp_name,
            VAULT_REGISTRY_PATH,
        )

    finally:
        if os.path.exists(
            temp_name
        ):
            try:
                os.unlink(
                    temp_name
                )
            except OSError:
                pass


def _save_registry(
    data: Dict[str, Any],
) -> None:
    normalized = _normalize_registry(
        data
    )

    normalized["version"] = (
        REGISTRY_VERSION
    )

    normalized["updated_at"] = _now()

    _atomic_write(
        normalized
    )


# ---------------------------------------------------------------------------
# BIN HELPERS
# ---------------------------------------------------------------------------

def _remove_bin_entries(
    registry: Dict[str, Any],
    item_type: str,
    item_id: str,
) -> None:
    normalized_type = str(
        item_type or ""
    ).strip()

    normalized_id = str(
        item_id or ""
    ).strip()

    registry["bin"] = [
        entry
        for entry in registry["bin"]
        if not (
            str(
                entry.get(
                    "item_type",
                    "",
                )
            ).strip()
            == normalized_type
            and str(
                entry.get(
                    "item_id",
                    "",
                )
            ).strip()
            == normalized_id
        )
    ]


def _add_bin_entry(
    registry: Dict[str, Any],
    entry: Dict[str, Any],
) -> None:
    item_type = str(
        entry.get(
            "item_type",
            "",
        )
    ).strip()

    item_id = str(
        entry.get(
            "item_id",
            "",
        )
    ).strip()

    if not item_type or not item_id:
        return

    _remove_bin_entries(
        registry,
        item_type,
        item_id,
    )

    registry["bin"].append(
        dict(entry)
    )


# ---------------------------------------------------------------------------
# LOOKUPS
# ---------------------------------------------------------------------------

def _find_vault(
    registry: Dict[str, Any],
    vault_id: str,
    include_deleted: bool = False,
) -> Dict[str, Any]:
    normalized_id = str(
        vault_id or ""
    ).strip()

    if not normalized_id:
        raise FileNotFoundError(
            "Vault ID is required."
        )

    for vault in registry[
        "vaults"
    ]:
        if str(
            vault.get(
                "vault_id",
                "",
            )
        ).strip() != normalized_id:
            continue

        if (
            not include_deleted
            and vault.get(
                "status"
            ) == "deleted"
        ):
            raise FileNotFoundError(
                f"Vault not found: {normalized_id}"
            )

        return vault

    raise FileNotFoundError(
        f"Vault not found: {normalized_id}"
    )


def _find_file(
    registry: Dict[str, Any],
    file_id: str,
    include_deleted: bool = False,
) -> Dict[str, Any]:
    normalized_id = str(
        file_id or ""
    ).strip()

    if not normalized_id:
        raise FileNotFoundError(
            "File ID is required."
        )

    for item in registry[
        "files"
    ]:
        if str(
            item.get(
                "file_id",
                "",
            )
        ).strip() != normalized_id:
            continue

        if (
            not include_deleted
            and item.get(
                "status"
            ) == "deleted"
        ):
            raise FileNotFoundError(
                f"Vault file not found: {normalized_id}"
            )

        return item

    raise FileNotFoundError(
        f"Vault file not found: {normalized_id}"
    )


# ---------------------------------------------------------------------------
# VAULTS
# ---------------------------------------------------------------------------

def list_vaults(
    include_deleted: bool = False,
) -> List[Dict[str, Any]]:
    registry = _load_registry()

    result: List[
        Dict[str, Any]
    ] = []

    for vault in registry[
        "vaults"
    ]:
        if not isinstance(
            vault,
            dict,
        ):
            continue

        if (
            not include_deleted
            and vault.get(
                "status"
            ) == "deleted"
        ):
            continue

        vault_id = str(
            vault.get(
                "vault_id",
                "",
            )
        ).strip()

        active_files = [
            item
            for item in registry[
                "files"
            ]
            if (
                isinstance(
                    item,
                    dict,
                )
                and str(
                    item.get(
                        "vault_id",
                        "",
                    )
                ).strip()
                == vault_id
                and item.get(
                    "status"
                ) == "active"
            )
        ]

        file_count = len(
            active_files
        )

        indexed_count = sum(
            1
            for item in active_files
            if bool(
                item.get(
                    "indexed"
                )
            )
        )

        chunks = sum(
            max(
                0,
                int(
                    item.get(
                        "chunks",
                        0,
                    )
                    or 0
                ),
            )
            for item in active_files
        )

        characters = sum(
            max(
                0,
                int(
                    item.get(
                        "characters",
                        0,
                    )
                    or 0
                ),
            )
            for item in active_files
        )

        output = dict(
            vault
        )

        output["file_count"] = (
            file_count
        )

        output["indexed_count"] = (
            indexed_count
        )

        output["chunks"] = chunks

        output["characters"] = (
            characters
        )

        result.append(
            output
        )

    result.sort(
        key=lambda item: str(
            item.get(
                "updated_at",
                item.get(
                    "created_at",
                    "",
                ),
            )
        ),
        reverse=True,
    )

    return result


def create_vault(
    name: str,
) -> Dict[str, Any]:
    clean_name = str(
        name or ""
    ).strip()

    if not clean_name:
        raise ValueError(
            "Vault name cannot be empty."
        )

    if len(clean_name) > 120:
        raise ValueError(
            "Vault name cannot exceed 120 characters."
        )

    registry = _load_registry()

    existing_names = {
        str(
            item.get(
                "name",
                "",
            )
        ).strip().casefold()
        for item in registry[
            "vaults"
        ]
        if (
            isinstance(
                item,
                dict,
            )
            and item.get(
                "status"
            ) != "deleted"
        )
    }

    if clean_name.casefold() in (
        existing_names
    ):
        raise ValueError(
            "A vault with this name already exists."
        )

    now = _now()

    vault = {
        "vault_id": uuid4().hex,
        "name": clean_name,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }

    registry[
        "vaults"
    ].append(
        vault
    )

    _save_registry(
        registry
    )

    result = dict(
        vault
    )

    result["file_count"] = 0
    result["indexed_count"] = 0
    result["chunks"] = 0
    result["characters"] = 0

    return result


def rename_vault(
    vault_id: str,
    name: str,
) -> Dict[str, Any]:
    clean_name = str(
        name or ""
    ).strip()

    if not clean_name:
        raise ValueError(
            "Vault name cannot be empty."
        )

    if len(clean_name) > 120:
        raise ValueError(
            "Vault name cannot exceed 120 characters."
        )

    registry = _load_registry()

    vault = _find_vault(
        registry,
        vault_id,
    )

    normalized_id = str(
        vault_id
    ).strip()

    for other in registry[
        "vaults"
    ]:
        if str(
            other.get(
                "vault_id",
                "",
            )
        ).strip() == normalized_id:
            continue

        if other.get(
            "status"
        ) == "deleted":
            continue

        if (
            str(
                other.get(
                    "name",
                    "",
                )
            ).strip().casefold()
            == clean_name.casefold()
        ):
            raise ValueError(
                "A vault with this name already exists."
            )

    vault["name"] = clean_name
    vault["updated_at"] = _now()

    _save_registry(
        registry
    )

    return dict(
        vault
    )


def delete_vault(
    vault_id: str,
) -> Dict[str, Any]:
    registry = _load_registry()

    vault = _find_vault(
        registry,
        vault_id,
    )

    normalized_vault_id = str(
        vault_id
    ).strip()

    original_vault_name = str(
        vault.get(
            "name",
            "",
        )
    )

    deleted_at = _now()

    affected_files: List[
        str
    ] = []

    index_failures: List[
        str
    ] = []

    for item in registry[
        "files"
    ]:
        if (
            not isinstance(
                item,
                dict,
            )
            or str(
                item.get(
                    "vault_id",
                    "",
                )
            ).strip()
            != normalized_vault_id
            or item.get(
                "status"
            ) != "active"
        ):
            continue

        file_id = str(
            item.get(
                "file_id",
                "",
            )
        ).strip()

        if file_id:
            index_deleted = _delete_index(
                file_id=file_id,
                filename=str(
                    item.get(
                        "filename",
                        "",
                    )
                ),
            )

            if not index_deleted:
                index_failures.append(
                    file_id
                )

        item["status"] = "deleted"
        item["deleted_at"] = (
            deleted_at
        )
        item[
            "deleted_from_vault_id"
        ] = normalized_vault_id
        item[
            "deleted_from_vault_name"
        ] = original_vault_name
        item["updated_at"] = (
            deleted_at
        )
        item["indexed"] = False
        item["chunks"] = 0
        item["indexed_at"] = None

        _add_bin_entry(
            registry,
            {
                "item_type": "file",
                "item_id": file_id,
                "deleted_at": deleted_at,
                "original_vault_id": (
                    normalized_vault_id
                ),
                "original_vault_name": (
                    original_vault_name
                ),
                "original_filename": item.get(
                    "filename",
                    "",
                ),
                "original_stored_name": item.get(
                    "stored_name",
                    "",
                ),
                "original_stored_relative_path": item.get(
                    "stored_relative_path",
                    "",
                ),
            },
        )

        affected_files.append(
            file_id
        )

    vault["status"] = "deleted"
    vault["deleted_at"] = (
        deleted_at
    )
    vault["updated_at"] = (
        deleted_at
    )

    _add_bin_entry(
        registry,
        {
            "item_type": "vault",
            "item_id": normalized_vault_id,
            "deleted_at": deleted_at,
            "original_vault_id": (
                normalized_vault_id
            ),
            "original_vault_name": (
                original_vault_name
            ),
            "name": original_vault_name,
        },
    )

    _save_registry(
        registry
    )

    return {
        "vault": dict(
            vault
        ),
        "deleted_files": (
            affected_files
        ),
        "index_delete_failures": (
            index_failures
        ),
    }


# ---------------------------------------------------------------------------
# FILES
# ---------------------------------------------------------------------------

def list_vault_files(
    vault_id: str,
) -> List[Dict[str, Any]]:
    registry = _load_registry()

    _find_vault(
        registry,
        vault_id,
    )

    normalized_vault_id = str(
        vault_id
    ).strip()

    files = [
        dict(item)
        for item in registry[
            "files"
        ]
        if (
            isinstance(
                item,
                dict,
            )
            and str(
                item.get(
                    "vault_id",
                    "",
                )
            ).strip()
            == normalized_vault_id
            and item.get(
                "status"
            ) == "active"
        )
    ]

    return sorted(
        files,
        key=lambda item: str(
            item.get(
                "updated_at",
                item.get(
                    "created_at",
                    "",
                ),
            )
        ),
        reverse=True,
    )


def get_file(
    file_id: str,
) -> Dict[str, Any]:
    registry = _load_registry()

    return dict(
        _find_file(
            registry,
            file_id,
        )
    )


def resolve_file_path(
    file_id: str,
) -> Path:
    registry = _load_registry()

    item = _find_file(
        registry,
        file_id,
    )

    stored_name = str(
        item.get(
            "stored_name",
            "",
        )
    ).strip()

    if not stored_name:
        raise RuntimeError(
            "Vault file has no stored filename."
        )

    path = _safe_chat_file_path(
        stored_name
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Stored vault file is missing: {file_id}"
        )

    if not path.is_file():
        raise FileNotFoundError(
            f"Stored vault path is not a file: {file_id}"
        )

    return path


def register_chat_file(
    file_id: str,
    vault_id: str = "",
) -> Dict[str, Any]:
    from app.services.chat_files import (
        load_chat_file,
    )

    normalized_file_id = _safe_id(
        file_id,
        "File ID",
    )

    normalized_vault_id = str(
        vault_id or ""
    ).strip()

    registry = _load_registry()

    metadata = load_chat_file(
        normalized_file_id
    )

    if not isinstance(
        metadata,
        dict,
    ):
        raise ValueError(
            "Invalid chat file metadata."
        )

    if normalized_vault_id:
        _find_vault(
            registry,
            normalized_vault_id,
        )

    existing: Optional[
        Dict[str, Any]
    ] = None

    for candidate in registry[
        "files"
    ]:
        if (
            str(
                candidate.get(
                    "file_id",
                    "",
                )
            ).strip()
            == normalized_file_id
        ):
            existing = candidate
            break

    now = _now()

    metadata_filename = str(
        metadata.get(
            "filename",
            "",
        )
    ).strip()

    metadata_stored_name = str(
        metadata.get(
            "stored_name",
            "",
        )
    ).strip()

    metadata_relative_path = str(
        metadata.get(
            "stored_relative_path",
            "",
        )
    ).strip()

    if not metadata_stored_name:
        raise ValueError(
            "Uploaded file metadata has no stored filename."
        )

    stored_path = _safe_chat_file_path(
        metadata_stored_name
    )

    if (
        not stored_path.exists()
        or not stored_path.is_file()
    ):
        raise FileNotFoundError(
            "Uploaded file is missing from local storage: "
            f"{normalized_file_id}"
        )

    normalized_target_vault_id = (
        normalized_vault_id
        or None
    )

    previous_vault_id = None

    if existing is not None:
        previous_vault_id = (
            existing.get(
                "vault_id"
            )
        )

        vault_changed = (
            previous_vault_id
            != normalized_target_vault_id
        )

        if vault_changed:
            index_deleted = _delete_index(
                file_id=normalized_file_id,
                filename=str(
                    existing.get(
                        "filename",
                        metadata_filename,
                    )
                ),
            )

            existing["indexed"] = False
            existing["chunks"] = 0
            existing["indexed_at"] = None

            if not index_deleted:
                existing[
                    "index_sync_warning"
                ] = (
                    "Existing Chroma index could not be confirmed deleted."
                )
            else:
                existing.pop(
                    "index_sync_warning",
                    None,
                )

        existing["vault_id"] = (
            normalized_target_vault_id
        )

        existing["status"] = "active"
        existing["deleted_at"] = None
        existing[
            "deleted_from_vault_id"
        ] = None
        existing[
            "deleted_from_vault_name"
        ] = ""
        existing["updated_at"] = now

        existing["filename"] = (
            metadata_filename
            or existing.get(
                "filename",
                stored_path.name,
            )
        )

        existing[
            "original_filename"
        ] = (
            existing.get(
                "original_filename"
            )
            or metadata_filename
            or stored_path.name
        )

        existing["stored_name"] = (
            metadata_stored_name
        )

        existing[
            "stored_relative_path"
        ] = (
            metadata_relative_path
            or (
                "knowledge/chat_uploads/"
                f"{metadata_stored_name}"
            )
        )

        existing["content_type"] = (
            metadata.get(
                "content_type",
                existing.get(
                    "content_type",
                    "",
                ),
            )
        )

        existing["extension"] = (
            metadata.get(
                "extension",
                existing.get(
                    "extension",
                    stored_path.suffix.lower(),
                ),
            )
        )

        existing["file_type"] = (
            metadata.get(
                "file_type",
                existing.get(
                    "file_type",
                    "document",
                ),
            )
        )

        existing["size"] = int(
            metadata.get(
                "size",
                metadata.get(
                    "size_bytes",
                    existing.get(
                        "size",
                        0,
                    ),
                ),
            )
            or 0
        )

        metadata_sha256 = str(
            metadata.get(
                "sha256",
                metadata.get(
                    "content_sha256",
                    "",
                ),
            )
            or ""
        ).strip()

        if metadata_sha256:
            existing[
                "content_sha256"
            ] = metadata_sha256

        existing["source"] = (
            "knowledge-vault"
            if normalized_target_vault_id
            else "chat"
        )

        _remove_bin_entries(
            registry,
            "file",
            normalized_file_id,
        )

        _save_registry(
            registry
        )

        return dict(
            existing
        )

    metadata_sha256 = str(
        metadata.get(
            "sha256",
            metadata.get(
                "content_sha256",
                "",
            ),
        )
        or ""
    ).strip()

    item = {
        "file_id": normalized_file_id,
        "vault_id": (
            normalized_target_vault_id
        ),
        "filename": (
            metadata_filename
            or stored_path.name
        ),
        "original_filename": (
            metadata_filename
            or stored_path.name
        ),
        "stored_name": (
            metadata_stored_name
        ),
        "stored_relative_path": (
            metadata_relative_path
            or (
                "knowledge/chat_uploads/"
                f"{metadata_stored_name}"
            )
        ),
        "content_type": metadata.get(
            "content_type",
            "",
        ),
        "extension": metadata.get(
            "extension",
            stored_path.suffix.lower(),
        ),
        "file_type": metadata.get(
            "file_type",
            "document",
        ),
        "size": int(
            metadata.get(
                "size",
                metadata.get(
                    "size_bytes",
                    0,
                ),
            )
            or 0
        ),
        "characters": int(
            metadata.get(
                "characters",
                0,
            )
            or 0
        ),
        "chunks": 0,
        "indexed": False,
        "indexed_at": None,
        "content_sha256": metadata_sha256,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
        "deleted_from_vault_id": None,
        "deleted_from_vault_name": "",
        "source": (
            "knowledge-vault"
            if normalized_target_vault_id
            else "chat"
        ),
    }

    registry[
        "files"
    ].append(
        item
    )

    _remove_bin_entries(
        registry,
        "file",
        normalized_file_id,
    )

    _save_registry(
        registry
    )

    return dict(
        item
    )


def add_existing_file_to_vault(
    file_id: str,
    vault_id: str,
) -> Dict[str, Any]:
    return register_chat_file(
        file_id=file_id,
        vault_id=vault_id,
    )


def rename_file(
    file_id: str,
    new_name: str,
) -> Dict[str, Any]:
    clean_name = _safe_name(
        new_name
    )

    registry = _load_registry()

    item = _find_file(
        registry,
        file_id,
    )

    current_name = str(
        item.get(
            "filename",
            "",
        )
    ).strip()

    old_extension = Path(
        current_name
    ).suffix.lower()

    new_extension = Path(
        clean_name
    ).suffix.lower()

    if (
        old_extension
        and new_extension
        and old_extension
        != new_extension
    ):
        raise ValueError(
            "Changing a file extension during rename is not supported."
        )

    if old_extension and not new_extension:
        clean_name = (
            clean_name
            + old_extension
        )

    old_path = _safe_chat_file_path(
        str(
            item.get(
                "stored_name",
                "",
            )
        )
    )

    if not old_path.exists():
        raise FileNotFoundError(
            f"Stored vault file is missing: {file_id}"
        )

    new_stored_name = (
        f"{file_id}_{clean_name}"
    )

    new_path = _safe_chat_file_path(
        new_stored_name
    )

    if (
        new_path.exists()
        and new_path != old_path
    ):
        new_stored_name = (
            f"{file_id}_"
            f"{uuid4().hex[:8]}_"
            f"{clean_name}"
        )

        new_path = _safe_chat_file_path(
            new_stored_name
        )

    index_deleted = _delete_index(
        file_id=str(
            item.get(
                "file_id",
                "",
            )
        ),
        filename=current_name,
    )

    try:
        old_path.rename(
            new_path
        )
    except OSError as exc:
        raise RuntimeError(
            f"Could not rename local file: {exc}"
        ) from exc

    metadata_path = _safe_metadata_path(
        file_id
    )

    metadata_updated = False

    if metadata_path.exists():
        try:
            metadata = json.loads(
                metadata_path.read_text(
                    encoding="utf-8"
                )
            )

            if isinstance(
                metadata,
                dict,
            ):
                metadata["filename"] = (
                    clean_name
                )

                metadata[
                    "stored_name"
                ] = (
                    new_stored_name
                )

                metadata[
                    "stored_relative_path"
                ] = (
                    "knowledge/chat_uploads/"
                    f"{new_stored_name}"
                )

                metadata[
                    "updated_at"
                ] = _now()

                metadata_path.write_text(
                    json.dumps(
                        metadata,
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

                metadata_updated = True

        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            print(
                "[NOVA VAULT METADATA UPDATE] "
                f"{type(exc).__name__}: {exc}"
            )

    item["filename"] = clean_name

    item[
        "original_filename"
    ] = item.get(
        "original_filename",
        current_name,
    )

    item["stored_name"] = (
        new_stored_name
    )

    item[
        "stored_relative_path"
    ] = (
        "knowledge/chat_uploads/"
        f"{new_stored_name}"
    )

    item["updated_at"] = _now()
    item["indexed"] = False
    item["chunks"] = 0
    item["indexed_at"] = None

    if not index_deleted:
        item[
            "index_sync_warning"
        ] = (
            "Previous Chroma index could not be confirmed deleted."
        )
    else:
        item.pop(
            "index_sync_warning",
            None,
        )

    _save_registry(
        registry
    )

    reindex_result = _reindex_item(
        item,
        path=new_path,
    )

    item["updated_at"] = _now()

    _save_registry(
        registry
    )

    result = dict(
        item
    )

    result[
        "metadata_updated"
    ] = metadata_updated

    result[
        "reindex"
    ] = reindex_result

    return result


def move_file(
    file_id: str,
    vault_id: str,
) -> Dict[str, Any]:
    registry = _load_registry()

    item = _find_file(
        registry,
        file_id,
    )

    target_vault = _find_vault(
        registry,
        vault_id,
    )

    normalized_file_id = str(
        file_id
    ).strip()

    normalized_vault_id = str(
        vault_id
    ).strip()

    previous_vault_id = (
        item.get(
            "vault_id"
        )
    )

    if (
        previous_vault_id
        == normalized_vault_id
    ):
        return dict(
            item
        )

    current_path = _safe_chat_file_path(
        str(
            item.get(
                "stored_name",
                "",
            )
        )
    )

    if not current_path.exists():
        raise FileNotFoundError(
            "Stored vault file is missing: "
            f"{normalized_file_id}"
        )

    old_filename = str(
        item.get(
            "filename",
            "",
        )
    )

    index_deleted = _delete_index(
        file_id=normalized_file_id,
        filename=old_filename,
    )

    item["vault_id"] = (
        normalized_vault_id
    )

    item["status"] = "active"
    item["deleted_at"] = None
    item["deleted_from_vault_id"] = None
    item["deleted_from_vault_name"] = ""
    item["updated_at"] = _now()
    item["source"] = "knowledge-vault"
    item["indexed"] = False
    item["chunks"] = 0
    item["indexed_at"] = None

    item[
        "moved_from_vault_id"
    ] = previous_vault_id

    item[
        "moved_to_vault_id"
    ] = normalized_vault_id

    item[
        "moved_to_vault_name"
    ] = target_vault.get(
        "name",
        "",
    )

    if not index_deleted:
        item[
            "index_sync_warning"
        ] = (
            "Previous Chroma index could not be confirmed deleted."
        )
    else:
        item.pop(
            "index_sync_warning",
            None,
        )

    _remove_bin_entries(
        registry,
        "file",
        normalized_file_id,
    )

    _save_registry(
        registry
    )

    reindex_result = _reindex_item(
        item,
        path=current_path,
    )

    item["updated_at"] = _now()

    _save_registry(
        registry
    )

    result = dict(
        item
    )

    result["reindex"] = (
        reindex_result
    )

    return result


def delete_file(
    file_id: str,
) -> Dict[str, Any]:
    registry = _load_registry()

    item = _find_file(
        registry,
        file_id,
    )

    normalized_file_id = str(
        file_id
    ).strip()

    original_vault_id = (
        item.get(
            "vault_id"
        )
    )

    original_vault_name = ""

    if original_vault_id:
        try:
            original_vault_name = str(
                _find_vault(
                    registry,
                    original_vault_id,
                    include_deleted=True,
                ).get(
                    "name",
                    "",
                )
            )
        except FileNotFoundError:
            original_vault_name = str(
                item.get(
                    "deleted_from_vault_name",
                    "",
                )
            )

    deleted_at = _now()

    index_deleted = _delete_index(
        file_id=normalized_file_id,
        filename=str(
            item.get(
                "filename",
                "",
            )
        ),
    )

    item["status"] = "deleted"
    item["deleted_at"] = (
        deleted_at
    )

    item[
        "deleted_from_vault_id"
    ] = original_vault_id

    item[
        "deleted_from_vault_name"
    ] = original_vault_name

    item["updated_at"] = (
        deleted_at
    )

    item["indexed"] = False
    item["chunks"] = 0
    item["indexed_at"] = None

    if not index_deleted:
        item[
            "index_sync_warning"
        ] = (
            "Chroma index deletion could not be confirmed."
        )
    else:
        item.pop(
            "index_sync_warning",
            None,
        )

    _add_bin_entry(
        registry,
        {
            "item_type": "file",
            "item_id": normalized_file_id,
            "deleted_at": deleted_at,
            "original_vault_id": (
                original_vault_id
            ),
            "original_vault_name": (
                original_vault_name
            ),
            "original_filename": item.get(
                "filename",
                "",
            ),
            "original_stored_name": item.get(
                "stored_name",
                "",
            ),
            "original_stored_relative_path": item.get(
                "stored_relative_path",
                "",
            ),
        },
    )

    _save_registry(
        registry
    )

    result = dict(
        item
    )

    result[
        "index_deleted"
    ] = index_deleted

    return result


# ---------------------------------------------------------------------------
# RECENT UPLOADS
# ---------------------------------------------------------------------------

def _metadata_mtime_iso(
    path: Path,
) -> str:
    try:
        return datetime.fromtimestamp(
            path.stat().st_mtime,
            timezone.utc,
        ).isoformat()

    except OSError:
        return ""


def list_recent_uploads(
    limit: int = 25,
) -> List[Dict[str, Any]]:
    from app.services.chat_files import (
        CHAT_UPLOADS_DIR as ACTUAL_CHAT_UPLOADS_DIR,
    )

    ACTUAL_CHAT_UPLOADS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        safe_limit = max(
            1,
            min(
                int(limit),
                100,
            ),
        )

    except (
        TypeError,
        ValueError,
    ):
        safe_limit = 25

    registry = _load_registry()

    known = {
        str(
            item.get(
                "file_id",
                "",
            )
        ): item
        for item in registry[
            "files"
        ]
        if (
            isinstance(
                item,
                dict,
            )
            and item.get(
                "file_id"
            )
        )
    }

    recent: List[
        Dict[str, Any]
    ] = []

    for metadata_path in (
        ACTUAL_CHAT_UPLOADS_DIR.glob(
            "*.json"
        )
    ):
        try:
            metadata = json.loads(
                metadata_path.read_text(
                    encoding="utf-8"
                )
            )

        except (
            OSError,
            json.JSONDecodeError,
        ):
            continue

        if not isinstance(
            metadata,
            dict,
        ):
            continue

        file_id = str(
            metadata.get(
                "file_id",
                "",
            )
        ).strip()

        if not file_id:
            continue

        registry_item = known.get(
            file_id
        )

        recent_timestamp = (
            _metadata_mtime_iso(
                metadata_path
            )
        )

        if registry_item:
            if (
                registry_item.get(
                    "status"
                )
                == "deleted"
            ):
                continue

            combined = dict(
                registry_item
            )

            combined[
                "recent_source"
            ] = metadata.get(
                "source",
                registry_item.get(
                    "source",
                    "chat",
                ),
            )

            combined[
                "recent_at"
            ] = (
                recent_timestamp
                or registry_item.get(
                    "created_at",
                    "",
                )
            )

            combined[
                "registered"
            ] = True

            recent.append(
                combined
            )

            continue

        stored_name = str(
            metadata.get(
                "stored_name",
                "",
            )
        ).strip()

        if not stored_name:
            continue

        try:
            stored_path = (
                _safe_chat_file_path(
                    stored_name
                )
            )
        except Exception:
            continue

        if not (
            stored_path.exists()
            and stored_path.is_file()
        ):
            continue

        metadata_sha256 = str(
            metadata.get(
                "sha256",
                metadata.get(
                    "content_sha256",
                    "",
                ),
            )
            or ""
        ).strip()

        combined = {
            "file_id": file_id,
            "vault_id": None,
            "filename": metadata.get(
                "filename",
                stored_path.name,
            ),
            "original_filename": metadata.get(
                "filename",
                stored_path.name,
            ),
            "stored_name": stored_name,
            "stored_relative_path": metadata.get(
                "stored_relative_path",
                (
                    "knowledge/chat_uploads/"
                    f"{stored_name}"
                ),
            ),
            "content_type": metadata.get(
                "content_type",
                "",
            ),
            "extension": metadata.get(
                "extension",
                stored_path.suffix.lower(),
            ),
            "file_type": metadata.get(
                "file_type",
                "document",
            ),
            "size": int(
                metadata.get(
                    "size",
                    metadata.get(
                        "size_bytes",
                        0,
                    ),
                )
                or 0
            ),
            "characters": int(
                metadata.get(
                    "characters",
                    0,
                )
                or 0
            ),
            "chunks": 0,
            "indexed": False,
            "indexed_at": None,
            "content_sha256": metadata_sha256,
            "status": "active",
            "created_at": recent_timestamp,
            "updated_at": recent_timestamp,
            "recent_at": recent_timestamp,
            "source": "chat",
            "recent_source": "chat",
            "registered": False,
        }

        recent.append(
            combined
        )

    recent.sort(
        key=lambda item: str(
            item.get(
                "recent_at",
                item.get(
                    "created_at",
                    "",
                ),
            )
        ),
        reverse=True,
    )

    return recent[
        :safe_limit
    ]


# ---------------------------------------------------------------------------
# BIN
# ---------------------------------------------------------------------------

def list_bin() -> List[Dict[str, Any]]:
    registry = _load_registry()

    result: List[
        Dict[str, Any]
    ] = []

    for entry in registry[
        "bin"
    ]:
        if not isinstance(
            entry,
            dict,
        ):
            continue

        item_type = str(
            entry.get(
                "item_type",
                "",
            )
        ).strip()

        item_id = str(
            entry.get(
                "item_id",
                "",
            )
        ).strip()

        if not item_type or not item_id:
            continue

        output = dict(
            entry
        )

        item = None

        if item_type == "file":
            try:
                item = _find_file(
                    registry,
                    item_id,
                    include_deleted=True,
                )
            except FileNotFoundError:
                item = None

        elif item_type == "vault":
            try:
                item = _find_vault(
                    registry,
                    item_id,
                    include_deleted=True,
                )
            except FileNotFoundError:
                item = None

        if item is not None:
            item_copy = dict(
                item
            )

            output[
                "item"
            ] = item_copy

            if item_type == "file":
                output[
                    "filename"
                ] = item_copy.get(
                    "filename",
                    output.get(
                        "original_filename",
                        "",
                    ),
                )

                output[
                    "name"
                ] = item_copy.get(
                    "filename",
                    output.get(
                        "original_filename",
                        "",
                    ),
                )

                output[
                    "original_vault_name"
                ] = item_copy.get(
                    "deleted_from_vault_name",
                    output.get(
                        "original_vault_name",
                        "",
                    ),
                )

                output[
                    "original_path"
                ] = item_copy.get(
                    "stored_relative_path",
                    output.get(
                        "original_stored_relative_path",
                        "",
                    ),
                )

                output[
                    "original_filename"
                ] = item_copy.get(
                    "filename",
                    output.get(
                        "original_filename",
                        "",
                    ),
                )

            elif item_type == "vault":
                vault_name = item_copy.get(
                    "name",
                    output.get(
                        "original_vault_name",
                        "Deleted Vault",
                    ),
                )

                output[
                    "name"
                ] = vault_name

                output[
                    "vault_name"
                ] = vault_name

        result.append(
            output
        )

    result.sort(
        key=lambda value: str(
            value.get(
                "deleted_at",
                "",
            )
        ),
        reverse=True,
    )

    return result


# ---------------------------------------------------------------------------
# RESTORE
# ---------------------------------------------------------------------------

def restore_file(
    file_id: str,
) -> Dict[str, Any]:
    registry = _load_registry()

    item = _find_file(
        registry,
        file_id,
        include_deleted=True,
    )

    normalized_file_id = str(
        file_id
    ).strip()

    previous_deleted_vault_id = (
        item.get(
            "deleted_from_vault_id"
        )
    )

    restored_vault_id = (
        previous_deleted_vault_id
    )

    if restored_vault_id:
        try:
            vault = _find_vault(
                registry,
                restored_vault_id,
            )

            restored_vault_id = (
                vault["vault_id"]
            )

        except FileNotFoundError:
            restored_vault_id = None

    item["vault_id"] = (
        restored_vault_id
    )

    item["status"] = "active"
    item["deleted_at"] = None
    item["deleted_from_vault_id"] = None
    item["deleted_from_vault_name"] = ""
    item["updated_at"] = _now()

    item["source"] = (
        "knowledge-vault"
        if restored_vault_id
        else "chat"
    )

    _remove_bin_entries(
        registry,
        "file",
        normalized_file_id,
    )

    item["indexed"] = False
    item["chunks"] = 0
    item["indexed_at"] = None

    current_path: Optional[
        Path
    ] = None

    try:
        current_path = (
            _safe_chat_file_path(
                str(
                    item.get(
                        "stored_name",
                        "",
                    )
                )
            )
        )
    except Exception:
        current_path = None

    _save_registry(
        registry
    )

    reindex_result: Dict[
        str,
        Any,
    ] = {
        "indexed": False,
        "chunks": 0,
        "characters": int(
            item.get(
                "characters",
                0,
            )
            or 0
        ),
    }

    if (
        restored_vault_id
        and current_path is not None
    ):
        reindex_result = (
            _reindex_item(
                item,
                path=current_path,
            )
        )

    item["updated_at"] = _now()

    _save_registry(
        registry
    )

    response = dict(
        item
    )

    response[
        "reindex"
    ] = reindex_result

    return response


def restore_vault(
    vault_id: str,
) -> Dict[str, Any]:
    registry = _load_registry()

    vault = _find_vault(
        registry,
        vault_id,
        include_deleted=True,
    )

    normalized_vault_id = str(
        vault_id
    ).strip()

    vault["status"] = "active"
    vault["deleted_at"] = None
    vault["updated_at"] = _now()

    restored_files: List[
        str
    ] = []

    restore_failures: List[
        str
    ] = []

    _save_registry(
        registry
    )

    for item in registry[
        "files"
    ]:
        if (
            not isinstance(
                item,
                dict,
            )
            or str(
                item.get(
                    "deleted_from_vault_id",
                    "",
                )
            ).strip()
            != normalized_vault_id
            or item.get(
                "status"
            ) != "deleted"
        ):
            continue

        current_file_id = str(
            item.get(
                "file_id",
                "",
            )
        ).strip()

        if not current_file_id:
            continue

        item["vault_id"] = (
            normalized_vault_id
        )

        item["status"] = "active"
        item["deleted_at"] = None
        item["deleted_from_vault_id"] = None
        item["deleted_from_vault_name"] = ""
        item["updated_at"] = _now()
        item["source"] = "knowledge-vault"
        item["indexed"] = False
        item["chunks"] = 0
        item["indexed_at"] = None

        restored_files.append(
            current_file_id
        )

        try:
            current_path = (
                _safe_chat_file_path(
                    str(
                        item.get(
                            "stored_name",
                            "",
                        )
                    )
                )
            )

            reindex_result = (
                _reindex_item(
                    item,
                    path=current_path,
                )
            )

            if not reindex_result.get(
                "indexed"
            ):
                restore_failures.append(
                    current_file_id
                )

        except Exception as exc:
            print(
                "[NOVA VAULT RESTORE INDEX] "
                f"{type(exc).__name__}: {exc}"
            )

            restore_failures.append(
                current_file_id
            )

        _remove_bin_entries(
            registry,
            "file",
            current_file_id,
        )

    _remove_bin_entries(
        registry,
        "vault",
        normalized_vault_id,
    )

    _save_registry(
        registry
    )

    result = dict(
        vault
    )

    result[
        "restored_files"
    ] = restored_files

    result[
        "restore_index_failures"
    ] = restore_failures

    return result


# ---------------------------------------------------------------------------
# PERMANENT DELETE
# ---------------------------------------------------------------------------

def permanent_delete_file(
    file_id: str,
) -> Dict[str, Any]:
    registry = _load_registry()

    item = _find_file(
        registry,
        file_id,
        include_deleted=True,
    )

    normalized_file_id = str(
        file_id
    ).strip()

    stored_name = str(
        item.get(
            "stored_name",
            "",
        )
    ).strip()

    physical_deleted = False
    metadata_deleted = False
    index_deleted = False

    if stored_name:
        try:
            path = _safe_chat_file_path(
                stored_name
            )

            if path.exists():
                if not path.is_file():
                    raise RuntimeError(
                        "Stored vault path is not a file."
                    )

                path.unlink()

            physical_deleted = True

        except Exception as exc:
            print(
                "[NOVA VAULT FILE DELETE] "
                f"{type(exc).__name__}: {exc}"
            )

    metadata_path = _safe_metadata_path(
        normalized_file_id
    )

    if metadata_path.exists():
        try:
            metadata_path.unlink()

            metadata_deleted = True

        except OSError as exc:
            print(
                "[NOVA VAULT METADATA DELETE] "
                f"{type(exc).__name__}: {exc}"
            )
    else:
        metadata_deleted = True

    index_deleted = _delete_index(
        file_id=normalized_file_id,
        filename=str(
            item.get(
                "filename",
                "",
            )
        ),
    )

    registry["files"] = [
        candidate
        for candidate in registry[
            "files"
        ]
        if str(
            candidate.get(
                "file_id",
                "",
            )
        ).strip()
        != normalized_file_id
    ]

    _remove_bin_entries(
        registry,
        "file",
        normalized_file_id,
    )

    _save_registry(
        registry
    )

    return {
        "deleted": True,
        "file_id": normalized_file_id,
        "physical_file_deleted": (
            physical_deleted
        ),
        "metadata_deleted": (
            metadata_deleted
        ),
        "index_deleted": (
            index_deleted
        ),
    }


def permanent_delete_vault(
    vault_id: str,
) -> Dict[str, Any]:
    normalized_vault_id = str(
        vault_id or ""
    ).strip()

    if not normalized_vault_id:
        raise FileNotFoundError(
            "Vault ID is required."
        )

    registry = _load_registry()

    _find_vault(
        registry,
        normalized_vault_id,
        include_deleted=True,
    )

    file_ids = [
        str(
            item.get(
                "file_id",
                "",
            )
        ).strip()
        for item in registry[
            "files"
        ]
        if (
            isinstance(
                item,
                dict,
            )
            and (
                str(
                    item.get(
                        "vault_id",
                        "",
                    )
                ).strip()
                == normalized_vault_id
                or str(
                    item.get(
                        "deleted_from_vault_id",
                        "",
                    )
                ).strip()
                == normalized_vault_id
            )
        )
    ]

    unique_file_ids = list(
        dict.fromkeys(
            file_id
            for file_id in file_ids
            if file_id
        )
    )

    deleted_files: List[
        str
    ] = []

    failed_files: List[
        str
    ] = []

    for current_file_id in (
        unique_file_ids
    ):
        try:
            result = (
                permanent_delete_file(
                    current_file_id
                )
            )

            if result.get(
                "deleted"
            ):
                if (
                    result.get(
                        "physical_file_deleted",
                        False,
                    )
                    and result.get(
                        "metadata_deleted",
                        False,
                    )
                    and result.get(
                        "index_deleted",
                        False,
                    )
                ):
                    deleted_files.append(
                        current_file_id
                    )
                else:
                    failed_files.append(
                        current_file_id
                    )

        except FileNotFoundError:
            continue

        except Exception as exc:
            print(
                "[NOVA VAULT PERMANENT DELETE] "
                f"{type(exc).__name__}: {exc}"
            )

            failed_files.append(
                current_file_id
            )

    registry = _load_registry()

    registry["vaults"] = [
        candidate
        for candidate in registry[
            "vaults"
        ]
        if str(
            candidate.get(
                "vault_id",
                "",
            )
        ).strip()
        != normalized_vault_id
    ]

    _remove_bin_entries(
        registry,
        "vault",
        normalized_vault_id,
    )

    registry["bin"] = [
        entry
        for entry in registry[
            "bin"
        ]
        if not (
            str(
                entry.get(
                    "item_type",
                    "",
                )
            ).strip()
            == "file"
            and str(
                entry.get(
                    "original_vault_id",
                    "",
                )
            ).strip()
            == normalized_vault_id
        )
    ]

    _save_registry(
        registry
    )

    return {
        "deleted": True,
        "vault_id": normalized_vault_id,
        "deleted_files": deleted_files,
        "failed_files": failed_files,
    }


# ---------------------------------------------------------------------------
# RE-INDEX / STATE API
# ---------------------------------------------------------------------------

def reindex_file(
    file_id: str,
    characters: Optional[int] = None,
    chunks: Optional[int] = None,
    indexed: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Public registry synchronization API.

    Mode 1:
        reindex_file(file_id)

    Runs the real extractor + Chroma indexing pipeline.

    Mode 2:
        reindex_file(
            file_id,
            characters=...,
            chunks=...,
            indexed=...,
        )

    Synchronizes already-computed indexing state.
    """

    registry = _load_registry()

    item = _find_file(
        registry,
        file_id,
    )

    # -----------------------------------------------------------------------
    # REAL RE-INDEX
    # -----------------------------------------------------------------------

    if (
        characters is None
        and chunks is None
        and indexed is None
    ):
        result = _reindex_item(
            item
        )

        item["updated_at"] = _now()

        _save_registry(
            registry
        )

        response = dict(
            item
        )

        response[
            "reindex"
        ] = result

        return response

    # -----------------------------------------------------------------------
    # SYNCHRONIZATION MODE
    # -----------------------------------------------------------------------

    if characters is not None:
        item["characters"] = max(
            0,
            int(
                characters or 0
            ),
        )

    if chunks is not None:
        item["chunks"] = max(
            0,
            int(
                chunks or 0
            ),
        )

    if indexed is not None:
        item["indexed"] = bool(
            indexed
        )

        if not item["indexed"]:
            item["indexed_at"] = None
        elif not item.get(
            "indexed_at"
        ):
            item["indexed_at"] = (
                _now()
            )

    item["updated_at"] = _now()

    _save_registry(
        registry
    )

    response = dict(
        item
    )

    response[
        "reindex"
    ] = {
        "indexed": bool(
            item.get(
                "indexed",
                False,
            )
        ),
        "chunks": int(
            item.get(
                "chunks",
                0,
            )
            or 0
        ),
        "characters": int(
            item.get(
                "characters",
                0,
            )
            or 0
        ),
        "indexed_at": item.get(
            "indexed_at"
        ),
        "content_sha256": item.get(
            "content_sha256",
            "",
        ),
    }

    return response


def update_index_state(
    file_id: str,
    *,
    indexed: bool,
    chunks: int = 0,
    characters: int = 0,
) -> Dict[str, Any]:
    registry = _load_registry()

    item = _find_file(
        registry,
        file_id,
    )

    item["indexed"] = bool(
        indexed
    )

    item["chunks"] = max(
        0,
        int(
            chunks or 0
        ),
    )

    item["characters"] = max(
        0,
        int(
            characters or 0
        ),
    )

    if item["indexed"]:
        item["indexed_at"] = (
            item.get(
                "indexed_at"
            )
            or _now()
        )
    else:
        item["indexed_at"] = None

    item["updated_at"] = _now()

    _save_registry(
        registry
    )

    return dict(
        item
    )


# ---------------------------------------------------------------------------
# STATISTICS
# ---------------------------------------------------------------------------

def get_stats() -> Dict[str, Any]:
    registry = _load_registry()

    active_vaults = [
        item
        for item in registry[
            "vaults"
        ]
        if (
            isinstance(
                item,
                dict,
            )
            and item.get(
                "status"
            ) == "active"
        )
    ]

    active_files = [
        item
        for item in registry[
            "files"
        ]
        if (
            isinstance(
                item,
                dict,
            )
            and item.get(
                "status"
            ) == "active"
        )
    ]

    indexed_files = [
        item
        for item in active_files
        if bool(
            item.get(
                "indexed"
            )
        )
    ]

    total_chunks = sum(
        max(
            0,
            int(
                item.get(
                    "chunks",
                    0,
                )
                or 0
            ),
        )
        for item in active_files
    )

    total_characters = sum(
        max(
            0,
            int(
                item.get(
                    "characters",
                    0,
                )
                or 0
            ),
        )
        for item in active_files
    )

    return {
        "vaults": len(
            active_vaults
        ),
        "files": len(
            active_files
        ),
        "indexed_files": len(
            indexed_files
        ),
        "chunks": total_chunks,
        "total_chunks": total_chunks,
        "total_characters": total_characters,
        "bin_items": len(
            registry[
                "bin"
            ]
        ),
    }