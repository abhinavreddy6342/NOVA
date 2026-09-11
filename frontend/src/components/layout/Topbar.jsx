import {
  ChevronRight,
  Command,
  LockKeyhole,
  Menu,
} from "lucide-react";

export default function Topbar({
  activePage,
  onMenuClick,
  onCommandClick,
}) {
  return (
    <header className="nova-topbar">
      <button
        className="mobile-menu-button"
        onClick={onMenuClick}
        aria-label="Open navigation"
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

        <div className="profile-badge">
          AR
        </div>
      </div>
    </header>
  );
}