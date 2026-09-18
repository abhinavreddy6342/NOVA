import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  Activity,
  CheckCircle2,
  Cpu,
  Database,
  HardDrive,
  Layers3,
  MemoryStick,
  Network,
  RefreshCw,
  ShieldCheck,
  Server,
  Wifi,
  XCircle,
} from "lucide-react";

import { getSovereignty } from "../../services/api";


const REFRESH_INTERVAL = 5000;


function formatNumber(value, digits = 1) {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {
    return "NOT REPORTED";
  }

  return Number(value).toFixed(digits);
}


function formatBytes(value) {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {
    return "NOT REPORTED";
  }

  const bytes = Number(value);

  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 ** 2) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  if (bytes < 1024 ** 3) {
    return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  }

  if (bytes < 1024 ** 4) {
    return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  }

  return `${(bytes / 1024 ** 4).toFixed(1)} TB`;
}


function formatDateTime(value) {
  if (!value) {
    return "NOT AVAILABLE";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString();
}


function normalizeStatus(value) {
  return String(
    value ?? "NOT REPORTED"
  )
    .trim()
    .toUpperCase();
}


function isPositiveStatus(value) {
  return [
    "READY",
    "AVAILABLE",
    "VERIFIED",
    "ONLINE",
    "LOCAL",
    "ACTIVE",
    "HEALTHY",
    "OK",
  ].includes(
    normalizeStatus(value)
  );
}


function StatusBadge({
  value,
  compact = false,
}) {
  const status =
    normalizeStatus(value);

  const positive =
    isPositiveStatus(status);

  return (
    <span
      className={[
        "nova-sovereignty-status",
        positive
          ? "is-positive"
          : "is-neutral",
        compact
          ? "is-compact"
          : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <span className="nova-sovereignty-status-dot" />
      {status}
    </span>
  );
}


function MetricBar({
  value,
  label,
}) {
  const numeric =
    Number(value);

  const valid =
    Number.isFinite(numeric);

  const percent =
    valid
      ? Math.max(
          0,
          Math.min(
            100,
            numeric
          )
        )
      : 0;

  return (
    <div className="nova-sovereignty-meter">
      <div className="nova-sovereignty-meter-head">
        <span>{label}</span>

        <strong>
          {valid
            ? `${formatNumber(
                numeric
              )}%`
            : "NOT REPORTED"}
        </strong>
      </div>

      <div className="nova-sovereignty-meter-track">
        <div
          className="nova-sovereignty-meter-fill"
          style={{
            width: `${percent}%`,
          }}
        />
      </div>
    </div>
  );
}


function SectionHeader({
  eyebrow,
  title,
  icon: Icon,
}) {
  return (
    <div className="nova-sovereignty-section-header">
      <div className="nova-sovereignty-section-icon">
        <Icon size={16} />
      </div>

      <div>
        <span>
          {eyebrow}
        </span>

        <h2>
          {title}
        </h2>
      </div>
    </div>
  );
}


function getStorageEntries(storage) {
  if (!storage) {
    return [];
  }

  if (Array.isArray(storage)) {
    return storage.map(
      (item, index) => ({
        name:
          item?.name ||
          item?.path ||
          `Storage ${index + 1}`,

        path:
          item?.path ||
          item?.directory ||
          item?.location ||
          "NOT REPORTED",

        status:
          item?.status ||
          (item?.exists
            ? "AVAILABLE"
            : "NOT REPORTED"),

        fileCount:
          item?.file_count ??
          item?.files ??
          null,

        size:
          item?.size_bytes ??
          item?.bytes ??
          null,
      })
    );
  }

  if (
    typeof storage ===
    "object"
  ) {
    return Object.entries(
      storage
    ).map(
      ([name, item]) => {
        if (
          item &&
          typeof item ===
            "object"
        ) {
          return {
            name:
              item.name ||
              name,

            path:
              item.path ||
              item.directory ||
              item.location ||
              name,

            status:
              item.status ||
              (item.exists
                ? "AVAILABLE"
                : "NOT REPORTED"),

            fileCount:
              item.file_count ??
              item.files ??
              null,

            size:
              item.size_bytes ??
              item.bytes ??
              null,
          };
        }

        return {
          name,
          path: name,
          status:
            item
              ? "AVAILABLE"
              : "NOT REPORTED",
          fileCount: null,
          size: null,
        };
      }
    );
  }

  return [];
}


function getVerificationChecks(
  verification
) {
  if (!verification) {
    return [];
  }

  if (
    Array.isArray(
      verification.checks
    )
  ) {
    return verification.checks.map(
      (item, index) => {
        if (
          typeof item ===
          "string"
        ) {
          return {
            name: item,
            status:
              "AVAILABLE",
          };
        }

        return {
          name:
            item?.name ||
            item?.check ||
            `Check ${index + 1}`,

          status:
            item?.status ||
            (item?.passed
              ? "PASSED"
              : "NOT REPORTED"),

          detail:
            item?.detail ||
            item?.message ||
            "",
        };
      }
    );
  }

  if (
    verification.checks &&
    typeof verification.checks ===
      "object"
  ) {
    return Object.entries(
      verification.checks
    ).map(
      ([name, value]) => ({
        name,
        status:
          typeof value ===
          "boolean"
            ? value
              ? "PASSED"
              : "FAILED"
            : normalizeStatus(
                value
              ),
        detail: "",
      })
    );
  }

  return [];
}


export default function SovereigntyCenter() {
  const [
    snapshot,
    setSnapshot,
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

  const loadSnapshot =
    useCallback(
      async (
        isRefresh = false
      ) => {
        try {
          if (isRefresh) {
            setRefreshing(true);
          } else {
            setLoading(true);
          }

          const data =
            await getSovereignty();

          setSnapshot(data);
          setError("");
        } catch (requestError) {
          setError(
            requestError?.message ||
              "Unable to read the NOVA sovereignty state."
          );
        } finally {
          setLoading(false);
          setRefreshing(false);
        }
      },
      []
    );

  useEffect(() => {
    loadSnapshot();

    const timer =
      window.setInterval(
        () => {
          loadSnapshot(true);
        },
        REFRESH_INTERVAL
      );

    return () => {
      window.clearInterval(
        timer
      );
    };
  }, [loadSnapshot]);


  const runtime =
    snapshot?.runtime || {};

  const hardware =
    snapshot?.hardware || {};

  const cpu =
    hardware?.cpu || {};

  const memory =
    hardware?.memory || {};

  const gpu =
    hardware?.gpu || {};

  const network =
    snapshot?.network || {};

  const verification =
    snapshot?.verification || {};

  const storageEntries =
    useMemo(
      () =>
        getStorageEntries(
          snapshot?.storage
        ),
      [snapshot?.storage]
    );

  const verificationChecks =
    useMemo(
      () =>
        getVerificationChecks(
          verification
        ),
      [verification]
    );

  const installedModels =
    Array.isArray(
      runtime?.installed_models
    )
      ? runtime.installed_models
      : [];

  const verificationStatus =
    normalizeStatus(
      verification?.status
    );

  const runtimeStatus =
    normalizeStatus(
      runtime?.status
    );

  const networkStatus =
    normalizeStatus(
      network?.status ||
        network?.network_status
    );

  const cpuUsage =
    cpu?.usage_percent ??
    cpu?.percent ??
    cpu?.usage;

  const memoryUsage =
    memory?.usage_percent ??
    memory?.percent ??
    memory?.usage;

  const gpuMemoryUsage =
    gpu?.memory_used_percent ??
    gpu?.vram_usage_percent;

  return (
    <div className="nova-sovereignty-page">

      <header className="nova-sovereignty-header">
        <div>
          <div className="nova-sovereignty-eyebrow">
            SOVEREIGN RUNTIME
          </div>

          <h1>
            Sovereignty Center
          </h1>

          <p>
            Runtime-observed local execution,
            storage residency, hardware state,
            and application-level network activity.
          </p>
        </div>

        <button
          className="nova-sovereignty-refresh"
          type="button"
          onClick={() =>
            loadSnapshot(true)
          }
          disabled={refreshing}
        >
          <RefreshCw
            size={15}
            className={
              refreshing
                ? "nova-sovereignty-spin"
                : ""
            }
          />

          {refreshing
            ? "REFRESHING"
            : "REFRESH STATE"}
        </button>
      </header>


      {error && (
        <div className="nova-sovereignty-error">
          <XCircle size={17} />

          <div>
            <strong>
              SOVEREIGNTY STATE UNAVAILABLE
            </strong>

            <span>
              {error}
            </span>
          </div>
        </div>
      )}


      {loading && !snapshot ? (
        <div className="nova-sovereignty-loading">
          <RefreshCw
            size={18}
            className="nova-sovereignty-spin"
          />

          <span>
            READING LOCAL RUNTIME STATE...
          </span>
        </div>
      ) : (
        <>
          <section className="nova-sovereignty-command-strip">

            <div className="nova-sovereignty-command-cell">
              <span>
                VERIFICATION
              </span>

              <StatusBadge
                value={
                  verificationStatus
                }
              />
            </div>

            <div className="nova-sovereignty-command-cell">
              <span>
                RUNTIME
              </span>

              <StatusBadge
                value={
                  runtimeStatus
                }
              />
            </div>

            <div className="nova-sovereignty-command-cell">
              <span>
                NETWORK
              </span>

              <StatusBadge
                value={
                  networkStatus
                }
              />
            </div>

            <div className="nova-sovereignty-command-cell">
              <span>
                LOCAL MODELS
              </span>

              <strong>
                {
                  runtime?.installed_model_count ??
                  installedModels.length ??
                  "NOT REPORTED"
                }
              </strong>
            </div>

          </section>


          <section className="nova-sovereignty-overview">

            <div className="nova-sovereignty-overview-panel nova-sovereignty-topology-panel">

              <SectionHeader
                eyebrow="EXECUTION TOPOLOGY"
                title="Local intelligence boundary"
                icon={Layers3}
              />

              <div className="nova-sovereignty-topology">

                <div className="nova-sovereignty-node">
                  <div className="nova-sovereignty-node-icon">
                    <Activity size={18} />
                  </div>

                  <strong>
                    NOVA
                  </strong>

                  <span>
                    Application runtime
                  </span>
                </div>

                <div className="nova-sovereignty-link">
                  <span />
                </div>

                <div className="nova-sovereignty-node">
                  <div className="nova-sovereignty-node-icon">
                    <Server size={18} />
                  </div>

                  <strong>
                    OLLAMA
                  </strong>

                  <span>
                    {runtime?.base_url ||
                      runtime?.ollama_url ||
                      "LOCAL RUNTIME"}
                  </span>
                </div>

                <div className="nova-sovereignty-link">
                  <span />
                </div>

                <div className="nova-sovereignty-node">
                  <div className="nova-sovereignty-node-icon">
                    <Database size={18} />
                  </div>

                  <strong>
                    LOCAL DATA
                  </strong>

                  <span>
                    Knowledge + workspace
                  </span>
                </div>

              </div>

              <div className="nova-sovereignty-topology-note">
                <ShieldCheck size={15} />

                <span>
                  This panel describes NOVA's
                  local execution boundary.
                  Runtime claims below are
                  populated from the backend
                  snapshot.
                </span>
              </div>

            </div>


            <div className="nova-sovereignty-overview-panel nova-sovereignty-verification-panel">

              <SectionHeader
                eyebrow="TRUST STATE"
                title="Verification"
                icon={ShieldCheck}
              />

              <div className="nova-sovereignty-verification-main">
                <div
                  className={[
                    "nova-sovereignty-verification-icon",
                    isPositiveStatus(
                      verificationStatus
                    )
                      ? "is-positive"
                      : "is-neutral",
                  ].join(" ")}
                >
                  {isPositiveStatus(
                    verificationStatus
                  ) ? (
                    <CheckCircle2
                      size={27}
                    />
                  ) : (
                    <Activity
                      size={27}
                    />
                  )}
                </div>

                <div>
                  <strong>
                    {
                      verificationStatus
                    }
                  </strong>

                  <span>
                    Current backend
                    verification result
                  </span>
                </div>
              </div>

              {verification?.message && (
                <p className="nova-sovereignty-verification-message">
                  {verification.message}
                </p>
              )}

              {verificationChecks.length >
                0 && (
                <div className="nova-sovereignty-check-list">
                  {verificationChecks.map(
                    (check, index) => (
                      <div
                        className="nova-sovereignty-check-row"
                        key={`${check.name}-${index}`}
                      >
                        <CheckCircle2
                          size={14}
                        />

                        <div>
                          <strong>
                            {check.name}
                          </strong>

                          {check.detail && (
                            <span>
                              {check.detail}
                            </span>
                          )}
                        </div>

                        <span>
                          {normalizeStatus(
                            check.status
                          )}
                        </span>
                      </div>
                    )
                  )}
                </div>
              )}

            </div>

          </section>


          <section className="nova-sovereignty-grid">

            <div className="nova-sovereignty-card">

              <SectionHeader
                eyebrow="AI RUNTIME"
                title="Local model execution"
                icon={Server}
              />

              <div className="nova-sovereignty-card-stat">
                <span>
                  SERVICE
                </span>

                <StatusBadge
                  value={
                    runtime?.status
                  }
                  compact
                />
              </div>

              <div className="nova-sovereignty-card-stat">
                <span>
                  INSTALLED
                </span>

                <strong>
                  {
                    runtime?.installed_model_count ??
                    "NOT REPORTED"
                  }
                </strong>
              </div>

              <div className="nova-sovereignty-card-stat">
                <span>
                  ACTIVE MODEL
                </span>

                <strong className="nova-sovereignty-mono">
                  {
                    runtime?.active_model ||
                    "NOT REPORTED"
                  }
                </strong>
              </div>

              {installedModels.length >
                0 && (
                <div className="nova-sovereignty-model-list">
                  {installedModels.map(
                    (model, index) => {
                      const name =
                        typeof model ===
                        "string"
                          ? model
                          : model?.name ||
                            model?.model ||
                            `MODEL ${index + 1}`;

                      return (
                        <span
                          key={`${name}-${index}`}
                        >
                          {name}
                        </span>
                      );
                    }
                  )}
                </div>
              )}

            </div>


            <div className="nova-sovereignty-card">

              <SectionHeader
                eyebrow="PROCESSOR"
                title="CPU state"
                icon={Cpu}
              />

              <div className="nova-sovereignty-card-stat">
                <span>
                  STATUS
                </span>

                <StatusBadge
                  value={
                    cpu?.status
                  }
                  compact
                />
              </div>

              <div className="nova-sovereignty-card-stat">
                <span>
                  CORES
                </span>

                <strong>
                  {
                    cpu?.logical_cores ??
                    cpu?.cores ??
                    "NOT REPORTED"
                  }
                </strong>
              </div>

              <MetricBar
                value={
                  cpuUsage
                }
                label="CURRENT UTILIZATION"
              />

            </div>


            <div className="nova-sovereignty-card">

              <SectionHeader
                eyebrow="SYSTEM MEMORY"
                title="RAM state"
                icon={MemoryStick}
              />

              <div className="nova-sovereignty-card-stat">
                <span>
                  TOTAL
                </span>

                <strong>
                  {memory?.total_gb != null
                    ? `${formatNumber(
                        memory.total_gb
                      )} GB`
                    : memory?.total_bytes !=
                        null
                      ? formatBytes(
                          memory.total_bytes
                        )
                      : "NOT REPORTED"}
                </strong>
              </div>

              <div className="nova-sovereignty-card-stat">
                <span>
                  USED
                </span>

                <strong>
                  {memory?.used_gb != null
                    ? `${formatNumber(
                        memory.used_gb
                      )} GB`
                    : memory?.used_bytes !=
                        null
                      ? formatBytes(
                          memory.used_bytes
                        )
                      : "NOT REPORTED"}
                </strong>
              </div>

              <MetricBar
                value={
                  memoryUsage
                }
                label="CURRENT UTILIZATION"
              />

            </div>


            <div className="nova-sovereignty-card">

              <SectionHeader
                eyebrow="GRAPHICS"
                title="GPU / VRAM"
                icon={Activity}
              />

              <div className="nova-sovereignty-card-stat">
                <span>
                  STATUS
                </span>

                <StatusBadge
                  value={
                    gpu?.status
                  }
                  compact
                />
              </div>

              <div className="nova-sovereignty-card-stat">
                <span>
                  DEVICE
                </span>

                <strong>
                  {
                    gpu?.name ||
                    gpu?.device ||
                    "NOT REPORTED"
                  }
                </strong>
              </div>

              <MetricBar
                value={
                  gpuMemoryUsage
                }
                label="VRAM UTILIZATION"
              />

            </div>

          </section>


          <section className="nova-sovereignty-lower-grid">

            <div className="nova-sovereignty-large-card">

              <SectionHeader
                eyebrow="RESIDENCY"
                title="Local storage surfaces"
                icon={HardDrive}
              />

              {storageEntries.length >
              0 ? (
                <div className="nova-sovereignty-storage-list">
                  {storageEntries.map(
                    (
                      item,
                      index
                    ) => (
                      <div
                        className="nova-sovereignty-storage-row"
                        key={`${item.path}-${index}`}
                      >
                        <div className="nova-sovereignty-storage-icon">
                          <HardDrive
                            size={15}
                          />
                        </div>

                        <div className="nova-sovereignty-storage-info">
                          <strong>
                            {item.name}
                          </strong>

                          <span className="nova-sovereignty-mono">
                            {item.path}
                          </span>
                        </div>

                        <div className="nova-sovereignty-storage-meta">
                          <span>
                            {item.fileCount !=
                            null
                              ? `${item.fileCount} files`
                              : "FILE COUNT NOT REPORTED"}
                          </span>

                          <span>
                            {item.size !=
                            null
                              ? formatBytes(
                                  item.size
                                )
                              : "SIZE NOT REPORTED"}
                          </span>
                        </div>

                        <StatusBadge
                          value={
                            item.status
                          }
                          compact
                        />
                      </div>
                    )
                  )}
                </div>
              ) : (
                <div className="nova-sovereignty-empty">
                  STORAGE STATE NOT REPORTED
                </div>
              )}

            </div>


            <div className="nova-sovereignty-large-card">

              <SectionHeader
                eyebrow="NETWORK OBSERVATION"
                title="Application-level egress"
                icon={Network}
              />

              <div className="nova-sovereignty-network-head">
                <div>
                  <span>
                    TRACKING SCOPE
                  </span>

                  <strong>
                    {
                      network?.tracking ||
                      "APPLICATION LEVEL"
                    }
                  </strong>
                </div>

                <Wifi
                  size={19}
                />
              </div>

              <div className="nova-sovereignty-network-grid">

                <div>
                  <span>
                    EXTERNAL API CALLS
                  </span>

                  <strong>
                    {
                      network?.external_api_calls ??
                      0
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    CLOUD UPLOADS
                  </span>

                  <strong>
                    {
                      network?.cloud_uploads ??
                      0
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    LOCAL NETWORK
                  </span>

                  <strong>
                    {
                      network?.local_network_events ??
                      0
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    NETWORK ERRORS
                  </span>

                  <strong>
                    {
                      network?.network_errors ??
                      0
                    }
                  </strong>
                </div>

              </div>

              <div className="nova-sovereignty-network-foot">
                <span>
                  EVENTS RECORDED
                </span>

                <strong>
                  {
                    network?.total_events ??
                    0
                  }
                </strong>
              </div>

              <p>
                These counters represent
                application-level events
                recorded by NOVA's network
                ledger, not unrestricted
                operating-system traffic
                telemetry.
              </p>

            </div>

          </section>


          <footer className="nova-sovereignty-footer">

            <div>
              <span>
                LAST SNAPSHOT
              </span>

              <strong>
                {formatDateTime(
                  snapshot?.timestamp
                )}
              </strong>
            </div>

            <div>
              <span>
                NETWORK SCOPE
              </span>

              <strong>
                {
                  network?.measurement_scope ||
                  "NOVA-RECORDED EVENTS ONLY"
                }
              </strong>
            </div>

            <div>
              <span>
                SNAPSHOT MODE
              </span>

              <strong>
                LIVE BACKEND STATE
              </strong>
            </div>

          </footer>

        </>
      )}

    </div>
  );
}