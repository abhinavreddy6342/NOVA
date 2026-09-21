import {
  Activity,
  AlertCircle,
  ArrowDownToLine,
  CheckCircle2,
  Clock3,
  Code2,
  Database,
  FileJson,
  Filter,
  Gauge,
  Globe2,
  Info,
  Layers3,
  ListFilter,
  Network,
  PanelRightOpen,
  RefreshCw,
  Search,
  Server,
  ShieldCheck,
  Timer,
  X,
  XCircle,
  Zap,
} from "lucide-react";

import {
  AnimatePresence,
  motion,
} from "framer-motion";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  downloadAuditExport,
  getAuditEvent,
  getAuditEvents,
  getAuditSummary,
} from "../../services/api";


// =========================================================
// CONSTANTS
// =========================================================

const REFRESH_INTERVAL_MS = 4000;

const PAGE_LIMIT = 100;

const EMPTY_FILTERS = {
  query: "",
  category: "",
  action: "",
  service: "",
  status: "",
  model: "",
  taskType: "",
  startDate: "",
  endDate: "",
};

const STATUS_ORDER = [
  "success",
  "failed",
  "running",
  "pending",
  "error",
  "cancelled",
  "blocked",
  "info",
];


// =========================================================
// NORMALIZATION
// =========================================================

function normalizeListResponse(
  payload
) {
  if (Array.isArray(payload)) {
    return {
      events: payload,
      total: payload.length,
      limit: PAGE_LIMIT,
      offset: 0,
    };
  }

  if (!payload || typeof payload !== "object") {
    return {
      events: [],
      total: 0,
      limit: PAGE_LIMIT,
      offset: 0,
    };
  }

  const events =
    Array.isArray(payload.events)
      ? payload.events
      : Array.isArray(payload.items)
        ? payload.items
        : Array.isArray(payload.results)
          ? payload.results
          : [];

  return {
    events,
    total:
      Number.isFinite(
        Number(payload.total)
      )
        ? Number(payload.total)
        : events.length,
    limit:
      Number.isFinite(
        Number(payload.limit)
      )
        ? Number(payload.limit)
        : PAGE_LIMIT,
    offset:
      Number.isFinite(
        Number(payload.offset)
      )
        ? Number(payload.offset)
        : 0,
  };
}


function normalizeEvent(
  event
) {
  if (
    event?.event &&
    typeof event.event === "object"
  ) {
    return normalizeEvent(
      event.event
    );
  }

  if (!event || typeof event !== "object") {
    return {};
  }

  const metadata =
    event.metadata &&
    typeof event.metadata === "object"
      ? event.metadata
      : {};

  return {
    ...event,

    event_id:
      event.event_id ||
      event.id ||
      event.eventId ||
      "unknown-event",

    timestamp:
      event.timestamp ||
      event.created_at ||
      event.createdAt ||
      null,

    category:
      event.category ||
      "system",

    action:
      event.action ||
      "event",

    service:
      event.service ||
      "unknown",

    status:
      String(
        event.status ||
          "info"
      ).toLowerCase(),

    duration_ms:
      event.duration_ms ??
      event.durationMs ??
      null,

    model:
      event.model ||
      metadata.model ||
      null,

    task_type:
      event.task_type ||
      event.taskType ||
      metadata.task_type ||
      metadata.taskType ||
      null,

    resource:
      event.resource ||
      metadata.resource ||
      null,

    resource_id:
      event.resource_id ||
      event.resourceId ||
      metadata.resource_id ||
      metadata.resourceId ||
      null,

    request_id:
      event.request_id ||
      event.requestId ||
      metadata.request_id ||
      metadata.requestId ||
      null,

    correlation_id:
      event.correlation_id ||
      event.correlationId ||
      metadata.correlation_id ||
      metadata.correlationId ||
      null,

    user_id:
      event.user_id ||
      event.userId ||
      metadata.user_id ||
      metadata.userId ||
      null,

    message:
      event.message ||
      event.description ||
      event.action ||
      "Audit event",

    metadata,
  };
}


function normalizeSummary(
  summary,
  events
) {
  const raw =
    summary?.summary &&
    typeof summary.summary === "object"
      ? summary.summary
      : summary &&
        typeof summary === "object"
          ? summary
          : {};

  const eventList =
    Array.isArray(events)
      ? events.map(normalizeEvent)
      : [];

  const eventSuccessCount =
    eventList.filter(
      (event) =>
        event.status ===
        "success"
    ).length;

  const eventFailedCount =
    eventList.filter(
      (event) =>
        [
          "failed",
          "failure",
          "error",
        ].includes(
          event.status
        )
    ).length;

  const eventRunningCount =
    eventList.filter(
      (event) =>
        [
          "running",
          "pending",
        ].includes(
          event.status
        )
    ).length;

  const eventExternalCount =
    eventList.filter(
      (event) => {
        const metadata =
          event.metadata || {};

        const eventType =
          String(
            metadata.event_type ||
              event.action ||
              ""
          ).toLowerCase();

        const category =
          String(
            event.category ||
              ""
          ).toLowerCase();

        return (
          eventType.includes(
            "external"
          ) ||
          eventType.includes(
            "cloud"
          ) ||
          category ===
            "external"
        );
      }
    ).length;

  const eventNetworkCount =
    eventList.filter(
      (event) => {
        const metadata =
          event.metadata || {};

        const eventType =
          String(
            metadata.event_type ||
              ""
          ).toLowerCase();

        const category =
          String(
            event.category ||
              ""
          ).toLowerCase();

        return (
          category ===
            "sovereignty" ||
          eventType.includes(
            "network"
          ) ||
          eventType.includes(
            "cloud"
          ) ||
          eventType.includes(
            "external"
          )
        );
      }
    ).length;

  const recentCutoff =
    Date.now() -
    5 * 60 * 1000;

  const eventRecentCount =
    eventList.filter(
      (event) => {
        const timestamp =
          parseTimestamp(
            event.timestamp
          );

        return (
          timestamp &&
          timestamp >=
            recentCutoff
        );
      }
    ).length;

  const pickNumber = (
    keys,
    fallback
  ) => {
    for (const key of keys) {
      const value =
        raw[key];

      if (
        Number.isFinite(
          Number(value)
        )
      ) {
        return Number(value);
      }
    }

    return fallback;
  };

  return {
    total:
      pickNumber(
        [
          "total_events",
          "total",
          "event_count",
          "count",
        ],
        eventList.length
      ),

    success:
      pickNumber(
        [
          "success_events",
          "successful_events",
          "success_count",
          "successful",
          "success",
        ],
        eventSuccessCount
      ),

    failed:
      pickNumber(
        [
          "failed_events",
          "failure_events",
          "failed_count",
          "failures",
          "failed",
        ],
        eventFailedCount
      ),

    running:
      pickNumber(
        [
          "running_events",
          "active_events",
          "running_count",
          "running",
        ],
        eventRunningCount
      ),

    recent:
      pickNumber(
        [
          "recent_events",
          "recent_count",
        ],
        eventRecentCount
      ),

    external:
      pickNumber(
        [
          "external_api_calls",
          "external_api_events",
          "external_events",
          "external_count",
        ],
        eventExternalCount
      ),

    network:
      pickNumber(
        [
          "network_events",
          "network_count",
          "sovereignty_events",
        ],
        eventNetworkCount
      ),
  };
}


function parseTimestamp(
  value
) {
  if (!value) {
    return null;
  }

  const date =
    new Date(value);

  const time =
    date.getTime();

  return Number.isFinite(time)
    ? time
    : null;
}


function formatTimestamp(
  value
) {
  if (!value) {
    return "—";
  }

  const timestamp =
    parseTimestamp(value);

  if (!timestamp) {
    return String(value);
  }

  return new Date(
    timestamp
  ).toLocaleString(
    "en-IN",
    {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }
  );
}


function formatRelativeTime(
  value
) {
  const timestamp =
    parseTimestamp(value);

  if (!timestamp) {
    return "";
  }

  const seconds = Math.max(
    0,
    Math.floor(
      (Date.now() -
        timestamp) /
        1000
    )
  );

  if (seconds < 5) {
    return "just now";
  }

  if (seconds < 60) {
    return `${seconds}s ago`;
  }

  const minutes =
    Math.floor(
      seconds / 60
    );

  if (minutes < 60) {
    return `${minutes}m ago`;
  }

  const hours =
    Math.floor(
      minutes / 60
    );

  if (hours < 24) {
    return `${hours}h ago`;
  }

  const days =
    Math.floor(
      hours / 24
    );

  return `${days}d ago`;
}


function formatDuration(
  value
) {
  if (
    value ===
      null ||
    value ===
      undefined ||
    value === ""
  ) {
    return "—";
  }

  const numeric =
    Number(value);

  if (!Number.isFinite(numeric)) {
    return String(value);
  }

  if (numeric < 1000) {
    return `${numeric.toFixed(
      numeric % 1 === 0
        ? 0
        : 2
    )} ms`;
  }

  return `${(
    numeric / 1000
  ).toFixed(2)} s`;
}


function humanize(
  value
) {
  if (!value) {
    return "—";
  }

  return String(
    value
  )
    .replace(
      /[_-]+/g,
      " "
    )
    .replace(
      /\b\w/g,
      (char) =>
        char.toUpperCase()
    );
}


function stringifyValue(
  value
) {
  if (
    value ===
      null ||
    value ===
      undefined
  ) {
    return "null";
  }

  if (
    typeof value ===
      "string"
  ) {
    return value;
  }

  try {
    return JSON.stringify(
      value,
      null,
      2
    );
  } catch {
    return String(
      value
    );
  }
}


function createDateBoundary(
  dateValue,
  endOfDay = false
) {
  if (!dateValue) {
    return undefined;
  }

  return endOfDay
    ? `${dateValue}T23:59:59`
    : `${dateValue}T00:00:00`;
}


// =========================================================
// UI HELPERS
// =========================================================

function statusIcon(
  status
) {
  const normalized =
    String(
      status ||
        "info"
    ).toLowerCase();

  if (
    normalized ===
    "success"
  ) {
    return (
      <CheckCircle2
        size={15}
      />
    );
  }

  if (
    [
      "failed",
      "failure",
      "error",
    ].includes(
      normalized
    )
  ) {
    return (
      <XCircle
        size={15}
      />
    );
  }

  if (
    [
      "running",
      "pending",
    ].includes(
      normalized
    )
  ) {
    return (
      <Activity
        size={15}
      />
    );
  }

  if (
    normalized ===
    "blocked"
  ) {
    return (
      <AlertCircle
        size={15}
      />
    );
  }

  return (
    <Info
      size={15}
    />
  );
}


function categoryIcon(
  category
) {
  const value =
    String(
      category ||
        ""
    ).toLowerCase();

  if (
    value.includes(
      "model"
    )
  ) {
    return (
      <Zap
        size={16}
      />
    );
  }

  if (
    value.includes(
      "mission"
    ) ||
    value.includes(
      "agent"
    )
  ) {
    return (
      <Activity
        size={16}
      />
    );
  }

  if (
    value.includes(
      "knowledge"
    )
  ) {
    return (
      <Database
        size={16}
      />
    );
  }

  if (
    value.includes(
      "artifact"
    )
  ) {
    return (
      <Layers3
        size={16}
      />
    );
  }

  if (
    value.includes(
      "sovereignty"
    ) ||
    value.includes(
      "network"
    )
  ) {
    return (
      <ShieldCheck
        size={16}
      />
    );
  }

  if (
    value.includes(
      "chat"
    )
  ) {
    return (
      <Code2
        size={16}
      />
    );
  }

  return (
    <Server
      size={16}
    />
  );
}


function StatBlock({
  icon,
  label,
  value,
  detail,
  tone = "default",
}) {
  return (
    <motion.div
      className={`nova-audit-stat nova-audit-stat-${tone}`}
      whileHover={{
        y: -2,
      }}
      transition={{
        duration: 0.18,
      }}
    >
      <div className="nova-audit-stat-icon">
        {icon}
      </div>

      <div className="nova-audit-stat-content">
        <span className="nova-audit-stat-label">
          {label}
        </span>

        <strong className="nova-audit-stat-value">
          {value}
        </strong>

        <span className="nova-audit-stat-detail">
          {detail}
        </span>
      </div>
    </motion.div>
  );
}


function FilterSelect({
  label,
  value,
  onChange,
  options,
  disabled = false,
}) {
  return (
    <label className="nova-audit-filter-field">
      <span>
        {label}
      </span>

      <select
        value={
          value || ""
        }
        onChange={(
          event
        ) =>
          onChange(
            event.target
              .value
          )
        }
        disabled={
          disabled
        }
      >
        <option value="">
          All
        </option>

        {options.map(
          (option) => (
            <option
              key={option}
              value={option}
            >
              {humanize(
                option
              )}
            </option>
          )
        )}
      </select>
    </label>
  );
}


function EmptyState({
  loading,
  hasFilters,
  onReset,
}) {
  return (
    <div className="nova-audit-empty">
      <div className="nova-audit-empty-icon">
        {loading ? (
          <RefreshCw
            size={22}
            className="nova-audit-spin"
          />
        ) : (
          <ShieldCheck
            size={22}
          />
        )}
      </div>

      <strong>
        {loading
          ? "Loading audit stream"
          : hasFilters
            ? "No matching audit events"
            : "No audit events recorded"}
      </strong>

      <span>
        {loading
          ? "Reading the real NOVA audit store."
          : hasFilters
            ? "Adjust the filters or clear them to inspect the complete stream."
            : "Runtime activity will appear here when NOVA performs auditable operations."}
      </span>

      {hasFilters &&
        !loading && (
          <button
            type="button"
            className="nova-audit-secondary-button"
            onClick={
              onReset
            }
          >
            Clear filters
          </button>
        )}
    </div>
  );
}


// =========================================================
// EVENT ROW
// =========================================================

function AuditEventRow({
  event,
  selected,
  onSelect,
}) {
  const normalized =
    normalizeEvent(
      event
    );

  return (
    <motion.button
      type="button"
      className={`nova-audit-event-row ${
        selected
          ? "is-selected"
          : ""
      }`}
      onClick={() =>
        onSelect(
          normalized
        )
      }
      whileHover={{
        x: 2,
      }}
      transition={{
        duration: 0.15,
      }}
    >
      <div
        className={`nova-audit-event-node nova-audit-status-${normalized.status}`}
      >
        {categoryIcon(
          normalized.category
        )}
      </div>

      <div className="nova-audit-event-time">
        <strong>
          {formatRelativeTime(
            normalized.timestamp
          )}
        </strong>

        <span>
          {formatTimestamp(
            normalized.timestamp
          )}
        </span>
      </div>

      <div className="nova-audit-event-main">
        <div className="nova-audit-event-title">
          <strong>
            {humanize(
              normalized.action
            )}
          </strong>

          <span
            className={`nova-audit-status nova-audit-status-pill-${normalized.status}`}
          >
            {statusIcon(
              normalized.status
            )}

            {humanize(
              normalized.status
            )}
          </span>
        </div>

        <p>
          {normalized.message}
        </p>

        <div className="nova-audit-event-meta">
          <span>
            {humanize(
              normalized.category
            )}
          </span>

          <span>
            {humanize(
              normalized.service
            )}
          </span>

          {normalized.model && (
            <span>
              {normalized.model}
            </span>
          )}

          {normalized.task_type && (
            <span>
              {humanize(
                normalized.task_type
              )}
            </span>
          )}
        </div>
      </div>

      <div className="nova-audit-event-side">
        <span>
          {formatDuration(
            normalized.duration_ms
          )}
        </span>

        <PanelRightOpen
          size={15}
        />
      </div>
    </motion.button>
  );
}


// =========================================================
// EVENT INSPECTOR
// =========================================================

function EventInspector({
  event,
  onClose,
  onTrace,
}) {
  const normalized =
    normalizeEvent(
      event
    );

  return (
    <motion.aside
      className="nova-audit-inspector"
      initial={{
        opacity: 0,
        x: 30,
      }}
      animate={{
        opacity: 1,
        x: 0,
      }}
      exit={{
        opacity: 0,
        x: 30,
      }}
      transition={{
        duration: 0.22,
      }}
    >
      <div className="nova-audit-inspector-header">
        <div>
          <span>
            EVENT INSPECTOR
          </span>

          <h3>
            {humanize(
              normalized.action
            )}
          </h3>
        </div>

        <button
          type="button"
          onClick={
            onClose
          }
          aria-label="Close event inspector"
        >
          <X
            size={17}
          />
        </button>
      </div>

      <div className="nova-audit-inspector-status">
        <span
          className={`nova-audit-status nova-audit-status-pill-${normalized.status}`}
        >
          {statusIcon(
            normalized.status
          )}

          {humanize(
            normalized.status
          )}
        </span>

        <span>
          {formatTimestamp(
            normalized.timestamp
          )}
        </span>
      </div>

      <section className="nova-audit-inspector-section">
        <div className="nova-audit-inspector-section-title">
          <Info
            size={15}
          />
          <span>
            EVENT IDENTITY
          </span>
        </div>

        <div className="nova-audit-detail-grid">
          <DetailValue
            label="Event ID"
            value={
              normalized.event_id
            }
            mono
          />

          <DetailValue
            label="Request ID"
            value={
              normalized.request_id
            }
            mono
          />

          {normalized.correlation_id && (
            <DetailValue
              label="Correlation ID"
              value={
                normalized.correlation_id
              }
              mono
            />
          )}

          {normalized.user_id && (
            <DetailValue
              label="User ID"
              value={
                normalized.user_id
              }
              mono
            />
          )}

          <DetailValue
            label="Category"
            value={
              humanize(
                normalized.category
              )
            }
          />

          <DetailValue
            label="Action"
            value={
              normalized.action
            }
          />

          <DetailValue
            label="Service"
            value={
              normalized.service
            }
          />

          <DetailValue
            label="Status"
            value={
              humanize(
                normalized.status
              )
            }
          />
        </div>
      </section>

      {(normalized.request_id ||
        normalized.correlation_id) && (
        <button
          type="button"
          className="nova-audit-trace-button"
          onClick={() =>
            onTrace(
              normalized.correlation_id ||
                normalized.request_id
            )
          }
        >
          View related trace
        </button>
      )}

      <section className="nova-audit-inspector-section">
        <div className="nova-audit-inspector-section-title">
          <Gauge
            size={15}
          />
          <span>
            EXECUTION CONTEXT
          </span>
        </div>

        <div className="nova-audit-detail-grid">
          <DetailValue
            label="Duration"
            value={
              formatDuration(
                normalized.duration_ms
              )
            }
          />

          <DetailValue
            label="Model"
            value={
              normalized.model
            }
          />

          <DetailValue
            label="Task Type"
            value={
              humanize(
                normalized.task_type
              )
            }
          />

          <DetailValue
            label="Resource"
            value={
              normalized.resource
            }
          />

          <DetailValue
            label="Resource ID"
            value={
              normalized.resource_id
            }
            mono
          />
        </div>
      </section>

      <section className="nova-audit-inspector-section">
        <div className="nova-audit-inspector-section-title">
          <Code2
            size={15}
          />
          <span>
            MESSAGE
          </span>
        </div>

        <div className="nova-audit-message-box">
          {normalized.message}
        </div>
      </section>

      <section className="nova-audit-inspector-section">
        <div className="nova-audit-inspector-section-title">
          <Database
            size={15}
          />
          <span>
            STRUCTURED METADATA
          </span>
        </div>

        <pre className="nova-audit-metadata">
          {stringifyValue(
            normalized.metadata
          )}
        </pre>
      </section>
    </motion.aside>
  );
}


function DetailValue({
  label,
  value,
  mono = false,
}) {
  return (
    <div className="nova-audit-detail-value">
      <span>
        {label}
      </span>

      <strong
        className={
          mono
            ? "nova-audit-mono"
            : ""
        }
        title={
          value
            ? String(
                value
              )
            : ""
        }
      >
        {value || "—"}
      </strong>
    </div>
  );
}


// =========================================================
// MAIN COMPONENT
// =========================================================

export default function AuditTrail() {
  const [
    events,
    setEvents,
  ] = useState([]);

  const [
    totalEvents,
    setTotalEvents,
  ] = useState(0);

  const [
    summary,
    setSummary,
  ] = useState(null);

  const [
    filters,
    setFilters,
  ] = useState(
    EMPTY_FILTERS
  );

  const [
    selectedEvent,
    setSelectedEvent,
  ] = useState(null);

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    refreshing,
    setRefreshing,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState("");

  const [
    live,
    setLive,
  ] = useState(true);

  const [
    inspectorLoading,
    setInspectorLoading,
  ] = useState(false);

  useEffect(() => {
    if (!selectedEvent) {
      return undefined;
    }

    const closeOnEscape = (event) => {
      if (event.key === "Escape") {
        setSelectedEvent(null);
      }
    };

    window.addEventListener(
      "keydown",
      closeOnEscape
    );

    return () =>
      window.removeEventListener(
        "keydown",
        closeOnEscape
      );
  }, [selectedEvent]);


  // =======================================================
  // FETCH
  // =======================================================

  const loadAudit = useCallback(
    async ({
      silent = false,
    } = {}) => {
      try {
        if (silent) {
          setRefreshing(
            true
          );
        } else {
          setLoading(
            true
          );
        }

        setError(
          ""
        );

        const query = {
          limit:
            PAGE_LIMIT,
          offset: 0,
        };

        const cleanQuery =
          filters.query.trim();

        if (
          cleanQuery
        ) {
          query.query =
            cleanQuery;
        }

        if (
          filters.category
        ) {
          query.category =
            filters.category;
        }

        if (
          filters.action
        ) {
          query.action =
            filters.action;
        }

        if (
          filters.service
        ) {
          query.service =
            filters.service;
        }

        if (
          filters.status
        ) {
          query.status =
            filters.status;
        }

        if (
          filters.model
        ) {
          query.model =
            filters.model;
        }

        if (
          filters.taskType
        ) {
          query.taskType =
            filters.taskType;
        }

        const start =
          createDateBoundary(
            filters.startDate
          );

        const end =
          createDateBoundary(
            filters.endDate,
            true
          );

        if (start) {
          query.start =
            start;
        }

        if (end) {
          query.end =
            end;
        }

        const [
          eventPayload,
          summaryPayload,
        ] =
          await Promise.all([
            getAuditEvents(
              query
            ),
            getAuditSummary(),
          ]);

        const normalized =
          normalizeListResponse(
            eventPayload
          );

        const nextEvents =
          normalized.events
            .map(
              normalizeEvent
            )
            .sort(
              (
                a,
                b
              ) =>
                (
                  parseTimestamp(
                    b.timestamp
                  ) || 0
                ) -
                (
                  parseTimestamp(
                    a.timestamp
                  ) || 0
                )
            );

        setEvents(
          nextEvents
        );

        setTotalEvents(
          normalized.total
        );

        setSummary(
          normalizeSummary(
            summaryPayload,
            nextEvents
          )
        );
      } catch (
        requestError
      ) {
        setError(
          requestError?.message ||
            "Unable to load the NOVA audit stream."
        );
      } finally {
        if (silent) {
          setRefreshing(
            false
          );
        } else {
          setLoading(
            false
          );
        }
      }
    },
    [filters]
  );


  useEffect(() => {
    loadAudit();

    if (!live) {
      return undefined;
    }

    const interval =
      window.setInterval(
        () =>
          loadAudit({
            silent: true,
          }),
        REFRESH_INTERVAL_MS
      );

    return () =>
      window.clearInterval(
        interval
      );
  }, [
    loadAudit,
    live,
  ]);


  // =======================================================
  // FILTER OPTIONS
  // =======================================================

  const optionSets =
    useMemo(() => {
      const collect =
        (
          getter
        ) =>
        Array.from(
          new Set(
            events
              .map(
                getter
              )
              .filter(
                Boolean
              )
              .map(
                String
              )
          )
        ).sort();

      return {
        categories:
          collect(
            (event) =>
              event.category
          ),

        actions:
          collect(
            (event) =>
              event.action
          ),

        services:
          collect(
            (event) =>
              event.service
          ),

        statuses:
          collect(
            (event) =>
              event.status
          ).sort(
            (a, b) => {
              const ai =
                STATUS_ORDER.indexOf(
                  a
                );

              const bi =
                STATUS_ORDER.indexOf(
                  b
                );

              if (
                ai === -1 &&
                bi === -1
              ) {
                return a.localeCompare(
                  b
                );
              }

              if (
                ai === -1
              ) {
                return 1;
              }

              if (
                bi === -1
              ) {
                return -1;
              }

              return ai - bi;
            }
          ),

        models:
          collect(
            (event) =>
              event.model
          ),

        taskTypes:
          collect(
            (event) =>
              event.task_type
          ),
      };
    }, [
      events,
    ]);


  // =======================================================
  // FILTER ACTIONS
  // =======================================================

  const updateFilter =
    useCallback(
      (
        key,
        value
      ) => {
        setFilters(
          (current) => ({
            ...current,
            [key]:
              value,
          })
        );
      },
      []
    );


  const clearFilters =
    useCallback(
      () => {
        setFilters(
          EMPTY_FILTERS
        );
        setSelectedEvent(
          null
        );
      },
      []
    );


  const hasFilters =
    useMemo(
      () =>
        Object.values(
          filters
        ).some(
          Boolean
        ),
      [filters]
    );


  // =======================================================
  // INSPECTOR
  // =======================================================

  const openInspector =
    useCallback(
      async (
        event
      ) => {
        const eventId =
          event?.event_id;

        if (
          !eventId
        ) {
          setSelectedEvent(
            event
          );
          return;
        }

        setSelectedEvent(
          event
        );

        try {
          setInspectorLoading(
            true
          );

          const fullEvent =
            await getAuditEvent(
              eventId
            );

          setSelectedEvent(
            normalizeEvent(
              fullEvent
            )
          );
        } catch {
          /*
           * Keep the already loaded event visible.
           * The list endpoint remains useful even when the
           * individual inspector request is unavailable.
           */
        } finally {
          setInspectorLoading(
            false
          );
        }
      },
      []
    );


  // =======================================================
  // EXPORT
  // =======================================================

  const exportAudit =
    useCallback(
      async (
        format
      ) => {
        try {
          const query = {
            query:
              filters.query ||
              undefined,

            category:
              filters.category ||
              undefined,

            action:
              filters.action ||
              undefined,

            service:
              filters.service ||
              undefined,

            status:
              filters.status ||
              undefined,

            model:
              filters.model ||
              undefined,

            taskType:
              filters.taskType ||
              undefined,

            start:
              createDateBoundary(
                filters.startDate
              ),

            end:
              createDateBoundary(
                filters.endDate,
                true
              ),
          };

          await downloadAuditExport(
            format,
            query
          );
        } catch (
          exportError
        ) {
          setError(
            exportError?.message ||
              `Unable to export audit ${format.toUpperCase()}.`
          );
        }
      },
      [filters]
    );


  // =======================================================
  // SUMMARY
  // =======================================================

  const displaySummary =
    summary ||
    normalizeSummary(
      null,
      events
    );

  const successRate =
    displaySummary.total >
    0
      ? Math.round(
          (
            displaySummary.success /
            displaySummary.total
          ) *
            100
        )
      : 0;

  const averageLatency =
    useMemo(() => {
      const durations = events
        .map((event) =>
          Number(event.duration_ms)
        )
        .filter(Number.isFinite);

      if (!durations.length) {
        return null;
      }

      return durations.reduce(
        (total, value) => total + value,
        0
      ) / durations.length;
    }, [events]);

  const latestTimestamp =
    events[0]?.timestamp ||
    displaySummary.latest_event?.timestamp ||
    null;


  // =======================================================
  // RENDER
  // =======================================================

  return (
    <div className="nova-audit-page">
      <div className="nova-audit-page-glow" />

      <div className="nova-audit-header">
        <div className="nova-audit-heading">
          <div className="nova-audit-eyebrow">
            <span className="nova-live-dot" />
            SYSTEM TRACEABILITY
          </div>

          <h1>
            Audit Trail
          </h1>

          <p>
            Real execution history across
            NOVA's local AI, agent,
            knowledge, artifact and
            application-level network
            subsystems.
          </p>
        </div>

        <div className="nova-audit-header-actions">
          <button
            type="button"
            className={`nova-audit-live-toggle ${
              live
                ? "is-live"
                : ""
            }`}
            onClick={() =>
              setLive(
                (
                  current
                ) =>
                  !current
              )
            }
            aria-pressed={
              live
            }
          >
            <span className="nova-audit-live-indicator" />
            {live
              ? "LIVE"
              : "PAUSED"}
          </button>

          <button
            type="button"
            className="nova-audit-icon-button"
            onClick={() =>
              loadAudit({
                silent: true,
              })
            }
            disabled={
              loading ||
              refreshing
            }
            title="Refresh audit stream"
          >
            <RefreshCw
              size={16}
              className={
                refreshing
                  ? "nova-audit-spin"
                  : ""
              }
            />
          </button>

          <button
            type="button"
            className="nova-audit-export-button"
            onClick={() =>
              exportAudit(
                "json"
              )
            }
          >
            <FileJson
              size={15}
            />
            JSON
          </button>

          <button
            type="button"
            className="nova-audit-export-button"
            onClick={() =>
              exportAudit(
                "csv"
              )
            }
          >
            <ArrowDownToLine
              size={15}
            />
            CSV
          </button>
        </div>
      </div>

      {error && (
        <motion.div
          className="nova-audit-error"
          initial={{
            opacity: 0,
            y: -5,
          }}
          animate={{
            opacity: 1,
            y: 0,
          }}
        >
          <AlertCircle
            size={16}
          />

          <span>
            {error}
          </span>

          <button
            type="button"
            onClick={() =>
              setError(
                ""
              )
            }
            aria-label="Dismiss error"
          >
            <X
              size={14}
            />
          </button>
        </motion.div>
      )}

      <div className="nova-audit-stats-grid">
        <StatBlock
          icon={
            <Layers3
              size={18}
            />
          }
          label="TOTAL EVENTS"
          value={
            displaySummary.total
          }
          detail={`${totalEvents.toLocaleString()} in current query`}
        />

        <StatBlock
          icon={
            <CheckCircle2
              size={18}
            />
          }
          label="SUCCESSFUL"
          value={
            displaySummary.success
          }
          detail={`${successRate}% of recorded events`}
          tone="success"
        />

        <StatBlock
          icon={
            <XCircle
              size={18}
            />
          }
          label="FAILED"
          value={
            displaySummary.failed
          }
          detail="Recorded failure/error states"
          tone={
            displaySummary.failed >
            0
              ? "danger"
              : "default"
          }
        />

        <StatBlock
          icon={
            <Activity
              size={18}
            />
          }
          label="RECENT / ACTIVE"
          value={
            displaySummary.running +
            displaySummary.recent
          }
          detail={`${displaySummary.running} active · ${displaySummary.recent} recent`}
          tone="accent"
        />

        <StatBlock
          icon={
            <Globe2
              size={18}
            />
          }
          label="EXTERNAL / NETWORK"
          value={
            displaySummary.external +
            displaySummary.network
          }
          detail={`${displaySummary.external} external · ${displaySummary.network} network`}
        />
      </div>

      <div className="nova-audit-query-state">
        <span>
          RANGE COUNT: {totalEvents.toLocaleString()}
        </span>

        <span>
          AVG LATENCY: {averageLatency === null ? "NOT AVAILABLE" : formatDuration(averageLatency)}
        </span>

        <span>
          LAST EVENT: {latestTimestamp ? formatTimestamp(latestTimestamp) : "NOT AVAILABLE"}
        </span>
      </div>

      <div className="nova-audit-toolbar">
        <div className="nova-audit-search">
          <Search
            size={16}
          />

          <input
            value={
              filters.query
            }
            onChange={(
              event
            ) =>
              updateFilter(
                "query",
                event
                  .target
                  .value
              )
            }
            placeholder="Search message, event ID, request ID, action, resource..."
            aria-label="Search audit events"
          />

          {filters.query && (
            <button
              type="button"
              onClick={() =>
                updateFilter(
                  "query",
                  ""
                )
              }
              aria-label="Clear audit search"
            >
              <X
                size={14}
              />
            </button>
          )}
        </div>

        <div className="nova-audit-toolbar-label">
          <Filter
            size={15}
          />
          FILTERS
        </div>

        {hasFilters && (
          <button
            type="button"
            className="nova-audit-clear-button"
            onClick={
              clearFilters
            }
          >
            Clear all
          </button>
        )}
      </div>

      <div className="nova-audit-filter-grid">
        <FilterSelect
          label="Category"
          value={
            filters.category
          }
          onChange={(
            value
          ) =>
            updateFilter(
              "category",
              value
            )
          }
          options={
            optionSets.categories
          }
        />

        <FilterSelect
          label="Status"
          value={
            filters.status
          }
          onChange={(
            value
          ) =>
            updateFilter(
              "status",
              value
            )
          }
          options={
            optionSets.statuses
          }
        />

        <FilterSelect
          label="Service"
          value={
            filters.service
          }
          onChange={(
            value
          ) =>
            updateFilter(
              "service",
              value
            )
          }
          options={
            optionSets.services
          }
        />

        <FilterSelect
          label="Action"
          value={
            filters.action
          }
          onChange={(
            value
          ) =>
            updateFilter(
              "action",
              value
            )
          }
          options={
            optionSets.actions
          }
        />

        <FilterSelect
          label="Model"
          value={
            filters.model
          }
          onChange={(
            value
          ) =>
            updateFilter(
              "model",
              value
            )
          }
          options={
            optionSets.models
          }
        />

        <FilterSelect
          label="Task Type"
          value={
            filters.taskType
          }
          onChange={(
            value
          ) =>
            updateFilter(
              "taskType",
              value
            )
          }
          options={
            optionSets.taskTypes
          }
        />

        <label className="nova-audit-filter-field">
          <span>
            From
          </span>

          <input
            type="date"
            value={
              filters.startDate
            }
            max={
              filters.endDate ||
              undefined
            }
            onChange={(
              event
            ) =>
              updateFilter(
                "startDate",
                event
                  .target
                  .value
              )
            }
          />
        </label>

        <label className="nova-audit-filter-field">
          <span>
            To
          </span>

          <input
            type="date"
            value={
              filters.endDate
            }
            min={
              filters.startDate ||
              undefined
            }
            onChange={(
              event
            ) =>
              updateFilter(
                "endDate",
                event
                  .target
                  .value
              )
            }
          />
        </label>
      </div>

      <div className="nova-audit-layout">
        <section className="nova-audit-stream-panel">
          <div className="nova-audit-stream-header">
            <div>
              <div className="nova-audit-stream-title">
                <Network
                  size={17}
                />

                <span>
                  EXECUTION STREAM
                </span>

                <span className="nova-audit-stream-count">
                  {events.length}
                </span>
              </div>

              <p>
                Newest events first. Click
                an event to inspect the
                complete structured record.
              </p>
            </div>

            <div className="nova-audit-stream-health">
              <span className="nova-live-dot" />

              {live
                ? `LIVE / ${REFRESH_INTERVAL_MS / 1000}s`
                : "REFRESH PAUSED"}
            </div>
          </div>

          <div className="nova-audit-stream-body">
            {loading ? (
              <EmptyState
                loading
                hasFilters={
                  false
                }
                onReset={
                  clearFilters
                }
              />
            ) : events.length ===
              0 ? (
              <EmptyState
                loading={
                  false
                }
                hasFilters={
                  hasFilters
                }
                onReset={
                  clearFilters
                }
              />
            ) : (
              <div className="nova-audit-event-list">
                {events.map(
                  (
                    event
                  ) => (
                    <AuditEventRow
                      key={
                        event.event_id
                      }
                      event={
                        event
                      }
                      selected={
                        selectedEvent?.event_id ===
                        event.event_id
                      }
                      onSelect={
                        openInspector
                      }
                    />
                  )
                )}
              </div>
            )}
          </div>
        </section>

        <AnimatePresence mode="wait">
          {selectedEvent && (
            <EventInspector
              key={
                selectedEvent.event_id
              }
              event={
                selectedEvent
              }
              onClose={() =>
                setSelectedEvent(
                  null
                )
              }
              onTrace={(traceId) => {
                updateFilter(
                  "query",
                  traceId
                );
                setSelectedEvent(null);
              }}
            />
          )}
        </AnimatePresence>
      </div>

      {selectedEvent &&
        inspectorLoading && (
          <div className="nova-audit-inspector-loading">
            <Timer
              size={14}
              className="nova-audit-spin"
            />
            Loading complete
            event record…
          </div>
        )}

      <div className="nova-audit-footer">
        <div>
          <ShieldCheck
            size={14}
          />

          <span>
            APPEND-ONLY RUNTIME TRACE
          </span>
        </div>

        <div>
          <Clock3
            size={14}
          />

          <span>
            Last refresh{" "}
            {formatTimestamp(
              new Date()
            )}
          </span>
        </div>

        <div>
          <ListFilter
            size={14}
          />

          <span>
            {hasFilters
              ? "FILTERED VIEW"
              : "FULL QUERY"}
          </span>
        </div>
      </div>
    </div>
  );
}
