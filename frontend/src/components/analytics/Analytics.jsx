import { useCallback, useEffect, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Brain,
  CheckCircle2,
  Clock,
  Cpu,
  Database,
  Download,
  FileText,
  Filter,
  HardDrive,
  Layers,
  Pause,
  Play,
  RefreshCw,
  Search,
  Server,
  ShieldCheck,
  Zap,
  XCircle,
  BarChart3,
  Globe,
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

import {
  getAnalyticsDashboard,
  downloadAnalyticsExport,
} from "../../services/api";

const CHART_COLORS = [
  "#3b82f6", // blue
  "#10b981", // emerald
  "#f59e0b", // amber
  "#ef4444", // red
  "#8b5cf6", // purple
  "#06b6d4", // cyan
  "#ec4899", // pink
  "#64748b", // slate
];

const STATUS_COLORS = {
  success: "#10b981",
  successful: "#10b981",
  completed: "#10b981",
  pass: "#10b981",
  failed: "#ef4444",
  failure: "#ef4444",
  error: "#ef4444",
  running: "#3b82f6",
  started: "#3b82f6",
  in_progress: "#3b82f6",
  pending: "#f59e0b",
};

export default function Analytics({ onNavigate }) {
  // State
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [isLive, setIsLive] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);

  // Filters
  const [rangeKey, setRangeKey] = useState("24h");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [service, setService] = useState("");
  const [status, setStatus] = useState("");
  const [model, setModel] = useState("");
  const [taskType, setTaskType] = useState("");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");

  const pollTimerRef = useRef(null);

  // Fetch Dashboard Data
  const fetchDashboard = useCallback(
    async (isManualRefresh = false) => {
      try {
        if (isManualRefresh) setRefreshing(true);
        setError(null);

        const filters = {
          range_key: rangeKey,
          search,
          category,
          service,
          status,
          model,
          task_type: taskType,
          custom_start: rangeKey === "custom" ? customStart : undefined,
          custom_end: rangeKey === "custom" ? customEnd : undefined,
        };

        const res = await getAnalyticsDashboard(filters);
        setData(res);
        setLastUpdated(new Date().toLocaleTimeString());
      } catch (err) {
        console.error("Analytics fetch error:", err);
        setError(err?.message || "Failed to load operational analytics.");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [rangeKey, search, category, service, status, model, taskType, customStart, customEnd]
  );

  // Initial & Filter Change Load
  useEffect(() => {
    setLoading(true);
    fetchDashboard();
  }, [fetchDashboard]);

  // Live Refresh Loop
  useEffect(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }

    if (isLive) {
      pollTimerRef.current = setInterval(() => {
        fetchDashboard(false);
      }, 5000); // Refresh every 5 seconds
    }

    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, [isLive, fetchDashboard]);

  // Handle Export
  const handleExport = async (format) => {
    try {
      const filters = {
        range_key: rangeKey,
        search,
        category,
        service,
        status,
        model,
        task_type: taskType,
        custom_start: rangeKey === "custom" ? customStart : undefined,
        custom_end: rangeKey === "custom" ? customEnd : undefined,
      };
      await downloadAnalyticsExport(format, filters);
    } catch (err) {
      alert(`Export failed: ${err.message}`);
    }
  };

  // Reset Filters
  const handleResetFilters = () => {
    setRangeKey("24h");
    setSearch("");
    setCategory("");
    setService("");
    setStatus("");
    setModel("");
    setTaskType("");
    setCustomStart("");
    setCustomEnd("");
  };

  if (loading && !data) {
    return (
      <div className="analytics-loading-container">
        <div className="analytics-spinner" />
        <p>INITIALIZING OPERATIONAL INTELLIGENCE ANALYTICS...</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="analytics-error-container">
        <AlertTriangle size={36} className="text-red-400" />
        <h2>Analytics Unavailable</h2>
        <p>{error}</p>
        <button type="button" onClick={() => fetchDashboard(true)} className="nova-btn-primary">
          <RefreshCw size={16} /> Retry Connection
        </button>
      </div>
    );
  }

  const summary = data?.summary || {};
  const trends = data?.trends?.series || [];
  const categoriesList = data?.categories || [];
  const servicesList = data?.services || [];
  const modelsList = data?.models || [];
  const taskTypesList = data?.task_types || [];
  const statusesList = data?.statuses || [];
  const latencyInfo = data?.latency || {};
  const missionsInfo = data?.missions || {};
  const knowledgeInfo = data?.knowledge || {};
  const artifactsInfo = data?.artifacts || {};
  const networkInfo = data?.network || {};
  const resourcesInfo = data?.resources || {};
  const recentEvents = data?.recent_activity || [];
  const topActionsList = data?.top_actions || [];

  return (
    <div className="analytics-page">
      {/* HEADER */}
      <header className="analytics-header">
        <div>
          <div className="analytics-title-row">
            <h1>ANALYTICS</h1>
            <span className="sovereign-badge">SOVEREIGN INTELLIGENCE</span>
          </div>
          <p className="analytics-subtitle">
            Operational intelligence and real-time system activity overview
          </p>
        </div>

        <div className="analytics-header-actions">
          {/* Live / Paused Toggle */}
          <button
            type="button"
            className={`live-toggle-btn ${isLive ? "live" : "paused"}`}
            onClick={() => setIsLive(!isLive)}
            title={isLive ? "Pause live polling" : "Resume live polling"}
          >
            {isLive ? <Play size={14} className="animate-pulse" /> : <Pause size={14} />}
            <span>{isLive ? "LIVE" : "PAUSED"}</span>
          </button>

          {/* Refresh Button */}
          <button
            type="button"
            className="nova-icon-btn"
            onClick={() => fetchDashboard(true)}
            disabled={refreshing}
            title="Manual refresh"
          >
            <RefreshCw size={16} className={refreshing ? "spin" : ""} />
          </button>

          {/* Export Options */}
          <div className="export-dropdown">
            <button type="button" className="nova-btn-secondary" onClick={() => handleExport("json")}>
              <Download size={14} /> Export JSON
            </button>
            <button type="button" className="nova-btn-secondary" onClick={() => handleExport("csv")}>
              <Download size={14} /> Export CSV
            </button>
          </div>

          <div className="last-updated-text">
            <span>Last updated:</span>
            <strong>{lastUpdated || "Just now"}</strong>
          </div>
        </div>
      </header>

      {/* GLOBAL FILTER BAR */}
      <section className="analytics-filter-bar">
        <div className="filter-group">
          <label>Time Range:</label>
          <select value={rangeKey} onChange={(e) => setRangeKey(e.target.value)}>
            <option value="1h">Last 1 Hour</option>
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
            <option value="custom">Custom Range</option>
          </select>
        </div>

        {rangeKey === "custom" && (
          <div className="filter-group custom-range-group">
            <input
              type="datetime-local"
              value={customStart}
              onChange={(e) => setCustomStart(e.target.value)}
              placeholder="From"
            />
            <span>to</span>
            <input
              type="datetime-local"
              value={customEnd}
              onChange={(e) => setCustomEnd(e.target.value)}
              placeholder="To"
            />
          </div>
        )}

        <div className="filter-group search-group">
          <Search size={14} />
          <input
            type="text"
            placeholder="Search events..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="filter-group">
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">All Categories</option>
            {categoriesList.map((c) => (
              <option key={c.category} value={c.category}>
                {c.category} ({c.count})
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <select value={service} onChange={(e) => setService(e.target.value)}>
            <option value="">All Services</option>
            {servicesList.map((s) => (
              <option key={s.service} value={s.service}>
                {s.service} ({s.count})
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All Statuses</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
            <option value="running">Running</option>
          </select>
        </div>

        <div className="filter-group">
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            <option value="">All Models</option>
            {modelsList.map((m) => (
              <option key={m.model} value={m.model}>
                {m.model}
              </option>
            ))}
          </select>
        </div>

        <button type="button" className="reset-filters-btn" onClick={handleResetFilters}>
          Reset
        </button>
      </section>

      {/* ROW 1: OVERVIEW KPI CARDS */}
      <section className="analytics-kpi-grid">
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">TOTAL EVENTS</span>
            <Activity size={18} className="text-blue-400" />
          </div>
          <div className="kpi-value">{summary.total_events ?? 0}</div>
          <div className="kpi-subtitle">Recorded in current filter range</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">SUCCESSFUL EVENTS</span>
            <CheckCircle2 size={18} className="text-emerald-400" />
          </div>
          <div className="kpi-value text-emerald-400">{summary.successful_events ?? 0}</div>
          <div className="kpi-subtitle">Passed cleanly</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">FAILED EVENTS</span>
            <XCircle size={18} className="text-red-400" />
          </div>
          <div className="kpi-value text-red-400">{summary.failed_events ?? 0}</div>
          <div className="kpi-subtitle">Errors or exceptions</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">RUNNING / ACTIVE</span>
            <Clock size={18} className="text-cyan-400" />
          </div>
          <div className="kpi-value text-cyan-400">{summary.running_events ?? 0}</div>
          <div className="kpi-subtitle">In-progress operations</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">SUCCESS RATE</span>
            <Zap size={18} className="text-amber-400" />
          </div>
          <div className="kpi-value">{summary.success_rate_percent ?? 0}%</div>
          <div className="kpi-subtitle">Completion ratio</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">AVG LATENCY</span>
            <BarChart3 size={18} className="text-purple-400" />
          </div>
          <div className="kpi-value">
            {summary.latency?.avg_ms != null ? `${summary.latency.avg_ms} ms` : "N/A"}
          </div>
          <div className="kpi-subtitle">
            {summary.latency?.measured_count ? `${summary.latency.measured_count} measured` : "No duration data"}
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">EXTERNAL / NETWORK</span>
            <Globe size={18} className="text-cyan-400" />
          </div>
          <div className="kpi-value">{summary.external_events ?? 0}</div>
          <div className="kpi-subtitle">Application-level tracking</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-title">MODELS USED</span>
            <Brain size={18} className="text-pink-400" />
          </div>
          <div className="kpi-value">{summary.models_used_count ?? 0}</div>
          <div className="kpi-subtitle">Distinct active local LLMs</div>
        </div>
      </section>

      {/* ROW 2: ACTIVITY OVER TIME & STATUS BREAKDOWN */}
      <section className="analytics-grid-two">
        {/* Activity Trend Chart */}
        <div className="analytics-panel">
          <div className="panel-header">
            <h3>ACTIVITY TREND (EVENTS OVER TIME)</h3>
            <span className="panel-badge">{rangeKey.toUpperCase()} WINDOW</span>
          </div>

          {trends.length === 0 || trends.every((t) => t.total === 0) ? (
            <div className="chart-empty-state">
              <Activity size={32} />
              <p>No activity recorded for this period.</p>
            </div>
          ) : (
            <div className="chart-container">
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={trends} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorSuccess" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="label" stroke="#64748b" fontSize={11} />
                  <YAxis stroke="#64748b" fontSize={11} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", borderRadius: "6px" }}
                    labelStyle={{ color: "#f8fafc" }}
                  />
                  <Area type="monotone" dataKey="total" stroke="#3b82f6" fillOpacity={1} fill="url(#colorTotal)" name="Total Events" />
                  <Area type="monotone" dataKey="success" stroke="#10b981" fillOpacity={1} fill="url(#colorSuccess)" name="Successful" />
                  <Area type="monotone" dataKey="failed" stroke="#ef4444" fillOpacity={0.2} fill="#ef4444" name="Failed" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Status Breakdown Pie */}
        <div className="analytics-panel">
          <div className="panel-header">
            <h3>STATUS DISTRIBUTION</h3>
          </div>

          {statusesList.length === 0 ? (
            <div className="chart-empty-state">
              <PieChart size={32} />
              <p>No status data recorded.</p>
            </div>
          ) : (
            <div className="status-chart-row">
              <div className="chart-container pie-container">
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={statusesList}
                      dataKey="count"
                      nameKey="status"
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={80}
                      paddingAngle={4}
                    >
                      {statusesList.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={STATUS_COLORS[entry.status.toLowerCase()] || CHART_COLORS[index % CHART_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155" }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="status-legend-list">
                {statusesList.map((st) => (
                  <div key={st.status} className="status-legend-item" onClick={() => setStatus(st.status)}>
                    <span
                      className="status-dot"
                      style={{
                        backgroundColor:
                          STATUS_COLORS[st.status.toLowerCase()] || "#64748b",
                      }}
                    />
                    <span className="status-name">{st.status}</span>
                    <strong className="status-count">{st.count}</strong>
                    <span className="status-pct">({st.percentage}%)</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ROW 3: CATEGORY DISTRIBUTION & SERVICE USAGE */}
      <section className="analytics-grid-two">
        {/* Category Breakdown */}
        <div className="analytics-panel">
          <div className="panel-header">
            <h3>EVENT CATEGORIES</h3>
          </div>

          {categoriesList.length === 0 ? (
            <div className="chart-empty-state">
              <Layers size={32} />
              <p>No category events recorded.</p>
            </div>
          ) : (
            <div className="category-table-list">
              {categoriesList.map((c, i) => (
                <div
                  key={c.category}
                  className="category-row-item"
                  onClick={() => setCategory(c.category)}
                  title="Click to filter by category"
                >
                  <div className="category-label-row">
                    <span className="category-name">{c.category}</span>
                    <span className="category-meta">
                      {c.count} events ({c.percentage}%)
                    </span>
                  </div>
                  <div className="category-bar-bg">
                    <div
                      className="category-bar-fill"
                      style={{
                        width: `${c.percentage}%`,
                        backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Service Usage Bar Chart */}
        <div className="analytics-panel">
          <div className="panel-header">
            <h3>SERVICE USAGE</h3>
          </div>

          {servicesList.length === 0 ? (
            <div className="chart-empty-state">
              <Server size={32} />
              <p>No service operations recorded.</p>
            </div>
          ) : (
            <div className="chart-container">
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={servicesList} layout="vertical" margin={{ top: 5, right: 20, left: 40, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis type="number" stroke="#64748b" fontSize={11} />
                  <YAxis type="category" dataKey="service" stroke="#64748b" fontSize={11} width={100} />
                  <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155" }} />
                  <Bar dataKey="success" stackId="a" fill="#10b981" name="Success" />
                  <Bar dataKey="failed" stackId="a" fill="#ef4444" name="Failed" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </section>

      {/* ROW 4: MODEL USAGE & TASK TYPE ANALYTICS */}
      <section className="analytics-grid-two">
        {/* Model Usage */}
        <div className="analytics-panel">
          <div className="panel-header">
            <h3>AI MODEL USAGE & LATENCY</h3>
          </div>

          {modelsList.length === 0 ? (
            <div className="chart-empty-state">
              <Brain size={32} />
              <p>No model activity recorded.</p>
            </div>
          ) : (
            <div className="model-analytics-wrapper">
              <table className="analytics-table">
                <thead>
                  <tr>
                    <th>MODEL NAME</th>
                    <th>REQUESTS</th>
                    <th>SUCCESS</th>
                    <th>FAILED</th>
                    <th>AVG LATENCY</th>
                  </tr>
                </thead>
                <tbody>
                  {modelsList.map((m) => (
                    <tr key={m.model} onClick={() => setModel(m.model)} className="clickable-tr">
                      <td className="font-semibold text-blue-400">{m.model}</td>
                      <td>{m.request_count}</td>
                      <td className="text-emerald-400">{m.success_count}</td>
                      <td className="text-red-400">{m.failed_count}</td>
                      <td>{m.avg_latency_ms != null ? `${m.avg_latency_ms} ms` : "N/A"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Task Type Breakdown */}
        <div className="analytics-panel">
          <div className="panel-header">
            <h3>TASK TYPE ANALYTICS</h3>
          </div>

          {taskTypesList.length === 0 ? (
            <div className="chart-empty-state">
              <FileText size={32} />
              <p>No task type data recorded.</p>
            </div>
          ) : (
            <div className="chart-container">
              <ResponsiveContainer width="100%" height={230}>
                <BarChart data={taskTypesList} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="task_type" stroke="#64748b" fontSize={11} />
                  <YAxis stroke="#64748b" fontSize={11} />
                  <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155" }} />
                  <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} name="Operations" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </section>

      {/* ROW 5: LATENCY & PERFORMANCE DETAILED STATS */}
      <section className="analytics-panel">
        <div className="panel-header">
          <h3>LATENCY / PERFORMANCE SPECTRUM</h3>
        </div>

        <div className="latency-stats-row">
          <div className="latency-stat-box">
            <span className="lbl">AVERAGE LATENCY</span>
            <strong className="val text-blue-400">
              {latencyInfo.overall?.avg_ms != null ? `${latencyInfo.overall.avg_ms} ms` : "No duration data"}
            </strong>
          </div>

          <div className="latency-stat-box">
            <span className="lbl">MEDIAN (P50)</span>
            <strong className="val text-emerald-400">
              {latencyInfo.overall?.median_ms != null ? `${latencyInfo.overall.median_ms} ms` : "N/A"}
            </strong>
          </div>

          <div className="latency-stat-box">
            <span className="lbl">P95 LATENCY</span>
            <strong className="val text-amber-400">
              {latencyInfo.overall?.p95_ms != null ? `${latencyInfo.overall.p95_ms} ms` : "N/A"}
            </strong>
          </div>

          <div className="latency-stat-box">
            <span className="lbl">MAX LATENCY</span>
            <strong className="val text-red-400">
              {latencyInfo.overall?.max_ms != null ? `${latencyInfo.overall.max_ms} ms` : "N/A"}
            </strong>
          </div>
        </div>

        {latencyInfo.by_service && latencyInfo.by_service.length > 0 && (
          <div className="latency-breakdown-table">
            <h4>LATENCY BY SERVICE</h4>
            <table className="analytics-table">
              <thead>
                <tr>
                  <th>SERVICE</th>
                  <th>SAMPLE SAMPLES</th>
                  <th>AVG LATENCY</th>
                  <th>MIN LATENCY</th>
                  <th>MAX LATENCY</th>
                  <th>P95 LATENCY</th>
                </tr>
              </thead>
              <tbody>
                {latencyInfo.by_service.map((s) => (
                  <tr key={s.service}>
                    <td className="font-medium">{s.service}</td>
                    <td>{s.sample_count}</td>
                    <td>{s.avg_ms} ms</td>
                    <td>{s.min_ms} ms</td>
                    <td>{s.max_ms} ms</td>
                    <td>{s.p95_ms != null ? `${s.p95_ms} ms` : "N/A"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ROW 6: MISSION, AGENT & KNOWLEDGE ANALYTICS */}
      <section className="analytics-grid-two">
        {/* Mission Analytics */}
        <div className="analytics-panel">
          <div className="panel-header">
            <h3>MISSION & AGENT INTELLIGENCE</h3>
          </div>
          <div className="subsystem-grid">
            <div className="subsystem-stat">
              <span>STARTED</span>
              <strong>{missionsInfo.started ?? 0}</strong>
            </div>
            <div className="subsystem-stat">
              <span>COMPLETED</span>
              <strong className="text-emerald-400">{missionsInfo.completed ?? 0}</strong>
            </div>
            <div className="subsystem-stat">
              <span>FAILED</span>
              <strong className="text-red-400">{missionsInfo.failed ?? 0}</strong>
            </div>
            <div className="subsystem-stat">
              <span>AGENT RUNS</span>
              <strong className="text-blue-400">{missionsInfo.agent_runs ?? 0}</strong>
            </div>
          </div>
        </div>

        {/* Knowledge Analytics */}
        <div className="analytics-panel">
          <div className="panel-header">
            <h3>KNOWLEDGE VAULT ANALYTICS</h3>
          </div>
          <div className="subsystem-grid">
            <div className="subsystem-stat">
              <span>INDEXING OPS</span>
              <strong>{knowledgeInfo.indexing_operations ?? 0}</strong>
            </div>
            <div className="subsystem-stat">
              <span>FILE UPLOADS</span>
              <strong className="text-cyan-400">{knowledgeInfo.file_uploads ?? 0}</strong>
            </div>
            <div className="subsystem-stat">
              <span>FILE ADDITIONS</span>
              <strong className="text-emerald-400">{knowledgeInfo.file_additions ?? 0}</strong>
            </div>
            <div className="subsystem-stat">
              <span>DELETIONS</span>
              <strong className="text-red-400">{knowledgeInfo.file_deletions ?? 0}</strong>
            </div>
          </div>
        </div>
      </section>

      {/* ROW 7: NETWORK & TELEMETRY */}
      <section className="analytics-grid-two">
        {/* Network Analytics */}
        <div className="analytics-panel">
          <div className="panel-header">
            <h3>SOVEREIGN NETWORK TRACKING</h3>
          </div>
          <div className="network-analytics-box">
            <div className="scope-tag">{networkInfo.disclaimer || "Application-level network tracking"}</div>
            <div className="network-counters">
              <div>
                <span>ALLOWED REQUESTS:</span> <strong>{networkInfo.allowed_requests ?? 0}</strong>
              </div>
              <div>
                <span>BLOCKED REQUESTS:</span> <strong>{networkInfo.blocked_requests ?? 0}</strong>
              </div>
              <div>
                <span>EXTERNAL REQUESTS:</span> <strong>{networkInfo.external_requests ?? 0}</strong>
              </div>
            </div>
          </div>
        </div>

        {/* System Resources Telemetry */}
        <div className="analytics-panel">
          <div className="panel-header">
            <h3>SYSTEM TELEMETRY (REAL OS METRICS)</h3>
          </div>
          <div className="telemetry-grid">
            <div className="telemetry-card">
              <Cpu size={16} className="text-blue-400" />
              <span>CPU USAGE:</span>
              <strong>
                {resourcesInfo.cpu?.status === "AVAILABLE"
                  ? `${resourcesInfo.cpu.usage_percent}% (${resourcesInfo.cpu.logical_cores} cores)`
                  : "Unavailable"}
              </strong>
            </div>
            <div className="telemetry-card">
              <HardDrive size={16} className="text-emerald-400" />
              <span>RAM USAGE:</span>
              <strong>
                {resourcesInfo.memory?.status === "AVAILABLE"
                  ? `${resourcesInfo.memory.used_gb} GB / ${resourcesInfo.memory.total_gb} GB (${resourcesInfo.memory.usage_percent}%)`
                  : "Unavailable"}
              </strong>
            </div>
            <div className="telemetry-card">
              <Zap size={16} className="text-amber-400" />
              <span>GPU TELEMETRY:</span>
              <strong>
                {resourcesInfo.gpu?.status === "AVAILABLE"
                  ? `${resourcesInfo.gpu.name || "GPU"} (${resourcesInfo.gpu.vram_usage_percent}% VRAM)`
                  : resourcesInfo.gpu?.reason || "No GPU Detected"}
              </strong>
            </div>
            <div className="telemetry-card">
              <Brain size={16} className="text-pink-400" />
              <span>ACTIVE LOCAL MODEL:</span>
              <strong>
                {resourcesInfo.model_runtime?.active_model || "None configured"}
              </strong>
            </div>
          </div>
        </div>
      </section>

      {/* ROW 8: RECENT ACTIVITY EVENT STREAM */}
      <section className="analytics-panel">
        <div className="panel-header">
          <h3>RECENT OPERATIONAL ACTIVITY STREAM</h3>
          <span className="panel-badge">REAL AUDIT EVENTS</span>
        </div>

        {recentEvents.length === 0 ? (
          <div className="chart-empty-state">
            <Activity size={32} />
            <p>No recent activity recorded.</p>
          </div>
        ) : (
          <div className="recent-activity-table-wrapper">
            <table className="analytics-table">
              <thead>
                <tr>
                  <th>TIMESTAMP</th>
                  <th>CATEGORY</th>
                  <th>ACTION</th>
                  <th>SERVICE</th>
                  <th>STATUS</th>
                  <th>MODEL</th>
                  <th>TASK TYPE</th>
                  <th>DURATION</th>
                  <th>MESSAGE</th>
                </tr>
              </thead>
              <tbody>
                {recentEvents.map((ev) => (
                  <tr key={ev.event_id}>
                    <td className="text-slate-400 whitespace-nowrap">
                      {ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : "-"}
                    </td>
                    <td>
                      <span className="cat-badge">{ev.category}</span>
                    </td>
                    <td className="font-medium text-slate-200">{ev.action}</td>
                    <td>{ev.service}</td>
                    <td>
                      <span
                        className={`status-pill ${
                          ev.status === "success"
                            ? "success"
                            : ev.status === "failed" || ev.status === "error"
                            ? "failed"
                            : "running"
                        }`}
                      >
                        {ev.status}
                      </span>
                    </td>
                    <td>{ev.model || "-"}</td>
                    <td>{ev.task_type || "-"}</td>
                    <td>{ev.duration_ms != null ? `${ev.duration_ms} ms` : "-"}</td>
                    <td className="truncate max-w-xs" title={ev.message}>
                      {ev.message || "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* FOOTER */}
      <footer className="analytics-footer">
        <div>
          Data source: <strong>NOVA Audit Trail & Sovereign Local Telemetry</strong>
        </div>
        <div>Sovereign Industrial Intelligence Center</div>
      </footer>
    </div>
  );
}
