import {
  Activity,
  BrainCircuit,
  Database,
  Home,
  MessageSquare,
  Plus,
  Settings,
  ShieldCheck,
  TerminalSquare,
  Trash2,
  Zap,
} from "lucide-react";

const workspaceItems = [
  {
    id: "command",
    label: "Command Center",
    icon: Home,
  },
  {
    id: "chat",
    label: "Local Chat",
    icon: MessageSquare,
  },
  {
    id: "missions",
    label: "Missions",
    icon: Zap,
  },
  {
    id: "knowledge",
    label: "Knowledge Vault",
    icon: Database,
  },
  {
    id: "models",
    label: "AI Models",
    icon: BrainCircuit,
  },
];

const systemItems = [
  {
    id: "sovereignty",
    label: "Sovereignty",
    icon: ShieldCheck,
  },
  {
    id: "audit",
    label: "Audit Trail",
    icon: TerminalSquare,
  },
  {
    id: "analytics",
    label: "Analytics",
    icon: Activity,
  },
];

function formatRecentTime(value) {
  if (!value) {
    return "";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export default function Sidebar({
  activePage,
  onNavigate,
  mobileOpen,
  conversations = [],
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
}) {
  const recentConversations = conversations;

  return (
    <aside
      className={`nova-sidebar ${
        mobileOpen ? "mobile-visible" : ""
      }`}
    >
      <div className="sidebar-brand">
        <div className="nova-logo">
          <span />
          <span />
          <span />
        </div>

        <div>
          <div className="brand-title">NOVA</div>

          <div className="brand-caption">
            SOVEREIGN AI
          </div>
        </div>
      </div>

      <button
        className="new-conversation"
        onClick={() => {
          onNewConversation();
          onNavigate("chat");
        }}
        type="button"
      >
        <span className="new-conversation-icon">
          <Plus size={16} />
        </span>

        <span>New conversation</span>
      </button>

      <div className="sidebar-section">
        <div className="sidebar-label">
          WORKSPACE
        </div>

        {workspaceItems.map((item) => {
          const Icon = item.icon;

          const active =
            activePage === item.id;

          return (
            <button
              key={item.id}
              className={`sidebar-item ${
                active ? "active" : ""
              }`}
              onClick={() =>
                onNavigate(item.id)
              }
              type="button"
            >
              <Icon
                size={17}
                strokeWidth={1.8}
              />

              <span>{item.label}</span>

              {active && (
                <span className="active-indicator" />
              )}
            </button>
          );
        })}
      </div>

      <div className="sidebar-section recent-chat-section">
        <div className="sidebar-label recent-label">
          RECENT CHATS
        </div>

        <div className="recent-chat-list">
          {recentConversations.length === 0 ? (
            <div className="recent-empty">
              NO SAVED CONVERSATIONS
            </div>
          ) : (
            recentConversations.map(
              (conversation) => {
                const active =
                  String(
                    activeConversationId
                  ) ===
                  String(
                    conversation.id
                  );

                return (
                  <div
                    key={
                      conversation.id
                    }
                    className={`recent-chat-row ${
                      active
                        ? "active"
                        : ""
                    }`}
                  >
                    <button
                      type="button"
                      className="recent-chat-open"
                      onClick={() => {
                        onSelectConversation(
                          conversation.id
                        );

                        onNavigate(
                          "chat"
                        );
                      }}
                    >
                      <span className="recent-chat-title">
                        {conversation.title ||
                          "Untitled conversation"}
                      </span>

                      <span className="recent-chat-preview">
                        {conversation.preview ||
                          "No messages yet"}
                      </span>

                      <span className="recent-chat-time">
                        {formatRecentTime(
                          conversation.updated_at
                        )}
                      </span>
                    </button>

                    <button
                      type="button"
                      className="recent-chat-delete"
                      onClick={(event) => {
                        event.stopPropagation();

                        onDeleteConversation(
                          conversation.id
                        );
                      }}
                      aria-label={`Delete ${
                        conversation.title ||
                        "conversation"
                      }`}
                      title="Delete conversation"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                );
              }
            )
          )}
        </div>
      </div>

      <div className="sidebar-section system-section">
        <div className="sidebar-label">
          SYSTEM
        </div>

        {systemItems.map((item) => {
          const Icon = item.icon;

          const active =
            activePage === item.id;

          return (
            <button
              key={item.id}
              className={`sidebar-item ${
                active ? "active" : ""
              }`}
              onClick={() =>
                onNavigate(item.id)
              }
              type="button"
            >
              <Icon
                size={17}
                strokeWidth={1.8}
              />

              <span>{item.label}</span>

              {active && (
                <span className="active-indicator" />
              )}
            </button>
          );
        })}
      </div>

      <div className="sidebar-bottom">
        <div className="runtime-card">
          <div className="runtime-heading">
            <span className="status-dot" />
            LOCAL RUNTIME
          </div>

          <div className="runtime-model">
            SOVEREIGN WORKSPACE
          </div>

          <div className="runtime-info">
            <span>
              LIVE DATA SHOWN IN MODULES
            </span>
          </div>

          <div className="runtime-progress">
            <span />
          </div>
        </div>

        <button
          className="sidebar-item"
          type="button"
          onClick={() =>
            onNavigate("sovereignty")
          }
        >
          <Settings
            size={17}
            strokeWidth={1.8}
          />

          <span>Settings</span>
        </button>
      </div>
    </aside>
  );
}