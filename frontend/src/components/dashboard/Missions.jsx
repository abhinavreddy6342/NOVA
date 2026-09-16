import {
  Activity,
  Bot,
  Check,
  CheckCircle2,
  ChevronRight,
  Cpu,
  Database,
  FileCheck2,
  FileSearch,
  Filter,
  FolderOpen,
  Gauge,
  KeyRound,
  Layers3,
  LockKeyhole,
  MessageSquare,
  Network,
  Pause,
  Plus,
  RefreshCw,
  Search,
  Send,
  ServerCog,
  ShieldCheck,
  Sparkles,
  Target,
  Timer,
  Workflow,
  X,
  Zap,
  Paperclip,
  FileText,
  Image as ImageIcon,
  Pencil,
  Download,
  LoaderCircle,
} from "lucide-react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

const API_URL =
  "http://127.0.0.1:8001";

const MISSION_API_URL =
  `${API_URL}/api/agents/mission/run`;

const AGENT_API_URL =
  `${API_URL}/api/agents/run`;

const HISTORY_API_URL =
  `${API_URL}/api/history/conversations`;

const UPLOAD_API_URL =
  `${API_URL}/api/chat/upload`;

const STORAGE_KEY =
  "nova.missions.v2";

const MAX_FILE_SIZE =
  20 * 1024 * 1024;

const TEMPLATE_OPTIONS = [
  {
    label: "Incident Investigation",
    type: "INCIDENT INVESTIGATION",
    description:
      "Investigate an operational issue using local evidence and controlled reasoning.",
  },
  {
    label: "Predictive Maintenance",
    type: "PREDICTIVE ANALYSIS",
    description:
      "Analyze maintenance signals and identify emerging operational risks.",
  },
  {
    label: "Knowledge Review",
    type: "KNOWLEDGE REVIEW",
    description:
      "Review local documents and identify gaps, conflicts or recommendations.",
  },
  {
    label: "Quality Audit",
    type: "QUALITY ANALYSIS",
    description:
      "Analyze quality records and produce an evidence-backed assessment.",
  },
];

const STATUS_FILTERS = [
  "ALL",
  "RUNNING",
  "READY",
  "COMPLETED",
  "FAILED",
];

function getTodayLabel() {
  return new Date()
    .toLocaleDateString(
      "en-GB",
      {
        day: "2-digit",
        month: "short",
        year: "numeric",
      }
    )
    .toUpperCase();
}

function formatRuntime(
  startedAt,
  finishedAt = null
) {
  if (!startedAt) {
    return "00:00";
  }

  const end =
    finishedAt || Date.now();

  const elapsed = Math.max(
    0,
    end - startedAt
  );

  const totalSeconds =
    Math.floor(
      elapsed / 1000
    );

  const minutes =
    Math.floor(
      totalSeconds / 60
    );

  const seconds =
    totalSeconds % 60;

  return `${String(
    minutes
  ).padStart(
    2,
    "0"
  )}:${String(
    seconds
  ).padStart(
    2,
    "0"
  )}`;
}

function normalizeArtifacts(
  artifacts
) {
  if (!Array.isArray(artifacts)) {
    return [];
  }

  return artifacts.map(
    (artifact, index) => ({
      id:
        artifact?.step_id ||
        artifact?.stepId ||
        `artifact-${index}`,
      fileName:
        artifact?.file_name ||
        artifact?.fileName ||
        "Generated artifact",
      filePath:
        artifact?.file_path ||
        artifact?.filePath ||
        "",
      extension:
        artifact?.extension ||
        "",
      sizeBytes:
        Number(
          artifact?.size_bytes ||
            artifact?.sizeBytes ||
            0
        ),
      verification:
        artifact?.verification_status ||
        artifact?.verificationStatus ||
        "COMPLETED",
      available:
        artifact?.available !== false,
    })
  );
}

function formatArtifactSize(
  bytes
) {
  if (!bytes || bytes <= 0) {
    return "--";
  }

  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(
      bytes / 1024
    ).toFixed(1)} KB`;
  }

  return `${(
    bytes /
    (1024 * 1024)
  ).toFixed(1)} MB`;
}

function getPlanSteps(plan) {
  return Array.isArray(
    plan?.steps
  )
    ? plan.steps
    : [];
}

function getCompletedStepIds(
  execution
) {
  return Array.isArray(
    execution?.completed_steps
  )
    ? execution.completed_steps
    : [];
}

function getStepStatus(
  step,
  execution
) {
  const completed =
    getCompletedStepIds(
      execution
    );

  if (
    completed.includes(
      step?.id
    )
  ) {
    return "COMPLETED";
  }

  if (
    execution?.failed_steps?.includes(
      step?.id
    )
  ) {
    return "FAILED";
  }

  if (
    execution?.blocked_steps?.includes(
      step?.id
    )
  ) {
    return "BLOCKED";
  }

  const rawStatus =
    String(
      step?.status || ""
    ).toLowerCase();

  if (
    rawStatus ===
    "completed"
  ) {
    return "COMPLETED";
  }

  if (
    rawStatus ===
    "running"
  ) {
    return "RUNNING";
  }

  return "PENDING";
}

function normalizeMission(
  mission,
  index = 0
) {
  return {
    id:
      mission?.id ||
      `M-${String(
        index + 1
      ).padStart(
        3,
        "0"
      )}`,

    number:
      mission?.number ||
      String(
        index + 1
      ).padStart(
        2,
        "0"
      ),

    title:
      mission?.title ||
      "Untitled Mission",

    subtitle:
      mission?.subtitle ||
      "Sovereign intelligence workflow",

    description:
      mission?.description ||
      mission?.objective ||
      "",

    objective:
      mission?.objective ||
      "",

    type:
      mission?.type ||
      "SOVEREIGN WORKFLOW",

    priority:
      mission?.priority ||
      "MEDIUM",

    autonomy:
      mission?.autonomy ||
      "SUPERVISED",

    status:
      mission?.status ||
      "READY",

    created:
      mission?.created ||
      getTodayLabel(),

    updated:
      mission?.updated ||
      "JUST NOW",

    progress:
      Number.isFinite(
        mission?.progress
      )
        ? mission.progress
        : 0,

    steps:
      Number.isFinite(
        mission?.steps
      )
        ? mission.steps
        : 0,

    completedSteps:
      Number.isFinite(
        mission?.completedSteps
      )
        ? mission.completedSteps
        : 0,

    duration:
      mission?.duration ||
      "00:00",

    evidence:
      Number.isFinite(
        mission?.evidence
      )
        ? mission.evidence
        : Array.isArray(
              mission?.sources
            )
          ? mission.sources.length
          : 0,

    sources:
      Array.isArray(
        mission?.sources
      )
        ? mission.sources
        : [],

    attachments:
      Array.isArray(
        mission?.attachments
      )
        ? mission.attachments
        : [],

    outputs:
      Array.isArray(
        mission?.outputs
      )
        ? mission.outputs
        : [],

    confidence:
      Number.isFinite(
        mission?.confidence
      )
        ? mission.confidence
        : null,

    startedAt:
      mission?.startedAt ||
      null,

    finishedAt:
      mission?.finishedAt ||
      null,

    plan:
      mission?.plan ||
      null,

    execution:
      mission?.execution ||
      null,

    artifacts:
      Array.isArray(
        mission?.artifacts
      )
        ? mission.artifacts
        : [],

    sovereignty:
      mission?.sovereignty ||
      null,

    response:
      mission?.response ||
      "",

    error:
      mission?.error ||
      "",

    conversationId:
      mission?.conversationId ||
      mission?.conversation_id ||
      null,
  };
}

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

    return parsed.map(
      (mission, index) =>
        normalizeMission(
          mission,
          index
        )
    );
  } catch {
    return [];
  }
}

function saveStoredMissions(
  missions
) {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(
        missions
      )
    );
  } catch {
    // Ignore storage failures.
  }
}

function isSpreadsheetFile(
  file
) {
  const extension =
    String(
      file?.extension ||
        file?.name
          ?.split(".")
          .pop() ||
        ""
    )
      .replace(
        ".",
        ""
      )
      .toLowerCase();

  return [
    "xlsx",
    "xls",
    "csv",
  ].includes(
    extension
  );
}

function getFileIcon(
  file
) {
  const contentType =
    String(
      file?.content_type ||
        file?.contentType ||
        file?.type ||
        ""
    ).toLowerCase();

  if (
    contentType.startsWith(
      "image/"
    )
  ) {
    return (
      <ImageIcon
        size={16}
      />
    );
  }

  return (
    <FileText
      size={16}
    />
  );
}

function StatusBadge({
  status,
}) {
  const normalized =
    String(
      status || "READY"
    ).toUpperCase();

  const Icon =
    normalized ===
    "RUNNING"
      ? Activity
      : normalized ===
          "COMPLETED"
        ? Check
        : normalized ===
            "FAILED"
          ? X
          : normalized ===
              "READY"
            ? CheckCircle2
            : Target;

  const running =
    normalized === "RUNNING";

  const completed =
    normalized ===
    "COMPLETED";

  const failed =
    normalized === "FAILED";

  return (
    <span
      style={{
        display:
          "inline-flex",
        alignItems:
          "center",
        gap: 7,
        padding:
          "7px 10px",
        borderRadius:
          4,
        border:
          completed
            ? "1px solid rgba(123,226,242,0.30)"
            : failed
              ? "1px solid rgba(239,184,167,0.30)"
              : running
                ? "1px solid rgba(123,225,244,0.36)"
                : "1px solid rgba(255,255,255,0.10)",
        background:
          completed
            ? "rgba(94,190,211,0.08)"
            : failed
              ? "rgba(133,63,50,0.08)"
              : running
                ? "rgba(94,195,221,0.10)"
                : "rgba(255,255,255,0.025)",
        color:
          completed
            ? "#a9eff9"
            : failed
              ? "#e8b7a7"
              : running
                ? "#baf3ff"
                : "#a8b6bc",
        fontSize:
          9,
        fontWeight:
          800,
        letterSpacing:
          "0.11em",
        whiteSpace:
          "nowrap",
      }}
    >
      <Icon
        size={13}
      />
      {normalized}
    </span>
  );
}

function PriorityBadge({
  priority,
}) {
  return (
    <span
      style={{
        display:
          "inline-flex",
        alignItems:
          "center",
        gap: 7,
        color:
          priority ===
          "HIGH"
            ? "#e5baa9"
            : priority ===
                "MEDIUM"
              ? "#dac58e"
              : "#8fd9e8",
        fontSize:
          9,
        letterSpacing:
          "0.10em",
        fontWeight:
          700,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius:
            "50%",
          background:
            "currentColor",
          boxShadow:
            "0 0 11px currentColor",
        }}
      />

      {priority}
    </span>
  );
}

function MissionCard({
  mission,
  selected,
  onSelect,
}) {
  return (
    <motion.button
      type="button"
      onClick={() =>
        onSelect(
          mission
        )
      }
      whileHover={{
        y: -2,
      }}
      transition={{
        duration:
          0.18,
      }}
      style={{
        width:
          "100%",
        padding:
          0,
        textAlign:
          "left",
        color:
          "#fff",
        cursor:
          "pointer",
        border:
          selected
            ? "1px solid rgba(129,225,247,0.38)"
            : "1px solid rgba(255,255,255,0.075)",
        background:
          selected
            ? "linear-gradient(145deg, rgba(50,102,116,0.15), rgba(7,11,14,0.95))"
            : "rgba(7,10,13,0.78)",
        position:
          "relative",
        overflow:
          "hidden",
        borderRadius:
          5,
      }}
    >
      {selected && (
        <div
          style={{
            position:
              "absolute",
            left: 0,
            top: 0,
            bottom: 0,
            width: 3,
            background:
              "linear-gradient(180deg, transparent, #9beeff, transparent)",
          }}
        />
      )}

      <div
        style={{
          padding:
            "18px 19px 16px",
          borderBottom:
            "1px solid rgba(255,255,255,0.055)",
        }}
      >
        <div
          style={{
            display:
              "flex",
            justifyContent:
              "space-between",
            alignItems:
              "center",
            gap: 12,
          }}
        >
          <div
            style={{
              display:
                "flex",
              alignItems:
                "center",
              gap: 12,
            }}
          >
            <span
              style={{
                color:
                  "#66757c",
                fontFamily:
                  "monospace",
                fontSize:
                  9,
              }}
            >
              {mission.id}
            </span>

            <PriorityBadge
              priority={
                mission.priority
              }
            />
          </div>

          <StatusBadge
            status={
              mission.status
            }
          />
        </div>

        <div
          style={{
            display:
              "flex",
            alignItems:
              "flex-start",
            gap: 13,
            marginTop:
              17,
          }}
        >
          <div
            style={{
              width: 38,
              height: 38,
              display:
                "grid",
              placeItems:
                "center",
              flexShrink: 0,
              border:
                "1px solid rgba(255,255,255,0.08)",
              background:
                "rgba(255,255,255,0.02)",
              color:
                "#91e4f8",
              fontFamily:
                "monospace",
              fontSize:
                10,
            }}
          >
            {mission.number}
          </div>

          <div
            style={{
              flex: 1,
              minWidth: 0,
            }}
          >
            <div
              style={{
                display:
                  "flex",
                justifyContent:
                  "space-between",
                gap: 10,
              }}
            >
              <strong
                style={{
                  color:
                    "#edf5f7",
                  fontSize:
                    14,
                  lineHeight:
                    1.35,
                  fontWeight:
                    700,
                }}
              >
                {mission.title}
              </strong>

              <ChevronRight
                size={16}
                color="#5d6a73"
              />
            </div>

            <div
              style={{
                marginTop:
                  6,
                color:
                  "#6f7e86",
                fontSize:
                  10,
                lineHeight:
                  1.5,
              }}
            >
              {mission.type}
            </div>
          </div>
        </div>
      </div>

      <div
        style={{
          padding:
            "14px 19px 16px",
        }}
      >
        <div
          style={{
            display:
              "flex",
            justifyContent:
              "space-between",
            color:
              "#65737b",
            fontSize:
              8,
            letterSpacing:
              "0.13em",
          }}
        >
          <span>
            EXECUTION
          </span>

          <span
            style={{
              fontFamily:
                "monospace",
            }}
          >
            {mission.completedSteps}/
            {mission.steps || 0}
          </span>
        </div>

        <div
          style={{
            height: 4,
            marginTop:
              8,
            background:
              "rgba(255,255,255,0.06)",
          }}
        >
          <motion.div
            animate={{
              width: `${Math.min(
                100,
                Math.max(
                  0,
                  mission.progress
                )
              )}%`,
            }}
            transition={{
              duration:
                0.5,
            }}
            style={{
              height:
                "100%",
              background:
                "linear-gradient(90deg, #4b8fa3, #9ce9fb)",
            }}
          />
        </div>

        <div
          style={{
            display:
              "flex",
            alignItems:
              "center",
            gap: 6,
            marginTop:
              10,
            color:
              "#5c6a72",
            fontSize:
              9,
          }}
        >
          <FileSearch
            size={12}
          />

          {mission.evidence || 0} evidence file
          {mission.evidence ===
          1
            ? ""
            : "s"}
        </div>
      </div>
    </motion.button>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
}) {
  return (
    <div
      style={{
        minHeight:
          78,
        padding:
          "14px 16px",
        border:
          "1px solid rgba(255,255,255,0.07)",
        background:
          "rgba(255,255,255,0.018)",
        borderRadius:
          4,
      }}
    >
      <div
        style={{
          display:
            "flex",
          justifyContent:
            "space-between",
          alignItems:
            "center",
          gap: 10,
        }}
      >
        <span
          style={{
            color:
              "#65737a",
            fontSize:
              8,
            letterSpacing:
              "0.12em",
            fontWeight:
              700,
          }}
        >
          {label}
        </span>

        <Icon
          size={15}
          color="#82dced"
        />
      </div>

      <strong
        style={{
          display:
            "block",
          marginTop:
            10,
          color:
            "#daf2f6",
          fontFamily:
            "monospace",
          fontSize:
            18,
          lineHeight:
            1,
        }}
      >
        {value}
      </strong>
    </div>
  );
}

function StepRow({
  step,
  execution,
  index,
}) {
  const status =
    getStepStatus(
      step,
      execution
    );

  const completed =
    status ===
    "COMPLETED";

  const running =
    status ===
    "RUNNING";

  const failed =
    status ===
      "FAILED" ||
    status ===
      "BLOCKED";

  return (
    <div
      style={{
        display:
          "flex",
        gap: 12,
      }}
    >
      <div
        style={{
          width: 30,
          height: 30,
          display:
            "grid",
          placeItems:
            "center",
          flexShrink: 0,
          border:
            completed
              ? "1px solid rgba(125,225,243,0.34)"
              : failed
                ? "1px solid rgba(239,184,167,0.25)"
                : running
                  ? "1px solid rgba(130,225,247,0.42)"
                  : "1px solid rgba(255,255,255,0.08)",
          background:
            completed
              ? "rgba(93,190,210,0.08)"
              : failed
                ? "rgba(125,59,47,0.07)"
                : running
                  ? "rgba(89,184,211,0.08)"
                  : "rgba(255,255,255,0.018)",
          color:
            completed
              ? "#8de5f4"
              : failed
                ? "#e0afa0"
                : running
                  ? "#a7efff"
                  : "#65737b",
          fontFamily:
            "monospace",
          fontSize:
            9,
          borderRadius:
            4,
        }}
      >
        {completed
          ? "✓"
          : failed
            ? "!"
            : String(
                index + 1
              ).padStart(
                2,
                "0"
              )}
      </div>

      <div
        style={{
          flex: 1,
          minWidth: 0,
          paddingBottom:
            17,
        }}
      >
        <div
          style={{
            display:
              "flex",
            justifyContent:
              "space-between",
            alignItems:
              "center",
            gap: 12,
          }}
        >
          <strong
            style={{
              color:
                completed ||
                running
                  ? "#dcecef"
                  : "#7f8c92",
              fontSize:
                11,
              lineHeight:
                1.4,
            }}
          >
            {step.title ||
              step.description ||
              `Step ${
                index + 1
              }`}
          </strong>

          <span
            style={{
              flexShrink: 0,
              color:
                completed
                  ? "#83dfe9"
                  : failed
                    ? "#dfad9e"
                    : running
                      ? "#a2ecfb"
                      : "#54626a",
              fontFamily:
                "monospace",
              fontSize:
                8,
              letterSpacing:
                "0.08em",
            }}
          >
            {status}
          </span>
        </div>

        <div
          style={{
            marginTop:
              5,
            color:
              "#65747c",
            fontSize:
              9,
            lineHeight:
              1.55,
          }}
        >
          {step.tool ||
            "LOCAL EXECUTION STEP"}
        </div>

        {(
          step.description ||
          step.expected_output
        ) && (
          <div
            style={{
              marginTop:
                5,
              color:
                "#516069",
              fontSize:
                8,
              lineHeight:
                1.5,
            }}
          >
            {step.description ||
              step.expected_output}
          </div>
        )}
      </div>
    </div>
  );
}

function MissionMarkdown({
  content,
}) {
  return (
    <div
      style={{
        color:
          "#c5d9de",
        fontSize:
          11,
        lineHeight:
          1.7,
      }}
    >
      <ReactMarkdown
        components={{
          p: ({
            children,
          }) => (
            <p
              style={{
                margin:
                  "0 0 10px",
              }}
            >
              {children}
            </p>
          ),

          strong: ({
            children,
          }) => (
            <strong
              style={{
                color:
                  "#e4f5f8",
              }}
            >
              {children}
            </strong>
          ),

          ul: ({
            children,
          }) => (
            <ul
              style={{
                paddingLeft:
                  20,
                margin:
                  "8px 0 12px",
              }}
            >
              {children}
            </ul>
          ),

          ol: ({
            children,
          }) => (
            <ol
              style={{
                paddingLeft:
                  20,
                margin:
                  "8px 0 12px",
              }}
            >
              {children}
            </ol>
          ),

          li: ({
            children,
          }) => (
            <li>
              {children}
            </li>
          ),

          code: ({
            children,
          }) => (
            <code
              style={{
                padding:
                  "2px 5px",
                borderRadius:
                  3,
                background:
                  "rgba(255,255,255,0.05)",
                color:
                  "#b8edf6",
                fontFamily:
                  "monospace",
              }}
            >
              {children}
            </code>
          ),
        }}
      >
        {content || ""}
      </ReactMarkdown>
    </div>
  );
}

function mapMissionChatMessage(
  message
) {
  return {
    id:
      message?.id ||
      `mission-chat-${Date.now()}-${Math.random()}`,

    role:
      message?.role ===
      "user"
        ? "user"
        : "assistant",

    content:
      message?.content ||
      "",

    createdAt:
      message?.created_at
        ? new Date(
            message.created_at
          )
        : new Date(),

    attachments:
      Array.isArray(
        message?.attachments
      )
        ? message.attachments
        : [],

    agent:
      message?.agent ||
      null,
  };
}

export default function Missions() {
  const [
    missions,
    setMissions,
  ] = useState(
    loadStoredMissions
  );

  const [
    selectedMissionId,
    setSelectedMissionId,
  ] = useState(
    null
  );

  const [
    searchQuery,
    setSearchQuery,
  ] = useState("");

  const [
    activeFilter,
    setActiveFilter,
  ] = useState(
    "ALL"
  );

  const [
    showNewMission,
    setShowNewMission,
  ] = useState(
    false
  );

  const [
    showEditMission,
    setShowEditMission,
  ] = useState(
    false
  );

  const [
    selectedTemplate,
    setSelectedTemplate,
  ] = useState(
    "Incident Investigation"
  );

  const [
    newMissionTitle,
    setNewMissionTitle,
  ] = useState("");

  const [
    newMissionObjective,
    setNewMissionObjective,
  ] = useState("");

  const [
    newMissionPriority,
    setNewMissionPriority,
  ] = useState(
    "MEDIUM"
  );

  const [
    newMissionAutonomy,
    setNewMissionAutonomy,
  ] = useState(
    "SUPERVISED"
  );

  const [
    newMissionFiles,
    setNewMissionFiles,
  ] = useState([]);

  const [
    editMissionTitle,
    setEditMissionTitle,
  ] = useState("");

  const [
    editMissionObjective,
    setEditMissionObjective,
  ] = useState("");

  const [
    editMissionPriority,
    setEditMissionPriority,
  ] = useState(
    "MEDIUM"
  );

  const [
    editMissionAutonomy,
    setEditMissionAutonomy,
  ] = useState(
    "SUPERVISED"
  );

  const [
    editMissionFiles,
    setEditMissionFiles,
  ] = useState([]);

  const [
    launchingMission,
    setLaunchingMission,
  ] = useState(false);

  const [
    uploadingMissionFiles,
    setUploadingMissionFiles,
  ] = useState(false);

  const [
    savingMissionEdit,
    setSavingMissionEdit,
  ] = useState(false);

  const [
    missionError,
    setMissionError,
  ] = useState("");

  const [
    runtimeTick,
    setRuntimeTick,
  ] = useState(0);

  const [
    missionChatMessages,
    setMissionChatMessages,
  ] = useState([]);

  const [
    missionChatInput,
    setMissionChatInput,
  ] = useState("");

  const [
    loadingMissionChat,
    setLoadingMissionChat,
  ] = useState(false);

  const [
    sendingMissionChat,
    setSendingMissionChat,
  ] = useState(false);

  const [
    missionChatError,
    setMissionChatError,
  ] = useState("");

  const missionFileInputRef =
    useRef(null);

  const editFileInputRef =
    useRef(null);

  const missionChatEndRef =
    useRef(null);

  useEffect(() => {
    saveStoredMissions(
      missions
    );
  }, [missions]);

  useEffect(() => {
    const running =
      missions.some(
        (mission) =>
          mission.status ===
          "RUNNING"
      );

    if (!running) {
      return undefined;
    }

    const timer =
      window.setInterval(
        () =>
          setRuntimeTick(
            (value) =>
              value + 1
          ),
        1000
      );

    return () =>
      window.clearInterval(
        timer
      );
  }, [missions]);

  const selectedMission =
    missions.find(
      (mission) =>
        mission.id ===
        selectedMissionId
    ) || null;

  useEffect(() => {
    let cancelled = false;

    const loadMissionConversation =
      async () => {
        if (
          !selectedMission?.conversationId
        ) {
          setMissionChatMessages(
            []
          );
          return;
        }

        setLoadingMissionChat(
          true
        );

        setMissionChatError(
          ""
        );

        try {
          const response =
            await fetch(
              `${HISTORY_API_URL}/${selectedMission.conversationId}`
            );

          if (!response.ok) {
            throw new Error(
              "Unable to load mission conversation."
            );
          }

          const data =
            await response.json();

          if (cancelled) {
            return;
          }

          const messages =
            Array.isArray(
              data?.messages
            )
              ? data.messages.map(
                  mapMissionChatMessage
                )
              : [];

          setMissionChatMessages(
            messages
          );
        } catch (
          error
        ) {
          if (
            cancelled
          ) {
            return;
          }

          setMissionChatError(
            error?.message ||
              "Unable to load mission conversation."
          );
        } finally {
          if (
            !cancelled
          ) {
            setLoadingMissionChat(
              false
            );
          }
        }
      };

    loadMissionConversation();

    return () => {
      cancelled = true;
    };
  }, [
    selectedMission?.conversationId,
  ]);

  useEffect(() => {
    missionChatEndRef.current?.scrollIntoView(
      {
        behavior:
          "smooth",
        block:
          "end",
      }
    );
  }, [
    missionChatMessages,
    sendingMissionChat,
  ]);

  const filteredMissions =
    useMemo(() => {
      const query =
        searchQuery
          .trim()
          .toLowerCase();

      return missions.filter(
        (mission) => {
          const statusMatch =
            activeFilter ===
              "ALL" ||
            mission.status ===
              activeFilter;

          const searchMatch =
            !query ||
            mission.id
              .toLowerCase()
              .includes(
                query
              ) ||
            mission.title
              .toLowerCase()
              .includes(
                query
              ) ||
            mission.type
              .toLowerCase()
              .includes(
                query
              );

          return (
            statusMatch &&
            searchMatch
          );
        }
      );
    }, [
      missions,
      searchQuery,
      activeFilter,
    ]);

  const runningCount =
    missions.filter(
      (mission) =>
        mission.status ===
        "RUNNING"
    ).length;

  const readyCount =
    missions.filter(
      (mission) =>
        mission.status ===
        "READY"
    ).length;

  const completedCount =
    missions.filter(
      (mission) =>
        mission.status ===
        "COMPLETED"
    ).length;

  const failedCount =
    missions.filter(
      (mission) =>
        mission.status ===
        "FAILED"
    ).length;

  const nextMissionId =
    () => {
      const ids =
        missions
          .map(
            (mission) =>
              Number(
                String(
                  mission.id
                ).replace(
                  "M-",
                  ""
                )
              )
          )
          .filter(
            (
              value
            ) =>
              Number.isFinite(
                value
              )
          );

      return ids.length
        ? Math.max(
            ...ids
          ) + 1
        : 1;
    };

  const updateMission = (
    missionId,
    updates
  ) => {
    setMissions(
      (current) =>
        current.map(
          (mission) =>
            mission.id ===
            missionId
              ? {
                  ...mission,
                  ...updates,
                }
              : mission
        )
    );
  };

  const uploadMissionFiles =
    async (
      browserFiles
    ) => {
      if (
        !browserFiles.length
      ) {
        return [];
      }

      setUploadingMissionFiles(
        true
      );

      try {
        const uploaded =
          [];

        for (
          const file of browserFiles
        ) {
          const formData =
            new FormData();

          formData.append(
            "file",
            file
          );

          const response =
            await fetch(
              UPLOAD_API_URL,
              {
                method:
                  "POST",
                body:
                  formData,
              }
            );

          let payload =
            null;

          try {
            payload =
              await response.json();
          } catch {
            payload =
              null;
          }

          if (
            !response.ok
          ) {
            throw new Error(
              payload?.detail ||
                `Failed to upload ${file.name}.`
            );
          }

          const uploadedFile =
            payload?.file;

          if (
            !uploadedFile?.file_id
          ) {
            throw new Error(
              `Backend did not return a file ID for ${file.name}.`
            );
          }

          uploaded.push({
            file_id:
              uploadedFile.file_id,

            filename:
              uploadedFile.filename ||
              file.name,

            content_type:
              uploadedFile.content_type ||
              file.type ||
              "",

            extension:
              uploadedFile.extension ||
              (
                file.name.includes(
                  "."
                )
                  ? `.${file.name
                      .split(".")
                      .pop()
                      .toLowerCase()}`
                  : ""
              ),

            file_type:
              uploadedFile.file_type ||
              "",

            size:
              Number(
                uploadedFile.size ||
                  file.size ||
                  0
              ),
          });
        }

        return uploaded;
      } finally {
        setUploadingMissionFiles(
          false
        );
      }
    };

  const handleMissionFileSelection =
    async (
      event
    ) => {
      const files =
        Array.from(
          event.target.files ||
            []
        );

      event.target.value = "";

      if (!files.length) {
        return;
      }

      setMissionError("");

      const oversized =
        files.filter(
          (file) =>
            file.size >
            MAX_FILE_SIZE
        );

      if (
        oversized.length
      ) {
        setMissionError(
          "ONE OR MORE FILES EXCEED THE 20 MB LIMIT."
        );
      }

      const validFiles =
        files.filter(
          (file) =>
            file.size <=
            MAX_FILE_SIZE
        );

      if (!validFiles.length) {
        return;
      }

      try {
        const existingKeys =
          new Set(
            newMissionFiles.map(
              (file) =>
                `${file.filename}-${file.size}`
            )
          );

        const uniqueFiles =
          validFiles.filter(
            (file) =>
              !existingKeys.has(
                `${file.name}-${file.size}`
              )
          );

        if (!uniqueFiles.length) {
          return;
        }

        const uploaded =
          await uploadMissionFiles(
            uniqueFiles
          );

        setNewMissionFiles(
          (current) => [
            ...current,
            ...uploaded,
          ]
        );
      } catch (
        error
      ) {
        setMissionError(
          error?.message ||
            "Unable to upload mission evidence."
        );
      }
    };

  const handleEditFileSelection =
    async (
      event
    ) => {
      const files =
        Array.from(
          event.target.files ||
            []
        );

      event.target.value = "";

      if (!files.length) {
        return;
      }

      setMissionError("");

      const oversized =
        files.filter(
          (file) =>
            file.size >
            MAX_FILE_SIZE
        );

      if (
        oversized.length
      ) {
        setMissionError(
          "ONE OR MORE FILES EXCEED THE 20 MB LIMIT."
        );
      }

      const validFiles =
        files.filter(
          (file) =>
            file.size <=
            MAX_FILE_SIZE
        );

      if (!validFiles.length) {
        return;
      }

      try {
        const existingKeys =
          new Set(
            editMissionFiles.map(
              (file) =>
                `${file.filename}-${file.size}`
            )
          );

        const uniqueFiles =
          validFiles.filter(
            (file) =>
              !existingKeys.has(
                `${file.name}-${file.size}`
              )
          );

        if (!uniqueFiles.length) {
          return;
        }

        const uploaded =
          await uploadMissionFiles(
            uniqueFiles
          );

        setEditMissionFiles(
          (current) => [
            ...current,
            ...uploaded,
          ]
        );
      } catch (
        error
      ) {
        setMissionError(
          error?.message ||
            "Unable to upload mission evidence."
        );
      }
    };

  const removeMissionFile =
    (fileToRemove) => {
      setNewMissionFiles(
        (current) =>
          current.filter(
            (file) =>
              file.file_id !==
              fileToRemove.file_id
          )
      );
    };

  const removeEditMissionFile =
    (fileToRemove) => {
      setEditMissionFiles(
        (current) =>
          current.filter(
            (file) =>
              file.file_id !==
              fileToRemove.file_id
          )
      );
    };

  const resetMissionCreationForm =
    () => {
      setNewMissionTitle(
        ""
      );
      setNewMissionObjective(
        ""
      );
      setNewMissionPriority(
        "MEDIUM"
      );
      setNewMissionAutonomy(
        "SUPERVISED"
      );
      setSelectedTemplate(
        "Incident Investigation"
      );
      setNewMissionFiles(
        []
      );
    };

  const openEditMission =
    () => {
      if (
        !selectedMission ||
        selectedMission.status ===
          "RUNNING"
      ) {
        return;
      }

      setEditMissionTitle(
        selectedMission.title
      );

      setEditMissionObjective(
        selectedMission.objective
      );

      setEditMissionPriority(
        selectedMission.priority
      );

      setEditMissionAutonomy(
        selectedMission.autonomy
      );

      setEditMissionFiles(
        selectedMission.attachments.map(
          (file) => ({
            ...file,
          })
        )
      );

      setMissionError("");
      setShowEditMission(
        true
      );
    };

  const saveMissionEdit =
    async () => {
      if (
        !selectedMission ||
        savingMissionEdit
      ) {
        return;
      }

      const title =
        editMissionTitle.trim();

      const objective =
        editMissionObjective.trim();

      if (
        !title ||
        !objective
      ) {
        setMissionError(
          "MISSION NAME AND OBJECTIVE ARE REQUIRED."
        );
        return;
      }

      if (
        editMissionFiles.length ===
        0
      ) {
        setMissionError(
          "A REAL EVIDENCE PACKAGE IS REQUIRED."
        );
        return;
      }

      setSavingMissionEdit(
        true
      );
      setMissionError("");

      try {
        const changed =
          title !==
            selectedMission.title ||
          objective !==
            selectedMission.objective ||
          editMissionPriority !==
            selectedMission.priority ||
          editMissionAutonomy !==
            selectedMission.autonomy ||
          JSON.stringify(
            editMissionFiles
          ) !==
            JSON.stringify(
              selectedMission.attachments
            );

        updateMission(
          selectedMission.id,
          {
            title,
            objective,
            description:
              objective,
            priority:
              editMissionPriority,
            autonomy:
              editMissionAutonomy,
            attachments:
              editMissionFiles,
            sources:
              editMissionFiles.map(
                (file) =>
                  file.filename
              ),
            evidence:
              editMissionFiles.length,

            ...(changed
              ? {
                  status:
                    "READY",
                  progress:
                    0,
                  steps:
                    0,
                  completedSteps:
                    0,
                  duration:
                    "00:00",
                  startedAt:
                    null,
                  finishedAt:
                    null,
                  plan:
                    null,
                  execution:
                    null,
                  artifacts:
                    [],
                  sovereignty:
                    null,
                  response:
                    "",
                  outputs:
                    [],
                  error:
                    "",
                }
              : {}),
          }
        );

        setShowEditMission(
          false
        );
      } finally {
        setSavingMissionEdit(
          false
        );
      }
    };

  const createMission =
    () => {
      const title =
        newMissionTitle.trim();

      const objective =
        newMissionObjective.trim();

      if (
        !title ||
        !objective
      ) {
        setMissionError(
          "MISSION NAME AND OBJECTIVE ARE REQUIRED."
        );
        return;
      }

      if (
        newMissionFiles.length ===
        0
      ) {
        setMissionError(
          "ADD AT LEAST ONE REAL EVIDENCE FILE BEFORE INITIALIZING THE MISSION."
        );
        return;
      }

      const template =
        TEMPLATE_OPTIONS.find(
          (item) =>
            item.label ===
            selectedTemplate
        ) ||
        TEMPLATE_OPTIONS[0];

      const nextId =
        nextMissionId();

      const normalizedFiles =
        newMissionFiles.map(
          (file) => ({
            file_id:
              file.file_id,
            filename:
              file.filename,
            content_type:
              file.content_type ||
              "",
            extension:
              file.extension ||
              "",
            file_type:
              file.file_type ||
              "",
            size:
              Number(
                file.size ||
                  0
              ),
          })
        );

      const mission =
        normalizeMission({
          id: `M-${String(
            nextId
          ).padStart(
            3,
            "0"
          )}`,
          number: String(
            nextId
          ).padStart(
            2,
            "0"
          ),
          title,
          subtitle:
            "Sovereign intelligence workflow",
          description:
            objective,
          objective,
          type:
            template.type,
          priority:
            newMissionPriority,
          autonomy:
            newMissionAutonomy,
          status:
            "READY",
          progress: 0,
          steps: 0,
          completedSteps: 0,
          duration:
            "00:00",
          evidence:
            normalizedFiles.length,
          sources:
            normalizedFiles.map(
              (file) =>
                file.filename
            ),
          attachments:
            normalizedFiles,
          outputs: [],
          confidence:
            null,
          created:
            getTodayLabel(),
          updated:
            "JUST NOW",
          conversationId:
            null,
        });

      setMissions(
        (current) => [
          mission,
          ...current,
        ]
      );

      setSelectedMissionId(
        mission.id
      );

      resetMissionCreationForm();

      setShowNewMission(
        false
      );

      setMissionError("");
    };

  const launchMission =
    async () => {
      if (
        !selectedMission ||
        launchingMission
      ) {
        return;
      }

      if (
        !selectedMission.attachments?.length
      ) {
        setMissionError(
          "THIS MISSION HAS NO EVIDENCE PACKAGE."
        );
        return;
      }

      const startedAt =
        Date.now();

      setMissionError(
        ""
      );

      setMissionChatError(
        ""
      );

      setLaunchingMission(
        true
      );

      updateMission(
        selectedMission.id,
        {
          status:
            "RUNNING",
          progress: 1,
          completedSteps: 0,
          startedAt,
          finishedAt:
            null,
          duration:
            "00:00",
          error: "",
          plan:
            null,
          execution:
            null,
          artifacts: [],
          sovereignty:
            null,
          response:
            "",
        }
      );

      try {
        const response =
          await fetch(
            MISSION_API_URL,
            {
              method:
                "POST",
              headers: {
                "Content-Type":
                  "application/json",
              },
              body:
                JSON.stringify({
                  mission_id:
                    selectedMission.id,
                  title:
                    selectedMission.title,
                  objective:
                    selectedMission.objective,
                  context: {
                    source:
                      "nova-mission-control",
                    mission_type:
                      selectedMission.type,
                    priority:
                      selectedMission.priority,
                    autonomy:
                      selectedMission.autonomy,
                    attachments:
                      selectedMission.attachments ||
                      [],
                    mission_sources:
                      selectedMission.sources ||
                      [],
                  },
                  auto_confirm:
                    true,
                }),
            }
          );

        let payload =
          null;

        try {
          payload =
            await response.json();
        } catch {
          payload =
            null;
        }

        if (
          !response.ok
        ) {
          throw new Error(
            payload?.detail ||
              `Mission request failed with HTTP ${response.status}.`
          );
        }

        if (!payload) {
          throw new Error(
            "Mission backend returned an empty response."
          );
        }

        const plan =
          payload.plan ||
          null;

        const execution =
          payload.execution ||
          null;

        const artifacts =
          normalizeArtifacts(
            payload.artifacts
          );

        const sovereignty =
          payload.sovereignty ||
          null;

        const planSteps =
          getPlanSteps(
            plan
          );

        const completedSteps =
          getCompletedStepIds(
            execution
          ).length;

        const stepCount =
          planSteps.length ||
          completedSteps;

        const returnedStatus =
          String(
            payload.status ||
              execution?.status ||
              "COMPLETED"
          ).toUpperCase();

        const normalizedStatus =
          returnedStatus ===
              "COMPLETED" ||
          returnedStatus ===
              "COMPLETE" ||
          returnedStatus ===
              "SUCCESS" ||
          returnedStatus ===
              "SUCCESSFUL"
            ? "COMPLETED"
            : returnedStatus ===
                "FAILED"
              ? "FAILED"
              : returnedStatus ===
                  "BLOCKED"
                ? "FAILED"
                : "RUNNING";

        const progress =
          normalizedStatus ===
          "COMPLETED"
            ? 100
            : stepCount > 0
              ? Math.round(
                  (completedSteps /
                    stepCount) *
                    100
                )
              : 1;

        const finishedAt =
          Date.now();

        const nextMission =
          normalizeMission({
            ...selectedMission,

            status:
              normalizedStatus,

            progress,

            steps:
              stepCount,

            completedSteps,

            duration:
              formatRuntime(
                startedAt,
                finishedAt
              ),

            finishedAt:
              normalizedStatus ===
              "RUNNING"
                ? null
                : finishedAt,

            updated:
              "JUST NOW",

            plan,

            execution,

            artifacts,

            sovereignty,

            response:
              payload.response ||
              "",

            outputs:
              artifacts.map(
                (artifact) =>
                  artifact.fileName
              ),

            evidence:
              selectedMission
                .attachments
                ?.length ||
              0,

            error: "",

            conversationId:
              payload.conversation_id ||
              selectedMission.conversationId ||
              null,
          });

        updateMission(
          selectedMission.id,
          nextMission
        );

        setSelectedMissionId(
          nextMission.id
        );
      } catch (
        error
      ) {
        const message =
          error?.message ||
          "Unable to execute this mission.";

        const finishedAt =
          Date.now();

        setMissionError(
          message
        );

        updateMission(
          selectedMission.id,
          {
            status:
              "FAILED",
            updated:
              "JUST NOW",
            finishedAt,
            duration:
              formatRuntime(
                startedAt,
                finishedAt
              ),
            error:
              message,
          }
        );
      } finally {
        setLaunchingMission(
          false
        );
      }
    };

  const sendMissionChat =
    async () => {
      const message =
        missionChatInput.trim();

      if (
        !selectedMission ||
        !selectedMission.conversationId ||
        !message ||
        sendingMissionChat
      ) {
        return;
      }

      setMissionChatError(
        ""
      );

      setSendingMissionChat(
        true
      );

      const localUserMessage =
        {
          id: `local-user-${Date.now()}`,
          role: "user",
          content:
            message,
          createdAt:
            new Date(),
          attachments: [],
          agent:
            null,
        };

      setMissionChatMessages(
        (current) => [
          ...current,
          localUserMessage,
        ]
      );

      setMissionChatInput(
        ""
      );

      try {
        const historyForAgent =
          missionChatMessages.map(
            (item) => ({
              role:
                item.role,
              content:
                item.content,
            })
          );

        historyForAgent.push({
          role:
            "user",
          content:
            message,
        });

        const response =
          await fetch(
            AGENT_API_URL,
            {
              method:
                "POST",
              headers: {
                "Content-Type":
                  "application/json",
              },
              body:
                JSON.stringify({
                  objective:
                    `MISSION FOLLOW-UP:\n${message}`,

                  context: {
                    source:
                      "nova-mission-chat",

                    conversation_id:
                      selectedMission.conversationId,

                    mission_id:
                      selectedMission.id,

                    mission: {
                      mission_id:
                        selectedMission.id,

                      title:
                        selectedMission.title,

                      objective:
                        selectedMission.objective,

                      mission_type:
                        selectedMission.type,

                      priority:
                        selectedMission.priority,

                      autonomy:
                        selectedMission.autonomy,
                    },

                    attachments:
                      selectedMission.attachments ||
                      [],

                    mission_sources:
                      selectedMission.sources ||
                      [],

                    mission_execution:
                      selectedMission.execution ||
                      null,

                    mission_plan:
                      selectedMission.plan ||
                      null,

                    last_mission_result:
                      selectedMission.response ||
                      "",

                    conversation_history:
                      historyForAgent,
                  },

                  auto_confirm:
                    true,
                }),
            }
          );

        let payload =
          null;

        try {
          payload =
            await response.json();
        } catch {
          payload =
            null;
        }

        if (
          !response.ok
        ) {
          throw new Error(
            payload?.detail ||
              "Mission conversation request failed."
          );
        }

        const responseText =
          String(
            payload?.response ||
              ""
          ).trim();

        if (!responseText) {
          throw new Error(
            "NOVA returned an empty mission response."
          );
        }

        const assistantMessage =
          {
            id: `local-assistant-${Date.now()}`,

            role:
              "assistant",

            content:
              responseText,

            createdAt:
              new Date(),

            attachments:
              [],

            agent: {
              plan:
                payload?.plan ||
                null,

              execution:
                payload?.execution ||
                null,

              artifacts:
                normalizeArtifacts(
                  payload?.artifacts
                ),
            },
          };

        setMissionChatMessages(
          (current) => [
            ...current,
            assistantMessage,
          ]
        );

        if (
          payload?.conversation_id &&
          payload.conversation_id !==
            selectedMission.conversationId
        ) {
          updateMission(
            selectedMission.id,
            {
              conversationId:
                payload.conversation_id,
            }
          );
        }

        if (
          Array.isArray(
            payload?.artifacts
          ) &&
          payload.artifacts.length
        ) {
          const artifacts =
            normalizeArtifacts(
              payload.artifacts
            );

          updateMission(
            selectedMission.id,
            {
              artifacts,
              outputs:
                artifacts.map(
                  (artifact) =>
                    artifact.fileName
                ),
              response:
                responseText,
            }
          );
        }
      } catch (
        error
      ) {
        setMissionChatError(
          error?.message ||
            "Unable to continue the mission conversation."
        );
      } finally {
        setSendingMissionChat(
          false
        );
      }
    };

  const handleMissionChatKeyDown =
    (event) => {
      if (
        event.key ===
          "Enter" &&
        !event.shiftKey
      ) {
        event.preventDefault();
        sendMissionChat();
      }
    };

  const clearMissionState =
    () => {
      if (
        !selectedMission
      ) {
        return;
      }

      updateMission(
        selectedMission.id,
        {
          status:
            "READY",
          progress: 0,
          completedSteps: 0,
          duration:
            "00:00",
          startedAt:
            null,
          finishedAt:
            null,
          plan:
            null,
          execution:
            null,
          artifacts: [],
          sovereignty:
            null,
          response:
            "",
          error:
            "",
          outputs: [],
          steps: 0,
        }
      );

      setMissionError(
        ""
      );
    };

  const togglePauseDisplay =
    () => {
      if (
        !selectedMission ||
        selectedMission.status !==
          "RUNNING"
      ) {
        return;
      }

      setMissionError(
        "Pause is not exposed by the current synchronous mission endpoint."
      );
    };

  const planSteps =
    getPlanSteps(
      selectedMission?.plan
    );

  const runtime =
    selectedMission?.status ===
      "RUNNING" &&
    selectedMission?.startedAt
      ? formatRuntime(
          selectedMission.startedAt
        )
      : selectedMission?.duration ||
        "00:00";

  const canLaunch =
    Boolean(
      selectedMission?.attachments
        ?.length
    ) &&
    !launchingMission &&
    selectedMission?.status !==
      "RUNNING";

  return (
    <>
      <div
        style={{
          minHeight:
            "calc(100vh - 70px)",
          padding:
            "34px clamp(22px, 4vw, 58px) 60px",
          color:
            "#edf5f7",
        }}
      >
        <div
          style={{
            width:
              "100%",
            maxWidth:
              1760,
            margin:
              "0 auto",
          }}
        >
          <motion.div
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
                0.45,
            }}
          >
            <div
              style={{
                display:
                  "flex",
                justifyContent:
                  "space-between",
                alignItems:
                  "flex-end",
                gap: 28,
                flexWrap:
                  "wrap",
              }}
            >
              <div
                style={{
                  maxWidth:
                    920,
                }}
              >
                <div
                  style={{
                    display:
                      "flex",
                    alignItems:
                      "center",
                    gap: 9,
                    color:
                      "#6e7b83",
                    fontFamily:
                      "monospace",
                    fontSize:
                      10,
                    letterSpacing:
                      "0.17em",
                  }}
                >
                  <span
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius:
                        "50%",
                      background:
                        "#8ce8fa",
                      boxShadow:
                        "0 0 14px rgba(140,232,250,0.75)",
                    }}
                  />

                  NOVA MISSION CONTROL // AGENT ORCHESTRATION
                </div>

                <h1
                  style={{
                    margin:
                      "14px 0 0",
                    fontSize:
                      "clamp(38px, 5vw, 68px)",
                    lineHeight:
                      0.98,
                    letterSpacing:
                      "-0.048em",
                    fontWeight:
                      800,
                  }}
                >
                  MISSION{" "}
                  <span
                    style={{
                      color:
                        "#87e2f7",
                    }}
                  >
                    CONTROL
                  </span>
                </h1>

                <p
                  style={{
                    maxWidth:
                      820,
                    margin:
                      "16px 0 0",
                    color:
                      "#75828a",
                    fontSize:
                      13,
                    lineHeight:
                      1.7,
                  }}
                >
                  Create, execute and continue real sovereign
                  workflows from user-defined objectives and
                  real evidence packages.
                </p>
              </div>

              <div
                style={{
                  display:
                    "flex",
                  alignItems:
                    "center",
                  gap: 11,
                  padding:
                    "13px 16px",
                  minWidth:
                    235,
                  border:
                    "1px solid rgba(117,221,242,0.16)",
                  background:
                    "rgba(64,147,169,0.045)",
                  borderRadius:
                    5,
                }}
              >
                <LockKeyhole
                  size={17}
                  color="#88e4fa"
                />

                <div>
                  <div
                    style={{
                      color:
                        "#7d8c94",
                      fontSize:
                        8,
                      letterSpacing:
                        "0.14em",
                    }}
                  >
                    EXECUTION BOUNDARY
                  </div>

                  <strong
                    style={{
                      display:
                        "block",
                      marginTop:
                        5,
                      color:
                        "#d9f8fe",
                      fontFamily:
                        "monospace",
                      fontSize:
                        10,
                    }}
                  >
                    LOCAL / AIR-GAPPED
                  </strong>
                </div>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{
              opacity: 0,
              y: 16,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            transition={{
              duration:
                0.45,
              delay:
                0.07,
            }}
            style={{
              display:
                "grid",
              gridTemplateColumns:
                "repeat(4, minmax(0, 1fr))",
              gap: 10,
              marginTop:
                30,
            }}
          >
            <MetricCard
              icon={
                Layers3
              }
              label="TOTAL MISSIONS"
              value={
                missions.length
              }
            />

            <MetricCard
              icon={
                Activity
              }
              label="ACTIVE NOW"
              value={
                runningCount
              }
            />

            <MetricCard
              icon={
                CheckCircle2
              }
              label="READY"
              value={
                readyCount
              }
            />

            <MetricCard
              icon={
                FileCheck2
              }
              label="COMPLETED"
              value={
                completedCount
              }
            />
          </motion.div>

          {missionError && (
            <motion.div
              initial={{
                opacity: 0,
                y: -5,
              }}
              animate={{
                opacity: 1,
                y: 0,
              }}
              style={{
                marginTop:
                  14,
                padding:
                  "13px 15px",
                border:
                  "1px solid rgba(239,184,167,0.25)",
                background:
                  "rgba(120,52,39,0.08)",
                borderRadius:
                  4,
              }}
            >
              <div
                style={{
                  color:
                    "#e6b2a2",
                  fontFamily:
                    "monospace",
                  fontSize:
                    9,
                  letterSpacing:
                    "0.11em",
                }}
              >
                MISSION CONTROL / MESSAGE
              </div>

              <div
                style={{
                  marginTop:
                    5,
                  color:
                    "#b3948b",
                  fontSize:
                    10,
                  lineHeight:
                    1.5,
                }}
              >
                {missionError}
              </div>
            </motion.div>
          )}

          <div
            style={{
              display:
                "grid",
              gridTemplateColumns:
                "minmax(350px, 0.72fr) minmax(520px, 1.28fr)",
              gap: 16,
              marginTop:
                16,
              alignItems:
                "start",
            }}
          >
            <motion.section
              initial={{
                opacity: 0,
                x: -16,
              }}
              animate={{
                opacity: 1,
                x: 0,
              }}
              transition={{
                duration:
                  0.45,
                delay:
                  0.11,
              }}
              style={{
                border:
                  "1px solid rgba(255,255,255,0.075)",
                background:
                  "rgba(7,10,13,0.82)",
                borderRadius:
                  5,
                overflow:
                  "hidden",
              }}
            >
              <div
                style={{
                  padding:
                    "19px 20px 16px",
                  borderBottom:
                    "1px solid rgba(255,255,255,0.055)",
                }}
              >
                <div
                  style={{
                    display:
                      "flex",
                    justifyContent:
                      "space-between",
                    alignItems:
                      "center",
                    gap: 15,
                  }}
                >
                  <div>
                    <div
                      style={{
                        display:
                          "flex",
                        alignItems:
                          "center",
                        gap: 8,
                        color:
                          "#637179",
                        fontSize:
                          9,
                        letterSpacing:
                          "0.14em",
                      }}
                    >
                      <Network
                        size={14}
                      />
                      WORKFLOW REGISTRY
                    </div>

                    <h2
                      style={{
                        margin:
                          "8px 0 0",
                        fontSize:
                          17,
                        lineHeight:
                          1.1,
                      }}
                    >
                      MISSION QUEUE
                    </h2>
                  </div>

                  <button
                    type="button"
                    onClick={() => {
                      setMissionError(
                        ""
                      );
                      setShowNewMission(
                        true
                      );
                    }}
                    style={{
                      display:
                        "inline-flex",
                      alignItems:
                        "center",
                      gap: 7,
                      padding:
                        "10px 12px",
                      border:
                        "1px solid rgba(128,224,246,0.28)",
                      background:
                        "rgba(105,188,211,0.08)",
                      color:
                        "#d8f7fd",
                      fontSize:
                        9,
                      fontWeight:
                        800,
                      letterSpacing:
                        "0.11em",
                      cursor:
                        "pointer",
                      borderRadius:
                        4,
                      whiteSpace:
                        "nowrap",
                    }}
                  >
                    <Plus
                      size={14}
                    />
                    NEW MISSION
                  </button>
                </div>

                <div
                  style={{
                    display:
                      "flex",
                    alignItems:
                      "center",
                    gap: 9,
                    marginTop:
                      16,
                    padding:
                      "11px 12px",
                    border:
                      "1px solid rgba(255,255,255,0.06)",
                    background:
                      "rgba(255,255,255,0.018)",
                    borderRadius:
                      4,
                  }}
                >
                  <Search
                    size={15}
                    color="#5d6a73"
                  />

                  <input
                    value={
                      searchQuery
                    }
                    onChange={(
                      event
                    ) =>
                      setSearchQuery(
                        event.target.value
                      )
                    }
                    placeholder="SEARCH YOUR MISSIONS"
                    style={{
                      flex:
                        1,
                      minWidth:
                        0,
                      border:
                        "none",
                      outline:
                        "none",
                      background:
                        "transparent",
                      color:
                        "#dce9ed",
                      fontSize:
                        10,
                      letterSpacing:
                        "0.07em",
                    }}
                  />

                  <Filter
                    size={15}
                    color="#5d6a73"
                  />
                </div>

                <div
                  style={{
                    display:
                      "flex",
                    gap: 6,
                    marginTop:
                      11,
                    overflowX:
                      "auto",
                    paddingBottom:
                      2,
                  }}
                >
                  {STATUS_FILTERS.map(
                    (
                      filter
                    ) => {
                      const active =
                        activeFilter ===
                        filter;

                      return (
                        <button
                          key={
                            filter
                          }
                          type="button"
                          onClick={() =>
                            setActiveFilter(
                              filter
                            )
                          }
                          style={{
                            flexShrink:
                              0,
                            padding:
                              "7px 10px",
                            border:
                              active
                                ? "1px solid rgba(130,224,246,0.34)"
                                : "1px solid rgba(255,255,255,0.06)",
                            background:
                              active
                                ? "rgba(106,193,216,0.11)"
                                : "rgba(255,255,255,0.018)",
                            color:
                              active
                                ? "#d8f8ff"
                                : "#5f6d76",
                            fontSize:
                              8,
                            letterSpacing:
                              "0.1em",
                            cursor:
                              "pointer",
                            borderRadius:
                              3,
                          }}
                        >
                          {
                            filter
                          }
                        </button>
                      );
                    }
                  )}
                </div>
              </div>

              <div
                style={{
                  padding:
                    12,
                  display:
                    "grid",
                  gap: 10,
                  maxHeight:
                    900,
                  overflowY:
                    "auto",
                }}
              >
                {filteredMissions.length >
                0 ? (
                  filteredMissions.map(
                    (
                      mission
                    ) => (
                      <MissionCard
                        key={
                          mission.id
                        }
                        mission={
                          mission
                        }
                        selected={
                          selectedMissionId ===
                          mission.id
                        }
                        onSelect={(
                          value
                        ) => {
                          setMissionError(
                            ""
                          );
                          setSelectedMissionId(
                            value.id
                          );
                        }}
                      />
                    )
                  )
                ) : (
                  <div
                    style={{
                      minHeight:
                        450,
                      display:
                        "grid",
                      placeItems:
                        "center",
                      padding:
                        35,
                      textAlign:
                        "center",
                      border:
                        "1px dashed rgba(255,255,255,0.075)",
                      background:
                        "radial-gradient(circle at center, rgba(90,176,199,0.045), transparent 58%)",
                      borderRadius:
                        4,
                    }}
                  >
                    <div
                      style={{
                        maxWidth:
                          340,
                      }}
                    >
                      <div
                        style={{
                          width: 70,
                          height: 70,
                          margin:
                            "0 auto",
                          display:
                            "grid",
                          placeItems:
                            "center",
                          border:
                            "1px solid rgba(125,224,245,0.18)",
                          background:
                            "rgba(89,178,201,0.05)",
                          boxShadow:
                            "0 0 50px rgba(70,178,206,0.08)",
                          borderRadius:
                            5,
                        }}
                      >
                        <Workflow
                          size={29}
                          color="#88e3f5"
                        />
                      </div>

                      <div
                        style={{
                          marginTop:
                            18,
                          color:
                            "#e1edf0",
                          fontSize:
                            15,
                          fontWeight:
                            700,
                        }}
                      >
                        {missions.length ===
                        0
                          ? "MISSION REGISTRY IS EMPTY"
                          : "NO MISSION MATCHES"}
                      </div>

                      <p
                        style={{
                          margin:
                            "9px auto 0",
                          color:
                            "#65737b",
                          fontSize:
                            10,
                          lineHeight:
                            1.7,
                        }}
                      >
                        {missions.length ===
                        0
                          ? "Create your first mission using your own objective and evidence package."
                          : "Change your search or status filter to locate a mission already created in this workspace."}
                      </p>

                      {missions.length ===
                        0 && (
                        <button
                          type="button"
                          onClick={() => {
                            setMissionError(
                              ""
                            );
                            setShowNewMission(
                              true
                            );
                          }}
                          style={{
                            display:
                              "inline-flex",
                            alignItems:
                              "center",
                            gap: 7,
                            marginTop:
                              20,
                            padding:
                              "11px 14px",
                            border:
                              "1px solid rgba(132,226,249,0.34)",
                            background:
                              "rgba(95,184,211,0.10)",
                            color:
                              "#e0faff",
                            fontSize:
                              9,
                            fontWeight:
                              800,
                            letterSpacing:
                              "0.11em",
                            cursor:
                              "pointer",
                            borderRadius:
                              4,
                          }}
                        >
                          <Plus
                            size={13}
                          />
                          CREATE FIRST MISSION
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </motion.section>

            <motion.section
              initial={{
                opacity: 0,
                x: 16,
              }}
              animate={{
                opacity: 1,
                x: 0,
              }}
              transition={{
                duration:
                  0.45,
                delay:
                  0.15,
              }}
              style={{
                border:
                  "1px solid rgba(255,255,255,0.075)",
                background:
                  "rgba(7,10,13,0.84)",
                borderRadius:
                  5,
                overflow:
                  "hidden",
              }}
            >
              {!selectedMission ? (
                <div
                  style={{
                    minHeight:
                      760,
                    display:
                      "grid",
                    placeItems:
                      "center",
                    padding:
                      40,
                    textAlign:
                      "center",
                  }}
                >
                  <div
                    style={{
                      maxWidth:
                        400,
                    }}
                  >
                    <div
                      style={{
                        width: 76,
                        height: 76,
                        margin:
                          "0 auto",
                        display:
                          "grid",
                        placeItems:
                          "center",
                        border:
                          "1px solid rgba(126,226,246,0.18)",
                        background:
                          "radial-gradient(circle, rgba(87,182,205,0.09), rgba(255,255,255,0.01))",
                        boxShadow:
                          "0 0 60px rgba(81,188,212,0.08)",
                        borderRadius:
                          5,
                      }}
                    >
                      <Target
                        size={31}
                        color="#89e4f6"
                      />
                    </div>

                    <div
                      style={{
                        marginTop:
                          21,
                        color:
                          "#e4eff2",
                        fontSize:
                          18,
                        fontWeight:
                          700,
                      }}
                    >
                      NO MISSION SELECTED
                    </div>

                    <p
                      style={{
                        margin:
                          "10px auto 0",
                        color:
                          "#65737b",
                        fontSize:
                          10,
                        lineHeight:
                          1.75,
                      }}
                    >
                      Create a mission or select one
                      from your registry. Execution
                      information will appear here after
                      NOVA receives a real mission.
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  <div
                    style={{
                      padding:
                        "21px 22px 18px",
                      borderBottom:
                        "1px solid rgba(255,255,255,0.055)",
                    }}
                  >
                    <div
                      style={{
                        display:
                          "flex",
                        justifyContent:
                          "space-between",
                        alignItems:
                          "flex-start",
                        gap: 20,
                      }}
                    >
                      <div
                        style={{
                          minWidth:
                            0,
                          flex:
                            1,
                        }}
                      >
                        <div
                          style={{
                            display:
                              "flex",
                            alignItems:
                              "center",
                            gap: 11,
                            flexWrap:
                              "wrap",
                          }}
                        >
                          <span
                            style={{
                              color:
                                "#607079",
                              fontFamily:
                                "monospace",
                              fontSize:
                                9,
                            }}
                          >
                            {
                              selectedMission.id
                            }
                          </span>

                          <PriorityBadge
                            priority={
                              selectedMission.priority
                            }
                          />
                        </div>

                        <div
                          style={{
                            display:
                              "flex",
                            alignItems:
                              "center",
                            gap: 12,
                            marginTop:
                              10,
                            flexWrap:
                              "wrap",
                          }}
                        >
                          <h2
                            style={{
                              margin:
                                0,
                              color:
                                "#edf6f8",
                              fontSize:
                                "clamp(24px, 3vw, 36px)",
                              lineHeight:
                                1.08,
                              letterSpacing:
                                "-0.025em",
                            }}
                          >
                            {
                              selectedMission.title
                            }
                          </h2>

                          <button
                            type="button"
                            onClick={
                              openEditMission
                            }
                            disabled={
                              selectedMission.status ===
                              "RUNNING"
                            }
                            style={{
                              display:
                                "inline-flex",
                              alignItems:
                                "center",
                              gap: 7,
                              padding:
                                "8px 10px",
                              border:
                                "1px solid rgba(255,255,255,0.08)",
                              background:
                                "rgba(255,255,255,0.025)",
                              color:
                                "#8b9aa1",
                              fontSize:
                                8,
                              fontWeight:
                                800,
                              letterSpacing:
                                "0.09em",
                              cursor:
                                selectedMission.status ===
                                "RUNNING"
                                  ? "not-allowed"
                                  : "pointer",
                              borderRadius:
                                4,
                            }}
                          >
                            <Pencil
                              size={
                                12
                              }
                            />
                            EDIT MISSION
                          </button>
                        </div>

                        <p
                          style={{
                            maxWidth:
                              820,
                            margin:
                              "10px 0 0",
                            color:
                              "#71808a",
                            fontSize:
                              11,
                            lineHeight:
                              1.7,
                          }}
                        >
                          {
                            selectedMission.description
                          }
                        </p>
                      </div>

                      <StatusBadge
                        status={
                          launchingMission
                            ? "RUNNING"
                            : selectedMission.status
                        }
                      />
                    </div>

                    <div
                      style={{
                        display:
                          "grid",
                        gridTemplateColumns:
                          "minmax(0, 1.3fr) minmax(150px, 0.7fr)",
                        gap: 10,
                        marginTop:
                          20,
                      }}
                    >
                      <div
                        style={{
                          padding:
                            "14px 15px",
                          border:
                            "1px solid rgba(124,220,241,0.11)",
                          background:
                            "rgba(77,162,185,0.035)",
                          borderRadius:
                            4,
                        }}
                      >
                        <div
                          style={{
                            display:
                              "flex",
                            justifyContent:
                              "space-between",
                            alignItems:
                              "center",
                          }}
                        >
                          <span
                            style={{
                              color:
                                "#607079",
                              fontSize:
                                8,
                              letterSpacing:
                                "0.13em",
                            }}
                          >
                            EXECUTION PROGRESS
                          </span>

                          <strong
                            style={{
                              color:
                                "#d9f9ff",
                              fontFamily:
                                "monospace",
                              fontSize:
                                16,
                            }}
                          >
                            {
                              selectedMission.progress
                            }
                            %
                          </strong>
                        </div>

                        <div
                          style={{
                            height:
                              5,
                            marginTop:
                              9,
                            background:
                              "rgba(255,255,255,0.06)",
                          }}
                        >
                          <motion.div
                            animate={{
                              width: `${selectedMission.progress}%`,
                            }}
                            transition={{
                              duration:
                                0.5,
                            }}
                            style={{
                              height:
                                "100%",
                              background:
                                "linear-gradient(90deg, #4b95aa, #a4ecff)",
                            }}
                          />
                        </div>
                      </div>

                      <div
                        style={{
                          padding:
                            "14px 15px",
                          border:
                            "1px solid rgba(255,255,255,0.07)",
                          background:
                            "rgba(255,255,255,0.017)",
                          borderRadius:
                            4,
                        }}
                      >
                        <span
                          style={{
                            color:
                              "#617079",
                            fontSize:
                              8,
                            letterSpacing:
                              "0.13em",
                          }}
                        >
                          RUNTIME
                        </span>

                        <strong
                          style={{
                            display:
                              "block",
                            marginTop:
                              8,
                            color:
                              "#e0f7fb",
                            fontFamily:
                              "monospace",
                            fontSize:
                              18,
                          }}
                        >
                          {runtime}
                        </strong>
                      </div>
                    </div>
                  </div>

                  <div
                    style={{
                      display:
                        "grid",
                      gridTemplateColumns:
                        "repeat(4, minmax(0, 1fr))",
                      gap: 8,
                      padding:
                        "13px 18px",
                      borderBottom:
                        "1px solid rgba(255,255,255,0.055)",
                    }}
                  >
                    <MetricCard
                      icon={
                        Bot
                      }
                      label="PLAN STEPS"
                      value={
                        selectedMission.steps ||
                        0
                      }
                    />

                    <MetricCard
                      icon={
                        Database
                      }
                      label="EVIDENCE"
                      value={
                        selectedMission.attachments
                          ?.length ||
                        0
                      }
                    />

                    <MetricCard
                      icon={
                        Timer
                      }
                      label="RUNTIME"
                      value={
                        runtime
                      }
                    />

                    <MetricCard
                      icon={
                        Cpu
                      }
                      label="LOCAL MODEL"
                      value={
                        selectedMission.sovereignty
                          ? "ACTIVE"
                          : "--"
                      }
                    />
                  </div>

                  <div
                    style={{
                      display:
                        "grid",
                      gridTemplateColumns:
                        "minmax(0, 1fr) 280px",
                      borderBottom:
                        "1px solid rgba(255,255,255,0.055)",
                    }}
                  >
                    <div
                      style={{
                        padding:
                          "19px 20px",
                        borderRight:
                          "1px solid rgba(255,255,255,0.055)",
                      }}
                    >
                      <div
                        style={{
                          display:
                            "flex",
                          justifyContent:
                            "space-between",
                          alignItems:
                            "center",
                          gap: 14,
                        }}
                      >
                        <div>
                          <div
                            style={{
                              display:
                                "flex",
                              alignItems:
                                "center",
                              gap: 8,
                              color:
                                "#66757e",
                              fontSize:
                                9,
                              letterSpacing:
                                "0.14em",
                            }}
                          >
                            <Network
                              size={
                                14
                              }
                            />
                            REAL AGENT PLAN
                          </div>

                          <h3
                            style={{
                              margin:
                                "8px 0 0",
                              fontSize:
                                15,
                            }}
                          >
                            EXECUTION GRAPH
                          </h3>
                        </div>

                        <span
                          style={{
                            color:
                              "#65747d",
                            fontFamily:
                              "monospace",
                            fontSize:
                              8,
                          }}
                        >
                          {planSteps.length
                            ? `${planSteps.length} STEPS`
                            : "AWAITING PLAN"}
                        </span>
                      </div>

                      <div
                        style={{
                          marginTop:
                            19,
                        }}
                      >
                        {planSteps.length >
                        0 ? (
                          planSteps.map(
                            (
                              step,
                              index
                            ) => (
                              <StepRow
                                key={
                                  step.id ||
                                  index
                                }
                                step={
                                  step
                                }
                                execution={
                                  selectedMission.execution
                                }
                                index={
                                  index
                                }
                              />
                            )
                          )
                        ) : (
                          <div
                            style={{
                              padding:
                                "32px 16px",
                              textAlign:
                                "center",
                              border:
                                "1px dashed rgba(255,255,255,0.065)",
                              color:
                                "#58666e",
                              fontSize:
                                10,
                              lineHeight:
                                1.65,
                              borderRadius:
                                4,
                            }}
                          >
                            {launchingMission
                              ? "LOCAL PLANNER IS GENERATING THE MISSION PLAN..."
                              : "The real backend plan will appear here after this mission is launched."}
                          </div>
                        )}
                      </div>
                    </div>

                    <div
                      style={{
                        padding:
                          "19px 18px",
                      }}
                    >
                      <div
                        style={{
                          display:
                            "flex",
                          alignItems:
                            "center",
                          gap: 8,
                          color:
                            "#66757e",
                          fontSize:
                            9,
                          letterSpacing:
                            "0.14em",
                        }}
                      >
                        <Gauge
                          size={
                            14
                          }
                        />
                        RUNTIME STATE
                      </div>

                      <div
                        style={{
                          display:
                            "grid",
                          gap: 14,
                          marginTop:
                            18,
                        }}
                      >
                        {[
                          [
                            "STATUS",
                            selectedMission.status,
                          ],
                          [
                            "COMPLETED STEPS",
                            `${selectedMission.completedSteps}/${selectedMission.steps || 0}`,
                          ],
                          [
                            "EXTERNAL AI",
                            selectedMission.sovereignty
                              ?.external_ai_calls !=
                              null
                              ? String(
                                  selectedMission
                                    .sovereignty
                                    .external_ai_calls
                                )
                              : "--",
                          ],
                          [
                            "NETWORK",
                            selectedMission.sovereignty
                              ?.network_mode ||
                              "--",
                          ],
                        ].map(
                          ([label, value]) => (
                            <div
                              key={
                                label
                              }
                              style={{
                                display:
                                  "flex",
                                justifyContent:
                                  "space-between",
                                alignItems:
                                  "center",
                                gap: 12,
                              }}
                            >
                              <span
                                style={{
                                  color:
                                    "#5c6971",
                                  fontSize:
                                    9,
                                }}
                              >
                                {
                                  label
                                }
                              </span>

                              <strong
                                style={{
                                  color:
                                    "#b8eaf3",
                                  fontFamily:
                                    "monospace",
                                  fontSize:
                                    9,
                                  textAlign:
                                    "right",
                                }}
                              >
                                {
                                  value
                                }
                              </strong>
                            </div>
                          )
                        )}
                      </div>

                      <div
                        style={{
                          marginTop:
                            20,
                          padding:
                            "11px",
                          border:
                            "1px solid rgba(117,218,239,0.1)",
                          background:
                            "rgba(72,151,174,0.03)",
                          color:
                            "#71838a",
                          fontSize:
                            8,
                          lineHeight:
                            1.6,
                          borderRadius:
                            4,
                        }}
                      >
                        Runtime telemetry is limited to
                        information actually returned by
                        NOVA.
                      </div>
                    </div>
                  </div>

                  <div
                    style={{
                      display:
                        "grid",
                      gridTemplateColumns:
                        "1fr 1fr",
                      borderBottom:
                        "1px solid rgba(255,255,255,0.055)",
                    }}
                  >
                    <div
                      style={{
                        padding:
                          "19px 20px",
                        borderRight:
                          "1px solid rgba(255,255,255,0.055)",
                      }}
                    >
                      <div
                        style={{
                          display:
                            "flex",
                          alignItems:
                            "center",
                          gap: 8,
                          color:
                            "#66757e",
                          fontSize:
                            9,
                          letterSpacing:
                            "0.14em",
                        }}
                      >
                        <FolderOpen
                          size={
                            14
                          }
                        />
                        MISSION INPUTS
                      </div>

                      <h3
                        style={{
                          margin:
                            "8px 0 0",
                          fontSize:
                            15,
                        }}
                      >
                        SOURCES & CONTEXT
                      </h3>

                      <div
                        style={{
                          marginTop:
                            14,
                        }}
                      >
                        {selectedMission.attachments?.length >
                        0 ? (
                          <div
                            style={{
                              display:
                                "grid",
                              gap: 7,
                            }}
                          >
                            {selectedMission.attachments.map(
                              (
                                source
                              ) => (
                                <div
                                  key={
                                    source.file_id
                                  }
                                  style={{
                                    display:
                                      "flex",
                                    alignItems:
                                      "center",
                                    gap: 10,
                                    padding:
                                      "9px 10px",
                                    border:
                                      "1px solid rgba(255,255,255,0.055)",
                                    background:
                                      "rgba(255,255,255,0.016)",
                                    borderRadius:
                                      4,
                                  }}
                                >
                                  <span
                                    style={{
                                      width:
                                        30,
                                      height:
                                        30,
                                      display:
                                        "grid",
                                      placeItems:
                                        "center",
                                      flexShrink:
                                        0,
                                      border:
                                        "1px solid rgba(125,224,245,0.12)",
                                      background:
                                        "rgba(89,178,201,0.04)",
                                      color:
                                        "#84ddec",
                                    }}
                                  >
                                    {getFileIcon(
                                      source
                                    )}
                                  </span>

                                  <div
                                    style={{
                                      minWidth:
                                        0,
                                      flex:
                                        1,
                                    }}
                                  >
                                    <div
                                      style={{
                                        overflow:
                                          "hidden",
                                        textOverflow:
                                          "ellipsis",
                                        whiteSpace:
                                          "nowrap",
                                        color:
                                          "#b8d6dc",
                                        fontSize:
                                          9,
                                      }}
                                    >
                                      {
                                        source.filename
                                      }
                                    </div>

                                    <div
                                      style={{
                                        marginTop:
                                          3,
                                        color:
                                          "#56656d",
                                        fontFamily:
                                          "monospace",
                                        fontSize:
                                          7,
                                      }}
                                    >
                                      {(
                                        Number(
                                          source.size ||
                                            0
                                        ) /
                                        1024 /
                                        1024
                                      ).toFixed(
                                        2
                                      )}{" "}
                                      MB
                                    </div>
                                  </div>
                                </div>
                              )
                            )}
                          </div>
                        ) : (
                          <div
                            style={{
                              padding:
                                "24px 12px",
                              border:
                                "1px dashed rgba(255,255,255,0.06)",
                              color:
                                "#58666e",
                              fontSize:
                                9,
                              textAlign:
                                "center",
                              lineHeight:
                                1.65,
                            }}
                          >
                            No mission-specific source
                            files were provided.
                          </div>
                        )}
                      </div>
                    </div>

                    <div
                      style={{
                        padding:
                          "19px 20px",
                      }}
                    >
                      <div
                        style={{
                          display:
                            "flex",
                          alignItems:
                            "center",
                          gap: 8,
                          color:
                            "#66757e",
                          fontSize:
                            9,
                          letterSpacing:
                            "0.14em",
                        }}
                      >
                        <FileCheck2
                          size={
                            14
                          }
                        />
                        DELIVERABLES
                      </div>

                      <h3
                        style={{
                          margin:
                            "8px 0 0",
                          fontSize:
                            15,
                        }}
                      >
                        VERIFIED OUTPUT
                      </h3>

                      <div
                        style={{
                          marginTop:
                            14,
                        }}
                      >
                        {selectedMission.artifacts.length >
                        0 ? (
                          <div
                            style={{
                              display:
                                "grid",
                              gap: 8,
                            }}
                          >
                            {selectedMission.artifacts.map(
                              (
                                artifact
                              ) => {
                                const downloadUrl =
                                  artifact.filePath
                                    ? `${API_URL}/api/chat/download/${artifact.filePath
                                        .replace(
                                          /^\/+/,
                                          ""
                                        )
                                        .split(
                                          "/"
                                        )
                                        .map(
                                          encodeURIComponent
                                        )
                                        .join(
                                          "/"
                                        )}`
                                    : null;

                                return (
                                  <div
                                    key={
                                      artifact.id
                                    }
                                    style={{
                                      display:
                                        "flex",
                                      alignItems:
                                        "center",
                                      gap: 10,
                                      padding:
                                        "10px",
                                      border:
                                        "1px solid rgba(117,220,239,0.09)",
                                      background:
                                        "rgba(76,158,180,0.03)",
                                      borderRadius:
                                        4,
                                    }}
                                  >
                                    <FileCheck2
                                      size={
                                        14
                                      }
                                      color="#7adbe9"
                                    />

                                    <div
                                      style={{
                                        minWidth:
                                          0,
                                        flex:
                                          1,
                                      }}
                                    >
                                      <div
                                        style={{
                                          overflow:
                                            "hidden",
                                          textOverflow:
                                            "ellipsis",
                                          whiteSpace:
                                            "nowrap",
                                          color:
                                            "#b9dde5",
                                          fontSize:
                                            9,
                                        }}
                                      >
                                        {
                                          artifact.fileName
                                        }
                                      </div>

                                      <div
                                        style={{
                                          marginTop:
                                            3,
                                          color:
                                            "#596971",
                                          fontFamily:
                                            "monospace",
                                          fontSize:
                                            7,
                                        }}
                                      >
                                        {
                                          artifact.filePath
                                        }{" "}
                                        •{" "}
                                        {formatArtifactSize(
                                          artifact.sizeBytes
                                        )}
                                      </div>
                                    </div>

                                    {downloadUrl &&
                                      artifact.available !==
                                        false && (
                                        <a
                                          href={
                                            downloadUrl
                                          }
                                          download={
                                            artifact.fileName
                                          }
                                          style={{
                                            display:
                                              "inline-flex",
                                            alignItems:
                                              "center",
                                            gap: 5,
                                            padding:
                                              "7px 8px",
                                            border:
                                              "1px solid rgba(132,226,249,0.18)",
                                            background:
                                              "rgba(95,184,211,0.05)",
                                            color:
                                              "#9feaf7",
                                            fontSize:
                                              7,
                                            fontWeight:
                                              800,
                                            letterSpacing:
                                              "0.08em",
                                            textDecoration:
                                              "none",
                                            borderRadius:
                                              4,
                                          }}
                                        >
                                          <Download
                                            size={
                                              11
                                            }
                                          />
                                          DOWNLOAD
                                        </a>
                                      )}
                                  </div>
                                );
                              }
                            )}
                          </div>
                        ) : (
                          <div
                            style={{
                              padding:
                                "24px 12px",
                              border:
                                "1px dashed rgba(255,255,255,0.06)",
                              color:
                                "#58666e",
                              fontSize:
                                9,
                              textAlign:
                                "center",
                              lineHeight:
                                1.65,
                            }}
                          >
                            No generated artifact has been
                            returned by the mission runtime
                            yet.
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <div
                    style={{
                      display:
                        "grid",
                      gridTemplateColumns:
                        "1fr 1fr",
                      borderBottom:
                        "1px solid rgba(255,255,255,0.055)",
                    }}
                  >
                    <div
                      style={{
                        padding:
                          "19px 20px",
                        borderRight:
                          "1px solid rgba(255,255,255,0.055)",
                      }}
                    >
                      <div
                        style={{
                          display:
                            "flex",
                          alignItems:
                            "center",
                          gap: 8,
                          color:
                            "#66757e",
                          fontSize:
                            9,
                          letterSpacing:
                            "0.14em",
                        }}
                      >
                        <ShieldCheck
                          size={
                            14
                          }
                        />
                        SOVEREIGNTY
                      </div>

                      <div
                        style={{
                          display:
                            "grid",
                          gap: 11,
                          marginTop:
                            15,
                        }}
                      >
                        {[
                          [
                            "Execution mode",
                            selectedMission
                              .sovereignty
                              ?.execution_mode ||
                              "NOT RUN",
                          ],
                          [
                            "Network mode",
                            selectedMission
                              .sovereignty
                              ?.network_mode ||
                              "NOT RUN",
                          ],
                          [
                            "External AI calls",
                            selectedMission
                              .sovereignty
                              ?.external_ai_calls !=
                              null
                              ? String(
                                  selectedMission
                                    .sovereignty
                                    .external_ai_calls
                                )
                              : "NOT RUN",
                          ],
                          [
                            "Local reasoning",
                            selectedMission
                              .sovereignty
                              ?.local_reasoning
                              ? "YES"
                              : "NOT RUN",
                          ],
                        ].map(
                          ([label, value]) => (
                            <div
                              key={
                                label
                              }
                              style={{
                                display:
                                  "flex",
                                justifyContent:
                                  "space-between",
                                gap: 14,
                              }}
                            >
                              <span
                                style={{
                                  color:
                                    "#5f6d75",
                                  fontSize:
                                    9,
                                }}
                              >
                                {
                                  label
                                }
                              </span>

                              <strong
                                style={{
                                  color:
                                    "#b6e8f1",
                                  fontFamily:
                                    "monospace",
                                  fontSize:
                                    9,
                                  textAlign:
                                    "right",
                                }}
                              >
                                {
                                  value
                                }
                              </strong>
                            </div>
                          )
                        )}
                      </div>
                    </div>

                    <div
                      style={{
                        padding:
                          "19px 20px",
                      }}
                    >
                      <div
                        style={{
                          display:
                            "flex",
                          alignItems:
                            "center",
                          gap: 8,
                          color:
                            "#66757e",
                          fontSize:
                            9,
                          letterSpacing:
                            "0.14em",
                        }}
                      >
                        <KeyRound
                          size={
                            14
                          }
                        />
                        MISSION POLICY
                      </div>

                      <div
                        style={{
                          display:
                            "grid",
                          gap: 11,
                          marginTop:
                            15,
                        }}
                      >
                        <div
                          style={{
                            display:
                              "flex",
                            justifyContent:
                              "space-between",
                            gap: 14,
                          }}
                        >
                          <span
                            style={{
                              color:
                                "#5f6d75",
                              fontSize:
                                9,
                            }}
                          >
                            Priority
                          </span>

                          <strong
                            style={{
                              color:
                                "#b8e8f1",
                              fontSize:
                                9,
                            }}
                          >
                            {
                              selectedMission.priority
                            }
                          </strong>
                        </div>

                        <div
                          style={{
                            display:
                              "flex",
                            justifyContent:
                              "space-between",
                            gap: 14,
                          }}
                        >
                          <span
                            style={{
                              color:
                                "#5f6d75",
                              fontSize:
                                9,
                            }}
                          >
                            Autonomy
                          </span>

                          <strong
                            style={{
                              color:
                                "#b8e8f1",
                              fontSize:
                                9,
                              textAlign:
                                "right",
                            }}
                          >
                            {
                              selectedMission.autonomy
                            }
                          </strong>
                        </div>

                        <div
                          style={{
                            marginTop:
                              3,
                            padding:
                              "11px 12px",
                            border:
                              "1px solid rgba(117,218,239,0.09)",
                            background:
                              "rgba(71,149,171,0.028)",
                            color:
                              "#6d8088",
                            fontSize:
                              8,
                            lineHeight:
                              1.6,
                          }}
                        >
                          Editing mission inputs resets the
                          current execution state so NOVA
                          never displays results for outdated
                          mission data.
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* =====================================================
                      MISSION CONVERSATION
                  ====================================================== */}
                  <div
                    style={{
                      borderBottom:
                        "1px solid rgba(255,255,255,0.055)",
                    }}
                  >
                    <div
                      style={{
                        padding:
                          "19px 20px 13px",
                        display:
                          "flex",
                        justifyContent:
                          "space-between",
                        alignItems:
                          "center",
                        gap: 14,
                      }}
                    >
                      <div>
                        <div
                          style={{
                            display:
                              "flex",
                            alignItems:
                              "center",
                            gap: 8,
                            color:
                              "#66757e",
                            fontSize:
                              9,
                            letterSpacing:
                              "0.14em",
                          }}
                        >
                          <MessageSquare
                            size={
                              14
                            }
                          />
                          MISSION CONVERSATION
                        </div>

                        <h3
                          style={{
                            margin:
                              "8px 0 0",
                            fontSize:
                              16,
                          }}
                        >
                          TALK TO NOVA ABOUT THIS MISSION
                        </h3>
                      </div>

                      <span
                        style={{
                          color:
                            "#64747c",
                          fontFamily:
                            "monospace",
                          fontSize:
                            8,
                        }}
                      >
                        {selectedMission.conversationId
                          ? "SAVED SESSION"
                          : "AVAILABLE AFTER RUN"}
                      </span>
                    </div>

                    <div
                      style={{
                        margin:
                          "0 20px 16px",
                        minHeight:
                          330,
                        maxHeight:
                          460,
                        overflowY:
                          "auto",
                        padding:
                          "14px",
                        border:
                          "1px solid rgba(255,255,255,0.055)",
                        background:
                          "rgba(2,5,7,0.65)",
                        borderRadius:
                          5,
                      }}
                    >
                      {!selectedMission.conversationId ? (
                        <div
                          style={{
                            minHeight:
                              290,
                            display:
                              "grid",
                            placeItems:
                              "center",
                            textAlign:
                              "center",
                            padding:
                              25,
                          }}
                        >
                          <div
                            style={{
                              maxWidth:
                                380,
                            }}
                          >
                            <MessageSquare
                              size={
                                30
                              }
                              color="#7bddec"
                            />

                            <div
                              style={{
                                marginTop:
                                  15,
                                color:
                                  "#dcebef",
                                fontSize:
                                  14,
                                fontWeight:
                                  700,
                              }}
                            >
                              MISSION CHAT WILL OPEN AFTER EXECUTION
                            </div>

                            <p
                              style={{
                                margin:
                                  "8px 0 0",
                                color:
                                  "#65737b",
                                fontSize:
                                  9,
                                lineHeight:
                                  1.7,
                              }}
                            >
                              Run the mission once. NOVA will
                              then preserve the mission session
                              so you can continue asking questions
                              and requesting follow-up work.
                            </p>
                          </div>
                        </div>
                      ) : loadingMissionChat ? (
                        <div
                          style={{
                            minHeight:
                              290,
                            display:
                              "grid",
                            placeItems:
                              "center",
                            color:
                              "#6d7c84",
                            fontFamily:
                              "monospace",
                            fontSize:
                              9,
                            letterSpacing:
                              "0.10em",
                          }}
                        >
                          <LoaderCircle
                            size={
                              22
                            }
                            style={{
                              marginBottom:
                                10,
                              animation:
                                "spin 1s linear infinite",
                            }}
                          />
                          LOADING MISSION SESSION...
                        </div>
                      ) : (
                        <>
                          {missionChatMessages.length ===
                          0 ? (
                            <div
                              style={{
                                minHeight:
                                  280,
                                display:
                                  "grid",
                                placeItems:
                                  "center",
                                textAlign:
                                  "center",
                                color:
                                  "#67757c",
                                fontSize:
                                  10,
                              }}
                            >
                              Your mission conversation will
                              appear here.
                            </div>
                          ) : (
                            missionChatMessages.map(
                              (
                                message
                              ) => (
                                <div
                                  key={
                                    message.id
                                  }
                                  style={{
                                    marginBottom:
                                      14,
                                    display:
                                      "flex",
                                    flexDirection:
                                      "column",
                                    alignItems:
                                      message.role ===
                                      "user"
                                        ? "flex-end"
                                        : "flex-start",
                                  }}
                                >
                                  <div
                                    style={{
                                      display:
                                        "flex",
                                      alignItems:
                                        "center",
                                      gap: 7,
                                      marginBottom:
                                        5,
                                      color:
                                        "#5d6d75",
                                      fontFamily:
                                        "monospace",
                                      fontSize:
                                        7,
                                      letterSpacing:
                                        "0.09em",
                                    }}
                                  >
                                    <span>
                                      {message.role ===
                                      "user"
                                        ? "YOU"
                                        : "NOVA"}
                                    </span>

                                    <span>
                                      {message.createdAt instanceof
                                      Date
                                        ? message.createdAt.toLocaleTimeString(
                                            [],
                                            {
                                              hour:
                                                "2-digit",
                                              minute:
                                                "2-digit",
                                            }
                                          )
                                        : ""}
                                    </span>
                                  </div>

                                  <div
                                    style={{
                                      maxWidth:
                                        "88%",
                                      padding:
                                        "11px 13px",
                                      border:
                                        message.role ===
                                        "user"
                                          ? "1px solid rgba(128,224,246,0.22)"
                                          : "1px solid rgba(255,255,255,0.065)",
                                      background:
                                        message.role ===
                                        "user"
                                          ? "rgba(88,183,210,0.08)"
                                          : "rgba(255,255,255,0.022)",
                                      borderRadius:
                                        5,
                                    }}
                                  >
                                    {message.role ===
                                    "assistant" ? (
                                      <MissionMarkdown
                                        content={
                                          message.content
                                        }
                                      />
                                    ) : (
                                      <div
                                        style={{
                                          color:
                                            "#d9eaee",
                                          fontSize:
                                            10,
                                          lineHeight:
                                            1.65,
                                          whiteSpace:
                                            "pre-wrap",
                                        }}
                                      >
                                        {
                                          message.content
                                        }
                                      </div>
                                    )}
                                  </div>
                                </div>
                              )
                            )
                          )}

                          {sendingMissionChat && (
                            <div
                              style={{
                                display:
                                  "flex",
                                alignItems:
                                  "center",
                                gap: 8,
                                color:
                                  "#7f9299",
                                fontFamily:
                                  "monospace",
                                fontSize:
                                  8,
                                letterSpacing:
                                  "0.09em",
                              }}
                            >
                              <RefreshCw
                                size={
                                  13
                                }
                                style={{
                                  animation:
                                    "spin 1s linear infinite",
                                }}
                              />
                              NOVA IS WORKING ON THE MISSION...
                            </div>
                          )}

                          <div
                            ref={
                              missionChatEndRef
                            }
                          />
                        </>
                      )}
                    </div>

                    {missionChatError && (
                      <div
                        style={{
                          margin:
                            "0 20px 10px",
                          padding:
                            "10px 12px",
                          border:
                            "1px solid rgba(239,184,167,0.20)",
                          background:
                            "rgba(120,52,39,0.06)",
                          color:
                            "#c99d91",
                          fontSize:
                            9,
                          lineHeight:
                            1.5,
                          borderRadius:
                            4,
                        }}
                      >
                        {
                          missionChatError
                        }
                      </div>
                    )}

                    <div
                      style={{
                        margin:
                          "0 20px 19px",
                        display:
                          "flex",
                        alignItems:
                          "flex-end",
                        gap: 8,
                        padding:
                          "10px 10px 10px 12px",
                        border:
                          "1px solid rgba(255,255,255,0.075)",
                        background:
                          "rgba(255,255,255,0.018)",
                        borderRadius:
                          5,
                      }}
                    >
                      <textarea
                        value={
                          missionChatInput
                        }
                        onChange={(
                          event
                        ) =>
                          setMissionChatInput(
                            event.target.value
                          )
                        }
                        onKeyDown={
                          handleMissionChatKeyDown
                        }
                        disabled={
                          !selectedMission.conversationId ||
                          sendingMissionChat
                        }
                        rows={
                          2
                        }
                        placeholder={
                          selectedMission.conversationId
                            ? "Ask NOVA about the mission, evidence, conclusion or request another controlled task..."
                            : "Run this mission to enable the mission conversation..."
                        }
                        style={{
                          flex:
                            1,
                          minHeight:
                            46,
                          maxHeight:
                            130,
                          resize:
                            "vertical",
                          border:
                            "none",
                          outline:
                            "none",
                          background:
                            "transparent",
                          color:
                            "#d9e8ec",
                          fontFamily:
                            "inherit",
                          fontSize:
                            10,
                          lineHeight:
                            1.6,
                        }}
                      />

                      <button
                        type="button"
                        onClick={
                          sendMissionChat
                        }
                        disabled={
                          !selectedMission.conversationId ||
                          !missionChatInput.trim() ||
                          sendingMissionChat
                        }
                        style={{
                          width:
                            38,
                          height:
                            38,
                          display:
                            "grid",
                          placeItems:
                            "center",
                          flexShrink:
                            0,
                          border:
                            "1px solid rgba(130,226,247,0.26)",
                          background:
                            !selectedMission.conversationId ||
                            !missionChatInput.trim() ||
                            sendingMissionChat
                              ? "rgba(255,255,255,0.025)"
                              : "rgba(95,184,211,0.10)",
                          color:
                            !selectedMission.conversationId ||
                            !missionChatInput.trim()
                              ? "#55636b"
                              : "#dffaff",
                          cursor:
                            !selectedMission.conversationId ||
                            !missionChatInput.trim() ||
                            sendingMissionChat
                              ? "not-allowed"
                              : "pointer",
                          borderRadius:
                            4,
                        }}
                      >
                        {sendingMissionChat ? (
                          <RefreshCw
                            size={
                              15
                            }
                            style={{
                              animation:
                                "spin 1s linear infinite",
                            }}
                          />
                        ) : (
                          <Send
                            size={
                              15
                            }
                          />
                        )}
                      </button>
                    </div>
                  </div>

                  <div
                    style={{
                      display:
                        "flex",
                      justifyContent:
                        "space-between",
                      alignItems:
                        "center",
                      gap: 15,
                      padding:
                        "15px 20px",
                      flexWrap:
                        "wrap",
                      background:
                        "rgba(255,255,255,0.012)",
                    }}
                  >
                    <div
                      style={{
                        display:
                          "flex",
                        alignItems:
                          "center",
                        gap: 8,
                        color:
                          "#64737a",
                        fontSize:
                          9,
                        letterSpacing:
                          "0.08em",
                      }}
                    >
                      <ServerCog
                        size={
                          14
                        }
                      />

                      {launchingMission
                        ? "LOCAL MISSION EXECUTION IN PROGRESS"
                        : selectedMission.status ===
                            "COMPLETED"
                          ? "REAL BACKEND RESULT RECEIVED"
                          : selectedMission.status ===
                              "FAILED"
                            ? "MISSION EXECUTION FAILED"
                            : "MISSION READY"}
                    </div>

                    <div
                      style={{
                        display:
                          "flex",
                        gap: 8,
                        flexWrap:
                          "wrap",
                      }}
                    >
                      {selectedMission.status ===
                        "RUNNING" && (
                        <button
                          type="button"
                          onClick={
                            togglePauseDisplay
                          }
                          style={{
                            display:
                              "inline-flex",
                            alignItems:
                              "center",
                            gap: 7,
                            padding:
                              "10px 13px",
                            border:
                              "1px solid rgba(255,255,255,0.08)",
                            background:
                              "rgba(255,255,255,0.02)",
                            color:
                              "#98a7ae",
                            fontSize:
                              9,
                            cursor:
                              "pointer",
                            borderRadius:
                              4,
                          }}
                        >
                          <Pause
                            size={
                              13
                            }
                          />
                          PAUSE
                        </button>
                      )}

                      {selectedMission.status ===
                        "COMPLETED" && (
                        <button
                          type="button"
                          onClick={
                            clearMissionState
                          }
                          style={{
                            display:
                              "inline-flex",
                            alignItems:
                              "center",
                            gap: 7,
                            padding:
                              "10px 13px",
                            border:
                              "1px solid rgba(255,255,255,0.08)",
                            background:
                              "rgba(255,255,255,0.02)",
                            color:
                              "#9eabb1",
                            fontSize:
                              9,
                            cursor:
                              "pointer",
                            borderRadius:
                              4,
                          }}
                        >
                          <RefreshCw
                            size={
                              13
                            }
                          />
                          RESET RUN
                        </button>
                      )}

                      <button
                        type="button"
                        onClick={
                          launchMission
                        }
                        disabled={
                          !canLaunch
                        }
                        style={{
                          display:
                            "inline-flex",
                          alignItems:
                            "center",
                          gap: 7,
                          padding:
                            "10px 15px",
                          border:
                            "1px solid rgba(132,226,249,0.42)",
                          background:
                            !canLaunch
                              ? "rgba(255,255,255,0.025)"
                              : "#102026",
                          color:
                            !canLaunch
                              ? "#55636b"
                              : "#e9fbff",
                          fontSize:
                            9,
                          fontWeight:
                            800,
                          letterSpacing:
                            "0.10em",
                          cursor:
                            !canLaunch
                              ? "not-allowed"
                              : "pointer",
                          borderRadius:
                            4,
                        }}
                      >
                        {launchingMission ? (
                          <RefreshCw
                            size={
                              13
                            }
                            style={{
                              animation:
                                "spin 1s linear infinite",
                            }}
                          />
                        ) : (
                          <Zap
                            size={
                              13
                            }
                          />
                        )}

                        {launchingMission
                          ? "EXECUTING..."
                          : selectedMission.status ===
                              "COMPLETED"
                            ? "RUN AGAIN"
                            : "LAUNCH MISSION"}
                      </button>
                    </div>
                  </div>
                </>
              )}
            </motion.section>
          </div>

          <div
            style={{
              display:
                "grid",
              gridTemplateColumns:
                "repeat(3, minmax(0, 1fr))",
              gap: 11,
              marginTop:
                16,
            }}
          >
            <motion.div
              initial={{
                opacity: 0,
                y: 13,
              }}
              animate={{
                opacity: 1,
                y: 0,
              }}
              transition={{
                duration:
                  0.4,
                delay:
                  0.21,
              }}
              style={{
                padding:
                  "18px 19px",
                border:
                  "1px solid rgba(255,255,255,0.06)",
                background:
                  "rgba(8,11,14,0.64)",
                borderRadius:
                  4,
              }}
            >
              <div
                style={{
                  display:
                    "flex",
                  alignItems:
                    "center",
                  gap: 8,
                  color:
                    "#66757f",
                  fontSize:
                    9,
                  letterSpacing:
                    "0.14em",
                }}
              >
                <ShieldCheck
                  size={
                    14
                  }
                />
                SOVEREIGN EXECUTION
              </div>

              <strong
                style={{
                  display:
                    "block",
                  marginTop:
                    11,
                  color:
                    "#d7edf1",
                  fontSize:
                    14,
                }}
              >
                {selectedMission?.sovereignty
                  ?.external_ai_calls ===
                0
                  ? "0 EXTERNAL AI CALLS"
                  : "SOVEREIGN BY DESIGN"}
              </strong>

              <p
                style={{
                  margin:
                    "8px 0 0",
                  color:
                    "#65737b",
                  fontSize:
                    9,
                  lineHeight:
                    1.6,
                }}
              >
                Runtime sovereignty values become visible
                after NOVA returns a real mission execution
                response.
              </p>
            </motion.div>

            <motion.div
              initial={{
                opacity: 0,
                y: 13,
              }}
              animate={{
                opacity: 1,
                y: 0,
              }}
              transition={{
                duration:
                  0.4,
                delay:
                  0.27,
              }}
              style={{
                padding:
                  "18px 19px",
                border:
                  "1px solid rgba(255,255,255,0.06)",
                background:
                  "rgba(8,11,14,0.64)",
                borderRadius:
                  4,
              }}
            >
              <div
                style={{
                  display:
                    "flex",
                  alignItems:
                    "center",
                  gap: 8,
                  color:
                    "#66757f",
                  fontSize:
                    9,
                  letterSpacing:
                    "0.14em",
                }}
              >
                <KeyRound
                  size={
                    14
                  }
                />
                HUMAN-IN-THE-LOOP
              </div>

              <strong
                style={{
                  display:
                    "block",
                  marginTop:
                    11,
                  color:
                    "#d7edf1",
                  fontSize:
                    14,
                }}
              >
                CONTROLLED AUTONOMY
              </strong>

              <p
                style={{
                  margin:
                    "8px 0 0",
                  color:
                    "#65737b",
                  fontSize:
                    9,
                  lineHeight:
                    1.6,
                }}
              >
                Each mission stores the autonomy policy you
                selected before execution.
              </p>
            </motion.div>

            <motion.div
              initial={{
                opacity: 0,
                y: 13,
              }}
              animate={{
                opacity: 1,
                y: 0,
              }}
              transition={{
                duration:
                  0.4,
                delay:
                  0.33,
              }}
              style={{
                padding:
                  "18px 19px",
                border:
                  "1px solid rgba(255,255,255,0.06)",
                background:
                  "rgba(8,11,14,0.64)",
                borderRadius:
                  4,
              }}
            >
              <div
                style={{
                  display:
                    "flex",
                  alignItems:
                    "center",
                  gap: 8,
                  color:
                    "#66757f",
                  fontSize:
                    9,
                  letterSpacing:
                    "0.14em",
                }}
              >
                <FileCheck2
                  size={
                    14
                  }
                />
                AUDITABILITY
              </div>

              <strong
                style={{
                  display:
                    "block",
                  marginTop:
                    11,
                  color:
                    "#d7edf1",
                  fontSize:
                    14,
                }}
              >
                {selectedMission?.conversationId
                  ? "PERSISTENT MISSION SESSION"
                  : "REAL EXECUTION EVIDENCE"}
              </strong>

              <p
                style={{
                  margin:
                    "8px 0 0",
                  color:
                    "#65737b",
                  fontSize:
                    9,
                  lineHeight:
                    1.6,
                }}
              >
                Mission results and follow-up conversation
                remain tied to the same NOVA session.
              </p>
            </motion.div>
          </div>

          <motion.section
            initial={{
              opacity: 0,
              y: 13,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            transition={{
              duration:
                0.42,
              delay:
                0.38,
            }}
            style={{
              marginTop:
                16,
              padding:
                "16px 19px",
              border:
                "1px solid rgba(255,255,255,0.06)",
              background:
                "rgba(8,11,14,0.62)",
              borderRadius:
                4,
            }}
          >
            <div
              style={{
                display:
                  "flex",
                justifyContent:
                  "space-between",
                alignItems:
                  "center",
                gap: 15,
                flexWrap:
                  "wrap",
              }}
            >
              <div
                style={{
                  display:
                    "flex",
                  alignItems:
                    "center",
                  gap: 9,
                }}
              >
                <ServerCog
                  size={15}
                  color="#87dff4"
                />

                <div>
                  <div
                    style={{
                      color:
                        "#66757f",
                      fontSize:
                        8,
                      letterSpacing:
                        "0.14em",
                    }}
                  >
                    MISSION REGISTRY
                  </div>

                  <strong
                    style={{
                      display:
                        "block",
                      marginTop:
                        4,
                      color:
                        "#dcecef",
                      fontSize:
                        12,
                    }}
                  >
                    LOCAL WORKSPACE STATE
                  </strong>
                </div>
              </div>

              <div
                style={{
                  display:
                    "flex",
                  alignItems:
                    "center",
                  gap: 15,
                  color:
                    "#596871",
                  fontFamily:
                    "monospace",
                  fontSize:
                    8,
                }}
              >
                <span>
                  FAILED:{" "}
                  {failedCount}
                </span>

                <span>
                  ACTIVE:{" "}
                  {runningCount}
                </span>

                <span>
                  READY:{" "}
                  {readyCount}
                </span>

                <span>
                  {missions.length} REGISTERED
                </span>
              </div>
            </div>

            <div
              style={{
                marginTop:
                  12,
                height: 1,
                background:
                  "linear-gradient(90deg, rgba(128,223,244,0.2), rgba(255,255,255,0.03), transparent)",
              }}
            />

            <div
              style={{
                marginTop:
                  10,
                color:
                  "#596871",
                fontSize:
                  8,
              }}
            >
              MISSION STATE SYNCHRONIZED LOCALLY
            </div>
          </motion.section>
        </div>
      </div>

      {/* =========================================================
          CREATE MISSION
      ========================================================== */}
      {showNewMission && (
        <motion.div
          initial={{
            opacity: 0,
          }}
          animate={{
            opacity: 1,
          }}
          style={{
            position:
              "fixed",
            inset: 0,
            zIndex:
              120,
            display:
              "grid",
            placeItems:
              "center",
            padding:
              24,
            background:
              "rgba(0,0,0,0.78)",
            backdropFilter:
              "blur(13px)",
          }}
        >
          <motion.div
            initial={{
              opacity: 0,
              y: 18,
              scale:
                0.975,
            }}
            animate={{
              opacity: 1,
              y: 0,
              scale: 1,
            }}
            style={{
              width:
                "min(920px, 100%)",
              maxHeight:
                "calc(100vh - 48px)",
              overflowY:
                "auto",
              border:
                "1px solid rgba(127,225,246,0.19)",
              background:
                "#080b0e",
              boxShadow:
                "0 40px 120px rgba(0,0,0,0.70)",
              borderRadius:
                6,
            }}
          >
            <div
              style={{
                display:
                  "flex",
                justifyContent:
                  "space-between",
                alignItems:
                  "center",
                gap: 18,
                padding:
                  "21px 22px",
                borderBottom:
                  "1px solid rgba(255,255,255,0.06)",
              }}
            >
              <div>
                <div
                  style={{
                    color:
                      "#687780",
                    fontSize:
                      9,
                    letterSpacing:
                      "0.17em",
                  }}
                >
                  MISSION FACTORY
                </div>

                <h2
                  style={{
                    margin:
                      "8px 0 0",
                    color:
                      "#eaf4f7",
                    fontSize:
                      23,
                  }}
                >
                  CREATE REAL MISSION
                </h2>
              </div>

              <button
                type="button"
                onClick={() => {
                  resetMissionCreationForm();
                  setShowNewMission(
                    false
                  );
                  setMissionError(
                    ""
                  );
                }}
                style={{
                  width:
                    36,
                  height:
                    36,
                  display:
                    "grid",
                  placeItems:
                    "center",
                  border:
                    "1px solid rgba(255,255,255,0.07)",
                  background:
                    "rgba(255,255,255,0.025)",
                  color:
                    "#7d8a91",
                  cursor:
                    "pointer",
                  borderRadius:
                    4,
                }}
              >
                <X
                  size={
                    16
                  }
                />
              </button>
            </div>

            <div
              style={{
                padding:
                  "22px",
              }}
            >
              <label
                style={{
                  display:
                    "block",
                  color:
                    "#687780",
                  fontSize:
                    9,
                  letterSpacing:
                    "0.13em",
                }}
              >
                WORKFLOW TEMPLATE
              </label>

              <div
                style={{
                  display:
                    "grid",
                  gridTemplateColumns:
                    "repeat(2, minmax(0,1fr))",
                  gap: 9,
                  marginTop:
                    10,
                }}
              >
                {TEMPLATE_OPTIONS.map(
                  (
                    template
                  ) => {
                    const active =
                      selectedTemplate ===
                      template.label;

                    return (
                      <button
                        key={
                          template.label
                        }
                        type="button"
                        onClick={() =>
                          setSelectedTemplate(
                            template.label
                          )
                        }
                        style={{
                          minHeight:
                            94,
                          padding:
                            "13px 14px",
                          textAlign:
                            "left",
                          border:
                            active
                              ? "1px solid rgba(127,224,247,0.36)"
                              : "1px solid rgba(255,255,255,0.07)",
                          background:
                            active
                              ? "rgba(96,184,210,0.09)"
                              : "rgba(255,255,255,0.018)",
                          color:
                            "#dcebef",
                          cursor:
                            "pointer",
                          borderRadius:
                            4,
                        }}
                      >
                        <div
                          style={{
                            display:
                              "flex",
                            alignItems:
                              "center",
                            gap: 9,
                          }}
                        >
                          <Workflow
                            size={
                              15
                            }
                            color={
                              active
                                ? "#92e8fa"
                                : "#6a7780"
                            }
                          />

                          <strong
                            style={{
                              fontSize:
                                11,
                            }}
                          >
                            {
                              template.label
                            }
                          </strong>
                        </div>

                        <p
                          style={{
                            margin:
                              "8px 0 0",
                            color:
                              "#64727a",
                            fontSize:
                              9,
                            lineHeight:
                              1.55,
                          }}
                        >
                          {
                            template.description
                          }
                        </p>
                      </button>
                    );
                  }
                )}
              </div>

              <label
                style={{
                  display:
                    "block",
                  marginTop:
                    18,
                  color:
                    "#687780",
                  fontSize:
                    9,
                }}
              >
                MISSION NAME
              </label>

              <input
                autoFocus
                value={
                  newMissionTitle
                }
                onChange={(
                  event
                ) =>
                  setNewMissionTitle(
                    event.target.value
                  )
                }
                placeholder="Enter a clear mission name"
                style={{
                  width:
                    "100%",
                  marginTop:
                    9,
                  height:
                    46,
                  padding:
                    "0 13px",
                  border:
                    "1px solid rgba(255,255,255,0.08)",
                  outline:
                    "none",
                  background:
                    "rgba(255,255,255,0.025)",
                  color:
                    "#e6f1f4",
                  fontSize:
                    11,
                  borderRadius:
                    4,
                  boxSizing:
                    "border-box",
                }}
              />

              <label
                style={{
                  display:
                    "block",
                  marginTop:
                    17,
                  color:
                    "#687780",
                  fontSize:
                    9,
                }}
              >
                MISSION OBJECTIVE
              </label>

              <textarea
                value={
                  newMissionObjective
                }
                onChange={(
                  event
                ) =>
                  setNewMissionObjective(
                    event.target.value
                  )
                }
                rows={6}
                placeholder="Describe exactly what NOVA should investigate, analyze, calculate or produce."
                style={{
                  width:
                    "100%",
                  marginTop:
                    9,
                  minHeight:
                    120,
                  resize:
                    "vertical",
                  padding:
                    "12px 13px",
                  border:
                    "1px solid rgba(255,255,255,0.08)",
                  outline:
                    "none",
                  background:
                    "rgba(255,255,255,0.025)",
                  color:
                    "#e6f1f4",
                  fontFamily:
                    "inherit",
                  fontSize:
                    11,
                  lineHeight:
                    1.65,
                  borderRadius:
                    4,
                }}
              />

              <div
                style={{
                  marginTop:
                    18,
                  display:
                    "grid",
                  gridTemplateColumns:
                    "1fr 1fr",
                  gap: 12,
                }}
              >
                <div>
                  <label
                    style={{
                      display:
                        "block",
                      color:
                        "#687780",
                      fontSize:
                        9,
                    }}
                  >
                    PRIORITY
                  </label>

                  <div
                    style={{
                      display:
                        "flex",
                      gap: 7,
                      marginTop:
                        9,
                    }}
                  >
                    {[
                      "LOW",
                      "MEDIUM",
                      "HIGH",
                    ].map(
                      (
                        priority
                      ) => (
                        <button
                          key={
                            priority
                          }
                          type="button"
                          onClick={() =>
                            setNewMissionPriority(
                              priority
                            )
                          }
                          style={{
                            flex:
                              1,
                            height:
                              46,
                            border:
                              newMissionPriority ===
                              priority
                                ? "1px solid rgba(128,224,246,0.34)"
                                : "1px solid rgba(255,255,255,0.07)",
                            background:
                              newMissionPriority ===
                              priority
                                ? "rgba(99,186,209,0.09)"
                                : "rgba(255,255,255,0.02)",
                            color:
                              newMissionPriority ===
                              priority
                                ? "#dcf8fd"
                                : "#697780",
                            fontSize:
                              9,
                            cursor:
                              "pointer",
                            borderRadius:
                              4,
                          }}
                        >
                          {
                            priority
                          }
                        </button>
                      )
                    )}
                  </div>
                </div>

                <div>
                  <label
                    style={{
                      display:
                        "block",
                      color:
                        "#687780",
                      fontSize:
                        9,
                    }}
                  >
                    AUTONOMY POLICY
                  </label>

                  <select
                    value={
                      newMissionAutonomy
                    }
                    onChange={(
                      event
                    ) =>
                      setNewMissionAutonomy(
                        event.target.value
                      )
                    }
                    style={{
                      width:
                        "100%",
                      height:
                        46,
                      marginTop:
                        9,
                      padding:
                        "0 11px",
                      border:
                        "1px solid rgba(255,255,255,0.07)",
                      outline:
                        "none",
                      background:
                        "#0d1114",
                      color:
                        "#dbe7eb",
                      fontSize:
                        10,
                      borderRadius:
                        4,
                    }}
                  >
                    <option>
                      SUPERVISED
                    </option>

                    <option>
                      AUTONOMOUS WITH GATES
                    </option>
                  </select>
                </div>
              </div>

              <label
                style={{
                  display:
                    "block",
                  marginTop:
                    18,
                  color:
                    "#687780",
                  fontSize:
                    9,
                }}
              >
                EVIDENCE PACKAGE
              </label>

              <div
                style={{
                  marginTop:
                    9,
                  padding:
                    "14px",
                  border:
                    "1px solid rgba(117,218,239,0.11)",
                  background:
                    "rgba(72,151,174,0.028)",
                  borderRadius:
                    4,
                }}
              >
                <input
                  ref={
                    missionFileInputRef
                  }
                  type="file"
                  hidden
                  multiple
                  accept=".pdf,.txt,.docx,.csv,.xlsx,.xls,image/png,image/jpeg,image/webp"
                  onChange={
                    handleMissionFileSelection
                  }
                />

                <button
                  type="button"
                  onClick={() =>
                    missionFileInputRef.current?.click()
                  }
                  disabled={
                    uploadingMissionFiles
                  }
                  style={{
                    display:
                      "inline-flex",
                    alignItems:
                      "center",
                    gap: 8,
                    padding:
                      "10px 13px",
                    border:
                      "1px solid rgba(132,226,249,0.27)",
                    background:
                      "rgba(95,184,211,0.07)",
                    color:
                      "#d9f8fd",
                    fontSize:
                      9,
                    fontWeight:
                      800,
                    cursor:
                      uploadingMissionFiles
                        ? "wait"
                        : "pointer",
                    borderRadius:
                      4,
                  }}
                >
                  {uploadingMissionFiles ? (
                    <RefreshCw
                      size={
                        13
                      }
                      style={{
                        animation:
                          "spin 1s linear infinite",
                      }}
                    />
                  ) : (
                    <Paperclip
                      size={
                        13
                      }
                    />
                  )}

                  {uploadingMissionFiles
                    ? "UPLOADING..."
                    : "ADD EVIDENCE FILES"}
                </button>

                {newMissionFiles.length >
                0 ? (
                  <div
                    style={{
                      display:
                        "grid",
                      gap: 7,
                      marginTop:
                        12,
                    }}
                  >
                    {newMissionFiles.map(
                      (
                        file
                      ) => (
                        <div
                          key={
                            file.file_id
                          }
                          style={{
                            display:
                              "flex",
                            alignItems:
                              "center",
                            gap: 10,
                            padding:
                              "10px",
                            border:
                              "1px solid rgba(255,255,255,0.06)",
                            background:
                              "rgba(255,255,255,0.015)",
                            borderRadius:
                              4,
                          }}
                        >
                          {getFileIcon(
                            file
                          )}

                          <div
                            style={{
                              flex:
                                1,
                              minWidth:
                                0,
                            }}
                          >
                            <div
                              style={{
                                overflow:
                                  "hidden",
                                textOverflow:
                                  "ellipsis",
                                whiteSpace:
                                  "nowrap",
                                color:
                                  "#bfdde3",
                                fontSize:
                                  10,
                              }}
                            >
                              {
                                file.filename
                              }
                            </div>

                            <div
                              style={{
                                marginTop:
                                  3,
                                color:
                                  "#596971",
                                fontSize:
                                  7,
                              }}
                            >
                              {(
                                Number(
                                  file.size ||
                                    0
                                ) /
                                1024 /
                                1024
                              ).toFixed(
                                2
                              )}{" "}
                              MB
                            </div>
                          </div>

                          <button
                            type="button"
                            onClick={() =>
                              removeMissionFile(
                                file
                              )
                            }
                            style={{
                              width:
                                30,
                              height:
                                30,
                              display:
                                "grid",
                              placeItems:
                                "center",
                              border:
                                "1px solid rgba(255,255,255,0.06)",
                              background:
                                "rgba(255,255,255,0.02)",
                              color:
                                "#738087",
                              cursor:
                                "pointer",
                            }}
                          >
                            <X
                              size={
                                13
                              }
                            />
                          </button>
                        </div>
                      )
                    )}
                  </div>
                ) : (
                  <div
                    style={{
                      marginTop:
                        12,
                      padding:
                        "18px",
                      border:
                        "1px dashed rgba(255,255,255,0.065)",
                      textAlign:
                        "center",
                      color:
                        "#59676f",
                      fontSize:
                        9,
                    }}
                  >
                    No evidence uploaded yet.
                  </div>
                )}
              </div>

              <div
                style={{
                  display:
                    "flex",
                  justifyContent:
                    "flex-end",
                  gap: 8,
                  marginTop:
                    22,
                  paddingTop:
                    17,
                  borderTop:
                    "1px solid rgba(255,255,255,0.06)",
                }}
              >
                <button
                  type="button"
                  onClick={() => {
                    resetMissionCreationForm();
                    setShowNewMission(
                      false
                    );
                    setMissionError(
                      ""
                    );
                  }}
                  style={{
                    height:
                      44,
                    padding:
                      "0 14px",
                    border:
                      "1px solid rgba(255,255,255,0.07)",
                    background:
                      "rgba(255,255,255,0.02)",
                    color:
                      "#8a969d",
                    fontSize:
                      9,
                    cursor:
                      "pointer",
                  }}
                >
                  CANCEL
                </button>

                <button
                  type="button"
                  onClick={
                    createMission
                  }
                  disabled={
                    !newMissionTitle.trim() ||
                    !newMissionObjective.trim() ||
                    newMissionFiles.length ===
                      0 ||
                    uploadingMissionFiles
                  }
                  style={{
                    height:
                      44,
                    padding:
                      "0 16px",
                    border:
                      "1px solid rgba(130,226,247,0.4)",
                    background:
                      !newMissionTitle.trim() ||
                      !newMissionObjective.trim() ||
                      newMissionFiles.length ===
                        0 ||
                      uploadingMissionFiles
                        ? "rgba(255,255,255,0.025)"
                        : "rgba(95,184,211,0.11)",
                    color:
                      !newMissionTitle.trim() ||
                      !newMissionObjective.trim() ||
                      newMissionFiles.length ===
                        0 ||
                      uploadingMissionFiles
                        ? "#55636b"
                        : "#e0faff",
                    fontSize:
                      9,
                    fontWeight:
                      800,
                    cursor:
                      !newMissionTitle.trim() ||
                      !newMissionObjective.trim() ||
                      newMissionFiles.length ===
                        0 ||
                      uploadingMissionFiles
                        ? "not-allowed"
                        : "pointer",
                  }}
                >
                  <Plus
                    size={
                      13
                    }
                  />{" "}
                  INITIALIZE MISSION
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}

      {/* =========================================================
          EDIT MISSION
      ========================================================== */}
      {showEditMission &&
        selectedMission && (
          <motion.div
            initial={{
              opacity: 0,
            }}
            animate={{
              opacity: 1,
            }}
            style={{
              position:
                "fixed",
              inset: 0,
              zIndex:
                125,
              display:
                "grid",
              placeItems:
                "center",
              padding:
                24,
              background:
                "rgba(0,0,0,0.78)",
              backdropFilter:
                "blur(13px)",
            }}
          >
            <motion.div
              initial={{
                opacity: 0,
                y: 18,
                scale:
                  0.975,
              }}
              animate={{
                opacity: 1,
                y: 0,
                scale: 1,
              }}
              style={{
                width:
                  "min(900px, 100%)",
                maxHeight:
                  "calc(100vh - 48px)",
                overflowY:
                  "auto",
                border:
                  "1px solid rgba(127,225,246,0.19)",
                background:
                  "#080b0e",
                boxShadow:
                  "0 40px 120px rgba(0,0,0,0.70)",
                borderRadius:
                  6,
              }}
            >
              <div
                style={{
                  display:
                    "flex",
                  justifyContent:
                    "space-between",
                  alignItems:
                    "center",
                  gap: 18,
                  padding:
                    "21px 22px",
                  borderBottom:
                    "1px solid rgba(255,255,255,0.06)",
                }}
              >
                <div>
                  <div
                    style={{
                      color:
                        "#687780",
                      fontSize:
                        9,
                      letterSpacing:
                        "0.17em",
                    }}
                  >
                    MISSION EDITOR
                  </div>

                  <h2
                    style={{
                      margin:
                        "8px 0 0",
                      color:
                        "#eaf4f7",
                      fontSize:
                        23,
                    }}
                  >
                    EDIT MISSION
                  </h2>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    setShowEditMission(
                      false
                    );
                    setMissionError(
                      ""
                    );
                  }}
                  style={{
                    width:
                      36,
                    height:
                      36,
                    display:
                      "grid",
                    placeItems:
                      "center",
                    border:
                      "1px solid rgba(255,255,255,0.07)",
                    background:
                      "rgba(255,255,255,0.025)",
                    color:
                      "#7d8a91",
                    cursor:
                      "pointer",
                    borderRadius:
                      4,
                  }}
                >
                  <X
                    size={
                      16
                    }
                  />
                </button>
              </div>

              <div
                style={{
                  padding:
                    "22px",
                }}
              >
                <div
                  style={{
                    padding:
                      "11px 12px",
                    border:
                      "1px solid rgba(239,196,151,0.13)",
                    background:
                      "rgba(156,113,61,0.045)",
                    color:
                      "#9d8b73",
                    fontSize:
                      9,
                    lineHeight:
                      1.55,
                    borderRadius:
                      4,
                  }}
                >
                  Changing mission inputs resets the current
                  execution state so the displayed run always
                  matches the current mission definition.
                </div>

                <label
                  style={{
                    display:
                      "block",
                    marginTop:
                      18,
                    color:
                      "#687780",
                    fontSize:
                      9,
                    letterSpacing:
                      "0.13em",
                  }}
                >
                  MISSION NAME
                </label>

                <input
                  value={
                    editMissionTitle
                  }
                  onChange={(
                    event
                  ) =>
                    setEditMissionTitle(
                      event.target.value
                    )
                  }
                  style={{
                    width:
                      "100%",
                    marginTop:
                      9,
                    height:
                      46,
                    padding:
                      "0 13px",
                    border:
                      "1px solid rgba(255,255,255,0.08)",
                    outline:
                      "none",
                    background:
                      "rgba(255,255,255,0.025)",
                    color:
                      "#e6f1f4",
                    fontSize:
                      11,
                    borderRadius:
                      4,
                    boxSizing:
                      "border-box",
                  }}
                />

                <label
                  style={{
                    display:
                      "block",
                    marginTop:
                      17,
                    color:
                      "#687780",
                    fontSize:
                      9,
                    letterSpacing:
                      "0.13em",
                  }}
                >
                  MISSION OBJECTIVE
                </label>

                <textarea
                  value={
                    editMissionObjective
                  }
                  onChange={(
                    event
                  ) =>
                    setEditMissionObjective(
                      event.target.value
                    )
                  }
                  rows={
                    6
                  }
                  style={{
                    width:
                      "100%",
                    marginTop:
                      9,
                    minHeight:
                      120,
                    resize:
                      "vertical",
                    padding:
                      "12px 13px",
                    border:
                      "1px solid rgba(255,255,255,0.08)",
                    outline:
                      "none",
                    background:
                      "rgba(255,255,255,0.025)",
                    color:
                      "#e6f1f4",
                    fontFamily:
                      "inherit",
                    fontSize:
                      11,
                    lineHeight:
                      1.65,
                    borderRadius:
                      4,
                  }}
                />

                <div
                  style={{
                    display:
                      "grid",
                    gridTemplateColumns:
                      "1fr 1fr",
                    gap: 12,
                    marginTop:
                      17,
                  }}
                >
                  <div>
                    <label
                      style={{
                        display:
                          "block",
                        color:
                          "#687780",
                        fontSize:
                          9,
                      }}
                    >
                      PRIORITY
                    </label>

                    <div
                      style={{
                        display:
                          "flex",
                        gap: 7,
                        marginTop:
                          9,
                      }}
                    >
                      {[
                        "LOW",
                        "MEDIUM",
                        "HIGH",
                      ].map(
                        (
                          priority
                        ) => (
                          <button
                            key={
                              priority
                            }
                            type="button"
                            onClick={() =>
                              setEditMissionPriority(
                                priority
                              )
                            }
                            style={{
                              flex:
                                1,
                              height:
                                46,
                              border:
                                editMissionPriority ===
                                priority
                                  ? "1px solid rgba(128,224,246,0.34)"
                                  : "1px solid rgba(255,255,255,0.07)",
                              background:
                                editMissionPriority ===
                                priority
                                  ? "rgba(99,186,209,0.09)"
                                  : "rgba(255,255,255,0.02)",
                              color:
                                editMissionPriority ===
                                priority
                                  ? "#dcf8fd"
                                  : "#697780",
                              fontSize:
                                9,
                              cursor:
                                "pointer",
                              borderRadius:
                                4,
                            }}
                          >
                            {
                              priority
                            }
                          </button>
                        )
                      )}
                    </div>
                  </div>

                  <div>
                    <label
                      style={{
                        display:
                          "block",
                        color:
                          "#687780",
                        fontSize:
                          9,
                      }}
                    >
                      AUTONOMY POLICY
                    </label>

                    <select
                      value={
                        editMissionAutonomy
                      }
                      onChange={(
                        event
                      ) =>
                        setEditMissionAutonomy(
                          event.target.value
                        )
                      }
                      style={{
                        width:
                          "100%",
                        height:
                          46,
                        marginTop:
                          9,
                        padding:
                          "0 11px",
                        border:
                          "1px solid rgba(255,255,255,0.07)",
                        outline:
                          "none",
                        background:
                          "#0d1114",
                        color:
                          "#dbe7eb",
                        fontSize:
                          10,
                        borderRadius:
                          4,
                      }}
                    >
                      <option>
                        SUPERVISED
                      </option>

                      <option>
                        AUTONOMOUS WITH GATES
                      </option>
                    </select>
                  </div>
                </div>

                <div
                  style={{
                    marginTop:
                      18,
                  }}
                >
                  <div
                    style={{
                      display:
                        "flex",
                      justifyContent:
                        "space-between",
                      alignItems:
                        "center",
                      gap: 10,
                    }}
                  >
                    <label
                      style={{
                        color:
                          "#687780",
                        fontSize:
                          9,
                      }}
                    >
                      EVIDENCE PACKAGE
                    </label>

                    <span
                      style={{
                        color:
                          "#56666e",
                        fontSize:
                          8,
                      }}
                    >
                      {editMissionFiles.length} FILE
                      {editMissionFiles.length ===
                      1
                        ? ""
                        : "S"}
                    </span>
                  </div>

                  <input
                    ref={
                      editFileInputRef
                    }
                    type="file"
                    hidden
                    multiple
                    accept=".pdf,.txt,.docx,.csv,.xlsx,.xls,image/png,image/jpeg,image/webp"
                    onChange={
                      handleEditFileSelection
                    }
                  />

                  <button
                    type="button"
                    onClick={() =>
                      editFileInputRef.current?.click()
                    }
                    disabled={
                      uploadingMissionFiles
                    }
                    style={{
                      display:
                        "inline-flex",
                      alignItems:
                        "center",
                      gap: 8,
                      marginTop:
                        9,
                      padding:
                        "10px 13px",
                      border:
                        "1px solid rgba(132,226,249,0.27)",
                      background:
                        "rgba(95,184,211,0.07)",
                      color:
                        "#d9f8fd",
                      fontSize:
                        9,
                      fontWeight:
                        800,
                      cursor:
                        uploadingMissionFiles
                          ? "wait"
                          : "pointer",
                      borderRadius:
                        4,
                    }}
                  >
                    <Paperclip
                      size={
                        13
                      }
                    />
                    ADD MORE EVIDENCE
                  </button>

                  <div
                    style={{
                      display:
                        "grid",
                      gap: 7,
                      marginTop:
                        10,
                    }}
                  >
                    {editMissionFiles.map(
                      (
                        file
                      ) => (
                        <div
                          key={
                            file.file_id
                          }
                          style={{
                            display:
                              "flex",
                            alignItems:
                              "center",
                            gap: 10,
                            padding:
                              "10px",
                            border:
                              "1px solid rgba(255,255,255,0.06)",
                            background:
                              "rgba(255,255,255,0.015)",
                            borderRadius:
                              4,
                          }}
                        >
                          {getFileIcon(
                            file
                          )}

                          <div
                            style={{
                              flex:
                                1,
                              minWidth:
                                0,
                            }}
                          >
                            <div
                              style={{
                                overflow:
                                  "hidden",
                                textOverflow:
                                  "ellipsis",
                                whiteSpace:
                                  "nowrap",
                                color:
                                  "#bfdde3",
                                fontSize:
                                  10,
                              }}
                            >
                              {
                                file.filename
                              }
                            </div>
                          </div>

                          <button
                            type="button"
                            onClick={() =>
                              removeEditMissionFile(
                                file
                              )
                            }
                            style={{
                              width:
                                30,
                              height:
                                30,
                              display:
                                "grid",
                              placeItems:
                                "center",
                              border:
                                "1px solid rgba(255,255,255,0.06)",
                              background:
                                "rgba(255,255,255,0.02)",
                              color:
                                "#738087",
                              cursor:
                                "pointer",
                            }}
                          >
                            <X
                              size={
                                13
                              }
                            />
                          </button>
                        </div>
                      )
                    )}
                  </div>
                </div>

                <div
                  style={{
                    display:
                      "flex",
                    justifyContent:
                      "flex-end",
                    gap: 8,
                    marginTop:
                      22,
                    paddingTop:
                      17,
                    borderTop:
                      "1px solid rgba(255,255,255,0.06)",
                  }}
                >
                  <button
                    type="button"
                    onClick={() => {
                      setShowEditMission(
                        false
                      );
                      setMissionError(
                        ""
                      );
                    }}
                    style={{
                      height:
                        44,
                      padding:
                        "0 14px",
                      border:
                        "1px solid rgba(255,255,255,0.07)",
                      background:
                        "rgba(255,255,255,0.02)",
                      color:
                        "#8a969d",
                      fontSize:
                        9,
                      cursor:
                        "pointer",
                    }}
                  >
                    CANCEL
                  </button>

                  <button
                    type="button"
                    onClick={
                      saveMissionEdit
                    }
                    disabled={
                      savingMissionEdit ||
                      uploadingMissionFiles ||
                      !editMissionTitle.trim() ||
                      !editMissionObjective.trim() ||
                      editMissionFiles.length ===
                        0
                    }
                    style={{
                      height:
                        44,
                      padding:
                        "0 16px",
                      border:
                        "1px solid rgba(130,226,247,0.4)",
                      background:
                        savingMissionEdit ||
                        uploadingMissionFiles ||
                        !editMissionTitle.trim() ||
                        !editMissionObjective.trim() ||
                        editMissionFiles.length ===
                          0
                          ? "rgba(255,255,255,0.025)"
                          : "rgba(95,184,211,0.11)",
                      color:
                        savingMissionEdit ||
                        uploadingMissionFiles ||
                        !editMissionTitle.trim() ||
                        !editMissionObjective.trim() ||
                        editMissionFiles.length ===
                          0
                          ? "#55636b"
                          : "#e0faff",
                      fontSize:
                        9,
                      fontWeight:
                        800,
                      cursor:
                        savingMissionEdit ||
                        uploadingMissionFiles ||
                        !editMissionTitle.trim() ||
                        !editMissionObjective.trim() ||
                        editMissionFiles.length ===
                          0
                          ? "not-allowed"
                          : "pointer",
                    }}
                  >
                    {savingMissionEdit ? (
                      <RefreshCw
                        size={
                          13
                        }
                        style={{
                          animation:
                            "spin 1s linear infinite",
                        }}
                      />
                    ) : (
                      <Check
                        size={
                          13
                        }
                      />
                    )}

                    SAVE MISSION
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}

      <style>
        {`
          @keyframes spin {
            from {
              transform: rotate(0deg);
            }
            to {
              transform: rotate(360deg);
            }
          }

          @media (max-width: 1100px) {
            .nova-mission-responsive {
              grid-template-columns: 1fr !important;
            }
          }
        `}
      </style>
    </>
  );
}