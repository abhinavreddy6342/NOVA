import { useRef, useState } from "react";
import {
  FileText,
  Upload,
  Database,
  Search,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { motion } from "framer-motion";

const API_URL = "http://127.0.0.1:8001";

function KnowledgeVault() {
  const fileInputRef = useRef(null);

  const [selectedFile, setSelectedFile] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);

  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState([]);

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    setSelectedFile(file);
    setError("");
    setMessage("");
  };

  const uploadDocument = async () => {
    if (!selectedFile || uploading) {
      return;
    }

    setUploading(true);
    setError("");
    setMessage("");

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await fetch(
        `${API_URL}/api/knowledge/upload`,
        {
          method: "POST",
          body: formData,
        },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            "Document upload failed.",
        );
      }

      setDocuments((current) => [
        {
          filename: data.filename,
          characters: data.characters,
          chunks: data.chunks,
          replaced: data.replaced_existing,
        },
        ...current.filter(
          (document) =>
            document.filename !== data.filename,
        ),
      ]);

      setMessage(
        data.replaced_existing
          ? "Document re-indexed successfully."
          : "Document indexed successfully.",
      );

      setSelectedFile(null);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (uploadError) {
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "Unable to upload document.",
      );
    } finally {
      setUploading(false);
    }
  };

  const searchKnowledge = async () => {
    const text = query.trim();

    if (!text || searching) {
      return;
    }

    setSearching(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/api/knowledge/search`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            query: text,
            top_k: 5,
          }),
        },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            "Knowledge search failed.",
        );
      }

      setResults(data.results || []);
    } catch (searchError) {
      setError(
        searchError instanceof Error
          ? searchError.message
          : "Unable to search Knowledge Vault.",
      );
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="nova-knowledge-page">
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
          duration: 0.65,
          ease: "easeOut",
        }}
      >
        <div>
          <div className="nova-chat-kicker">
            <span className="nova-chat-kicker-line" />
            LOCAL ENTERPRISE KNOWLEDGE
          </div>

          <h1>KNOWLEDGE VAULT</h1>

          <p>
            Store and retrieve confidential documents
            directly from NOVA's local knowledge system.
          </p>
        </div>

        <div className="nova-knowledge-status">
          <Database size={16} />
          <span>LOCAL VECTOR STORE</span>
        </div>
      </motion.section>

      <motion.section
        className="nova-knowledge-grid"
        initial={{
          opacity: 0,
          y: 20,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
        transition={{
          duration: 0.65,
          delay: 0.12,
          ease: "easeOut",
        }}
      >
        <div className="nova-knowledge-card">
          <div className="nova-knowledge-card-heading">
            <div>
              <span>DOCUMENT INGESTION</span>
              <strong>UPLOAD KNOWLEDGE</strong>
            </div>

            <Upload size={18} />
          </div>

          <button
            type="button"
            className="nova-upload-zone"
            onClick={() =>
              fileInputRef.current?.click()
            }
          >
            <FileText size={26} />

            <strong>
              {selectedFile
                ? selectedFile.name
                : "Select a document"}
            </strong>

            <span>
              PDF · DOCX · TXT
            </span>
          </button>

          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.txt"
            hidden
            onChange={handleFileChange}
          />

          <button
            type="button"
            className="nova-primary-action"
            disabled={!selectedFile || uploading}
            onClick={uploadDocument}
          >
            {uploading ? (
              <>
                <Loader2
                  size={16}
                  className="nova-spin"
                />
                INDEXING...
              </>
            ) : (
              <>
                <Upload size={16} />
                INDEX DOCUMENT
              </>
            )}
          </button>

          {message && (
            <div className="nova-knowledge-message">
              <CheckCircle2 size={15} />
              <span>{message}</span>
            </div>
          )}

          {error && (
            <div className="nova-knowledge-error">
              <AlertCircle size={15} />
              <span>{error}</span>
            </div>
          )}
        </div>

        <div className="nova-knowledge-card">
          <div className="nova-knowledge-card-heading">
            <div>
              <span>RETRIEVAL</span>
              <strong>SEARCH KNOWLEDGE</strong>
            </div>

            <Search size={18} />
          </div>

          <div className="nova-knowledge-search">
            <input
              value={query}
              onChange={(event) =>
                setQuery(event.target.value)
              }
              onKeyDown={(event) => {
                if (
                  event.key === "Enter"
                ) {
                  searchKnowledge();
                }
              }}
              placeholder="Ask about your documents..."
            />

            <button
              type="button"
              onClick={searchKnowledge}
              disabled={
                !query.trim() || searching
              }
            >
              {searching ? (
                <Loader2
                  size={16}
                  className="nova-spin"
                />
              ) : (
                <Search size={16} />
              )}
            </button>
          </div>

          <div className="nova-search-results">
            {results.length === 0 ? (
              <div className="nova-empty-state">
                Search results will appear here.
              </div>
            ) : (
              results.map((result, index) => (
                <motion.article
                  key={`${result.source}-${result.chunk}-${index}`}
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
                    duration: 0.3,
                    delay: index * 0.05,
                  }}
                >
                  <div className="nova-search-result-meta">
                    <span>
                      SOURCE {index + 1}
                    </span>

                    <span>
                      CHUNK {result.chunk}
                    </span>
                  </div>

                  <p>{result.text}</p>

                  <small>
                    {result.source}
                  </small>
                </motion.article>
              ))
            )}
          </div>
        </div>
      </motion.section>

      <motion.section
        className="nova-knowledge-documents"
        initial={{
          opacity: 0,
          y: 18,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
        transition={{
          duration: 0.6,
          delay: 0.2,
        }}
      >
        <div className="nova-knowledge-section-title">
          <span>INDEX</span>
          <strong>DOCUMENTS</strong>
        </div>

        {documents.length === 0 ? (
          <div className="nova-empty-state nova-document-empty">
            No documents uploaded during this session.
          </div>
        ) : (
          <div className="nova-document-list">
            {documents.map((document) => (
              <div
                className="nova-document-row"
                key={document.filename}
              >
                <div>
                  <FileText size={17} />

                  <div>
                    <strong>
                      {document.filename}
                    </strong>

                    <span>
                      {document.characters} characters
                      · {document.chunks} chunks
                    </span>
                  </div>
                </div>

                <span className="nova-indexed-badge">
                  <CheckCircle2 size={13} />
                  INDEXED
                </span>
              </div>
            ))}
          </div>
        )}
      </motion.section>
    </div>
  );
}

export default KnowledgeVault;