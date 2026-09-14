import { useEffect, useRef, useState } from "react";

import {
  ArrowUp,
  Cpu,
  LockKeyhole,
  MessageSquare,
  RotateCcw,
  Sparkles,
  Activity,
  Paperclip,
  FileText,
  Image as ImageIcon,
  X,
  LoaderCircle,
  BrainCircuit,
  CheckCircle2,
  AlertCircle,
  Download,
} from "lucide-react";

import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";

const API_URL = "http://127.0.0.1:8001";
const MODEL = "llama3.2:latest";

const welcomeMessage = {
  id: "nova-welcome",
  role: "assistant",
  content: "Hi! I'm NOVA. How can I help you today?",
  time: new Date(),
  attachments: [],
  agent: null,
};

function formatTime(date) {
  return new Intl.DateTimeFormat("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function createId(prefix = "msg") {
  return `${prefix}-${Date.now()}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
}

function getFileIcon(fileType = "") {
  if (fileType.startsWith("image/")) {
    return <ImageIcon size={14} />;
  }

  return <FileText size={14} />;
}

function mapHistoryMessage(message) {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    time: new Date(message.created_at),
    attachments: (message.attachments || []).map(
      (attachment) => ({
        name: attachment.filename,
        size: 0,
        type: attachment.content_type || "",
        file_id: attachment.file_id,
      })
    ),
    agent: null,
  };
}

/*
 * Sends the current NOVA state to the 3D runtime.
 */
function emitAvatarState(state, audioLevel = 0) {
  window.dispatchEvent(
    new CustomEvent("nova:avatar-state", {
      detail: {
        state,
        audioLevel,
        timestamp: Date.now(),
      },
    })
  );
}

/*
 * Decide whether the user is asking for an agentic workflow.
 *
 * Normal conversation remains on /api/chat/.
 * Explicit local knowledge / planning / execution / artifact
 * generation requests use /api/agents/run.
 */
function isAgentRequest(message) {
  const text = message.toLowerCase().trim();

  const agentSignals = [
    // Knowledge / retrieval
    "local knowledge",
    "knowledge base",
    "knowledge vault",
    "search my documents",
    "search the documents",
    "search documents",
    "find in my documents",
    "find in the knowledge",
    "look up in my documents",
    "retrieve from",
    "search the local",

    // File/document understanding
    "analyze the document",
    "analyse the document",
    "analyze the file",
    "analyse the file",

    // Planning / agentic execution
    "create a plan",
    "make a plan",
    "plan this task",
    "execute this",
    "execute the task",
    "perform this task",
    "run this task",
    "agent",
    "mission",
    "workflow",
    "investigate",
    "root cause",

    // Explicit DOCX / Word generation
    "create a docx",
    "create docx",
    "generate a docx",
    "generate docx",
    "write a docx",
    "write docx",
    "make a docx",
    "create a word document",
    "create word document",
    "generate a word document",
    "generate word document",
    "write a word document",
    "write word document",
    "create a word file",
    "create word file",
    "generate a word file",
    "generate word file",
    "make a word document",
    ".docx",

    // PDF
    "create a pdf",
    "generate a pdf",
    "write a pdf",
    ".pdf",

    // Excel
    "create an excel",
    "create excel",
    "generate an excel",
    "generate excel",
    ".xlsx",

    // PowerPoint
    "create a powerpoint",
    "create powerpoint",
    "generate a powerpoint",
    "generate powerpoint",
    ".pptx",

    // Plain file generation
    "create a file",
    "create file",
    "generate a file",
    "generate file",
    "write a file",
    "write file",
    "save this to",
    "save it to",
  ];

  /*
   * Natural-language document generation.
   *
   * Examples:
   * Create a document about cybersecurity
   * Create a 5-page professional report on NOVA
   * Generate a technical report on NOVA
   * Prepare a project proposal for NOVA
   * Draft a formal letter about ...
   * Write meeting notes for ...
   */
  const naturalDocumentPattern =
    /\b(create|generate|write|make|prepare|draft|produce|build)\b[\s\S]{0,120}\b(document|docx|word document|word file|report|proposal|letter|summary|notes|documentation)\b/i;

  return (
    agentSignals.some((signal) =>
      text.includes(signal)
    ) ||
    naturalDocumentPattern.test(text)
  );
}

/*
 * Decide whether the request specifically requires
 * automatic document artifact generation.
 *
 * This is intentionally broader than checking for ".docx".
 */
function isDocumentGenerationRequest(message) {
  const text = message.toLowerCase().trim();

  const explicitDocumentSignals = [
    "create a docx",
    "create docx",
    "generate a docx",
    "generate docx",
    "write a docx",
    "write docx",
    "make a docx",
    "create a word document",
    "create word document",
    "generate a word document",
    "generate word document",
    "write a word document",
    "write word document",
    "create a word file",
    "create word file",
    "generate a word file",
    "generate word file",
    "make a word document",
    ".docx",
  ];

  const naturalDocumentPattern =
    /\b(create|generate|write|make|prepare|draft|produce|build)\b[\s\S]{0,120}\b(document|docx|word document|word file|report|proposal|letter|summary|notes|documentation)\b/i;

  return (
    explicitDocumentSignals.some((signal) =>
      text.includes(signal)
    ) ||
    naturalDocumentPattern.test(text)
  );
}

function getStepStatusIcon(status) {
  if (status === "completed") {
    return <CheckCircle2 size={13} />;
  }

  if (status === "failed") {
    return <AlertCircle size={13} />;
  }

  return <Activity size={13} />;
}

/*
 * Convert a NOVA workspace-relative file path into
 * the backend download endpoint.
 */
function getDownloadUrl(filePath) {
  if (!filePath) {
    return null;
  }

  const normalizedPath = String(filePath)
    .replace(/\\/g, "/")
    .replace(/^\/+/, "");

  if (!normalizedPath) {
    return null;
  }

  const pathParts = normalizedPath
    .split("/")
    .filter(Boolean)
    .map((part) => encodeURIComponent(part));

  return `${API_URL}/api/chat/download/${pathParts.join("/")}`;
}

/*
 * Extract generated artifacts from the agent execution context.
 */
function getAgentArtifacts(execution) {
  if (!execution?.context) {
    return [];
  }

  const artifacts = [];

  Object.entries(execution.context).forEach(
    ([stepId, result]) => {
      if (
        !result ||
        typeof result !== "object" ||
        !result.file_path
      ) {
        return;
      }

      const filePath = String(
        result.file_path
      ).replace(/\\/g, "/");

      const fileName =
        result.file_name ||
        filePath.split("/").pop() ||
        `artifact-${stepId}`;

      const extension =
        result.extension ||
        `.${fileName.split(".").pop()}`;

      artifacts.push({
        stepId,
        filePath,
        fileName,
        extension,
        sizeBytes:
          typeof result.size_bytes === "number"
            ? result.size_bytes
            : null,
        downloadUrl: getDownloadUrl(filePath),
      });
    }
  );

  return artifacts;
}

function formatArtifactSize(sizeBytes) {
  if (
    typeof sizeBytes !== "number" ||
    sizeBytes <= 0
  ) {
    return "";
  }

  if (sizeBytes < 1024) {
    return `${sizeBytes} B`;
  }

  if (sizeBytes < 1024 * 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`;
  }

  return `${(
    sizeBytes /
    (1024 * 1024)
  ).toFixed(2)} MB`;
}

/*
 * Render NOVA Markdown responses as proper rich content.
 *
 * Markdown is rendered only for assistant messages.
 * User messages remain plain text.
 */
function NovaMarkdown({ content }) {
  return (
    <div className="nova-markdown">
      <ReactMarkdown
        components={{
          h1: ({ children }) => (
            <h1>{children}</h1>
          ),

          h2: ({ children }) => (
            <h2>{children}</h2>
          ),

          h3: ({ children }) => (
            <h3>{children}</h3>
          ),

          h4: ({ children }) => (
            <h4>{children}</h4>
          ),

          p: ({ children }) => (
            <p>{children}</p>
          ),

          strong: ({ children }) => (
            <strong>{children}</strong>
          ),

          em: ({ children }) => (
            <em>{children}</em>
          ),

          ul: ({ children }) => (
            <ul>{children}</ul>
          ),

          ol: ({ children }) => (
            <ol>{children}</ol>
          ),

          li: ({ children }) => (
            <li>{children}</li>
          ),

          blockquote: ({ children }) => (
            <blockquote>{children}</blockquote>
          ),

          hr: () => <hr />,

          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
            >
              {children}
            </a>
          ),

          code: ({
            inline,
            className,
            children,
          }) => {
            if (inline) {
              return (
                <code className={className}>
                  {children}
                </code>
              );
            }

            return (
              <pre className="nova-markdown-code-block">
                <code className={className}>
                  {children}
                </code>
              </pre>
            );
          },

          table: ({ children }) => (
            <div className="nova-markdown-table-wrap">
              <table>{children}</table>
            </div>
          ),

          thead: ({ children }) => (
            <thead>{children}</thead>
          ),

          tbody: ({ children }) => (
            <tbody>{children}</tbody>
          ),

          tr: ({ children }) => (
            <tr>{children}</tr>
          ),

          th: ({ children }) => (
            <th>{children}</th>
          ),

          td: ({ children }) => (
            <td>{children}</td>
          ),
        }}
      >
        {content || ""}
      </ReactMarkdown>
    </div>
  );
}

export default function ChatWindow({
  conversationId,
  onConversationChange,
  onConversationSaved,
  onNewConversation,
}) {
  const [messages, setMessages] = useState([
    welcomeMessage,
  ]);

  const [input, setInput] = useState("");
  const [status, setStatus] = useState("IDLE");
  const [error, setError] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isLoadingConversation, setIsLoadingConversation] =
    useState(false);

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const idleTimerRef = useRef(null);

  useEffect(() => {
    return () => {
      if (idleTimerRef.current) {
        window.clearTimeout(idleTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadConversation = async () => {
      if (!conversationId) {
        setMessages([welcomeMessage]);
        setStatus("IDLE");
        setError("");

        emitAvatarState("idle");

        return;
      }

      setIsLoadingConversation(true);
      setError("");

      emitAvatarState("idle");

      try {
        const response = await fetch(
          `${API_URL}/api/history/conversations/${conversationId}`
        );

        if (!response.ok) {
          throw new Error(
            "Unable to load this conversation."
          );
        }

        const data = await response.json();

        if (cancelled) {
          return;
        }

        setMessages(
          data.messages?.length
            ? data.messages.map(mapHistoryMessage)
            : [welcomeMessage]
        );

        setStatus("IDLE");
        emitAvatarState("idle");
      } catch (requestError) {
        if (cancelled) {
          return;
        }

        console.error(
          "Conversation loading error:",
          requestError
        );

        setError(
          requestError?.message ||
            "Unable to load conversation."
        );

        setMessages([welcomeMessage]);
        emitAvatarState("idle");
      } finally {
        if (!cancelled) {
          setIsLoadingConversation(false);
        }
      }
    };

    loadConversation();

    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }, [
    messages,
    status,
    isLoadingConversation,
  ]);

  const autoResize = () => {
    const textarea = textareaRef.current;

    if (!textarea) {
      return;
    }

    textarea.style.height = "auto";

    textarea.style.height = `${Math.min(
      textarea.scrollHeight,
      180
    )}px`;
  };

  const handleInputChange = (event) => {
    setInput(event.target.value);

    requestAnimationFrame(autoResize);
  };

  const handleFileSelection = (event) => {
    const files = Array.from(
      event.target.files || []
    );

    if (!files.length) {
      return;
    }

    setError("");

    const maxSize = 20 * 1024 * 1024;

    const validFiles = files.filter(
      (file) => file.size <= maxSize
    );

    const oversizedFiles = files.filter(
      (file) => file.size > maxSize
    );

    if (oversizedFiles.length) {
      setError(
        "One or more files exceed the 20 MB limit."
      );
    }

    setSelectedFiles((current) => {
      const existing = new Set(
        current.map(
          (file) =>
            `${file.name}-${file.size}`
        )
      );

      const next = [...current];

      for (const file of validFiles) {
        const key = `${file.name}-${file.size}`;

        if (!existing.has(key)) {
          next.push(file);
        }
      }

      return next;
    });

    event.target.value = "";
  };

  const removeFile = (fileToRemove) => {
    setSelectedFiles((current) =>
      current.filter(
        (file) =>
          !(
            file.name === fileToRemove.name &&
            file.size === fileToRemove.size
          )
      )
    );
  };

  const uploadSelectedFiles = async () => {
    if (!selectedFiles.length) {
      return [];
    }

    const uploaded = [];

    for (const file of selectedFiles) {
      const formData = new FormData();

      formData.append("file", file);

      const response = await fetch(
        `${API_URL}/api/chat/upload`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        const errorText = await response.text();

        throw new Error(
          errorText ||
            `Failed to upload ${file.name}`
        );
      }

      const data = await response.json();

      if (!data.file?.file_id) {
        throw new Error(
          `Backend did not return a file ID for ${file.name}.`
        );
      }

      uploaded.push({
        file_id: data.file.file_id,
        filename: data.file.filename,
        content_type:
          data.file.content_type || file.type,
      });
    }

    return uploaded;
  };

  /*
   * Run NOVA's agent endpoint.
   *
   * Document generation is automatically confirmed
   * because the user explicitly requested creation
   * of an artifact.
   */
  const runAgent = async (message) => {
    const directDocumentGeneration =
      isDocumentGenerationRequest(message);

    const response = await fetch(
      `${API_URL}/api/agents/run`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          objective: message,
          context: {
            conversation_id:
              conversationId || null,
            source: "nova-local-chat",
          },
          auto_confirm:
            directDocumentGeneration,
        }),
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data?.detail ||
          "NOVA agent could not process the request."
      );
    }

    return data;
  };

  /*
   * Run the existing normal chat endpoint.
   */
  const runNormalChat = async (
    message,
    uploadedFiles
  ) => {
    const response = await fetch(
      `${API_URL}/api/chat/`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message,
          model: MODEL,
          conversation_id:
            conversationId || null,
          attachments: uploadedFiles,
        }),
      }
    );

    if (!response.ok) {
      const errorText = await response.text();

      throw new Error(
        errorText ||
          "NOVA could not process the request."
      );
    }

    return response.json();
  };

  const sendMessage = async () => {
    const message = input.trim();

    if (
      (!message && !selectedFiles.length) ||
      isSending
    ) {
      return;
    }

    setError("");
    setIsSending(true);

    /*
     * Attachments continue through normal chat because
     * the current Agent API does not yet accept uploaded
     * attachment references.
     */
    const useAgent =
      !selectedFiles.length &&
      isAgentRequest(message);

    const initialStatus = selectedFiles.length
      ? "ANALYZING"
      : useAgent
        ? "PLANNING"
        : "THINKING";

    setStatus(initialStatus);

    emitAvatarState("thinking");

    const attachedFileMetadata =
      selectedFiles.map((file) => ({
        name: file.name,
        size: file.size,
        type: file.type,
      }));

    const userMessage = {
      id: createId("user"),
      role: "user",
      content:
        message ||
        "Please analyze the attached file.",
      time: new Date(),
      attachments: attachedFileMetadata,
      agent: null,
    };

    setMessages((current) => [
      ...current,
      userMessage,
    ]);

    setInput("");

    requestAnimationFrame(() => {
      if (textareaRef.current) {
        textareaRef.current.style.height =
          "auto";
      }
    });

    try {
      /*
       * =============================================================
       * AGENTIC PIPELINE
       * =============================================================
       */

      if (useAgent) {
        setStatus("PLANNING");

        const agentData =
          await runAgent(message);

        setStatus("EXECUTING");

        const assistantText =
          agentData.response ||
          "NOVA completed the agent workflow.";

        const assistantMessage = {
          id: createId("nova"),
          role: "assistant",
          content: assistantText,
          time: new Date(),
          attachments: [],
          agent: {
            plan: agentData.plan || null,
            execution:
              agentData.execution || null,
            artifacts: getAgentArtifacts(
              agentData.execution
            ),
          },
        };

        setMessages((current) => [
          ...current,
          assistantMessage,
        ]);

        window.dispatchEvent(
          new CustomEvent("nova:speak", {
            detail: {
              text: assistantText,
            },
          })
        );

        setStatus("RESPONDING");

        emitAvatarState(
          "speaking",
          0.7
        );

        if (
          agentData.plan?.status ===
          "failed"
        ) {
          setStatus("ERROR");
        }

        if (idleTimerRef.current) {
          window.clearTimeout(
            idleTimerRef.current
          );
        }

        idleTimerRef.current =
          window.setTimeout(() => {
            setStatus("IDLE");

            emitAvatarState(
              "idle",
              0
            );
          }, 900);

        return;
      }

      /*
       * =============================================================
       * NORMAL CHAT PIPELINE
       * =============================================================
       */

      const uploadedFiles =
        await uploadSelectedFiles();

      emitAvatarState("thinking");

      const data =
        await runNormalChat(
          message ||
            "Analyze the attached file.",
          uploadedFiles
        );

      setStatus("RESPONDING");

      emitAvatarState(
        "speaking",
        0.7
      );

      const responseText =
        data.response ||
        "NOVA did not return a response.";

      const assistantMessage = {
        id: createId("nova"),
        role: "assistant",
        content: responseText,
        time: new Date(),
        attachments: [],
        agent: null,
      };

      window.dispatchEvent(
        new CustomEvent("nova:speak", {
          detail: {
            text: responseText,
          },
        })
      );

      setMessages((current) => [
        ...current,
        assistantMessage,
      ]);

      setSelectedFiles([]);

      if (
        data.conversation_id &&
        data.conversation_id !== conversationId
      ) {
        onConversationChange(
          data.conversation_id
        );
      }

      onConversationSaved();

      setStatus("COMPLETE");

      if (idleTimerRef.current) {
        window.clearTimeout(
          idleTimerRef.current
        );
      }

      idleTimerRef.current =
        window.setTimeout(() => {
          setStatus("IDLE");

          emitAvatarState(
            "idle",
            0
          );
        }, 900);
    } catch (requestError) {
      console.error(
        "NOVA request error:",
        requestError
      );

      setError(
        requestError?.message ||
          "Something went wrong while contacting NOVA."
      );

      setStatus("ERROR");

      emitAvatarState(
        "idle",
        0
      );
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (event) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();

      sendMessage();
    }
  };

  const handleNewConversation = () => {
    setInput("");
    setSelectedFiles([]);
    setError("");
    setStatus("IDLE");

    emitAvatarState(
      "idle",
      0
    );

    onNewConversation();
  };

  return (
    <div className="nova-chat-page">
      {/* =========================================================
          HERO
      ========================================================== */}

      <motion.section
        className="nova-chat-hero"
        initial={{
          opacity: 0,
          y: 30,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
        transition={{
          duration: 0.55,
          ease: "easeOut",
        }}
      >
        <div className="nova-chat-hero-copy">
          <div className="nova-chat-eyebrow">
            <span />
            LOCAL INTELLIGENCE WORKSPACE
          </div>

          <div className="nova-chat-title-row">
            <h1>
              NOVA
              <span>LOCAL CHAT</span>
            </h1>

            <div className="nova-chat-live-badge">
              <i />
              LOCAL RUNTIME
            </div>
          </div>

          <p>
            Private AI interaction powered by
            your local inference runtime.
          </p>
        </div>

        <div className="nova-chat-hero-side">
          <div className="nova-chat-runtime-mark">
            <span>
              <Sparkles size={13} />
            </span>

            <div>
              <small>ACTIVE MODEL</small>
              <strong>LLAMA 3.2</strong>
            </div>
          </div>
        </div>
      </motion.section>

      {/* =========================================================
          RUNTIME STRIP
      ========================================================== */}

      <motion.section
        className="nova-chat-command-strip"
        initial={{
          opacity: 0,
          y: 20,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
        transition={{
          duration: 0.5,
          delay: 0.08,
        }}
      >
        <div className="nova-chat-command-item">
          <Cpu size={15} />

          <div>
            <small>MODEL</small>
            <strong>LLAMA 3.2</strong>
          </div>
        </div>

        <div className="nova-chat-command-item">
          <LockKeyhole size={15} />

          <div>
            <small>MODE</small>
            <strong>LOCAL</strong>
          </div>
        </div>

        <div className="nova-chat-command-item">
          <Activity size={15} />

          <div>
            <small>STATE</small>
            <strong>{status}</strong>
          </div>
        </div>

        <div className="nova-chat-command-item">
          <BrainCircuit size={15} />

          <div>
            <small>AGENT</small>
            <strong>READY</strong>
          </div>
        </div>

        <div className="nova-chat-command-item">
          <Sparkles size={15} />

          <div>
            <small>ENGINE</small>
            <strong>OLLAMA</strong>
          </div>
        </div>

        <div className="nova-chat-security">
          <span className="nova-chat-security-line" />
          NO CLOUD CHAT
        </div>
      </motion.section>

      {/* =========================================================
          MAIN CHAT SHELL
      ========================================================== */}

      <motion.section
        className="nova-chat-shell"
        initial={{
          opacity: 0,
          y: 25,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
        transition={{
          duration: 0.55,
          delay: 0.15,
        }}
      >
        <div className="nova-chat-shell-top">
          <div className="nova-chat-session-info">
            <div className="nova-chat-session-icon">
              <MessageSquare size={15} />
            </div>

            <div>
              <small>CONVERSATION</small>

              <strong>
                {conversationId
                  ? "SAVED SESSION"
                  : "NEW SESSION"}
              </strong>
            </div>
          </div>

          <button
            type="button"
            className="nova-chat-clear-button"
            onClick={handleNewConversation}
          >
            <RotateCcw size={13} />
            NEW CHAT
          </button>
        </div>

        <div className="nova-chat-body">
          <div className="nova-chat-body-grid" />

          <div className="nova-chat-messages">
            {isLoadingConversation ? (
              <div className="nova-chat-loading">
                <span className="nova-thinking-pulse" />
                LOADING CONVERSATION...
              </div>
            ) : (
              messages.map((message) => (
                <motion.div
                  key={message.id}
                  className={`nova-chat-message ${
                    message.role === "user"
                      ? "is-user"
                      : "is-assistant"
                  }`}
                  initial={{
                    opacity: 0,
                    y: 16,
                  }}
                  animate={{
                    opacity: 1,
                    y: 0,
                  }}
                  transition={{
                    duration: 0.3,
                    ease: "easeOut",
                  }}
                >
                  <div className="nova-chat-message-top">
                    <div className="nova-chat-message-author">
                      <span className="nova-chat-avatar">
                        {message.role === "user"
                          ? "U"
                          : "N"}
                      </span>

                      <span>
                        {message.role === "user"
                          ? "YOU"
                          : "NOVA"}
                      </span>
                    </div>

                    <time>
                      {formatTime(message.time)}
                    </time>
                  </div>

                  {message.attachments?.length >
                    0 && (
                    <div className="nova-chat-message-files">
                      {message.attachments.map(
                        (file) => (
                          <div
                            className="nova-chat-message-file"
                            key={`${file.name}-${
                              file.file_id ||
                              file.size
                            }`}
                          >
                            {getFileIcon(
                              file.type
                            )}

                            <span>
                              {file.name}
                            </span>
                          </div>
                        )
                      )}
                    </div>
                  )}

                  <div className="nova-chat-message-content">
                    {message.role === "assistant" ? (
                      <NovaMarkdown
                        content={
                          message.content
                        }
                      />
                    ) : (
                      message.content
                    )}
                  </div>

                  {/* =================================================
                      AGENT EXECUTION DETAILS
                  ================================================== */}

                  {message.agent?.plan && (
                    <div className="nova-agent-panel">
                      <div className="nova-agent-panel-header">
                        <div>
                          <BrainCircuit size={14} />

                          <span>
                            AGENT EXECUTION
                          </span>
                        </div>

                        <span
                          className={`nova-agent-status status-${
                            message.agent.plan
                              .status ||
                            "unknown"
                          }`}
                        >
                          {message.agent.plan
                            .status ||
                            "UNKNOWN"}
                        </span>
                      </div>

                      {message.agent.plan
                        .steps?.length >
                        0 && (
                        <div className="nova-agent-steps">
                          {message.agent.plan.steps.map(
                            (step) => (
                              <div
                                className="nova-agent-step"
                                key={step.id}
                              >
                                <span className="nova-agent-step-icon">
                                  {getStepStatusIcon(
                                    step.status
                                  )}
                                </span>

                                <div className="nova-agent-step-info">
                                  <strong>
                                    {step.title}
                                  </strong>

                                  <small>
                                    {step.tool}
                                  </small>
                                </div>

                                <span
                                  className={`nova-agent-step-status status-${step.status}`}
                                >
                                  {step.status}
                                </span>
                              </div>
                            )
                          )}
                        </div>
                      )}

                      {message.agent.execution && (
                        <div className="nova-agent-execution-summary">
                          <span>
                            COMPLETED{" "}
                            {
                              message.agent
                                .execution
                                .completed_steps
                                ?.length
                            }
                          </span>

                          <span>
                            FAILED{" "}
                            {
                              message.agent
                                .execution
                                .failed_steps
                                ?.length
                            }
                          </span>

                          <span>
                            BLOCKED{" "}
                            {
                              message.agent
                                .execution
                                .blocked_steps
                                ?.length
                            }
                          </span>
                        </div>
                      )}

                      {/* =================================================
                          GENERATED ARTIFACTS
                      ================================================== */}

                      {message.agent.artifacts?.length >
                        0 && (
                        <div className="nova-agent-artifacts">
                          <div className="nova-agent-artifacts-header">
                            <span>
                              GENERATED ARTIFACTS
                            </span>

                            <small>
                              LOCAL WORKSPACE
                            </small>
                          </div>

                          <div className="nova-agent-artifact-list">
                            {message.agent.artifacts.map(
                              (artifact) => (
                                <div
                                  className="nova-agent-artifact"
                                  key={`${artifact.stepId}-${artifact.filePath}`}
                                >
                                  <div className="nova-agent-artifact-icon">
                                    <FileText
                                      size={15}
                                    />
                                  </div>

                                  <div className="nova-agent-artifact-info">
                                    <strong>
                                      {artifact.fileName}
                                    </strong>

                                    <small>
                                      {artifact.extension}

                                      {artifact.sizeBytes
                                        ? ` · ${formatArtifactSize(
                                            artifact.sizeBytes
                                          )}`
                                        : ""}
                                    </small>
                                  </div>

                                  {artifact.downloadUrl && (
                                    <a
                                      className="nova-agent-artifact-download"
                                      href={
                                        artifact.downloadUrl
                                      }
                                      download={
                                        artifact.fileName
                                      }
                                      title={`Download ${artifact.fileName}`}
                                    >
                                      <Download
                                        size={14}
                                      />

                                      <span>
                                        DOWNLOAD
                                      </span>
                                    </a>
                                  )}
                                </div>
                              )
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </motion.div>
              ))
            )}

            {isSending && (
              <motion.div
                className="nova-chat-thinking"
                initial={{
                  opacity: 0,
                  y: 5,
                }}
                animate={{
                  opacity: 1,
                  y: 0,
                }}
                transition={{
                  duration: 0.25,
                  ease: "easeOut",
                }}
              >
                <span className="nova-thinking-pulse" />

                <strong>
                  {status === "PLANNING"
                    ? "NOVA IS PLANNING..."
                    : status === "EXECUTING"
                      ? "NOVA IS EXECUTING..."
                      : "NOVA IS THINKING..."}
                </strong>

                <span
                  className="nova-thinking-bars"
                  aria-hidden="true"
                >
                  <i />
                  <i />
                  <i />
                </span>
              </motion.div>
            )}

            {error && (
              <div className="nova-chat-runtime-error">
                <strong>
                  NOVA RUNTIME ERROR
                </strong>

                <span>{error}</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* =======================================================
            COMPOSER
        ======================================================== */}

        <div className="nova-chat-composer">
          <div className="nova-chat-composer-header">
            <div>
              <span className="composer-indicator" />
              <span>LOCAL REQUEST</span>
            </div>

            <span>
              AGENT TASKS AUTO-ROUTED · ENTER TO SEND
            </span>
          </div>

          {selectedFiles.length > 0 && (
            <div className="nova-chat-attachments">
              {selectedFiles.map((file) => (
                <div
                  className="nova-chat-attachment"
                  key={`${file.name}-${file.size}`}
                >
                  <span className="nova-chat-attachment-icon">
                    {getFileIcon(
                      file.type
                    )}
                  </span>

                  <div className="nova-chat-attachment-info">
                    <strong>
                      {file.name}
                    </strong>

                    <small>
                      {(
                        file.size /
                        1024 /
                        1024
                      ).toFixed(2)}{" "}
                      MB
                    </small>
                  </div>

                  <button
                    type="button"
                    onClick={() =>
                      removeFile(file)
                    }
                    aria-label={`Remove ${file.name}`}
                  >
                    <X size={13} />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="nova-chat-input-row">
            <button
              type="button"
              className="nova-chat-attach-button"
              onClick={() =>
                fileInputRef.current?.click()
              }
              disabled={isSending}
              title="Attach file"
            >
              <Paperclip size={17} />
            </button>

            <input
              ref={fileInputRef}
              type="file"
              hidden
              multiple
              accept=".pdf,.txt,.docx,image/png,image/jpeg,image/webp"
              onChange={
                handleFileSelection
              }
            />

            <textarea
              ref={textareaRef}
              className="nova-chat-composer-input"
              value={input}
              onChange={
                handleInputChange
              }
              onKeyDown={
                handleKeyDown
              }
              placeholder="Ask NOVA anything..."
              rows={1}
              disabled={
                isSending ||
                isLoadingConversation
              }
            />

            <button
              type="button"
              className="nova-chat-send"
              onClick={sendMessage}
              disabled={
                isSending ||
                isLoadingConversation ||
                (!input.trim() &&
                  !selectedFiles.length)
              }
              aria-label="Send message"
            >
              {isSending ? (
                <LoaderCircle
                  size={18}
                  className="nova-spin"
                />
              ) : (
                <ArrowUp size={18} />
              )}
            </button>
          </div>

          <div className="nova-chat-composer-footer">
            <span>
              PRIVATE SESSION
            </span>

            <span>
              LOCAL MODEL / AGENT READY / NO CLOUD
              TRANSMISSION
            </span>
          </div>
        </div>
      </motion.section>

      <div className="nova-chat-footer-signal">
        <span />
        NOVA INTELLIGENCE RUNTIME
      </div>
    </div>
  );
}