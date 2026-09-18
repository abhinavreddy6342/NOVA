import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  AnimatePresence,
  motion,
} from "framer-motion";

import {
  Command,
  Search,
  X,
} from "lucide-react";

import { useAuth } from "./context/AuthContext";

import LoginPage from "./components/auth/LoginPage";
import RegisterPage from "./components/auth/RegisterPage";

import Sidebar from "./components/layout/Sidebar";
import Topbar from "./components/layout/Topbar";
import CommandCenter from "./components/dashboard/CommandCenter";
import ChatWindow from "./components/chat/ChatWindow";
import KnowledgeVault from "./components/knowledge/KnowledgeVault";
import VoiceController from "./components/voice/VoiceController";
import SovereigntyCenter from "./components/sovereignty/SovereigntyCenter";
import AIModels from "./components/models/AIModels";
import AuditTrail from "./components/audit/AuditTrail";
import Analytics from "./components/analytics/Analytics";

const API_URL =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8001";

const pages = {
  command: "Command Center",
  chat: "Local Chat",
  missions: "Missions",
  knowledge: "Knowledge Vault",
  models: "AI Models",
  sovereignty: "Sovereignty",
  audit: "Audit Trail",
  analytics: "Analytics Center",
};



/* =========================================================
   PLACEHOLDER PAGE
   ========================================================= */

function PlaceholderPage({
  page,
  onBack,
}) {
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

      <span>
        MODULE INITIALIZATION
      </span>

      <h1>
        {pages[page]}
      </h1>

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



/* =========================================================
   COMMAND PALETTE
   ========================================================= */

function CommandPalette({
  onClose,
  onNavigate,
}) {
  const commands = [
    [
      "command",
      "Open Command Center",
    ],
    [
      "chat",
      "Open Local Chat",
    ],
    [
      "missions",
      "Start New Mission",
    ],
    [
      "knowledge",
      "Open Knowledge Vault",
    ],
    [
      "models",
      "Open AI Models",
    ],
    [
      "sovereignty",
      "Check Sovereignty",
    ],
    [
      "audit",
      "Open Audit Trail",
    ],
    [
      "analytics",
      "Open Analytics Center",
    ],
  ];

  return (
    <motion.div
      className="command-overlay"
      initial={{
        opacity: 0,
      }}
      animate={{
        opacity: 1,
      }}
      exit={{
        opacity: 0,
      }}
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

          <kbd>
            ESC
          </kbd>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close command palette"
          >
            <X size={16} />
          </button>
        </div>

        <div className="command-results">
          {commands.map(
            ([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => {
                  onNavigate(id);
                  onClose();
                }}
              >
                <span>
                  {label}
                </span>

                <span>
                  ↵
                </span>
              </button>
            )
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}



/* =========================================================
   AUTHENTICATION GATE
   ========================================================= */

function AuthenticationGate() {
  const {
    isAuthenticated,
    isLoading,
    error,
    login,
    register,
    clearError,
  } = useAuth();

  const [
    authView,
    setAuthView,
  ] = useState("login");

  const [
    authNotice,
    setAuthNotice,
  ] = useState("");

  useEffect(() => {
    if (isAuthenticated) {
      setAuthView("login");
      setAuthNotice("");
    }
  }, [isAuthenticated]);

  const handleLogin =
    useCallback(
      async (credentials) => {
        setAuthNotice("");
        clearError();

        return login(credentials);
      },
      [
        clearError,
        login,
      ]
    );

  const handleRegister =
    useCallback(
      async (credentials) => {
        setAuthNotice("");
        clearError();

        const result =
          await register(credentials);

        if (
          result?.success &&
          !result?.user
        ) {
          setAuthView("login");
          setAuthNotice(
            "Account created successfully. Sign in to continue."
          );
        }

        return result;
      },
      [
        clearError,
        register,
      ]
    );

  const handleForgotPassword =
    useCallback(() => {
      setAuthNotice(
        "Password recovery is not configured in this local workspace."
      );
    }, []);

  const handleCreateAccount =
    useCallback(() => {
      clearError();
      setAuthNotice("");
      setAuthView("register");
    }, [clearError]);

  const handleBackToLogin =
    useCallback(() => {
      clearError();
      setAuthNotice("");
      setAuthView("login");
    }, [clearError]);

  if (isLoading) {
    return null;
  }

  if (isAuthenticated) {
    return null;
  }

  if (authView === "register") {
    return (
      <RegisterPage
        onRegister={handleRegister}
        onBackToLogin={handleBackToLogin}
        isLoading={isLoading}
        authError={error}
      />
    );
  }

  return (
    <>
      <LoginPage
        onLogin={handleLogin}
        onForgotPassword={
          handleForgotPassword
        }
        onCreateAccount={
          handleCreateAccount
        }
        isLoading={isLoading}
        authError={error}
      />

      {authNotice ? (
        <div
          className="nova-auth-global-notice"
          role="status"
          aria-live="polite"
        >
          {authNotice}
        </div>
      ) : null}
    </>
  );
}



/* =========================================================
   MAIN NOVA WORKSPACE
   ========================================================= */

function NovaWorkspace() {
  const {
    isAuthenticated,
  } = useAuth();

  const [
    activePage,
    setActivePage,
  ] = useState("command");

  const [
    mobileSidebar,
    setMobileSidebar,
  ] = useState(false);

  const [
    commandOpen,
    setCommandOpen,
  ] = useState(false);

  const [
    conversations,
    setConversations,
  ] = useState([]);

  const [
    activeConversationId,
    setActiveConversationId,
  ] = useState(null);

  const [
    historyLoading,
    setHistoryLoading,
  ] = useState(false);



  /* =======================================================
     LOAD CONVERSATIONS
     ======================================================= */

  const loadConversations =
    useCallback(
      async () => {
        if (
          !isAuthenticated
        ) {
          setConversations([]);
          return;
        }

        try {
          setHistoryLoading(true);

          const response =
            await fetch(
              `${API_URL}/api/history/conversations`,
              {
                method: "GET",
                credentials: "include",
              }
            );

          if (
            response.status === 401
          ) {
            setConversations([]);
            return;
          }

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
      },
      [
        isAuthenticated,
      ]
    );



  /* =======================================================
     INITIAL HISTORY LOAD
     ======================================================= */

  useEffect(() => {
    if (isAuthenticated) {
      loadConversations();
    } else {
      setConversations([]);
      setActiveConversationId(null);
    }
  }, [
    isAuthenticated,
    loadConversations,
  ]);



  /* =======================================================
     NAVIGATION
     ======================================================= */

  const navigate = (
    page
  ) => {
    setActivePage(page);
    setMobileSidebar(false);
    setCommandOpen(false);
  };



  /* =======================================================
     NEW CONVERSATION
     ======================================================= */

  const handleNewConversation =
    () => {
      setActiveConversationId(
        null
      );

      setActivePage(
        "chat"
      );

      setMobileSidebar(
        false
      );
    };



  /* =======================================================
     SELECT SAVED CONVERSATION
     ======================================================= */

  const handleSelectConversation =
    (
      conversationId
    ) => {
      if (!conversationId) {
        return;
      }

      setActiveConversationId(
        conversationId
      );

      setActivePage(
        "chat"
      );

      setMobileSidebar(
        false
      );
    };



  /* =======================================================
     CONVERSATION ID CREATED BY BACKEND
     ======================================================= */

  const handleConversationChange =
    (
      conversationId
    ) => {
      if (!conversationId) {
        return;
      }

      setActiveConversationId(
        conversationId
      );

      setActivePage(
        "chat"
      );
    };



  /* =======================================================
     DELETE CONVERSATION
     ======================================================= */

  const handleDeleteConversation =
    async (
      conversationId
    ) => {
      if (
        !conversationId
      ) {
        return;
      }

      const conversation =
        conversations.find(
          (
            item
          ) =>
            String(
              item.id
            ) ===
            String(
              conversationId
            )
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
              method:
                "DELETE",
              credentials: "include",
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

          throw new Error(
            message
          );
        }

        setConversations(
          (
            current
          ) =>
            current.filter(
              (
                item
              ) =>
                String(
                  item.id
                ) !==
                String(
                  conversationId
                )
            )
        );

        if (
          String(
            activeConversationId
          ) ===
          String(
            conversationId
          )
        ) {
          setActiveConversationId(
            null
          );

          setActivePage(
            "chat"
          );
        }
      } catch (
        error
      ) {
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



  /* =======================================================
     WAIT FOR AUTH
     ======================================================= */

  if (!isAuthenticated) {
    return null;
  }



  /* =======================================================
     RENDER
     ======================================================= */

  return (
    <div className="nova-app">

      <div className="background-grid" />

      <div className="background-glow glow-one" />

      <div className="background-glow glow-two" />

      {/* Global NOVA voice runtime */}

      <VoiceController />



      {/* =================================================
          SIDEBAR
          ================================================= */}

      <Sidebar
        activePage={
          activePage
        }
        onNavigate={
          navigate
        }
        mobileOpen={
          mobileSidebar
        }
        conversations={
          conversations
        }
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



      {/* =================================================
          MOBILE SIDEBAR BACKDROP
          ================================================= */}

      {mobileSidebar && (
        <button
          className="mobile-backdrop"
          type="button"
          onClick={() =>
            setMobileSidebar(
              false
            )
          }
          aria-label="Close sidebar"
        />
      )}



      {/* =================================================
          MAIN AREA
          ================================================= */}

      <div className="nova-main">

        <Topbar
          activePage={
            pages[
              activePage
            ]
          }
          onMenuClick={() =>
            setMobileSidebar(
              true
            )
          }
          onCommandClick={() =>
            setCommandOpen(
              true
            )
          }
        />



        <AnimatePresence mode="wait">

          {/* =================================================
              COMMAND CENTER
              ================================================= */}

          {activePage ===
          "command" ? (

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
                onNavigate={
                  navigate
                }
              />
            </motion.div>



          ) : activePage ===
            "chat" ? (

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



          ) : activePage ===
            "knowledge" ? (

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



          ) : activePage ===
            "models" ? (

            <motion.div
              key="models"
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
              <AIModels />
            </motion.div>



          ) : activePage ===
            "sovereignty" ? (

            <motion.div
              key="sovereignty"
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
              <SovereigntyCenter />
            </motion.div>



          ) : activePage ===
            "audit" ? (

            <motion.div
              key="audit"
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
              <AuditTrail />
            </motion.div>



          ) : activePage ===
            "analytics" ? (

            <motion.div
              key="analytics"
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
              <Analytics
                onNavigate={
                  navigate
                }
              />
            </motion.div>



          ) : (

            <PlaceholderPage
              key={activePage}
              page={activePage}
              onBack={() =>
                navigate(
                  "command"
                )
              }
            />
          )}

        </AnimatePresence>
      </div>



      {/* =================================================
          COMMAND PALETTE
          ================================================= */}

      <AnimatePresence>

        {commandOpen && (
          <CommandPalette
            onClose={() =>
              setCommandOpen(
                false
              )
            }
            onNavigate={
              navigate
            }
          />
        )}

      </AnimatePresence>



      {/* =================================================
          HISTORY SYNC INDICATOR
          ================================================= */}

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



/* =========================================================
   ROOT APP
   ========================================================= */

function App() {
  return (
    <AuthenticatedApp />
  );
}

function AuthenticatedApp() {
  const {
    isAuthenticated,
    isLoading,
  } = useAuth();

  if (
    isLoading &&
    !isAuthenticated
  ) {
    return (
      <main
        className="nova-auth-page"
        aria-busy="true"
        aria-label="Loading NOVA"
      >
        <div className="nova-auth-loading">
          <span className="nova-auth-loading-mark">
            NOVA
          </span>

          <span className="nova-auth-loader" />

          <span className="nova-auth-loading-text">
            VERIFYING SESSION
          </span>
        </div>
      </main>
    );
  }

  if (!isAuthenticated) {
    return (
      <AuthenticationGate />
    );
  }

  return (
    <NovaWorkspace />
  );
}

export default App;
