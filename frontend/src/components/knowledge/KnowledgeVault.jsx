import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AlertCircle,
  Archive,
  ArrowRight,
  CheckCircle2,
  Database,
  Download,
  Eye,
  File,
  FileArchive,
  FileCode,
  FileImage,
  FileSpreadsheet,
  FileText,
  Folder,
  FolderOpen,
  FolderPlus,
  Grid2X2,
  HardDrive,
  History,
  Layers,
  Loader2,
  MoreHorizontal,
  Plus,
  RefreshCw,
  RotateCcw,
  Scan,
  Search,
  Shield,
  ShieldCheck,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import {
  motion,
  AnimatePresence,
} from "framer-motion";

const API_URL =
  "http://127.0.0.1:8001";

const ACCEPTED_FILES =
  ".pdf,.docx,.txt,.csv,.xlsx,.png,.jpg,.jpeg,.webp";

const MAX_UPLOAD_SIZE =
  20 * 1024 * 1024;

const REQUEST_TIMEOUT =
  15000;

const VISUAL_PREVIEW_EXTENSIONS =
  new Set([
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "webp",
  ]);

function formatBytes(bytes) {
  if (
    !Number.isFinite(
      Number(bytes),
    ) ||
    Number(bytes) <= 0
  ) {
    return "0 B";
  }

  const numericBytes =
    Number(bytes);

  const units = [
    "B",
    "KB",
    "MB",
    "GB",
  ];

  const exponent = Math.min(
    Math.floor(
      Math.log(
        numericBytes,
      ) /
        Math.log(1024),
    ),
    units.length - 1,
  );

  return `${(
    numericBytes /
    1024 ** exponent
  ).toFixed(
    exponent === 0 ? 0 : 1,
  )} ${units[exponent]}`;
}

function formatNumber(value) {
  const number =
    Number(value);

  if (
    !Number.isFinite(number)
  ) {
    return "0";
  }

  return new Intl.NumberFormat(
    "en-IN",
  ).format(number);
}

function formatDate(value) {
  if (!value) {
    return "—";
  }

  const date =
    new Date(value);

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return "—";
  }

  return date.toLocaleString(
    "en-IN",
    {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    },
  );
}

function getFileExtension(
  filename = "",
) {
  const value =
    String(filename).toLowerCase();

  const index =
    value.lastIndexOf(".");

  return index >= 0
    ? value.slice(index + 1)
    : "";
}

function isVisualPreviewFile(
  filename = "",
) {
  return VISUAL_PREVIEW_EXTENSIONS.has(
    getFileExtension(filename),
  );
}

function isPdfFile(
  filename = "",
) {
  return (
    getFileExtension(
      filename,
    ) === "pdf"
  );
}

function isImageFile(
  filename = "",
) {
  return [
    "png",
    "jpg",
    "jpeg",
    "webp",
  ].includes(
    getFileExtension(
      filename,
    ),
  );
}

function isDocxFile(
  filename = "",
) {
  return [
    "doc",
    "docx",
  ].includes(
    getFileExtension(
      filename,
    ),
  );
}

function isSpreadsheetFile(
  filename = "",
) {
  return [
    "xlsx",
    "xls",
    "csv",
  ].includes(
    getFileExtension(
      filename,
    ),
  );
}

function isTxtFile(
  filename = "",
) {
  return [
    "txt",
    "md",
    "json",
    "py",
    "js",
    "html",
    "css",
    "c",
    "cpp",
    "java",
    "sh",
    "yaml",
    "yml",
    "log",
  ].includes(
    getFileExtension(
      filename,
    ),
  );
}

function parseSpreadsheetData(
  rawText = "",
) {
  if (!rawText || !rawText.trim()) return null;

  const lines = rawText.split("\n");
  const sheets = [];
  let currentSheet = { name: "Sheet 1", rows: [] };

  for (let rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue;

    const sheetMatch = line.match(/^\[SHEET\s*\d*:\s*(.*?)\]/i);
    if (sheetMatch) {
      if (currentSheet.rows.length > 0) {
        sheets.push(currentSheet);
      }
      currentSheet = {
        name: sheetMatch[1].trim() || `Sheet ${sheets.length + 1}`,
        rows: [],
      };
      continue;
    }

    let rowContent = line;
    const rowMatch = line.match(/^\[ROW\s*\d+\]\s*(.*)/i);
    if (rowMatch) {
      rowContent = rowMatch[1];
    }

    let cells = [];
    if (rowContent.includes(" | ")) {
      cells = rowContent.split(" | ").map((c) => c.trim());
    } else if (rowContent.includes("\t")) {
      cells = rowContent.split("\t").map((c) => c.trim());
    } else if (rowContent.includes(",")) {
      cells = rowContent.split(",").map((c) => c.trim());
    } else {
      cells = [rowContent];
    }

    if (cells.length > 0 && cells.some((c) => c !== "")) {
      currentSheet.rows.push(cells);
    }
  }

  if (currentSheet.rows.length > 0) {
    sheets.push(currentSheet);
  }

  return sheets.length > 0 ? sheets : null;
}

function SpreadsheetPreview({ text }) {
  const sheets = useMemo(() => parseSpreadsheetData(text), [text]);
  const [activeSheetIdx, setActiveSheetIdx] = useState(0);

  if (!sheets || sheets.length === 0) {
    return (
      <div className="nova-knowledge-preview-text-card">
        <pre className="nova-knowledge-preview-content">
          {text || "No readable content in spreadsheet."}
        </pre>
      </div>
    );
  }

  const currentSheet = sheets[activeSheetIdx] || sheets[0];
  const rows = currentSheet.rows;
  const headerRow = rows[0] || [];
  const bodyRows = rows.slice(1);

  return (
    <div className="nova-spreadsheet-wrap">
      {sheets.length > 1 && (
        <div className="nova-spreadsheet-tabs">
          {sheets.map((sheet, idx) => (
            <button
              key={idx}
              type="button"
              className={`nova-spreadsheet-tab ${
                idx === activeSheetIdx ? "active" : ""
              }`}
              onClick={() => setActiveSheetIdx(idx)}
            >
              {sheet.name}
            </button>
          ))}
        </div>
      )}
      <div className="nova-spreadsheet-table-container">
        <table className="nova-spreadsheet-table">
          <thead>
            <tr>
              <th className="nova-spreadsheet-row-num">#</th>
              {headerRow.map((cell, cIdx) => (
                <th key={cIdx}>{cell || `Col ${cIdx + 1}`}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {bodyRows.length > 0 ? (
              bodyRows.map((row, rIdx) => (
                <tr key={rIdx}>
                  <td className="nova-spreadsheet-row-num">{rIdx + 1}</td>
                  {headerRow.map((_, cIdx) => (
                    <td key={cIdx}>
                      {row[cIdx] !== undefined ? row[cIdx] : ""}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td className="nova-spreadsheet-row-num">1</td>
                {headerRow.map((cell, cIdx) => (
                  <td key={cIdx}>{cell}</td>
                ))}
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TxtViewerPreview({ text, filename }) {
  const lines = useMemo(() => (text ? text.split("\n") : []), [text]);

  return (
    <div className="nova-txt-viewer-wrap">
      <div className="nova-txt-viewer-header">
        <span>{filename}</span>
        <span>
          {lines.length} {lines.length === 1 ? "line" : "lines"}
        </span>
      </div>
      <pre className="nova-txt-viewer-content">
        {text || "No content in text file."}
      </pre>
    </div>
  );
}

function DocxSheetPreview({ text, filename }) {
  if (!text || !text.trim()) {
    return (
      <div className="nova-empty-state nova-document-empty">
        <FileText size={24} />
        <strong>Empty Document</strong>
        <span>No text could be extracted from this document file.</span>
      </div>
    );
  }

  const paragraphs = text.split(/\n\s*\n/).filter((p) => p.trim());

  return (
    <div className="nova-document-sheet-wrap">
      <div className="nova-document-sheet">
        <h1 className="nova-document-sheet-title">{filename}</h1>
        {paragraphs.map((para, idx) => {
          const trimmed = para.trim();
          if (
            trimmed.length < 80 &&
            (trimmed === trimmed.toUpperCase() ||
              trimmed.endsWith(":") ||
              idx === 0)
          ) {
            return (
              <h2 key={idx} className="nova-document-sheet-heading">
                {trimmed}
              </h2>
            );
          }
          return (
            <p key={idx} className="nova-document-sheet-paragraph">
              {trimmed}
            </p>
          );
        })}
      </div>
    </div>
  );
}

function getVisualMimeType(
  filename = "",
) {
  const extension =
    getFileExtension(
      filename,
    );

  if (
    extension === "pdf"
  ) {
    return "application/pdf";
  }

  if (
    extension === "png"
  ) {
    return "image/png";
  }

  if (
    extension === "jpg" ||
    extension === "jpeg"
  ) {
    return "image/jpeg";
  }

  if (
    extension === "webp"
  ) {
    return "image/webp";
  }

  return "";
}

function getFileDownloadUrl(
  fileId,
) {
  return `${API_URL}/api/knowledge/files/${encodeURIComponent(
    fileId,
  )}/download`;
}

function getFileIcon(
  filename = "",
) {
  const extension =
    getFileExtension(
      filename,
    );

  if (
    ["xlsx", "csv"].includes(
      extension,
    )
  ) {
    return FileSpreadsheet;
  }

  if (
    [
      "png",
      "jpg",
      "jpeg",
      "webp",
    ].includes(
      extension,
    )
  ) {
    return FileImage;
  }

  if (
    [
      "pdf",
      "docx",
      "txt",
    ].includes(
      extension,
    )
  ) {
    return FileText;
  }

  if (
    [
      "zip",
      "rar",
      "7z",
    ].includes(
      extension,
    )
  ) {
    return FileArchive;
  }

  return File;
}

function normalizeVault(
  vault,
) {
  if (
    !vault ||
    typeof vault !==
      "object"
  ) {
    return null;
  }

  return {
    ...vault,
    id:
      vault?.id ||
      vault?.vault_id ||
      null,
    name:
      vault?.name ||
      "Untitled Vault",
    description:
      vault?.description ||
      "",
    file_count: Number(
      vault?.file_count ??
        vault?.files_count ??
        0,
    ),
    indexed_count: Number(
      vault?.indexed_count ??
        0,
    ),
    chunks: Number(
      vault?.chunks ??
        0,
    ),
    characters: Number(
      vault?.characters ??
        0,
    ),
    created_at:
      vault?.created_at ||
      null,
    updated_at:
      vault?.updated_at ||
      vault?.created_at ||
      null,
    status:
      vault?.status ||
      "active",
  };
}

function normalizeFile(
  file,
) {
  if (
    !file ||
    typeof file !==
      "object"
  ) {
    return null;
  }

  return {
    ...file,
    id:
      file?.id ||
      file?.file_id ||
      null,
    filename:
      file?.filename ||
      file?.name ||
      file?.original_filename ||
      "Untitled file",
    vault_id:
      file?.vault_id ||
      null,
    indexed:
      Boolean(
        file?.indexed,
      ),
    characters: Number(
      file?.characters ??
        0,
    ),
    chunks: Number(
      file?.chunks ??
        0,
    ),
    size: Number(
      file?.size ??
        file?.size_bytes ??
        0,
    ),
    content_type:
      file?.content_type ||
      "",
    extension:
      file?.extension ||
      `.${getFileExtension(
        file?.filename ||
          file?.name ||
          "",
      )}`,
    file_type:
      file?.file_type ||
      "document",
    created_at:
      file?.created_at ||
      file?.uploaded_at ||
      file?.recent_at ||
      null,
    updated_at:
      file?.updated_at ||
      file?.recent_at ||
      file?.created_at ||
      null,
    indexed_at:
      file?.indexed_at ||
      null,
    deleted_at:
      file?.deleted_at ||
      null,
    original_vault_id:
      file?.original_vault_id ||
      file?.source_vault_id ||
      file?.deleted_from_vault_id ||
      null,
    original_vault_name:
      file?.original_vault_name ||
      file?.source_vault_name ||
      file?.deleted_from_vault_name ||
      null,
    original_path:
      file?.original_path ||
      file?.original_stored_relative_path ||
      file?.stored_relative_path ||
      "",
    stored_relative_path:
      file?.stored_relative_path ||
      "",
    stored_name:
      file?.stored_name ||
      "",
    content_sha256:
      file?.content_sha256 ||
      file?.sha256 ||
      "",
    source:
      file?.source ||
      file?.recent_source ||
      "",
    registered:
      file?.registered !== false,
  };
}

function normalizeBinItem(
  item,
) {
  if (
    !item ||
    typeof item !==
      "object"
  ) {
    return null;
  }

  const itemType =
    String(
      item?.item_type ||
        item?.type ||
        "",
    )
      .trim()
      .toLowerCase();

  const itemId =
    String(
      item?.item_id ||
        item?.id ||
        item?.file_id ||
        item?.vault_id ||
        item?.item?.file_id ||
        item?.item?.vault_id ||
        "",
    ).trim();

  if (
    !itemType ||
    !itemId
  ) {
    return null;
  }

  const nested =
    item?.item &&
    typeof item.item ===
      "object"
      ? item.item
      : {};

  const filename =
    item?.original_filename ||
    item?.filename ||
    nested?.filename ||
    nested?.original_filename ||
    "";

  const name =
    item?.name ||
    item?.vault_name ||
    nested?.name ||
    nested?.vault_name ||
    filename ||
    "Deleted item";

  return {
    ...item,
    item_type:
      itemType,
    item_id:
      itemId,
    name,
    filename,
    original_filename:
      item?.original_filename ||
      nested?.filename ||
      filename ||
      "",
    original_vault_id:
      item?.original_vault_id ||
      nested?.deleted_from_vault_id ||
      null,
    original_vault_name:
      item?.original_vault_name ||
      nested?.deleted_from_vault_name ||
      "",
    original_path:
      item?.original_path ||
      item?.original_stored_relative_path ||
      nested?.stored_relative_path ||
      "",
    deleted_at:
      item?.deleted_at ||
      nested?.deleted_at ||
      null,
    item: nested,
  };
}

/* ---------------------------------------------------------------------------
   REAL FILE THUMBNAIL

   Images use the real backend download endpoint directly and lazy-load.
   PDFs/documents keep lightweight file icons in the registry.
   --------------------------------------------------------------------------- */

function FileThumbnail({
  file,
  size = "normal",
}) {
  const [
    imageFailed,
    setImageFailed,
  ] = useState(false);

  useEffect(() => {
    setImageFailed(false);
  }, [
    file?.id,
    file?.filename,
  ]);

  const Icon =
    getFileIcon(
      file?.filename,
    );

  const visualClass =
    size === "small"
      ? "is-small"
      : "is-normal";

  const image =
    isImageFile(
      file?.filename,
    ) &&
    Boolean(file?.id);

  if (
    !image ||
    imageFailed
  ) {
    return (
      <div
        className={`nova-knowledge-file-icon ${visualClass}`}
        aria-hidden="true"
      >
        <Icon
          size={
            size ===
            "small"
              ? 18
              : 20
          }
        />
      </div>
    );
  }

  return (
    <div
      className={`nova-knowledge-file-icon ${visualClass}`}
      style={{
        overflow:
          "hidden",
        padding: 0,
        background:
          "#05090e",
      }}
      title={
        file?.filename ||
        "Image"
      }
    >
      <img
        src={getFileDownloadUrl(
          file.id,
        )}
        alt={
          file?.filename ||
          ""
        }
        loading="lazy"
        decoding="async"
        onError={() =>
          setImageFailed(
            true,
          )
        }
        style={{
          display:
            "block",
          width: "100%",
          height: "100%",
          objectFit:
            "cover",
        }}
      />
    </div>
  );
}

/* ---------------------------------------------------------------------------
   MAIN COMPONENT
   --------------------------------------------------------------------------- */

function KnowledgeVault() {
  const fileInputRef =
    useRef(null);

  const previewAssetUrlRef =
    useRef("");

  const [loading, setLoading] =
    useState(true);

  const [refreshing, setRefreshing] =
    useState(false);

  const [vaults, setVaults] =
    useState([]);

  const [activeVaultId, setActiveVaultId] =
    useState("all");

  const [vaultFiles, setVaultFiles] =
    useState([]);

  const [recentUploads, setRecentUploads] =
    useState([]);

  const [binItems, setBinItems] =
    useState([]);

  const [stats, setStats] =
    useState({
      vaults: 0,
      files: 0,
      indexed_files: 0,
      bin_items: 0,
      total_characters: 0,
      total_chunks: 0,
    });

  const [query, setQuery] =
    useState("");

  const [searching, setSearching] =
    useState(false);

  const [results, setResults] =
    useState([]);

  const [selectedFiles, setSelectedFiles] =
    useState([]);

  const [
    selectedBinItems,
    setSelectedBinItems,
  ] = useState([]);

  const [uploading, setUploading] =
    useState(false);

  const [pendingFile, setPendingFile] =
    useState(null);

  const [
    createVaultOpen,
    setCreateVaultOpen,
  ] = useState(false);

  const [creatingVault, setCreatingVault] =
    useState(false);

  const [newVaultName, setNewVaultName] =
    useState("");

  const [renameTarget, setRenameTarget] =
    useState(null);

  const [renameValue, setRenameValue] =
    useState("");

  const [renaming, setRenaming] =
    useState(false);

  const [movingFile, setMovingFile] =
    useState(null);

  const [moving, setMoving] =
    useState(false);

  const [previewFile, setPreviewFile] =
    useState(null);

  const [previewData, setPreviewData] =
    useState(null);

  const [previewLoading, setPreviewLoading] =
    useState(false);

  const [previewAssetUrl, setPreviewAssetUrl] =
    useState("");

  const [
    previewMode,
    setPreviewMode,
  ] = useState("visual");

  const [
    previewVisualFailed,
    setPreviewVisualFailed,
  ] = useState(false);

  const [openMenu, setOpenMenu] =
    useState(null);

  const [toast, setToast] =
    useState({
      type: "",
      text: "",
    });

  const [error, setError] =
    useState("");

  const activeVault =
    useMemo(
      () =>
        vaults.find(
          (vault) =>
            vault.id ===
            activeVaultId,
        ) || null,
      [
        vaults,
        activeVaultId,
      ],
    );

  const visibleFiles =
    useMemo(() => {
      if (
        activeVaultId ===
        "all"
      ) {
        return vaultFiles;
      }

      return vaultFiles.filter(
        (file) =>
          file.vault_id ===
          activeVaultId,
      );
    }, [
      vaultFiles,
      activeVaultId,
    ]);

  const indexedCount =
    useMemo(
      () =>
        visibleFiles.filter(
          (file) =>
            file.indexed,
        ).length,
      [
        visibleFiles,
      ],
    );

  const previewIsVisual =
    Boolean(
      previewFile &&
      isVisualPreviewFile(
        previewFile.filename,
      ),
    );

  useEffect(() => {
    previewAssetUrlRef.current =
      previewAssetUrl;
  }, [
    previewAssetUrl,
  ]);

  useEffect(() => {
    return () => {
      if (
        previewAssetUrlRef.current
      ) {
        window.URL.revokeObjectURL(
          previewAssetUrlRef.current,
        );
      }
    };
  }, []);

  const notify = (
    type,
    text,
  ) => {
    setToast({
      type,
      text,
    });

    window.setTimeout(
      () => {
        setToast({
          type: "",
          text: "",
        });
      },
      3500,
    );
  };

  const apiRequest =
    async (
      endpoint,
      options = {},
    ) => {
      const controller =
        new AbortController();

      const timeoutId =
        window.setTimeout(
          () =>
            controller.abort(),
          REQUEST_TIMEOUT,
        );

      try {
        const response =
          await fetch(
            `${API_URL}${endpoint}`,
            {
              ...options,
              signal:
                controller.signal,
            },
          );

        let data = {};

        try {
          data =
            await response.json();
        } catch {
          data = {};
        }

        if (
          !response.ok
        ) {
          throw new Error(
            data?.detail ||
              data?.message ||
              `Request failed with status ${response.status}.`,
          );
        }

        return data;
      } catch (
        requestError
      ) {
        if (
          requestError?.name ===
          "AbortError"
        ) {
          throw new Error(
            "Knowledge Vault request timed out. Check that the NOVA backend is running.",
          );
        }

        if (
          requestError instanceof
          TypeError
        ) {
          throw new Error(
            "Unable to reach the NOVA backend. Make sure port 8001 is running.",
          );
        }

        throw requestError;
      } finally {
        window.clearTimeout(
          timeoutId,
        );
      }
    };

  const fetchVisualAsset =
    async (
      file,
    ) => {
      if (
        !file?.id ||
        !isVisualPreviewFile(
          file.filename,
        )
      ) {
        return null;
      }

      const controller =
        new AbortController();

      const timeoutId =
        window.setTimeout(
          () =>
            controller.abort(),
          REQUEST_TIMEOUT,
        );

      try {
        const response =
          await fetch(
            getFileDownloadUrl(
              file.id,
            ),
            {
              signal:
                controller.signal,
            },
          );

        if (
          !response.ok
        ) {
          throw new Error(
            "Visual preview could not be loaded.",
          );
        }

        const blob =
          await response.blob();

        const objectUrl =
          window.URL.createObjectURL(
            blob,
          );

        return objectUrl;
      } catch (
        assetError
      ) {
        if (
          assetError?.name ===
          "AbortError"
        ) {
          throw new Error(
            "Visual preview timed out.",
          );
        }

        throw assetError;
      } finally {
        window.clearTimeout(
          timeoutId,
        );
      }
    };

  const releasePreviewAsset =
    () => {
      if (
        previewAssetUrlRef.current
      ) {
        window.URL.revokeObjectURL(
          previewAssetUrlRef.current,
        );

        previewAssetUrlRef.current =
          "";
      }

      setPreviewAssetUrl(
        "",
      );
    };

  const setPreviewAsset =
    (
      value,
    ) => {
      if (
        previewAssetUrlRef.current
      ) {
        window.URL.revokeObjectURL(
          previewAssetUrlRef.current,
        );
      }

      previewAssetUrlRef.current =
        value || "";

      setPreviewAssetUrl(
        value || "",
      );
    };

  const closePreview =
    () => {
      releasePreviewAsset();

      setPreviewFile(
        null,
      );

      setPreviewData(
        null,
      );

      setPreviewMode(
        "visual",
      );

      setPreviewVisualFailed(
        false,
      );
    };

  const applyStats = (
    data,
  ) => {
    setStats({
      vaults: Number(
        data?.vaults ??
          0,
      ),
      files: Number(
        data?.files ??
          0,
      ),
      indexed_files:
        Number(
          data?.indexed_files ??
            0,
        ),
      bin_items:
        Number(
          data?.bin_items ??
            0,
        ),
      total_characters:
        Number(
          data?.total_characters ??
            0,
        ),
      total_chunks:
        Number(
          data?.total_chunks ??
            data?.chunks ??
            0,
        ),
    });
  };

  const loadFilesForVault =
    async (
      vaultId,
    ) => {
      const data =
        await apiRequest(
          `/api/knowledge/vaults/${encodeURIComponent(
            vaultId,
          )}/files`,
        );

      if (
        !Array.isArray(
          data?.files,
        )
      ) {
        return [];
      }

      return data.files
        .map(
          normalizeFile,
        )
        .filter(
          Boolean,
        );
    };

  const loadVaultFiles =
    async (
      vaultList,
    ) => {
      if (
        !Array.isArray(
          vaultList,
        ) ||
        vaultList.length ===
          0
      ) {
        return [];
      }

      const responses =
        await Promise.allSettled(
          vaultList.map(
            (
              vault,
            ) =>
              loadFilesForVault(
                vault.id,
              ),
          ),
        );

      const uniqueFiles =
        new Map();

      responses.forEach(
        (
          response,
        ) => {
          if (
            response.status !==
            "fulfilled"
          ) {
            return;
          }

          response.value.forEach(
            (
              file,
            ) => {
              if (
                file?.id
              ) {
                uniqueFiles.set(
                  file.id,
                  file,
                );
              }
            },
          );
        },
      );

      return Array.from(
        uniqueFiles.values(),
      );
    };

  const loadSupportingData =
    async () => {
      const [
        statsResult,
        recentResult,
        binResult,
      ] =
        await Promise.allSettled(
          [
            apiRequest(
              "/api/knowledge/stats",
            ),
            apiRequest(
              "/api/knowledge/recent",
            ),
            apiRequest(
              "/api/knowledge/bin",
            ),
          ],
        );

      if (
        statsResult.status ===
        "fulfilled"
      ) {
        applyStats(
          statsResult.value,
        );
      }

      if (
        recentResult.status ===
        "fulfilled"
      ) {
        const normalizedRecent =
          Array.isArray(
            recentResult
              .value?.files,
          )
            ? recentResult.value.files
                .map(
                  normalizeFile,
                )
                .filter(
                  Boolean,
                )
            : [];

        setRecentUploads(
          normalizedRecent,
        );
      }

      if (
        binResult.status ===
        "fulfilled"
      ) {
        const normalizedBin =
          Array.isArray(
            binResult
              .value?.items,
          )
            ? binResult.value.items
                .map(
                  normalizeBinItem,
                )
                .filter(
                  Boolean,
                )
            : [];

        setBinItems(
          normalizedBin,
        );
      }

      return {
        statsOk:
          statsResult.status ===
          "fulfilled",
        recentOk:
          recentResult.status ===
          "fulfilled",
        binOk:
          binResult.status ===
          "fulfilled",
      };
    };

  const refreshData =
    async ({
      silent = false,
      showErrors = true,
    } = {}) => {
      if (
        silent
      ) {
        setRefreshing(
          true,
        );
      } else {
        setLoading(
          true,
        );
      }

      if (
        showErrors
      ) {
        setError("");
      }

      try {
        const vaultData =
          await apiRequest(
            "/api/knowledge/vaults",
          );

        const normalizedVaults =
          Array.isArray(
            vaultData?.vaults,
          )
            ? vaultData.vaults
                .map(
                  normalizeVault,
                )
                .filter(
                  Boolean,
                )
            : [];

        setVaults(
          normalizedVaults,
        );

        const currentActive =
          activeVaultId;

        if (
          currentActive !==
            "all" &&
          !normalizedVaults.some(
            (vault) =>
              vault.id ===
              currentActive,
          )
        ) {
          setActiveVaultId(
            "all",
          );
        }

        const files =
          await loadVaultFiles(
            normalizedVaults,
          );

        setVaultFiles(
          files,
        );

        const supporting =
          await loadSupportingData();

        if (
          showErrors &&
          (
            !supporting.statsOk ||
            !supporting.recentOk ||
            !supporting.binOk
          )
        ) {
          setError(
            "Some Knowledge Vault data could not be refreshed. Available local data is still shown.",
          );
        }

        return {
          vaults:
            normalizedVaults,
          files,
        };
      } catch (
        loadError
      ) {
        if (
          showErrors
        ) {
          setError(
            loadError instanceof
              Error
              ? loadError.message
              : "Unable to load Knowledge Vault.",
          );
        }

        return {
          vaults:
            vaults,
          files:
            vaultFiles,
        };
      } finally {
        setLoading(
          false,
        );

        setRefreshing(
          false,
        );
      }
    };

  useEffect(() => {
    refreshData();

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (
      loading ||
      !activeVaultId ||
      activeVaultId ===
        "all"
    ) {
      return;
    }

    let cancelled =
      false;

    loadFilesForVault(
      activeVaultId,
    )
      .then(
        (
          files,
        ) => {
          if (
            cancelled
          ) {
            return;
          }

          setVaultFiles(
            (
              current,
            ) => {
              const incoming =
                new Map(
                  files.map(
                    (
                      file,
                    ) => [
                      file.id,
                      file,
                    ],
                  ),
                );

              const next =
                current.filter(
                  (
                    file,
                  ) => {
                    if (
                      file.vault_id !==
                      activeVaultId
                    ) {
                      return true;
                    }

                    return incoming.has(
                      file.id,
                    );
                  },
                );

              const existing =
                new Map(
                  next.map(
                    (
                      file,
                    ) => [
                      file.id,
                      file,
                    ],
                  ),
                );

              files.forEach(
                (
                  file,
                ) => {
                  existing.set(
                    file.id,
                    file,
                  );
                },
              );

              return Array.from(
                existing.values(),
              );
            },
          );
        },
      )
      .catch(
        () => {},
      );

    return () => {
      cancelled = true;
    };
  }, [
    activeVaultId,
    loading,
  ]);

  const handleFileSelection =
    (
      event,
    ) => {
      const file =
        event.target
          .files?.[0] ||
        null;

      if (
        !file
      ) {
        return;
      }

      const extension =
        `.${getFileExtension(
          file.name,
        )}`;

      const accepted =
        ACCEPTED_FILES
          .split(",")
          .includes(
            extension,
          );

      if (
        !accepted
      ) {
        setError(
          "Unsupported file type. Use PDF, DOCX, TXT, CSV, XLSX, PNG, JPG, JPEG, or WEBP.",
        );

        event.target.value =
          "";

        return;
      }

      if (
        file.size >
        MAX_UPLOAD_SIZE
      ) {
        setError(
          "File is too large. Maximum size is 20 MB.",
        );

        event.target.value =
          "";

        return;
      }

      if (
        file.size <=
        0
      ) {
        setError(
          "The selected file is empty.",
        );

        event.target.value =
          "";

        return;
      }

      if (
        activeVaultId ===
        "all"
      ) {
        setError(
          "Select a vault before uploading a file.",
        );

        event.target.value =
          "";

        return;
      }

      setPendingFile(
        file,
      );

      setError("");
    };

  const uploadToVault =
    async () => {
      if (
        !pendingFile ||
        activeVaultId ===
          "all" ||
        uploading
      ) {
        return;
      }

      const targetVault =
        activeVault;

      setUploading(
        true,
      );

      setError("");

      const formData =
        new FormData();

      formData.append(
        "file",
        pendingFile,
      );

      const uploadedFilename =
        pendingFile.name;

      try {
        const data =
          await apiRequest(
            `/api/knowledge/vaults/${encodeURIComponent(
              activeVaultId,
            )}/files/upload`,
            {
              method:
                "POST",
              body:
                formData,
            },
          );

        const createdFile =
          data?.file
            ? normalizeFile(
                data.file,
              )
            : null;

        if (
          createdFile?.id
        ) {
          setVaultFiles(
            (
              current,
            ) => [
              createdFile,
              ...current.filter(
                (
                  file,
                ) =>
                  file.id !==
                  createdFile.id,
              ),
            ],
          );
        }

        setPendingFile(
          null,
        );

        if (
          fileInputRef.current
        ) {
          fileInputRef.current.value =
            "";
        }

        notify(
          "success",
          `${uploadedFilename} indexed into ${
            targetVault?.name ||
            "vault"
          }.`,
        );

        await refreshData({
          silent:
            true,
          showErrors:
            false,
        });
      } catch (
        uploadError
      ) {
        setError(
          uploadError instanceof
            Error
            ? uploadError.message
            : "Vault upload failed.",
        );
      } finally {
        setUploading(
          false,
        );
      }
    };

  const openCreateVault =
    () => {
      setOpenMenu(
        null,
      );

      setNewVaultName(
        "",
      );

      setError("");

      setCreateVaultOpen(
        true,
      );
    };

  const closeCreateVault =
    () => {
      if (
        creatingVault
      ) {
        return;
      }

      setCreateVaultOpen(
        false,
      );

      setNewVaultName(
        "",
      );
    };

  const createVault =
    async () => {
      const name =
        newVaultName.trim();

      if (
        !name ||
        creatingVault
      ) {
        return;
      }

      setCreatingVault(
        true,
      );

      setError("");

      try {
        const data =
          await apiRequest(
            "/api/knowledge/vaults",
            {
              method:
                "POST",
              headers: {
                "Content-Type":
                  "application/json",
              },
              body:
                JSON.stringify({
                  name,
                }),
            },
          );

        const created =
          normalizeVault(
            data?.vault,
          );

        if (
          !created?.id
        ) {
          throw new Error(
            "Vault was created but the backend did not return a vault ID.",
          );
        }

        setVaults(
          (
            current,
          ) => [
            created,
            ...current.filter(
              (
                vault,
              ) =>
                vault.id !==
                created.id,
            ),
          ],
        );

        setActiveVaultId(
          created.id,
        );

        setNewVaultName(
          "",
        );

        setCreateVaultOpen(
          false,
        );

        notify(
          "success",
          `Vault "${created.name}" created successfully.`,
        );

        await refreshData({
          silent:
            true,
          showErrors:
            false,
        });
      } catch (
        createError
      ) {
        setError(
          createError instanceof
            Error
            ? createError.message
            : "Vault creation failed.",
        );
      } finally {
        setCreatingVault(
          false,
        );
      }
    };

  const startVaultRename =
    (
      vault,
    ) => {
      if (
        !vault?.id
      ) {
        return;
      }

      setRenameTarget({
        type:
          "vault",
        id:
          vault.id,
        name:
          vault.name,
      });

      setRenameValue(
        vault.name,
      );

      setOpenMenu(
        null,
      );

      setError("");
    };

  const startFileRename =
    (
      file,
    ) => {
      if (
        !file?.id
      ) {
        return;
      }

      setRenameTarget({
        type:
          "file",
        id:
          file.id,
        name:
          file.filename,
        vaultId:
          file.vault_id,
      });

      setRenameValue(
        file.filename,
      );

      setOpenMenu(
        null,
      );

      setError("");
    };

  const submitRename =
    async () => {
      const value =
        renameValue.trim();

      if (
        !renameTarget ||
        !value ||
        renaming
      ) {
        return;
      }

      setRenaming(
        true,
      );

      setError("");

      try {
        if (
          renameTarget.type ===
          "vault"
        ) {
          const data =
            await apiRequest(
              `/api/knowledge/vaults/${encodeURIComponent(
                renameTarget.id,
              )}`,
              {
                method:
                  "PATCH",
                headers: {
                  "Content-Type":
                    "application/json",
                },
                body:
                  JSON.stringify({
                    name:
                      value,
                  }),
              },
            );

          const updatedVault =
            normalizeVault(
              data?.vault,
            );

          if (
            updatedVault?.id
          ) {
            setVaults(
              (
                current,
              ) =>
                current.map(
                  (
                    vault,
                  ) =>
                    vault.id ===
                    updatedVault.id
                      ? updatedVault
                      : vault,
                ),
            );
          }

          notify(
            "success",
            "Vault renamed successfully.",
          );
        } else {
          const file =
            vaultFiles.find(
              (
                item,
              ) =>
                item.id ===
                renameTarget.id,
            );

          if (
            file?.vault_id
          ) {
            const requestedExtension =
              getFileExtension(
                value,
              );

            const finalExtension =
              requestedExtension ||
              getFileExtension(
                file.filename,
              );

            const normalizedRequestedName =
              `${value}${
                requestedExtension
                  ? ""
                  : `.${finalExtension}`
              }`.toLowerCase();

            const duplicate =
              vaultFiles.some(
                (
                  item,
                ) =>
                  item.id !==
                    renameTarget.id &&
                  item.vault_id ===
                    file.vault_id &&
                  item.filename
                    .toLowerCase() ===
                    normalizedRequestedName,
              );

            if (
              duplicate
            ) {
              throw new Error(
                `A file named "${value}" already exists in this vault.`,
              );
            }
          }

          const data =
            await apiRequest(
              `/api/knowledge/files/${encodeURIComponent(
                renameTarget.id,
              )}`,
              {
                method:
                  "PATCH",
                headers: {
                  "Content-Type":
                    "application/json",
                },
                body:
                  JSON.stringify({
                    name:
                      value,
                  }),
              },
            );

          const updatedFile =
            data?.file
              ? normalizeFile(
                  data.file,
                )
              : null;

          if (
            updatedFile?.id
          ) {
            setVaultFiles(
              (
                current,
              ) =>
                current.map(
                  (
                    fileItem,
                  ) =>
                    fileItem.id ===
                    updatedFile.id
                      ? updatedFile
                      : fileItem,
                ),
            );
          }

          notify(
            "success",
            "File renamed successfully.",
          );
        }

        setRenameTarget(
          null,
        );

        setRenameValue(
          "",
        );

        await refreshData({
          silent:
            true,
          showErrors:
            false,
        });
      } catch (
        renameError
      ) {
        setError(
          renameError instanceof
            Error
            ? renameError.message
            : "Rename failed.",
        );
      } finally {
        setRenaming(
          false,
        );
      }
    };

  const deleteVault =
    async (
      vault,
    ) => {
      if (
        !vault?.id
      ) {
        return;
      }

      const confirmed =
        window.confirm(
          `Move "${vault.name}" to Bin? Its active files will also move to Bin.`,
        );

      if (
        !confirmed
      ) {
        return;
      }

      setOpenMenu(
        null,
      );

      setError("");

      try {
        const data =
          await apiRequest(
            `/api/knowledge/vaults/${encodeURIComponent(
              vault.id,
            )}`,
            {
              method:
                "DELETE",
            },
          );

        const deletedIds =
          Array.isArray(
            data?.deleted_files,
          )
            ? data.deleted_files.map(
                (
                  id,
                ) =>
                  String(id),
              )
            : [];

        setVaults(
          (
            current,
          ) =>
            current.filter(
              (
                item,
              ) =>
                item.id !==
                vault.id,
            ),
        );

        setVaultFiles(
          (
            current,
          ) =>
            current.filter(
              (
                file,
              ) =>
                file.vault_id !==
                  vault.id &&
                !deletedIds.includes(
                  String(
                    file.id,
                  ),
                ),
            ),
        );

        if (
          activeVaultId ===
          vault.id
        ) {
          setActiveVaultId(
            "all",
          );
        }

        setSelectedFiles(
          [],
        );

        notify(
          "success",
          "Vault moved to Bin.",
        );

        await refreshData({
          silent:
            true,
          showErrors:
            false,
        });
      } catch (
        deleteError
      ) {
        setError(
          deleteError instanceof
            Error
            ? deleteError.message
            : "Vault deletion failed.",
        );
      }
    };

  const deleteFile =
    async (
      file,
    ) => {
      if (
        !file?.id
      ) {
        return;
      }

      const confirmed =
        window.confirm(
          `Move "${file.filename}" to Bin?`,
        );

      if (
        !confirmed
      ) {
        return;
      }

      setOpenMenu(
        null,
      );

      setError("");

      try {
        await apiRequest(
          `/api/knowledge/files/${encodeURIComponent(
            file.id,
          )}`,
          {
            method:
              "DELETE",
          },
        );

        setVaultFiles(
          (
            current,
          ) =>
            current.filter(
              (
                item,
              ) =>
                item.id !==
                file.id,
            ),
        );

        setSelectedFiles(
          (
            current,
          ) =>
            current.filter(
              (
                id,
              ) =>
                id !==
                file.id,
            ),
        );

        notify(
          "success",
          "File moved to Bin.",
        );

        await refreshData({
          silent:
            true,
          showErrors:
            false,
        });
      } catch (
        deleteError
      ) {
        setError(
          deleteError instanceof
            Error
            ? deleteError.message
            : "File deletion failed.",
        );
      }
    };

  const reindexFile =
    async (
      file,
    ) => {
      if (
        !file?.id
      ) {
        return;
      }

      setOpenMenu(
        null,
      );

      setError("");

      try {
        const data =
          await apiRequest(
            `/api/knowledge/files/${encodeURIComponent(
              file.id,
            )}/reindex`,
            {
              method:
                "POST",
            },
          );

        const updatedFile =
          data?.file
            ? normalizeFile(
                data.file,
              )
            : null;

        if (
          updatedFile?.id
        ) {
          setVaultFiles(
            (
              current,
            ) =>
              current.map(
                (
                  item,
                ) =>
                  item.id ===
                  updatedFile.id
                    ? updatedFile
                    : item,
              ),
          );
        }

        notify(
          "success",
          `Re-indexed ${file.filename}.`,
        );

        await refreshData({
          silent:
            true,
          showErrors:
            false,
        });
      } catch (
        reindexError
      ) {
        setError(
          reindexError instanceof
            Error
            ? reindexError.message
            : "File re-indexing failed.",
        );
      }
    };

  const downloadFile =
    async (
      file,
    ) => {
      if (
        !file?.id
      ) {
        return;
      }

      setOpenMenu(
        null,
      );

      setError("");

      const controller =
        new AbortController();

      const timeoutId =
        window.setTimeout(
          () =>
            controller.abort(),
          REQUEST_TIMEOUT,
        );

      try {
        const response =
          await fetch(
            getFileDownloadUrl(
              file.id,
            ),
            {
              signal:
                controller.signal,
            },
          );

        if (
          !response.ok
        ) {
          let detail =
            "File download failed.";

          try {
            const body =
              await response.json();

            detail =
              body?.detail ||
              detail;
          } catch {
            // Ignore invalid error body.
          }

          throw new Error(
            detail,
          );
        }

        const blob =
          await response.blob();

        const url =
          window.URL.createObjectURL(
            blob,
          );

        const anchor =
          document.createElement(
            "a",
          );

        anchor.href =
          url;

        anchor.download =
          file.filename;

        document.body.appendChild(
          anchor,
        );

        anchor.click();

        anchor.remove();

        window.URL.revokeObjectURL(
          url,
        );
      } catch (
        downloadError
      ) {
        setError(
          downloadError?.name ===
            "AbortError"
            ? "File download timed out."
            : downloadError instanceof
                Error
              ? downloadError.message
              : "File download failed.",
        );
      } finally {
        window.clearTimeout(
          timeoutId,
        );
      }
    };

  const previewFileContent =
    async (
      file,
    ) => {
      if (
        !file?.id
      ) {
        return;
      }

      setOpenMenu(
        null,
      );

      releasePreviewAsset();

      const visual =
        isVisualPreviewFile(
          file.filename,
        );

      setPreviewFile(
        file,
      );

      setPreviewData(
        null,
      );

      setPreviewMode(
        visual
          ? "visual"
          : "text",
      );

      setPreviewVisualFailed(
        false,
      );

      setPreviewLoading(
        true,
      );

      setError("");

      try {
        const previewPromise =
          apiRequest(
            `/api/knowledge/files/${encodeURIComponent(
              file.id,
            )}/preview`,
          );

        const visualPromise =
          visual
            ? fetchVisualAsset(
                file,
              )
            : Promise.resolve(
                null,
              );

        const [
          previewResult,
          visualResult,
        ] =
          await Promise.allSettled(
            [
              previewPromise,
              visualPromise,
            ],
          );

        let nextPreviewData =
          null;

        if (
          previewResult.status ===
          "fulfilled"
        ) {
          nextPreviewData =
            previewResult.value
              ?.preview ||
            null;
        }

        if (
          visualResult.status ===
            "fulfilled" &&
          visualResult.value
        ) {
          setPreviewAsset(
            visualResult.value,
          );
        }

        if (
          !nextPreviewData &&
          visualResult.status ===
            "rejected"
        ) {
          throw (
            previewResult.reason ||
            visualResult.reason
          );
        }

        setPreviewData(
          nextPreviewData,
        );

        if (
          visual &&
          visualResult.status ===
            "rejected" &&
          !nextPreviewData
        ) {
          throw visualResult.reason;
        }
      } catch (
        previewError
      ) {
        setError(
          previewError instanceof
            Error
            ? previewError.message
            : "File preview failed.",
        );

        closePreview();
      } finally {
        setPreviewLoading(
          false,
        );
      }
    };

  const moveFileToVault =
    async (
      targetVaultId,
    ) => {
      if (
        !movingFile ||
        !targetVaultId ||
        moving
      ) {
        return;
      }

      const sourceFile =
        movingFile;

      if (
        sourceFile.vault_id ===
        targetVaultId
      ) {
        setMovingFile(
          null,
        );

        return;
      }

      setMoving(
        true,
      );

      setError("");

      try {
        if (
          !sourceFile.vault_id
        ) {
          await apiRequest(
            `/api/knowledge/vaults/${encodeURIComponent(
              targetVaultId,
            )}/files/${encodeURIComponent(
              sourceFile.id,
            )}/add`,
            {
              method:
                "POST",
            },
          );
        } else {
          await apiRequest(
            `/api/knowledge/files/${encodeURIComponent(
              sourceFile.id,
            )}/move`,
            {
              method:
                "POST",
              headers: {
                "Content-Type":
                  "application/json",
              },
              body:
                JSON.stringify({
                  vault_id:
                    targetVaultId,
                }),
            },
          );
        }

        setMovingFile(
          null,
        );

        notify(
          "success",
          sourceFile.vault_id
            ? "File moved successfully."
            : "File added to vault and indexed.",
        );

        await refreshData({
          silent:
            true,
          showErrors:
            false,
        });
      } catch (
        moveError
      ) {
        setError(
          moveError instanceof
            Error
            ? moveError.message
            : "Unable to add or move file.",
        );
      } finally {
        setMoving(
          false,
        );
      }
    };

  const restoreBinItem =
    async (
      item,
    ) => {
      const normalized =
        normalizeBinItem(
          item,
        );

      if (
        !normalized
      ) {
        setError(
          "Invalid Bin item reference.",
        );

        return;
      }

      setError("");

      try {
        const data =
          await apiRequest(
            "/api/knowledge/bin/restore",
            {
              method:
                "POST",
              headers: {
                "Content-Type":
                  "application/json",
              },
              body:
                JSON.stringify({
                  item_type:
                    normalized.item_type,
                  item_id:
                    normalized.item_id,
                }),
            },
          );

        const restored =
          data?.restored;

        if (
          normalized.item_type ===
            "file" &&
          restored
        ) {
          const restoredFile =
            normalizeFile(
              restored,
            );

          if (
            restoredFile?.id
          ) {
            setVaultFiles(
              (
                current,
              ) => [
                restoredFile,
                ...current.filter(
                  (
                    file,
                  ) =>
                    file.id !==
                    restoredFile.id,
                ),
              ],
            );
          }
        }

        if (
          normalized.item_type ===
            "vault" &&
          restored
        ) {
          const restoredVault =
            normalizeVault(
              restored,
            );

          if (
            restoredVault?.id
          ) {
            setVaults(
              (
                current,
              ) => [
                restoredVault,
                ...current.filter(
                  (
                    vault,
                  ) =>
                    vault.id !==
                    restoredVault.id,
                ),
              ],
            );
          }
        }

        setBinItems(
          (
            current,
          ) =>
            current.filter(
              (
                entry,
              ) =>
                !(
                  entry.item_type ===
                    normalized.item_type &&
                  String(
                    entry.item_id,
                  ) ===
                    String(
                      normalized.item_id,
                    )
                ),
            ),
        );

        notify(
          "success",
          "Item restored successfully.",
        );

        await refreshData({
          silent:
            true,
          showErrors:
            false,
        });
      } catch (
        restoreError
      ) {
        setError(
          restoreError instanceof
            Error
            ? restoreError.message
            : "Restore failed.",
        );
      }
    };

  const permanentlyDelete =
    async (
      item,
    ) => {
      const normalized =
        normalizeBinItem(
          item,
        );

      if (
        !normalized
      ) {
        setError(
          "Invalid Bin item reference.",
        );

        return;
      }

      const confirmed =
        window.confirm(
          "Permanently delete this item? This cannot be undone.",
        );

      if (
        !confirmed
      ) {
        return;
      }

      setError("");

      try {
        await apiRequest(
          `/api/knowledge/bin/${encodeURIComponent(
            normalized.item_type,
          )}/${encodeURIComponent(
            normalized.item_id,
          )}`,
          {
            method:
              "DELETE",
          },
        );

        setBinItems(
          (
            current,
          ) =>
            current.filter(
              (
                entry,
              ) =>
                !(
                  entry.item_type ===
                    normalized.item_type &&
                  String(
                    entry.item_id,
                  ) ===
                    String(
                      normalized.item_id,
                    )
                ),
            ),
        );

        setSelectedBinItems(
          (
            current,
          ) =>
            current.filter(
              (
                value,
              ) =>
                String(
                  value,
                ) !==
                String(
                  normalized.item_id,
                ),
            ),
        );

        notify(
          "success",
          "Item permanently deleted.",
        );

        await refreshData({
          silent:
            true,
          showErrors:
            false,
        });
      } catch (
        deleteError
      ) {
        setError(
          deleteError instanceof
            Error
            ? deleteError.message
            : "Permanent deletion failed.",
        );
      }
    };

  const searchKnowledge =
    async () => {
      const text =
        query.trim();

      if (
        !text ||
        searching
      ) {
        return;
      }

      setSearching(
        true,
      );

      setError("");

      try {
        const data =
          await apiRequest(
            "/api/knowledge/search",
            {
              method:
                "POST",
              headers: {
                "Content-Type":
                  "application/json",
              },
              body:
                JSON.stringify({
                  query:
                    text,
                  top_k:
                    8,
                  vault_id:
                    activeVaultId ===
                    "all"
                      ? null
                      : activeVaultId,
                }),
            },
          );

        setResults(
          Array.isArray(
            data?.results,
          )
            ? data.results
            : [],
        );
      } catch (
        searchError
      ) {
        setError(
          searchError instanceof
            Error
            ? searchError.message
            : "Knowledge search failed.",
        );
      } finally {
        setSearching(
          false,
        );
      }
    };

  const toggleSelectedFile =
    (
      fileId,
    ) => {
      setSelectedFiles(
        (
          current,
        ) =>
          current.includes(
            fileId,
          )
            ? current.filter(
                (
                  id,
                ) =>
                  id !==
                  fileId,
              )
            : [
                ...current,
                fileId,
              ],
      );
    };

  const toggleSelectedBin =
    (
      itemId,
    ) => {
      setSelectedBinItems(
        (
          current,
        ) =>
          current.includes(
            itemId,
          )
            ? current.filter(
                (
                  id,
                ) =>
                  id !==
                  itemId,
              )
            : [
                ...current,
                itemId,
              ],
      );
    };

  const clearSelection =
    () => {
      setSelectedFiles(
        [],
      );

      setSelectedBinItems(
        [],
      );
    };

  const closeAllMenus =
    () => {
      setOpenMenu(
        null,
      );
    };

  return (
    <div className="nova-knowledge-page">
      <AnimatePresence>
        {toast.text && (
          <motion.div
            className={`nova-knowledge-toast ${
              toast.type ===
              "success"
                ? "is-success"
                : "is-error"
            }`}
            initial={{
              opacity: 0,
              y: -12,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            exit={{
              opacity: 0,
              y: -12,
            }}
          >
            {toast.type ===
            "success" ? (
              <CheckCircle2
                size={15}
              />
            ) : (
              <AlertCircle
                size={15}
              />
            )}

            <span>
              {toast.text}
            </span>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.section
        className="nova-knowledge-header"
        initial={{
          opacity: 0,
          y: 18,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
        transition={{
          duration:
            0.55,
        }}
      >
        <div>
          <div className="nova-chat-eyebrow">
            <span />
            LOCAL ENTERPRISE KNOWLEDGE
          </div>

          <h1>
            KNOWLEDGE VAULT
          </h1>

          <p>
            Manage confidential
            local knowledge,
            searchable files,
            vaults and recovery
            lifecycle from one
            sovereign workspace.
          </p>
        </div>

        <div className="nova-knowledge-status">
          <Shield size={16} />

          <span>
            REGISTRY + LOCAL INDEX
          </span>
        </div>
      </motion.section>

      {error && (
        <motion.div
          className="nova-knowledge-error nova-knowledge-global-error"
          initial={{
            opacity: 0,
            y: -8,
          }}
          animate={{
            opacity: 1,
            y: 0,
          }}
        >
          <AlertCircle
            size={15}
          />

          <span>
            {error}
          </span>

          <button
            type="button"
            onClick={() =>
              setError("")
            }
            aria-label="Dismiss error"
          >
            <X size={14} />
          </button>
        </motion.div>
      )}

      <section className="nova-knowledge-stats-grid">
        <div className="nova-knowledge-stat-card">
          <Folder size={17} />

          <div>
            <span>
              VAULTS
            </span>

            <strong>
              {formatNumber(
                stats.vaults,
              )}
            </strong>
          </div>
        </div>

        <div className="nova-knowledge-stat-card">
          <FileText size={17} />

          <div>
            <span>
              FILES
            </span>

            <strong>
              {formatNumber(
                stats.files,
              )}
            </strong>
          </div>
        </div>

        <div className="nova-knowledge-stat-card">
          <Database size={17} />

          <div>
            <span>
              INDEXED
            </span>

            <strong>
              {formatNumber(
                stats.indexed_files,
              )}
            </strong>
          </div>
        </div>

        <div className="nova-knowledge-stat-card">
          <Grid2X2 size={17} />

          <div>
            <span>
              CHUNKS
            </span>

            <strong>
              {formatNumber(
                stats.total_chunks,
              )}
            </strong>
          </div>
        </div>

        <div className="nova-knowledge-stat-card">
          <History size={17} />

          <div>
            <span>
              RECENT
            </span>

            <strong>
              {formatNumber(
                recentUploads.length,
              )}
            </strong>
          </div>
        </div>

        <div className="nova-knowledge-stat-card">
          <Trash2 size={17} />

          <div>
            <span>
              BIN
            </span>

            <strong>
              {formatNumber(
                stats.bin_items,
              )}
            </strong>
          </div>
        </div>
      </section>

      <section className="nova-knowledge-workspace">
        <aside className="nova-knowledge-sidebar">
          <div className="nova-knowledge-sidebar-head">
            <div>
              <span>
                KNOWLEDGE REGISTRY
              </span>

              <strong>
                VAULTS
              </strong>
            </div>

            <button
              type="button"
              className="nova-knowledge-icon-button"
              onClick={
                openCreateVault
              }
              title="Create vault"
            >
              <Plus size={16} />
            </button>
          </div>

          <button
            type="button"
            className={`nova-knowledge-vault-item ${
              activeVaultId ===
              "all"
                ? "is-active"
                : ""
            }`}
            onClick={() => {
              closeAllMenus();

              setActiveVaultId(
                "all",
              );

              setSelectedFiles(
                [],
              );
            }}
          >
            <Database size={16} />

            <div>
              <strong>
                ALL KNOWLEDGE
              </strong>

              <span>
                {formatNumber(
                  vaultFiles.length,
                )}{" "}
                files
              </span>
            </div>
          </button>

          <div className="nova-knowledge-vault-list">
            {vaults.map(
              (
                vault,
              ) => (
                <div
                  className="nova-knowledge-vault-row"
                  key={
                    vault.id
                  }
                >
                  <button
                    type="button"
                    className={`nova-knowledge-vault-item ${
                      activeVaultId ===
                      vault.id
                        ? "is-active"
                        : ""
                    }`}
                    onClick={() => {
                      closeAllMenus();

                      setActiveVaultId(
                        vault.id,
                      );

                      setSelectedFiles(
                        [],
                      );
                    }}
                  >
                    {activeVaultId ===
                    vault.id ? (
                      <FolderOpen
                        size={16}
                      />
                    ) : (
                      <Folder
                        size={16}
                      />
                    )}

                    <div>
                      <strong>
                        {
                          vault.name
                        }
                      </strong>

                      <span>
                        {formatNumber(
                          vault.file_count,
                        )}{" "}
                        files ·{" "}
                        {formatNumber(
                          vault.indexed_count,
                        )}{" "}
                        indexed
                      </span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className="nova-knowledge-mini-menu"
                    onClick={() =>
                      setOpenMenu(
                        openMenu ===
                          `vault-${vault.id}`
                          ? null
                          : `vault-${vault.id}`,
                      )
                    }
                    aria-label={`Actions for ${vault.name}`}
                  >
                    <MoreHorizontal
                      size={15}
                    />
                  </button>

                  {openMenu ===
                    `vault-${vault.id}` && (
                    <div className="nova-knowledge-context-menu">
                      <button
                        type="button"
                        onClick={() =>
                          startVaultRename(
                            vault,
                          )
                        }
                      >
                        Rename
                      </button>

                      <button
                        type="button"
                        className="is-danger"
                        onClick={() =>
                          deleteVault(
                            vault,
                          )
                        }
                      >
                        Move to Bin
                      </button>
                    </div>
                  )}
                </div>
              ),
            )}
          </div>

          <button
            type="button"
            className="nova-secondary-action"
            style={{
              margin: "8px",
              width: "calc(100% - 16px)",
              minHeight: 36,
            }}
            onClick={
              openCreateVault
            }
          >
            <FolderPlus
              size={15}
            />
            NEW VAULT
          </button>

          <div className="nova-knowledge-sidebar-footer">
            <div>
              <Archive
                size={15}
              />

              <span>
                BIN
              </span>

              <strong>
                {binItems.length}
              </strong>
            </div>

            <button
              type="button"
              onClick={() =>
                document
                  .getElementById(
                    "nova-knowledge-bin",
                  )
                  ?.scrollIntoView({
                    behavior:
                      "smooth",
                    block:
                      "start",
                  })
              }
            >
              OPEN
              <ArrowRight
                size={13}
              />
            </button>
          </div>
        </aside>

        <main className="nova-knowledge-main">
          <div className="nova-knowledge-main-toolbar">
            <div>
              <span>
                {activeVault
                  ? "ACTIVE VAULT"
                  : "KNOWLEDGE REGISTRY"}
              </span>

              <strong>
                {activeVault
                  ? activeVault.name
                  : "ALL KNOWLEDGE"}
              </strong>

              <small>
                {formatNumber(
                  visibleFiles.length,
                )}{" "}
                files ·{" "}
                {formatNumber(
                  indexedCount,
                )}{" "}
                indexed
              </small>
            </div>

            <div className="nova-knowledge-toolbar-actions">
              <button
                type="button"
                className="nova-secondary-action"
                onClick={() =>
                  refreshData({
                    silent:
                      true,
                  })
                }
                disabled={
                  refreshing ||
                  loading
                }
              >
                <RefreshCw
                  size={15}
                  className={
                    refreshing
                      ? "nova-spin"
                      : ""
                  }
                />

                {refreshing
                  ? "REFRESHING..."
                  : "REFRESH"}
              </button>

              <button
                type="button"
                className="nova-primary-action"
                disabled={
                  activeVaultId ===
                    "all" ||
                  uploading ||
                  refreshing
                }
                onClick={() => {
                  closeAllMenus();

                  fileInputRef.current?.click();
                }}
              >
                <Upload
                  size={15}
                />
                UPLOAD
              </button>
            </div>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept={
              ACCEPTED_FILES
            }
            hidden
            onChange={
              handleFileSelection
            }
          />

          {pendingFile && (
            <motion.div
              className="nova-knowledge-upload-panel"
              initial={{
                opacity: 0,
                height: 0,
              }}
              animate={{
                opacity: 1,
                height:
                  "auto",
              }}
            >
              <div>
                <FileThumbnail
                  file={{
                    id: "",
                    filename:
                      pendingFile.name,
                  }}
                  size="small"
                />

                <div>
                  <strong>
                    {
                      pendingFile.name
                    }
                  </strong>

                  <span>
                    {formatBytes(
                      pendingFile.size,
                    )}{" "}
                    ·{" "}
                    {getFileExtension(
                      pendingFile.name,
                    ).toUpperCase()}
                  </span>
                </div>
              </div>

              <div>
                <button
                  type="button"
                  className="nova-secondary-action"
                  disabled={
                    uploading
                  }
                  onClick={() => {
                    setPendingFile(
                      null,
                    );

                    if (
                      fileInputRef.current
                    ) {
                      fileInputRef.current.value =
                        "";
                    }
                  }}
                >
                  CANCEL
                </button>

                <button
                  type="button"
                  className="nova-primary-action"
                  onClick={
                    uploadToVault
                  }
                  disabled={
                    uploading
                  }
                >
                  {uploading ? (
                    <>
                      <Loader2
                        size={15}
                        className="nova-spin"
                      />
                      INDEXING...
                    </>
                  ) : (
                    <>
                      <Database
                        size={15}
                      />
                      ADD TO VAULT
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          )}

          {activeVaultId ===
            "all" &&
            vaults.length ===
              0 &&
            !loading && (
              <div className="nova-knowledge-create-callout">
                <FolderPlus
                  size={21}
                />

                <div>
                  <strong>
                    CREATE YOUR FIRST VAULT
                  </strong>

                  <span>
                    Vaults are user-created
                    containers for the local
                    Knowledge Registry.
                  </span>
                </div>

                <button
                  type="button"
                  className="nova-primary-action"
                  onClick={
                    openCreateVault
                  }
                >
                  <Plus size={15} />
                  CREATE VAULT
                </button>
              </div>
            )}

          <section className="nova-knowledge-search-card">
            <div className="nova-knowledge-card-heading">
              <div>
                <span>
                  LOCAL RETRIEVAL
                </span>

                <strong>
                  SEARCH KNOWLEDGE
                </strong>
              </div>

              <Database size={17} />
            </div>

            <div className="nova-knowledge-search">
              <input
                value={
                  query
                }
                onChange={(
                  event,
                ) =>
                  setQuery(
                    event.target.value,
                  )
                }
                onKeyDown={(
                  event,
                ) => {
                  if (
                    event.key ===
                    "Enter"
                  ) {
                    searchKnowledge();
                  }
                }}
                placeholder={
                  activeVaultId ===
                  "all"
                    ? "Search across all indexed knowledge..."
                    : `Search ${
                        activeVault?.name ||
                        "this vault"
                      }...`
                }
              />

              <button
                type="button"
                onClick={
                  searchKnowledge
                }
                disabled={
                  !query.trim() ||
                  searching
                }
              >
                {searching ? (
                  <Loader2
                    size={16}
                    className="nova-spin"
                  />
                ) : (
                  <Search
                    size={16}
                  />
                )}
              </button>
            </div>

            <div className="nova-search-results">
              {results.length ===
              0 ? (
                <div className="nova-empty-state">
                  <Search
                    size={20}
                  />

                  <span>
                    Search results
                    will appear
                    here.
                  </span>
                </div>
              ) : (
                results.map(
                  (
                    result,
                    index,
                  ) => {
                    const resultVault =
                      vaults.find(
                        (
                          vault,
                        ) =>
                          vault.id ===
                          result.vault_id,
                      );

                    return (
                      <motion.article
                        key={`${result.file_id || result.source || "source"}-${result.chunk_id || result.chunk || index}`}
                        className="nova-search-result"
                        initial={{
                          opacity: 0,
                          y: 8,
                        }}
                        animate={{
                          opacity: 1,
                          y: 0,
                        }}
                        transition={{
                          duration:
                            0.25,
                          delay:
                            index *
                            0.04,
                        }}
                      >
                        <div className="nova-search-result-meta">
                          <span>
                            SOURCE{" "}
                            {index +
                              1}
                          </span>

                          <span>
                            {result.filename ||
                              result.source ||
                              "LOCAL SOURCE"}
                          </span>

                          {resultVault && (
                            <span>
                              VAULT{" "}
                              {
                                resultVault.name
                              }
                            </span>
                          )}

                          <span>
                            CHUNK{" "}
                            {formatNumber(
                              Number(
                                result.chunk ??
                                  0,
                              ) + 1,
                            )}
                          </span>

                          {result.score !==
                            undefined &&
                            result.score !==
                              null && (
                              <span>
                                SCORE{" "}
                                {Number(
                                  result.score,
                                ).toFixed(
                                  3,
                                )}
                              </span>
                            )}
                        </div>

                        <p>
                          {
                            result.text
                          }
                        </p>

                        <small>
                          FILE ID:{" "}
                          {result.file_id ||
                            "—"}
                          {result.path
                            ? ` · ${result.path}`
                            : ""}
                        </small>
                      </motion.article>
                    );
                  },
                )
              )}
            </div>
          </section>

          <section className="nova-knowledge-file-section">
            <div className="nova-knowledge-section-title">
              <div>
                <span>
                  REGISTRY
                </span>

                <strong>
                  FILES
                </strong>
              </div>

              <span className="nova-knowledge-section-count">
                {formatNumber(
                  visibleFiles.length,
                )}
              </span>
            </div>

            {loading ? (
              <div className="nova-empty-state nova-document-empty">
                <Loader2
                  size={19}
                  className="nova-spin"
                />

                Loading local
                registry...
              </div>
            ) : visibleFiles.length ===
              0 ? (
              <div className="nova-empty-state nova-document-empty">
                <FileText
                  size={21}
                />

                <div>
                  <strong>
                    NO FILES
                  </strong>

                  <span>
                    {activeVault
                      ? "Upload files into this vault to build local knowledge."
                      : "Files assigned to Knowledge Vaults will appear here."}
                  </span>
                </div>
              </div>
            ) : (
              <div className="nova-knowledge-file-list">
                <div className="nova-knowledge-file-list-head">
                  <span>
                    FILE
                  </span>

                  <span>
                    VAULT
                  </span>

                  <span>
                    INDEX
                  </span>

                  <span>
                    SIZE
                  </span>

                  <span>
                    UPDATED
                  </span>

                  <span />
                </div>

                {visibleFiles.map(
                  (
                    file,
                  ) => {
                    const vault =
                      vaults.find(
                        (
                          item,
                        ) =>
                          item.id ===
                          file.vault_id,
                      );

                    return (
                      <div
                        className="nova-knowledge-file-row"
                        key={
                          file.id
                        }
                      >
                        <div className="nova-knowledge-file-main">
                          <button
                            type="button"
                            className="nova-knowledge-checkbox"
                            onClick={() =>
                              toggleSelectedFile(
                                file.id,
                              )
                            }
                            aria-label={`Select ${file.filename}`}
                          >
                            {selectedFiles.includes(
                              file.id,
                            ) ? (
                              <CheckCircle2
                                size={
                                  15
                                }
                              />
                            ) : (
                              <span />
                            )}
                          </button>

                          <FileThumbnail
                            file={file}
                            size="normal"
                          />

                          <div>
                            <strong>
                              {
                                file.filename
                              }
                            </strong>

                            <span>
                              {formatNumber(
                                file.characters,
                              )}{" "}
                              chars ·{" "}
                              {formatNumber(
                                file.chunks,
                              )}{" "}
                              chunks
                            </span>

                            <small>
                              {file.content_sha256
                                ? `SHA-256 ${file.content_sha256.slice(
                                    0,
                                    12,
                                  )}…`
                                : "LOCAL FILE"}
                            </small>
                          </div>
                        </div>

                        <span className="nova-knowledge-file-vault">
                          {vault?.name ||
                            "Unassigned"}
                        </span>

                        <span>
                          {file.indexed ? (
                            <span className="nova-indexed-badge">
                              <CheckCircle2
                                size={
                                  12
                                }
                              />
                              INDEXED
                            </span>
                          ) : (
                            <span className="nova-knowledge-pending-badge">
                              PENDING
                            </span>
                          )}
                        </span>

                        <span>
                          {formatBytes(
                            file.size,
                          )}
                        </span>

                        <span>
                          {formatDate(
                            file.updated_at ||
                              file.created_at,
                          )}
                        </span>

                        <div className="nova-knowledge-file-actions">
                          <button
                            type="button"
                            className="nova-knowledge-mini-menu"
                            onClick={() =>
                              setOpenMenu(
                                openMenu ===
                                  `file-${file.id}`
                                  ? null
                                  : `file-${file.id}`,
                              )
                            }
                            aria-label={`Actions for ${file.filename}`}
                          >
                            <MoreHorizontal
                              size={
                                15
                              }
                            />
                          </button>

                          {openMenu ===
                            `file-${file.id}` && (
                            <div className="nova-knowledge-context-menu nova-knowledge-file-menu">
                              <button
                                type="button"
                                onClick={() =>
                                  previewFileContent(
                                    file,
                                  )
                                }
                              >
                                <Eye
                                  size={
                                    13
                                  }
                                />
                                Open / Preview
                              </button>

                              <button
                                type="button"
                                onClick={() =>
                                  downloadFile(
                                    file,
                                  )
                                }
                              >
                                Download
                              </button>

                              <button
                                type="button"
                                onClick={() =>
                                  startFileRename(
                                    file,
                                  )
                                }
                              >
                                Rename
                              </button>

                              <button
                                type="button"
                                onClick={() => {
                                  setOpenMenu(
                                    null,
                                  );

                                  setMovingFile(
                                    file,
                                  );
                                }}
                              >
                                Move
                              </button>

                              <button
                                type="button"
                                onClick={() =>
                                  reindexFile(
                                    file,
                                  )
                                }
                              >
                                Re-index
                              </button>

                              <button
                                type="button"
                                className="is-danger"
                                onClick={() =>
                                  deleteFile(
                                    file,
                                  )
                                }
                              >
                                Move to Bin
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  },
                )}
              </div>
            )}
          </section>

          <section className="nova-knowledge-recent-section">
            <div className="nova-knowledge-section-title">
              <div>
                <span>
                  FILE ACTIVITY
                </span>

                <strong>
                  RECENT UPLOADS
                </strong>
              </div>

              <History size={17} />
            </div>

            {recentUploads.length ===
            0 ? (
              <div className="nova-empty-state nova-document-empty">
                No recent local
                uploads.
              </div>
            ) : (
              <div className="nova-knowledge-recent-grid">
                {recentUploads
                  .slice(
                    0,
                    12,
                  )
                  .map(
                    (
                      file,
                    ) => (
                      <div
                        className="nova-knowledge-recent-card"
                        key={
                          file.id
                        }
                      >
                        <FileThumbnail
                          file={file}
                          size="small"
                        />

                        <div>
                          <strong>
                            {
                              file.filename
                            }
                          </strong>

                          <span>
                            {file.vault_id
                              ? "IN VAULT"
                              : "RECENT UPLOAD"}
                          </span>

                          <small>
                            {formatDate(
                              file.recent_at ||
                                file.created_at ||
                                file.updated_at,
                            )}
                          </small>
                        </div>

                        <button
                          type="button"
                          className="nova-knowledge-mini-menu"
                          title="Open preview"
                          onClick={() =>
                            previewFileContent(
                              file,
                            )
                          }
                        >
                          <Eye
                            size={
                              13
                            }
                          />
                        </button>

                        {!file.vault_id && (
                          <button
                            type="button"
                            className="nova-knowledge-add-vault-button"
                            onClick={() =>
                              setMovingFile(
                                file,
                              )
                            }
                          >
                            ADD
                          </button>
                        )}
                      </div>
                    ),
                  )}
              </div>
            )}
          </section>

          <section
            id="nova-knowledge-bin"
            className="nova-knowledge-bin-section"
          >
            <div className="nova-knowledge-section-title">
              <div>
                <span>
                  RECOVERY
                </span>

                <strong>
                  BIN
                </strong>
              </div>

              <Archive size={17} />
            </div>

            {binItems.length ===
            0 ? (
              <div className="nova-empty-state nova-document-empty">
                <Archive
                  size={20}
                />

                <div>
                  <strong>
                    BIN IS EMPTY
                  </strong>

                  <span>
                    Deleted vaults
                    and files will
                    appear here
                    before permanent
                    deletion.
                  </span>
                </div>
              </div>
            ) : (
              <div className="nova-knowledge-bin-list">
                {binItems.map(
                  (
                    item,
                  ) => {
                    const label =
                      item.item_type ===
                      "vault"
                        ? item.name ||
                          "Deleted Vault"
                        : item.original_filename ||
                          item.filename ||
                          "Deleted file";

                    return (
                      <div
                        className="nova-knowledge-bin-row"
                        key={`${item.item_type}-${item.item_id}`}
                      >
                        <button
                          type="button"
                          className="nova-knowledge-checkbox"
                          onClick={() =>
                            toggleSelectedBin(
                              item.item_id,
                            )
                          }
                          aria-label={`Select ${label}`}
                        >
                          {selectedBinItems.includes(
                            item.item_id,
                          ) ? (
                            <CheckCircle2
                              size={
                                15
                              }
                            />
                          ) : (
                            <span />
                          )}
                        </button>

                        {item.item_type ===
                        "vault" ? (
                          <Folder
                            size={
                              17
                            }
                          />
                        ) : (
                          <FileText
                            size={
                              17
                            }
                          />
                        )}

                        <div>
                          <strong>
                            {label}
                          </strong>

                          <span>
                            {item.item_type.toUpperCase()}{" "}
                            ·{" "}
                            {formatDate(
                              item.deleted_at,
                            )}
                          </span>

                          <small>
                            {item.item_type ===
                            "file"
                              ? `Original Vault: ${
                                  item.original_vault_name ||
                                  "—"
                                }${
                                  item.original_path
                                    ? ` · ${item.original_path}`
                                    : ""
                                }`
                              : "Vault and its deleted files can be restored from Bin."}
                          </small>
                        </div>

                        <div className="nova-knowledge-bin-actions">
                          <button
                            type="button"
                            className="nova-secondary-action"
                            onClick={() =>
                              restoreBinItem(
                                item,
                              )
                            }
                          >
                            <RotateCcw
                              size={
                                13
                              }
                            />
                            RESTORE
                          </button>

                          <button
                            type="button"
                            className="nova-danger-action"
                            onClick={() =>
                              permanentlyDelete(
                                item,
                              )
                            }
                          >
                            <Trash2
                              size={
                                13
                              }
                            />
                            DELETE
                          </button>
                        </div>
                      </div>
                    );
                  },
                )}
              </div>
            )}
          </section>
        </main>
      </section>

      {selectedFiles.length >
        0 && (
        <motion.div
          className="nova-knowledge-selection-bar"
          initial={{
            opacity: 0,
            y: 20,
          }}
          animate={{
            opacity: 1,
            y: 0,
          }}
        >
          <span>
            {selectedFiles.length}{" "}
            selected
          </span>

          <button
            type="button"
            onClick={
              clearSelection
            }
          >
            CLEAR
          </button>
        </motion.div>
      )}

      <AnimatePresence>
        {createVaultOpen && (
          <motion.div
            className="nova-knowledge-modal-backdrop"
            initial={{
              opacity: 0,
            }}
            animate={{
              opacity: 1,
            }}
            exit={{
              opacity: 0,
            }}
            onMouseDown={(
              event,
            ) => {
              if (
                event.target ===
                event.currentTarget
              ) {
                closeCreateVault();
              }
            }}
          >
            <motion.div
              className="nova-knowledge-modal"
              initial={{
                opacity: 0,
                y: 14,
                scale: 0.98,
              }}
              animate={{
                opacity: 1,
                y: 0,
                scale: 1,
              }}
              onMouseDown={(
                event,
              ) =>
                event.stopPropagation()
              }
            >
              <div className="nova-knowledge-modal-head">
                <div>
                  <span>
                    REGISTRY
                  </span>

                  <strong>
                    CREATE VAULT
                  </strong>
                </div>

                <button
                  type="button"
                  onClick={
                    closeCreateVault
                  }
                  disabled={
                    creatingVault
                  }
                  aria-label="Close create vault dialog"
                >
                  <X size={16} />
                </button>
              </div>

              <input
                value={
                  newVaultName
                }
                onChange={(
                  event,
                ) =>
                  setNewVaultName(
                    event.target.value,
                  )
                }
                onKeyDown={(
                  event,
                ) => {
                  if (
                    event.key ===
                    "Enter"
                  ) {
                    event.preventDefault();

                    createVault();
                  }

                  if (
                    event.key ===
                    "Escape"
                  ) {
                    closeCreateVault();
                  }
                }}
                placeholder="Vault name"
                autoFocus
                maxLength={120}
                disabled={
                  creatingVault
                }
              />

              <div className="nova-knowledge-modal-actions">
                <button
                  type="button"
                  className="nova-secondary-action"
                  onClick={
                    closeCreateVault
                  }
                  disabled={
                    creatingVault
                  }
                >
                  CANCEL
                </button>

                <button
                  type="button"
                  className="nova-primary-action"
                  disabled={
                    !newVaultName.trim() ||
                    creatingVault
                  }
                  onClick={
                    createVault
                  }
                >
                  {creatingVault ? (
                    <>
                      <Loader2
                        size={15}
                        className="nova-spin"
                      />
                      CREATING...
                    </>
                  ) : (
                    <>
                      <FolderPlus
                        size={15}
                      />
                      CREATE VAULT
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}

        {renameTarget && (
          <motion.div
            className="nova-knowledge-modal-backdrop"
            initial={{
              opacity: 0,
            }}
            animate={{
              opacity: 1,
            }}
            exit={{
              opacity: 0,
            }}
            onMouseDown={(
              event,
            ) => {
              if (
                event.target ===
                  event.currentTarget &&
                !renaming
              ) {
                setRenameTarget(
                  null,
                );
              }
            }}
          >
            <motion.div
              className="nova-knowledge-modal"
              initial={{
                opacity: 0,
                y: 14,
                scale: 0.98,
              }}
              animate={{
                opacity: 1,
                y: 0,
                scale: 1,
              }}
              onMouseDown={(
                event,
              ) =>
                event.stopPropagation()
              }
            >
              <div className="nova-knowledge-modal-head">
                <div>
                  <span>
                    REGISTRY
                  </span>

                  <strong>
                    RENAME{" "}
                    {renameTarget.type.toUpperCase()}
                  </strong>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    if (
                      renaming
                    ) {
                      return;
                    }

                    setRenameTarget(
                      null,
                    );
                  }}
                  disabled={
                    renaming
                  }
                  aria-label="Close rename dialog"
                >
                  <X size={16} />
                </button>
              </div>

              <input
                value={
                  renameValue
                }
                onChange={(
                  event,
                ) =>
                  setRenameValue(
                    event.target.value,
                  )
                }
                onKeyDown={(
                  event,
                ) => {
                  if (
                    event.key ===
                    "Enter"
                  ) {
                    event.preventDefault();

                    submitRename();
                  }

                  if (
                    event.key ===
                      "Escape" &&
                    !renaming
                  ) {
                    setRenameTarget(
                      null,
                    );
                  }
                }}
                autoFocus
                maxLength={255}
                disabled={
                  renaming
                }
              />

              <div className="nova-knowledge-modal-actions">
                <button
                  type="button"
                  className="nova-secondary-action"
                  onClick={() => {
                    if (
                      renaming
                    ) {
                      return;
                    }

                    setRenameTarget(
                      null,
                    );
                  }}
                  disabled={
                    renaming
                  }
                >
                  CANCEL
                </button>

                <button
                  type="button"
                  className="nova-primary-action"
                  disabled={
                    !renameValue.trim() ||
                    renaming
                  }
                  onClick={
                    submitRename
                  }
                >
                  {renaming ? (
                    <>
                      <Loader2
                        size={15}
                        className="nova-spin"
                      />
                      SAVING...
                    </>
                  ) : (
                    "SAVE"
                  )}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}

        {movingFile && (
          <motion.div
            className="nova-knowledge-modal-backdrop"
            initial={{
              opacity: 0,
            }}
            animate={{
              opacity: 1,
            }}
            exit={{
              opacity: 0,
            }}
            onMouseDown={(
              event,
            ) => {
              if (
                event.target ===
                  event.currentTarget &&
                !moving
              ) {
                setMovingFile(
                  null,
                );
              }
            }}
          >
            <motion.div
              className="nova-knowledge-modal"
              initial={{
                opacity: 0,
                y: 14,
                scale: 0.98,
              }}
              animate={{
                opacity: 1,
                y: 0,
                scale: 1,
              }}
              onMouseDown={(
                event,
              ) =>
                event.stopPropagation()
              }
            >
              <div className="nova-knowledge-modal-head">
                <div>
                  <span>
                    FILE ROUTING
                  </span>

                  <strong>
                    {movingFile.vault_id
                      ? "MOVE FILE"
                      : "ADD TO VAULT"}
                  </strong>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    if (
                      moving
                    ) {
                      return;
                    }

                    setMovingFile(
                      null,
                    );
                  }}
                  disabled={
                    moving
                  }
                  aria-label="Close file routing dialog"
                >
                  <X size={16} />
                </button>
              </div>

              <div className="nova-knowledge-move-file">
                <FileThumbnail
                  file={movingFile}
                  size="small"
                />

                <div>
                  <strong>
                    {
                      movingFile.filename
                    }
                  </strong>

                  <span>
                    Choose the
                    destination
                    vault.
                  </span>
                </div>
              </div>

              <div className="nova-knowledge-vault-select-list">
                {vaults.length ===
                0 ? (
                  <div className="nova-empty-state">
                    Create a vault
                    first.
                  </div>
                ) : (
                  vaults.map(
                    (
                      vault,
                    ) => (
                      <button
                        type="button"
                        key={
                          vault.id
                        }
                        disabled={
                          moving ||
                          movingFile.vault_id ===
                            vault.id
                        }
                        onClick={() =>
                          moveFileToVault(
                            vault.id,
                          )
                        }
                      >
                        <Folder
                          size={16}
                        />

                        <span>
                          {
                            vault.name
                          }
                        </span>

                        {moving &&
                        movingFile.vault_id !==
                          vault.id ? (
                          <Loader2
                            size={
                              14
                            }
                            className="nova-spin"
                          />
                        ) : (
                          <ArrowRight
                            size={
                              14
                            }
                          />
                        )}
                      </button>
                    ),
                  )
                )}
              </div>
            </motion.div>
          </motion.div>
        )}

        {previewFile && (
          <motion.div
            className="nova-knowledge-modal-backdrop"
            initial={{
              opacity: 0,
            }}
            animate={{
              opacity: 1,
            }}
            exit={{
              opacity: 0,
            }}
            onMouseDown={(
              event,
            ) => {
              if (
                event.target ===
                event.currentTarget
              ) {
                closePreview();
              }
            }}
          >
            <motion.div
              className="nova-knowledge-modal nova-knowledge-preview-modal"
              initial={{
                opacity: 0,
                y: 14,
                scale: 0.98,
              }}
              animate={{
                opacity: 1,
                y: 0,
                scale: 1,
              }}
              transition={{
                duration:
                  0.28,
              }}
              onMouseDown={(
                event,
              ) =>
                event.stopPropagation()
              }
            >
              <div className="nova-knowledge-modal-head">
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  {(() => {
                    const FileIconComponent = getFileIcon(previewFile.filename);
                    return <FileIconComponent size={20} style={{ color: "#6ddcff", flexShrink: 0 }} />;
                  })()}
                  <div>
                    <span>
                      LOCAL PREVIEW
                    </span>

                    <strong
                      title={
                        previewFile.filename
                      }
                    >
                      {
                        previewFile.filename
                      }
                    </strong>
                  </div>
                </div>

                <a
                  className="nova-secondary-action"
                  href={getFileDownloadUrl(
                    previewFile.id,
                  )}
                  download={
                    previewFile.filename
                  }
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    textDecoration:
                      "none",
                    minHeight:
                      34,
                    padding:
                      "0 12px",
                    margin:
                      "0 6px 0 auto",
                    display:
                      "inline-flex",
                    alignItems:
                      "center",
                    gap:
                      "6px",
                  }}
                >
                  <Download size={14} />
                  DOWNLOAD
                </a>

                <button
                  type="button"
                  onClick={
                    closePreview
                  }
                  aria-label="Close preview"
                >
                  <X size={17} />
                </button>
              </div>

              {previewLoading ? (
                <div className="nova-empty-state nova-document-empty">
                  <Loader2
                    size={24}
                    className="nova-spin"
                  />

                  <strong>
                    Preparing local preview
                  </strong>

                  <span>
                    Loading the real
                    file from NOVA local
                    storage...
                  </span>
                </div>
              ) : (
                <>
                  <div className="nova-knowledge-preview-meta">
                    <span>
                      <FileText size={12} style={{ marginRight: 5, color: "#6ddcff" }} />
                      TYPE{" "}
                      <strong>
                        {(
                          previewData?.file_type ||
                          getFileExtension(
                            previewFile.filename,
                          ) ||
                          "FILE"
                        ).toUpperCase()}
                      </strong>
                    </span>

                    <span>
                      <Layers size={12} style={{ marginRight: 5, color: "#6ddcff" }} />
                      CHARACTERS{" "}
                      <strong>
                        {formatNumber(
                          previewData?.character_count ??
                            previewFile.characters ??
                            0,
                        )}
                      </strong>
                    </span>

                    <span>
                      <File size={12} style={{ marginRight: 5, color: "#6ddcff" }} />
                      PAGES{" "}
                      <strong>
                        {formatNumber(
                          Array.isArray(
                            previewData?.pages,
                          )
                            ? previewData.pages.length
                            : Number(
                                previewData?.pages ??
                                  0,
                              ),
                        )}
                      </strong>
                    </span>

                    <span>
                      <HardDrive size={12} style={{ marginRight: 5, color: "#6ddcff" }} />
                      SIZE{" "}
                      <strong>
                        {formatBytes(
                          previewFile.size,
                        )}
                      </strong>
                    </span>

                    <span>
                      <ShieldCheck size={12} style={{ marginRight: 5, color: previewFile.indexed ? "#4ade80" : "#f59e0b" }} />
                      INDEX{" "}
                      <strong>
                        {previewFile.indexed
                          ? "READY"
                          : "PENDING"}
                      </strong>
                    </span>

                    {previewData?.used_ocr !==
                      undefined && (
                      <span>
                        <Scan size={12} style={{ marginRight: 5, color: "#6ddcff" }} />
                        OCR{" "}
                        <strong>
                          {previewData.used_ocr
                            ? "USED"
                            : "NOT USED"}
                        </strong>
                      </span>
                    )}
                  </div>

                  {previewIsVisual && (
                    <div className="nova-knowledge-modal-actions">
                      <button
                        type="button"
                        className={
                          previewMode ===
                          "visual"
                            ? "nova-primary-action"
                            : "nova-secondary-action"
                        }
                        onClick={() => {
                          setPreviewVisualFailed(
                            false,
                          );

                          setPreviewMode(
                            "visual",
                          );
                        }}
                        disabled={
                          !previewAssetUrl
                        }
                      >
                        <Eye size={14} />
                        VISUAL PREVIEW
                      </button>

                      <button
                        type="button"
                        className={
                          previewMode ===
                          "text"
                            ? "nova-primary-action"
                            : "nova-secondary-action"
                        }
                        onClick={() =>
                          setPreviewMode(
                            "text",
                          )
                        }
                        disabled={
                          !previewData?.text
                        }
                      >
                        <FileText
                          size={14}
                        />
                        EXTRACTED TEXT
                      </button>
                    </div>
                  )}

                  {previewMode ===
                    "visual" &&
                  previewIsVisual &&
                  previewAssetUrl &&
                  !previewVisualFailed ? (
                    <div className="nova-knowledge-preview-body">
                      {isPdfFile(
                        previewFile.filename,
                      ) ? (
                        <div className="nova-knowledge-preview-frame-wrap">
                          <iframe
                            className="nova-knowledge-preview-frame"
                            title={`PDF preview of ${previewFile.filename}`}
                            src={`${previewAssetUrl}#page=1&view=FitH`}
                          />
                        </div>
                      ) : (
                        <div className="nova-knowledge-preview-image-wrap">
                          <img
                            className="nova-knowledge-preview-image"
                            src={
                              previewAssetUrl
                            }
                            alt={
                              previewFile.filename
                            }
                            onError={() => {
                              setPreviewVisualFailed(
                                true,
                              );

                              if (
                                previewData?.text
                              ) {
                                setPreviewMode(
                                  "text",
                                );
                              }
                            }}
                          />
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="nova-knowledge-preview-body">
                      {isSpreadsheetFile(
                        previewFile.filename,
                      ) ? (
                        <SpreadsheetPreview
                          text={
                            previewData?.text
                          }
                        />
                      ) : isDocxFile(
                          previewFile.filename,
                        ) ||
                        isPdfFile(
                          previewFile.filename,
                        ) ? (
                        <DocxSheetPreview
                          text={
                            previewData?.text
                          }
                          filename={
                            previewFile.filename
                          }
                        />
                      ) : (
                        <TxtViewerPreview
                          text={
                            previewData?.text
                          }
                          filename={
                            previewFile.filename
                          }
                        />
                      )}
                    </div>
                  )}
                </>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default KnowledgeVault;