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
  Sparkles,
  Upload,
  Zap,
} from "lucide-react";
import { motion } from "framer-motion";

import NovaCore from "../three/NovaCore";

const metrics = [
  {
    label: "LOCAL MODELS",
    value: "01",
    detail: "Llama 3.2",
    icon: BrainCircuit,
  },
  {
    label: "KNOWLEDGE",
    value: "00",
    detail: "Documents indexed",
    icon: Database,
  },
  {
    label: "ACTIVE AGENTS",
    value: "01",
    detail: "Core runtime",
    icon: Sparkles,
  },
  {
    label: "EXTERNAL CALLS",
    value: "00",
    detail: "Sovereign runtime",
    icon: LockKeyhole,
  },
];

const missions = [
  {
    number: "01",
    title: "Pump P-204 Investigation",
    subtitle: "Industrial inspection intelligence",
    progress: 72,
    status: "READY",
  },
  {
    number: "02",
    title: "SOP Intelligence Review",
    subtitle: "Enterprise knowledge workflow",
    progress: 38,
    status: "DRAFT",
  },
  {
    number: "03",
    title: "Maintenance Risk Scan",
    subtitle: "Predictive analysis workflow",
    progress: 16,
    status: "PLANNED",
  },
];

function StatusDot() {
  return <span className="status-dot" />;
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

function MetricCard({ metric, index }) {
  const Icon = metric.icon;

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
        delay: index * 0.1,
        ease: "easeOut",
      }}
    >
      <div className="metric-icon">
        <Icon size={17} />
      </div>

      <div className="metric-data">
        <span>{metric.label}</span>
        <strong>{metric.value}</strong>
        <small>{metric.detail}</small>
      </div>

      <ArrowUpRight
        className="metric-arrow"
        size={15}
      />
    </motion.div>
  );
}

function MissionRow({ mission, onNavigate }) {
  return (
    <motion.button
      className="mission-row"
      type="button"
      onClick={() => onNavigate("missions")}
      whileHover={{
        x: 3,
      }}
      transition={{
        duration: 0.18,
      }}
    >
      <span className="mission-number">
        {mission.number}
      </span>

      <div className="mission-info">
        <div className="mission-title-line">
          <strong>{mission.title}</strong>

          <span
            className={`mission-status ${mission.status.toLowerCase()}`}
          >
            <span />
            {mission.status}
          </span>
        </div>

        <p>{mission.subtitle}</p>

        <div className="mission-progress-label">
          <span>Readiness</span>
          <strong>{mission.progress}%</strong>
        </div>

        <div className="mission-progress">
          <span
            style={{
              width: `${mission.progress}%`,
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
              duration: 0.55,
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
              duration: 0.8,
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
              duration: 0.6,
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
              duration: 0.6,
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
              duration: 0.55,
              delay: 0.36,
              ease: "easeOut",
            }}
          >
            <button
              className="primary-action"
              type="button"
              onClick={() =>
                onNavigate("missions")
              }
            >
              <Zap size={17} />
              START A MISSION
            </button>

            <button
              className="secondary-action"
              type="button"
              onClick={() =>
                onNavigate("chat")
              }
            >
              <MessageSquare size={17} />
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
              duration: 0.55,
              delay: 0.48,
              ease: "easeOut",
            }}
          >
            <span>
              <ShieldCheck size={14} />
              NO EXTERNAL AI APIs
            </span>

            <span>
              <LockKeyhole size={14} />
              DATA STAYS LOCAL
            </span>

            <span>
              <Radar size={14} />
              OFFLINE CAPABLE
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
            duration: 1,
            delay: 0.2,
            ease: [0.22, 1, 0.36, 1],
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
              LIVE
            </span>
          </div>

          <div className="core-scene">
            <div className="scene-grid-overlay" />

            <div className="scene-depth-line scene-depth-line-1" />
            <div className="scene-depth-line scene-depth-line-2" />
            <div className="scene-depth-line scene-depth-line-3" />

            <NovaCore />

            <div className="scene-label scene-label-top-left">
              <span>ENTITY</span>
              <strong>NOVA-001</strong>
            </div>

            <div className="scene-label scene-label-top-right">
              <span>STATE</span>
              <strong>ACTIVE</strong>
            </div>

            <div className="scene-label scene-label-bottom-left">
              <span>MODE</span>
              <strong>LOCAL</strong>
            </div>

            <div className="scene-label scene-label-bottom-right">
              <span>LINK</span>
              <strong>SECURE</strong>
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
                LLAMA 3.2 · OLLAMA · GPU ACCELERATED
              </span>
            </div>

            <div className="core-footer-status">
              <span className="footer-status-pulse" />
              RUNTIME STABLE
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
        {metrics.map((metric, index) => (
          <MetricCard
            key={metric.label}
            metric={metric}
            index={index}
          />
        ))}
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
            duration: 0.7,
            ease: "easeOut",
          }}
        >
          <div className="panel-header">
            <div>
              <span className="panel-eyebrow">
                ACTIVE WORKFLOWS
              </span>

              <h2>MISSION CONTROL</h2>

              <p>
                Agent-driven industrial workflows.
              </p>
            </div>

            <button
              type="button"
              onClick={() =>
                onNavigate("missions")
              }
            >
              VIEW ALL
              <ArrowUpRight size={14} />
            </button>
          </div>

          <div className="mission-list">
            {missions.map((mission) => (
              <MissionRow
                key={mission.number}
                mission={mission}
                onNavigate={onNavigate}
              />
            ))}
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
            duration: 0.7,
            delay: 0.1,
            ease: "easeOut",
          }}
        >
          <div className="panel-header">
            <div>
              <span className="panel-eyebrow">
                SYSTEM TELEMETRY
              </span>

              <h2>RUNTIME</h2>
            </div>
          </div>

          <div className="runtime-stat-list">
            <div>
              <span>GPU utilization</span>
              <strong>80%</strong>
            </div>

            <div>
              <span>GPU memory</span>
              <strong>2.9 / 4.0 GB</strong>
            </div>

            <div>
              <span>Inference engine</span>
              <strong>Ollama</strong>
            </div>

            <div>
              <span>Model</span>
              <strong>Llama 3.2</strong>
            </div>
          </div>

          <div className="runtime-chart">
            <div className="chart-header">
              <span>
                <Activity size={14} />
                LIVE INFERENCE
              </span>

              <Gauge size={14} />
            </div>

            <div className="bars">
              {Array.from({
                length: 28,
              }).map((_, index) => (
                <span
                  key={index}
                  style={{
                    height: `${
                      18 +
                      ((index * 17) % 58)
                    }%`,
                  }}
                />
              ))}
            </div>
          </div>
        </motion.div>
      </section>

      {/* QUICK SYSTEMS */}

      <section className="quick-grid">
        {[
          {
            icon: MessageSquare,
            title: "ASK NOVA",
            text: "Start a local conversation",
            page: "chat",
          },
          {
            icon: FileSearch,
            title: "KNOWLEDGE",
            text: "Analyze confidential documents",
            page: "knowledge",
          },
          {
            icon: Upload,
            title: "INGEST",
            text: "Add enterprise knowledge",
            page: "knowledge",
          },
          {
            icon: ShieldCheck,
            title: "SECURITY",
            text: "Inspect sovereign runtime",
            page: "sovereignty",
          },
        ].map((item, index) => {
          const Icon = item.icon;

          return (
            <motion.button
              key={item.title}
              className="quick-card"
              type="button"
              onClick={() =>
                onNavigate(item.page)
              }
              initial={{
                opacity: 0,
                y: 20,
              }}
              whileInView={{
                opacity: 1,
                y: 0,
              }}
              whileHover={{
                y: -4,
              }}
              viewport={{
                once: true,
                amount: 0.15,
              }}
              transition={{
                duration: 0.55,
                delay: index * 0.1,
                ease: "easeOut",
              }}
            >
              <Icon size={18} />

              <span>{item.title}</span>

              <strong>{item.text}</strong>

              <ArrowUpRight size={15} />
            </motion.button>
          );
        })}
      </section>
    </div>
  );
}