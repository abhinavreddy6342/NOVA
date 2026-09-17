import {
  Activity,
  ArrowUpRight,
  BrainCircuit,
  Database,
  FileSearch,
  Gauge,
  LockKeyhole,
  MessageSquare,
  Radar,
  ShieldCheck,
  Upload,
  Zap,
} from "lucide-react";
import { motion } from "framer-motion";
import {
  useEffect,
  useMemo,
  useState,
} from "react";

import NovaCore from "../three/NovaCore";

const API_URL =
  "http://127.0.0.1:8001";

const STORAGE_KEY =
  "nova.missions.v2";

function loadStoredMissions() {
  try {
    const raw =
      localStorage.getItem(
        STORAGE_KEY
      );

    if (!raw) {
      return [];
    }

    const parsed =
      JSON.parse(raw);

    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed.filter(
      (mission) =>
        mission &&
        typeof mission === "object"
    );
  } catch {
    return [];
  }
}

function formatMissionStatus(
  value
) {
  return String(
    value || "READY"
  ).toUpperCase();
}

function getMissionProgress(
  mission
) {
  const value =
    Number(
      mission?.progress
    );

  if (!Number.isFinite(value)) {
    return 0;
  }

  return Math.min(
    100,
    Math.max(
      0,
      Math.round(value)
    )
  );
}

function getMetricValue(
  value,
  fallback = "--"
) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return fallback;
  }

  return String(
    value
  );
}

function StatusDot() {
  return (
    <span className="status-dot" />
  );
}

const heroItem = {
  hidden: {
    opacity: 0,
    y: 40,
  },

  visible: {
    opacity: 1,
    y: 0,
  },
};

const heroTransition = {
  ease: "easeOut",
};

function MetricCard({
  metric,
  index,
}) {
  const Icon =
    metric.icon;

  return (
    <motion.div
      className="metric-card"
      initial={{
        opacity: 0,
        y: 20,
      }}
      animate={{
        opacity: 1,
        y: 0,
      }}
      whileHover={{
        y: -3,
      }}
      transition={{
        duration: 0.55,
        delay:
          index * 0.1,
        ease: "easeOut",
      }}
    >
      <div className="metric-icon">
        <Icon size={17} />
      </div>

      <div className="metric-data">
        <span>
          {metric.label}
        </span>

        <strong>
          {metric.value}
        </strong>

        <small>
          {metric.detail}
        </small>
      </div>

      <ArrowUpRight
        className="metric-arrow"
        size={15}
      />
    </motion.div>
  );
}

function MissionRow({
  mission,
  onNavigate,
}) {
  const status =
    formatMissionStatus(
      mission?.status
    );

  const progress =
    getMissionProgress(
      mission
    );

  return (
    <motion.button
      className="mission-row"
      type="button"
      onClick={() =>
        onNavigate("missions")
      }
      whileHover={{
        x: 3,
      }}
      transition={{
        duration: 0.18,
      }}
    >
      <span className="mission-number">
        {getMetricValue(
          mission?.number,
          "--"
        )}
      </span>

      <div className="mission-info">
        <div className="mission-title-line">
          <strong>
            {getMetricValue(
              mission?.title,
              "Untitled Mission"
            )}
          </strong>

          <span
            className={`mission-status ${status.toLowerCase()}`}
          >
            <span />
            {status}
          </span>
        </div>

        <p>
          {getMetricValue(
            mission?.description ||
              mission?.objective,
            "No mission description available."
          )}
        </p>

        <div className="mission-progress-label">
          <span>
            Execution
          </span>

          <strong>
            {progress}%
          </strong>
        </div>

        <div className="mission-progress">
          <span
            style={{
              width:
                `${progress}%`,
            }}
          />
        </div>
      </div>

      <ArrowUpRight
        size={16}
        className="mission-arrow"
      />
    </motion.button>
  );
}

export default function CommandCenter({
  onNavigate,
}) {
  const [
    missions,
    setMissions,
  ] = useState(
    loadStoredMissions
  );

  const [
    runtimeInfo,
    setRuntimeInfo,
  ] = useState(null);

  useEffect(() => {
    const syncMissions =
      () => {
        setMissions(
          loadStoredMissions()
        );
      };

    window.addEventListener(
      "storage",
      syncMissions
    );

    const interval =
      window.setInterval(
        syncMissions,
        1500
      );

    return () =>
      window.clearInterval(
        interval
      );
  }, []);

  useEffect(() => {
    let cancelled =
      false;

    const loadRuntimeInfo =
      async () => {
        try {
          const response =
            await fetch(
              `${API_URL}/health`,
              {
                method:
                  "GET",
              }
            );

          if (
            !response.ok
          ) {
            return;
          }

          const data =
            await response.json();

          if (!cancelled) {
            setRuntimeInfo(
              data || null
            );
          }
        } catch {
          if (!cancelled) {
            setRuntimeInfo(
              null
            );
          }
        }
      };

    loadRuntimeInfo();

    const interval =
      window.setInterval(
        loadRuntimeInfo,
        5000
      );

    return () => {
      cancelled = true;
      window.clearInterval(
        interval
      );
    };
  }, []);

  const displayedMissions =
    useMemo(
      () =>
        missions
          .filter(
            (mission) =>
              mission &&
              typeof mission ===
                "object"
          )
          .slice(
            0,
            3
          ),
      [
        missions,
      ]
    );

  const activeCount =
    missions.filter(
      (mission) =>
        formatMissionStatus(
          mission?.status
        ) ===
        "RUNNING"
    ).length;

  const completedCount =
    missions.filter(
      (mission) =>
        formatMissionStatus(
          mission?.status
        ) ===
        "COMPLETED"
    ).length;

  const evidenceCount =
    missions.reduce(
      (
        total,
        mission
      ) =>
        total +
        (
          Array.isArray(
            mission?.attachments
          )
            ? mission.attachments.length
            : 0
        ),
      0
    );

  const localModel =
    getMetricValue(
      runtimeInfo?.model ||
        runtimeInfo?.model_name ||
        runtimeInfo?.active_model,
      "NOT VERIFIED"
    );

  const runtimeEngine =
    getMetricValue(
      runtimeInfo?.engine ||
        runtimeInfo?.inference_engine,
      "NOT VERIFIED"
    );

  const runtimeStatus =
    runtimeInfo
      ? getMetricValue(
          runtimeInfo?.status ||
            runtimeInfo?.state,
          "ONLINE"
        )
      : "NOT VERIFIED";

  const metrics = [
    {
      label:
        "REGISTERED MISSIONS",
      value:
        String(
          missions.length
        ).padStart(
          2,
          "0"
        ),
      detail:
        missions.length ===
        0
          ? "No user missions yet"
          : `${missions.length} user-created mission${
              missions.length ===
              1
                ? ""
                : "s"
            }`,
      icon:
        Zap,
    },
    {
      label:
        "EVIDENCE FILES",
      value:
        String(
          evidenceCount
        ).padStart(
          2,
          "0"
        ),
      detail:
        evidenceCount ===
        0
          ? "No mission evidence"
          : "Attached mission evidence",
      icon:
        Database,
    },
    {
      label:
        "ACTIVE AGENTS",
      value:
        String(
          activeCount
        ).padStart(
          2,
          "0"
        ),
      detail:
        activeCount ===
        0
          ? "No active mission"
          : "Mission execution active",
      icon:
        Activity,
    },
    {
      label:
        "COMPLETED MISSIONS",
      value:
        String(
          completedCount
        ).padStart(
          2,
          "0"
        ),
      detail:
        completedCount ===
        0
          ? "No completed runs"
          : "Verified mission runs",
      icon:
        ShieldCheck,
    },
  ];

  return (
    <div className="command-center-page">
      {/* HERO */}

      <section className="hero-section">
        <div className="hero-copy">
          <motion.div
            className="hero-eyebrow"
            initial="hidden"
            animate="visible"
            variants={heroItem}
            transition={{
              duration:
                0.55,
              delay: 0,
              ...heroTransition,
            }}
          >
            <span className="eyebrow-line" />

            SYSTEM ONLINE · SOVEREIGN AI ENVIRONMENT
          </motion.div>

          <motion.h1
            initial="hidden"
            animate="visible"
            variants={heroItem}
            transition={{
              duration:
                0.8,
              delay: 0.05,
              ...heroTransition,
            }}
          >
            SOVEREIGN
            <br />
            INDUSTRIAL
            <br />

            <span className="hero-accent-text">
              INTELLIGENCE
            </span>
          </motion.h1>

          <motion.div
            className="hero-subtitle"
            initial={{
              opacity: 0,
              y: 25,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            transition={{
              duration:
                0.6,
              delay: 0.2,
              ease: "easeOut",
            }}
          >
            Intelligence without compromise.
          </motion.div>

          <motion.p
            initial={{
              opacity: 0,
              y: 25,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            transition={{
              duration:
                0.6,
              delay: 0.28,
              ease: "easeOut",
            }}
          >
            NOVA is a private AI operating environment
            engineered for confidential industrial
            intelligence, local reasoning, and controlled
            agentic workflows.
          </motion.p>

          <motion.div
            className="hero-buttons"
            initial={{
              opacity: 0,
              y: 25,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            transition={{
              duration:
                0.55,
              delay: 0.36,
              ease: "easeOut",
            }}
          >
            <button
              className="primary-action"
              type="button"
              onClick={() =>
                onNavigate(
                  "missions"
                )
              }
            >
              <Zap size={17} />
              START A MISSION
            </button>

            <button
              className="secondary-action"
              type="button"
              onClick={() =>
                onNavigate(
                  "chat"
                )
              }
            >
              <MessageSquare
                size={17}
              />
              ASK NOVA
            </button>
          </motion.div>

          <motion.div
            className="trust-row"
            initial={{
              opacity: 0,
              y: 20,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            transition={{
              duration:
                0.55,
              delay: 0.48,
              ease: "easeOut",
            }}
          >
            <span>
              <ShieldCheck size={14} />
              LOCAL EXECUTION
            </span>

            <span>
              <LockKeyhole
                size={14}
              />
              DATA STAYS LOCAL
            </span>

            <span>
              <Radar size={14} />
              AIR-GAPPED READY
            </span>
          </motion.div>
        </div>

        {/* NOVA ORB */}

        <motion.div
          className="core-panel"
          initial={{
            opacity: 0,
            scale: 0.94,
            y: 25,
          }}
          animate={{
            opacity: 1,
            scale: 1,
            y: 0,
          }}
          transition={{
            duration:
              1,
            delay:
              0.2,
            ease:
              [
                0.22,
                1,
                0.36,
                1,
              ],
          }}
        >
          <div className="core-panel-header">
            <div className="core-header-left">
              <span className="core-header-index">
                CORE INTELLIGENCE // 001
              </span>

              <span className="core-header-state">
                SOVEREIGN RUNTIME
              </span>
            </div>

            <span className="live-indicator">
              <StatusDot />
              {runtimeInfo
                ? "LIVE"
                : "LOCAL"}
            </span>
          </div>

          <div className="core-scene">
            <div className="scene-grid-overlay" />

            <div className="scene-depth-line scene-depth-line-1" />
            <div className="scene-depth-line scene-depth-line-2" />
            <div className="scene-depth-line scene-depth-line-3" />

            <NovaCore />

            <div className="scene-label scene-label-top-left">
              <span>
                ENTITY
              </span>

              <strong>
                NOVA-001
              </strong>
            </div>

            <div className="scene-label scene-label-top-right">
              <span>
                STATE
              </span>

              <strong>
                {runtimeInfo
                  ? runtimeStatus.toUpperCase()
                  : "LOCAL"}
              </strong>
            </div>

            <div className="scene-label scene-label-bottom-left">
              <span>
                MODE
              </span>

              <strong>
                LOCAL
              </strong>
            </div>

            <div className="scene-label scene-label-bottom-right">
              <span>
                LINK
              </span>

              <strong>
                SECURE
              </strong>
            </div>

            <div className="scene-center-marker">
              <span />
              <span />
              <span />
              <span />
            </div>
          </div>

          <div className="core-panel-footer">
            <div>
              <strong>
                LOCAL REASONING ENGINE
              </strong>

              <span>
                {runtimeInfo
                  ? `${localModel} · ${runtimeEngine}`
                  : "RUNTIME DETAILS AWAITING VERIFIED BACKEND DATA"}
              </span>
            </div>

            <div className="core-footer-status">
              <span className="footer-status-pulse" />

              {runtimeInfo
                ? "RUNTIME CONNECTED"
                : "RUNTIME STATUS UNVERIFIED"}
            </div>
          </div>

          <div className="core-corner core-corner-tl" />
          <div className="core-corner core-corner-tr" />
          <div className="core-corner core-corner-bl" />
          <div className="core-corner core-corner-br" />
        </motion.div>
      </section>

      {/* METRICS */}

      <section className="metrics-grid">
        {metrics.map(
          (
            metric,
            index
          ) => (
            <MetricCard
              key={
                metric.label
              }
              metric={
                metric
              }
              index={
                index
              }
            />
          )
        )}
      </section>

      {/* MISSION + RUNTIME */}

      <section className="lower-grid">
        <motion.div
          className="panel mission-panel"
          initial={{
            opacity: 0,
            y: 25,
          }}
          whileInView={{
            opacity: 1,
            y: 0,
          }}
          viewport={{
            once: true,
            amount: 0.15,
          }}
          transition={{
            duration:
              0.7,
            ease:
              "easeOut",
          }}
        >
          <div className="panel-header">
            <div>
              <span className="panel-eyebrow">
                USER WORKFLOWS
              </span>

              <h2>
                MISSION CONTROL
              </h2>

              <p>
                Real missions created in this NOVA workspace.
              </p>
            </div>

            <button
              type="button"
              onClick={() =>
                onNavigate(
                  "missions"
                )
              }
            >
              VIEW ALL
              <ArrowUpRight
                size={14}
              />
            </button>
          </div>

          <div className="mission-list">
            {displayedMissions.length >
            0 ? (
              displayedMissions.map(
                (
                  mission,
                  index
                ) => (
                  <MissionRow
                    key={
                      mission.id ||
                      mission.number ||
                      index
                    }
                    mission={
                      mission
                    }
                    onNavigate={
                      onNavigate
                    }
                  />
                )
              )
            ) : (
              <div
                style={{
                  minHeight:
                    240,

                  display:
                    "grid",

                  placeItems:
                    "center",

                  padding:
                    "30px 22px",

                  border:
                    "1px dashed rgba(255,255,255,0.07)",

                  background:
                    "rgba(255,255,255,0.012)",

                  color:
                    "#66757f",

                  textAlign:
                    "center",

                  fontSize:
                    10,

                  lineHeight:
                    1.7,
                }}
              >
                <div>
                  <Zap
                    size={
                      26
                    }
                    color="#7edff2"
                  />

                  <div
                    style={{
                      marginTop:
                        12,

                      color:
                        "#dcebed",

                      fontSize:
                        14,

                      fontWeight:
                        700,
                    }}
                  >
                    NO USER MISSIONS
                  </div>

                  <p
                    style={{
                      maxWidth:
                        300,

                      margin:
                        "8px auto 0",

                      color:
                        "#5d6d75",

                      fontSize:
                        9,

                      lineHeight:
                        1.7,
                    }}
                  >
                    Create a real mission from Mission Control
                    to see it reflected here.
                  </p>
                </div>
              </div>
            )}
          </div>
        </motion.div>

        <motion.div
          className="panel activity-panel"
          initial={{
            opacity: 0,
            y: 25,
          }}
          whileInView={{
            opacity: 1,
            y: 0,
          }}
          viewport={{
            once: true,
            amount: 0.15,
          }}
          transition={{
            duration:
              0.7,
            delay:
              0.1,
            ease:
              "easeOut",
          }}
        >
          <div className="panel-header">
            <div>
              <span className="panel-eyebrow">
                SYSTEM TELEMETRY
              </span>

              <h2>
                RUNTIME
              </h2>
            </div>
          </div>

          <div className="runtime-stat-list">
            <div>
              <span>
                Runtime status
              </span>

              <strong>
                {runtimeInfo
                  ? runtimeStatus
                  : "NOT VERIFIED"}
              </strong>
            </div>

            <div>
              <span>
                Inference engine
              </span>

              <strong>
                {runtimeInfo
                  ? runtimeEngine
                  : "NOT VERIFIED"}
              </strong>
            </div>

            <div>
              <span>
                Active model
              </span>

              <strong>
                {runtimeInfo
                  ? localModel
                  : "NOT VERIFIED"}
              </strong>
            </div>

            <div>
              <span>
                Mission agents
              </span>

              <strong>
                {activeCount}
              </strong>
            </div>
          </div>

          <div className="runtime-chart">
            <div className="chart-header">
              <span>
                <Activity
                  size={14}
                />
                MISSION ACTIVITY
              </span>

              <Gauge
                size={14}
              />
            </div>

            <div className="bars">
              {Array.from({
                length:
                  28,
              }).map(
                (
                  _,
                  index
                ) => {
                  const mission =
                    missions[
                      index %
                        Math.max(
                          1,
                          missions.length
                        )
                    ];

                  const progress =
                    missions.length
                      ? getMissionProgress(
                          mission
                        )
                      : 0;

                  const height =
                    missions.length
                      ? Math.max(
                          12,
                          Math.round(
                            progress *
                              (
                                0.35 +
                                (
                                  index %
                                    4
                                ) *
                                  0.08
                              )
                          )
                        )
                      : 10;

                  return (
                    <span
                      key={
                        index
                      }
                      style={{
                        height:
                          `${Math.min(
                            90,
                            height
                          )}%`,
                      }}
                    />
                  );
                }
              )}
            </div>
          </div>
        </motion.div>
      </section>

      {/* QUICK SYSTEMS */}

      <section className="quick-grid">
        {[
          {
            icon:
              MessageSquare,

            title:
              "ASK NOVA",

            text:
              "Start a local conversation",

            page:
              "chat",
          },
          {
            icon:
              FileSearch,

            title:
              "KNOWLEDGE",

            text:
              "Analyze confidential documents",

            page:
              "knowledge",
          },
          {
            icon:
              Upload,

            title:
              "INGEST",

            text:
              "Add enterprise knowledge",

            page:
              "knowledge",
          },
          {
            icon:
              ShieldCheck,

            title:
              "SECURITY",

            text:
              "Inspect sovereign runtime",

            page:
              "sovereignty",
          },
        ].map(
          (
            item,
            index
          ) => {
            const Icon =
              item.icon;

            return (
              <motion.button
                key={
                  item.title
                }
                className="quick-card"
                type="button"
                onClick={() =>
                  onNavigate(
                    item.page
                  )
                }
                initial={{
                  opacity:
                    0,

                  y:
                    20,
                }}
                whileInView={{
                  opacity:
                    1,

                  y:
                    0,
                }}
                whileHover={{
                  y:
                    -4,
                }}
                viewport={{
                  once:
                    true,

                  amount:
                    0.15,
                }}
                transition={{
                  duration:
                    0.55,

                  delay:
                    index *
                    0.1,

                  ease:
                    "easeOut",
                }}
              >
                <Icon
                  size={18}
                />

                <span>
                  {
                    item.title
                  }
                </span>

                <strong>
                  {
                    item.text
                  }
                </strong>

                <ArrowUpRight
                  size={15}
                />
              </motion.button>
            );
          }
        )}
      </section>
    </div>
  );
}