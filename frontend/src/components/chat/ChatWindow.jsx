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
} from "lucide-react";
import { motion } from "framer-motion";

const API_URL = "http://127.0.0.1:8001";
const MODEL = "llama3.2:latest";

const welcomeMessage = {
  id: "nova-welcome",
  role: "assistant",
  content: "Hi! I'm NOVA. How can I help you today?",
  time: new Date(),
  attachments: [],
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
  };
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

  useEffect(() => {
    let cancelled = false;

    const loadConversation = async () => {
      if (!conversationId) {
        setMessages([welcomeMessage]);
        setStatus("IDLE");
        setError("");
        return;
      }

      setIsLoadingConversation(true);
      setError("");

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
    };

    setMessages((current) => [
      ...current,
      userMessage,
    ]);

    setInput("");

    setStatus(
      selectedFiles.length
        ? "ANALYZING"
        : "THINKING"
    );

    requestAnimationFrame(() => {
      if (textareaRef.current) {
        textareaRef.current.style.height =
          "auto";
      }
    });

    try {
      const uploadedFiles =
        await uploadSelectedFiles();

      const response = await fetch(
        `${API_URL}/api/chat/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            message:
              message ||
              "Analyze the attached file.",
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

      setStatus("RESPONDING");

      const data = await response.json();

      const assistantMessage = {
        id: createId("nova"),
        role: "assistant",
        content:
          data.response ||
          "NOVA did not return a response.",
        time: new Date(),
        attachments: [],
      };

      setMessages((current) => [
        ...current,
        assistantMessage,
      ]);

      setSelectedFiles([]);

      /*
       * The backend creates a conversation when
       * conversation_id is null.
       */
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

      window.setTimeout(() => {
        setStatus("IDLE");
      }, 700);
    } catch (requestError) {
      console.error(
        "NOVA chat error:",
        requestError
      );

      setError(
        requestError?.message ||
          "Something went wrong while contacting NOVA."
      );

      setStatus("ERROR");

      /*
       * Don't remove the user's message from the UI here.
       * The user can see the failed request.
       */
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

    onNewConversation();
  };

  return (
    <div className="nova-chat-page">
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
              NOVA<span> LOCAL CHAT</span>
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
                        {message.role ===
                        "user"
                          ? "U"
                          : "N"}
                      </span>

                      <span>
                        {message.role ===
                        "user"
                          ? "YOU"
                          : "NOVA"}
                      </span>
                    </div>

                    <time>
                      {formatTime(
                        message.time
                      )}
                    </time>
                  </div>

                  {message.attachments?.length >
                    0 && (
                    <div className="nova-chat-message-files">
                      {message.attachments.map(
                        (file) => (
                          <div
                            className="nova-chat-message-file"
                            key={`${file.name}-${file.file_id || file.size}`}
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
                    {message.content}
                  </div>
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
                  NOVA IS THINKING...
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

        <div className="nova-chat-composer">
          <div className="nova-chat-composer-header">
            <div>
              <span className="composer-indicator" />
              <span>LOCAL REQUEST</span>
            </div>

            <span>
              ENTER TO SEND · SHIFT + ENTER
              FOR NEW LINE
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
                    {getFileIcon(file.type)}
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
              accept="
                .pdf,
                .txt,
                .docx,
                image/png,
                image/jpeg
              "
              onChange={handleFileSelection}
            />

            <textarea
              ref={textareaRef}
              className="nova-chat-composer-input"
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
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
            <span>PRIVATE SESSION</span>

            <span>
              LOCAL MODEL / NO CLOUD TRANSMISSION
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