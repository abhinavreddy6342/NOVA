import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Command, Search, X } from "lucide-react";

import Sidebar from "./components/layout/Sidebar";
import Topbar from "./components/layout/Topbar";
import CommandCenter from "./components/dashboard/CommandCenter";
import Missions from "./components/dashboard/Missions";
import ChatWindow from "./components/chat/ChatWindow";
import KnowledgeVault from "./components/knowledge/KnowledgeVault";
import VoiceController from "./components/voice/VoiceController";

const API_URL = "http://127.0.0.1:8001";

const pages = {
  command: "Command Center",
  chat: "Local Chat",
  missions: "Missions",
  knowledge: "Knowledge Vault",
  models: "AI Models",
  sovereignty: "Sovereignty",
  audit: "Audit Trail",
  analytics: "Analytics",
};

function PlaceholderPage({ page, onBack }) {
  return (
    <motion.div
      className="placeholder-page"
      initial={{
        opacity: 0,
        y: 14,
      }}
      animate={{
        opacity: 1,
        y: 0,
      }}
      exit={{
        opacity: 0,
        y: -10,
      }}
      transition={{
        duration: 0.3,
      }}
    >
      <div className="placeholder-symbol">
        <Command size={28} />
      </div>

      <span>MODULE INITIALIZATION</span>

      <h1>{pages[page]}</h1>

      <p>
        This NOVA module is part of the
        sovereign intelligence workspace
        and will be connected to the local
        AI runtime in the next implementation
        phase.
      </p>

      <button
        className="placeholder-button"
        onClick={onBack}
        type="button"
      >
        Return to Command Center
      </button>
    </motion.div>
  );
}

function CommandPalette({ onClose, onNavigate }) {
  const commands = [
    ["command", "Open Command Center"],
    ["chat", "Open Local Chat"],
    ["missions", "Start New Mission"],
    ["knowledge", "Open Knowledge Vault"],
    ["models", "Open AI Models"],
    ["sovereignty", "Check Sovereignty"],
  ];

  return (
    <motion.div
      className="command-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onMouseDown={onClose}
    >
      <motion.div
        className="command-modal"
        initial={{
          opacity: 0,
          y: -18,
          scale: 0.98,
        }}
        animate={{
          opacity: 1,
          y: 0,
          scale: 1,
        }}
        transition={{
          duration: 0.2,
        }}
        onMouseDown={(event) =>
          event.stopPropagation()
        }
      >
        <div className="command-search">
          <Search size={18} />

          <input
            autoFocus
            placeholder="Search NOVA..."
          />

          <kbd>ESC</kbd>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close command palette"
          >
            <X size={16} />
          </button>
        </div>

        <div className="command-results">
          {commands.map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => {
                onNavigate(id);
                onClose();
              }}
            >
              <span>{label}</span>
              <span>↵</span>
            </button>
          ))}
        </div>
      </motion.div>
    </motion.div>
  );
}

function App() {
  const [activePage, setActivePage] =
    useState("command");

  const [mobileSidebar, setMobileSidebar] =
    useState(false);

  const [commandOpen, setCommandOpen] =
    useState(false);

  const [conversations, setConversations] =
    useState([]);

  const [
    activeConversationId,
    setActiveConversationId,
  ] = useState(null);

  const [historyLoading, setHistoryLoading] =
    useState(false);

  const loadConversations =
    useCallback(async () => {
      try {
        setHistoryLoading(true);

        const response = await fetch(
          `${API_URL}/api/history/conversations`
        );

        if (!response.ok) {
          throw new Error(
            "Unable to load chat history."
          );
        }

        const data =
          await response.json();

        const savedConversations =
          Array.isArray(
            data?.conversations
          )
            ? data.conversations
            : [];

        setConversations(
          savedConversations
        );
      } catch (error) {
        console.error(
          "Chat history loading error:",
          error
        );
      } finally {
        setHistoryLoading(false);
      }
    }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const navigate = (page) => {
    setActivePage(page);
    setMobileSidebar(false);
    setCommandOpen(false);
  };

  const handleNewConversation = () => {
    setActiveConversationId(null);
    setActivePage("chat");
    setMobileSidebar(false);
  };

  const handleSelectConversation = (
    conversationId
  ) => {
    if (!conversationId) {
      return;
    }

    setActiveConversationId(
      conversationId
    );

    setActivePage("chat");
    setMobileSidebar(false);
  };

  const handleConversationChange = (
    conversationId
  ) => {
    if (!conversationId) {
      return;
    }

    setActiveConversationId(
      conversationId
    );

    setActivePage("chat");
  };

  const handleDeleteConversation =
    async (conversationId) => {
      if (!conversationId) {
        return;
      }

      const conversation =
        conversations.find(
          (item) =>
            String(item.id) ===
            String(conversationId)
        );

      const confirmed =
        window.confirm(
          `Delete "${
            conversation?.title ||
            "this conversation"
          }"?`
        );

      if (!confirmed) {
        return;
      }

      try {
        const response =
          await fetch(
            `${API_URL}/api/history/conversations/${conversationId}`,
            {
              method: "DELETE",
            }
          );

        if (!response.ok) {
          let message =
            "Conversation could not be deleted.";

          try {
            const data =
              await response.json();

            message =
              data?.detail ||
              message;
          } catch {
            // Keep default message.
          }

          throw new Error(message);
        }

        setConversations(
          (current) =>
            current.filter(
              (item) =>
                String(item.id) !==
                String(conversationId)
            )
        );

        if (
          String(activeConversationId) ===
          String(conversationId)
        ) {
          setActiveConversationId(null);
          setActivePage("chat");
        }
      } catch (error) {
        console.error(
          "Conversation deletion error:",
          error
        );

        window.alert(
          error?.message ||
            "Unable to delete conversation."
        );
      }
    };

  return (
    <div className="nova-app">
      <div className="background-grid" />

      <div className="background-glow glow-one" />

      <div className="background-glow glow-two" />

      <VoiceController />

      <Sidebar
        activePage={activePage}
        onNavigate={navigate}
        mobileOpen={mobileSidebar}
        conversations={conversations}
        activeConversationId={
          activeConversationId
        }
        onSelectConversation={
          handleSelectConversation
        }
        onNewConversation={
          handleNewConversation
        }
        onDeleteConversation={
          handleDeleteConversation
        }
      />

      {mobileSidebar && (
        <button
          className="mobile-backdrop"
          type="button"
          onClick={() =>
            setMobileSidebar(false)
          }
          aria-label="Close sidebar"
        />
      )}

      <div className="nova-main">
        <Topbar
          activePage={
            pages[activePage]
          }
          onMenuClick={() =>
            setMobileSidebar(true)
          }
          onCommandClick={() =>
            setCommandOpen(true)
          }
        />

        <AnimatePresence mode="wait">
          {activePage === "command" ? (
            <motion.div
              key="command"
              initial={{
                opacity: 0,
              }}
              animate={{
                opacity: 1,
              }}
              exit={{
                opacity: 0,
              }}
            >
              <CommandCenter
                onNavigate={navigate}
              />
            </motion.div>
          ) : activePage === "chat" ? (
            <motion.div
              key={`chat-${
                activeConversationId ||
                "new"
              }`}
              initial={{
                opacity: 0,
                y: 14,
              }}
              animate={{
                opacity: 1,
                y: 0,
              }}
              exit={{
                opacity: 0,
                y: -10,
              }}
              transition={{
                duration: 0.35,
                ease: "easeOut",
              }}
            >
              <ChatWindow
                conversationId={
                  activeConversationId
                }
                onConversationChange={
                  handleConversationChange
                }
                onConversationSaved={
                  loadConversations
                }
                onNewConversation={
                  handleNewConversation
                }
              />
            </motion.div>
          ) : activePage === "missions" ? (
            <motion.div
              key="missions"
              initial={{
                opacity: 0,
                y: 16,
              }}
              animate={{
                opacity: 1,
                y: 0,
              }}
              exit={{
                opacity: 0,
                y: -10,
              }}
              transition={{
                duration: 0.35,
                ease: "easeOut",
              }}
            >
              <Missions
                onNavigate={navigate}
              />
            </motion.div>
          ) : activePage === "knowledge" ? (
            <motion.div
              key="knowledge"
              initial={{
                opacity: 0,
                y: 14,
              }}
              animate={{
                opacity: 1,
                y: 0,
              }}
              exit={{
                opacity: 0,
                y: -10,
              }}
              transition={{
                duration: 0.35,
                ease: "easeOut",
              }}
            >
              <KnowledgeVault />
            </motion.div>
          ) : (
            <PlaceholderPage
              key={activePage}
              page={activePage}
              onBack={() =>
                navigate("command")
              }
            />
          )}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {commandOpen && (
          <CommandPalette
            onClose={() =>
              setCommandOpen(false)
            }
            onNavigate={navigate}
          />
        )}
      </AnimatePresence>

      {historyLoading && (
        <div
          className="nova-history-loading"
          aria-hidden="true"
        >
          SYNCING CHAT HISTORY
        </div>
      )}
    </div>
  );
}

export default App;