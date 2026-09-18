import {
  ChevronRight,
  Command,
  LockKeyhole,
  LogOut,
  Menu,
  UserRound,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";

export default function Topbar({
  activePage,
  onMenuClick,
  onCommandClick,
}) {
  const {
    user,
    logout,
    isLoading,
  } = useAuth();

  const email =
    user?.email ||
    user?.username ||
    "NOVA USER";

  const initials = email
    .split("@")[0]
    .split(/[._-\s]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0))
    .join("")
    .toUpperCase() || "NU";

  const handleLogout = async () => {
    if (isLoading) {
      return;
    }

    await logout();
  };

  return (
    <header className="nova-topbar">
      <button
        className="mobile-menu-button"
        onClick={onMenuClick}
        aria-label="Open navigation"
        type="button"
      >
        <Menu size={20} />
      </button>

      <div className="topbar-breadcrumb">
        <span>NOVA</span>

        <ChevronRight size={14} />

        <strong>{activePage}</strong>
      </div>

      <div className="topbar-right">
        <button
          className="command-button"
          onClick={onCommandClick}
          type="button"
        >
          <Command size={14} />
          <span>Command</span>
          <kbd>Ctrl K</kbd>
        </button>

        <div className="secure-badge">
          <span className="status-dot" />

          <LockKeyhole size={13} />

          LOCAL / SECURE
        </div>

        <div
          className="nova-user-menu"
          title={email}
        >
          <div className="nova-user-identity">
            <span className="nova-user-email">
              {email}
            </span>

            <span className="nova-user-label">
              AUTHENTICATED
            </span>
          </div>

          <div
            className="profile-badge"
            aria-label={`Signed in as ${email}`}
          >
            {initials || (
              <UserRound size={15} />
            )}
          </div>

          <button
            className="nova-logout-button"
            onClick={handleLogout}
            type="button"
            aria-label={`Sign out ${email}`}
            disabled={isLoading}
            title="Sign out"
          >
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </header>
  );
}