import { useEffect, useRef, useState } from "react";

import {
  ArrowUp,
  Cpu,
  LockKeyhole,
  MessageSquare,
  RotateCcw,
  Sparkles,
  Activity,
  Paperclip,
  FileText,
  Image as ImageIcon,
  X,
  LoaderCircle,
  BrainCircuit,
  CheckCircle2,
  AlertCircle,
  Download,
  ChevronDown,
  Database,
  FolderOpen,
} from "lucide-react";

import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";

const API_URL =
  "http://127.0.0.1:8001";

const MODEL =
  "llama3.2:latest";

const ICON_PROPS = {
  "aria-hidden": true,
  focusable: false,
};

const welcomeMessage = {
  id: "nova-welcome",
  role: "assistant",
  content:
    "Hi! I'm NOVA. How can I help you today?",
  time: new Date(),
  attachments: [],
  agent: null,
};

function formatTime(date) {
  return new Intl.DateTimeFormat(
    "en-IN",
    {
      hour: "2-digit",
      minute: "2-digit",
    }
  ).format(date);
}

function createId(prefix = "msg") {
  return `${prefix}-${Date.now()}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
}

function getFileIcon(
  fileType = ""
) {
  if (
    fileType.startsWith(
      "image/"
    )
  ) {
    return (
      <ImageIcon
        size={14}
        {...ICON_PROPS}
      />
    );
  }

  return (
    <FileText
      size={14}
      {...ICON_PROPS}
    />
  );
}

function normalizeArtifact(
  art,
  index = 0
) {
  const filePath = String(
    art?.file_path ||
      art?.filePath ||
      ""
  )
    .replace(
      /\\/g,
      "/"
    )
    .replace(
      /^\/+/,
      ""
    );

  const fileName =
    art?.file_name ||
    art?.fileName ||
    (
      filePath
        ? filePath
            .split("/")
            .pop()
        : `artifact-${index}`
    );

  const extension =
    art?.extension ||
    (
      fileName.includes(".")
        ? `.${fileName
            .split(".")
            .pop()
            .toLowerCase()}`
        : ""
    );

  const sizeBytes =
    typeof art?.size_bytes ===
    "number"
      ? art.size_bytes
      : typeof art?.sizeBytes ===
          "number"
        ? art.sizeBytes
        : null;

  const available =
    art?.available !== false;

  return {
    stepId:
      art?.step_id ||
      art?.stepId ||
      `step-${index}`,

    filePath,

    fileName,

    extension,

    sizeBytes,

    verificationStatus:
      art?.verification_status ||
      art?.verificationStatus ||
      "verified",

    downloadUrl:
      available &&
      filePath
        ? getDownloadUrl(
            filePath
          )
        : null,

    available,
  };
}

function mapHistoryMessage(
  message
) {
  let agentObj = null;

  if (
    message.agent &&
    typeof message.agent ===
      "object"
  ) {
    const rawArtifacts =
      Array.isArray(
        message.agent
          .artifacts
      )
        ? message.agent
            .artifacts
        : [];

    const artifacts =
      rawArtifacts
        .map(
          normalizeArtifact
        )
        .filter(
          (artifact) => {
            const normalized =
              String(
                artifact.filePath ||
                  ""
              ).toLowerCase();

            if (!normalized) {
              return false;
            }

            if (
              normalized.startsWith(
                "input/"
              ) ||
              normalized.startsWith(
                "workspace/input/"
              ) ||
              normalized.includes(
                "/input/"
              )
            ) {
              return false;
            }

            return (
              normalized.startsWith(
                "output/"
              ) ||
              normalized.startsWith(
                "workspace/output/"
              )
            );
          }
        )
        .filter(
          (artifact) =>
            Boolean(
              artifact.downloadUrl
            )
        );

    agentObj = {
      plan:
        message.agent.plan ||
        null,

      execution:
        message.agent.execution ||
        null,

      artifacts,
    };
  }

  return {
    id: message.id,

    role: message.role,

    content:
      message.content,

    time: new Date(
      message.created_at
    ),

    attachments:
      (
        message.attachments ||
        []
      ).map(
        (attachment) => ({
          name:
            attachment.filename,

          size:
            Number(
              attachment.size ||
                0
            ),

          type:
            attachment.content_type ||
            "",

          file_id:
            attachment.file_id,
        })
      ),

    agent: agentObj,
  };
}

function emitAvatarState(
  state,
  audioLevel = 0
) {
  window.dispatchEvent(
    new CustomEvent(
      "nova:avatar-state",
      {
        detail: {
          state,
          audioLevel,
          timestamp:
            Date.now(),
        },
      }
    )
  );
}

function isSpreadsheetFile(
  file
) {
  if (
    !file?.name &&
    !file?.extension
  ) {
    return false;
  }

  const extension =
    file.extension ||
    file.name
      ?.split(".")
      .pop()
      ?.toLowerCase();

  return (
    extension === "xlsx" ||
    extension === ".xlsx" ||
    extension === "xls" ||
    extension === ".xls" ||
    extension === "csv" ||
    extension === ".csv"
  );
}

function isPresentationGenerationRequest(
  message
) {
  const text = String(
    message || ""
  )
    .toLowerCase()
    .trim();

  if (!text) {
    return false;
  }

  const explicitSignals = [
    "create a powerpoint",
    "create powerpoint",
    "generate a powerpoint",
    "generate powerpoint",
    "make a powerpoint",
    "make powerpoint",
    "prepare a powerpoint",
    "prepare powerpoint",
    "write a powerpoint",
    "write powerpoint",
    "build a powerpoint",
    "build powerpoint",

    "create a presentation",
    "create presentation",
    "generate a presentation",
    "generate presentation",
    "make a presentation",
    "make presentation",
    "prepare a presentation",
    "prepare presentation",
    "build a presentation",
    "build presentation",
    "write a presentation",
    "write presentation",

    "create a pptx",
    "generate a pptx",
    "make a pptx",
    "prepare a pptx",
    "build a pptx",

    "create a slide deck",
    "create slide deck",
    "generate a slide deck",
    "generate slide deck",
    "make a slide deck",
    "make slide deck",
    "prepare a slide deck",
    "prepare slide deck",
    "build a slide deck",

    "create slides",
    "generate slides",
    "make slides",
    "prepare slides",
    "build slides",

    "create powerpoint presentation",
    "generate powerpoint presentation",
    "make powerpoint presentation",
    "prepare powerpoint presentation",
    "build powerpoint presentation",
  ];

  const naturalPresentationPattern =
    /\b(create|generate|make|prepare|write|produce|build|design|draft)\b[\s\S]{0,180}\b(powerpoint|presentation|pptx|slide deck|slides)\b/i;

  const presentationTopicPattern =
    /\b(powerpoint|presentation|pptx|slide deck|slides)\b[\s\S]{0,120}\b(about|on|for|regarding)\b/i;

  const presentationFilePattern =
    /\b(powerpoint|presentation|pptx|slide deck|slides)\b/i;

  const actionPattern =
    /\b(create|generate|make|prepare|write|produce|build|design|draft)\b/i;

  return (
    explicitSignals.some(
      (signal) =>
        text.includes(signal)
    ) ||
    naturalPresentationPattern.test(
      text
    ) ||
    presentationTopicPattern.test(
      text
    ) ||
    (
      presentationFilePattern.test(
        text
      ) &&
      actionPattern.test(text)
    )
  );
}

function isAgentRequest(
  message
) {
  const text = String(
    message || ""
  )
    .toLowerCase()
    .trim();

  const agentSignals = [
    "local knowledge",
    "knowledge base",
    "knowledge vault",
    "search my documents",
    "search the documents",
    "search documents",
    "find in my documents",
    "find in the knowledge",
    "look up in my documents",
    "retrieve from",
    "search the local",

    "analyze the document",
    "analyse the document",
    "analyze the file",
    "analyse the file",

    "create a plan",
    "make a plan",
    "plan this task",
    "execute this",
    "execute the task",
    "perform this task",
    "run this task",
    "agent",
    "mission",
    "workflow",
    "investigate",
    "root cause",

    "execute python",
    "run python",
    "using python",
    "with python",
    "execute code",
    "run code",
    "calculate using python",
    "calculate in python",
    "compute using python",
    "compute in python",
    "solve using python",
    "solve in python",
    "python calculation",
    "python computation",
    "python program",
    "write python code",
    "run this python",
    "execute this python",
    "code execution",

    "calculate ",
    "calculate\t",
    "compute ",
    "compute\t",
    "factorial",
    "fibonacci",
    "arithmetic",
    "mathematical calculation",
    "math calculation",
    "solve this equation",
    "solve the equation",
    "calculate the sum",
    "calculate the average",
    "calculate the maximum",
    "calculate the minimum",

    "spreadsheet",
    "excel",
    "excel file",
    "excel sheet",
    "excel workbook",
    "workbook",
    "worksheet",
    "csv",
    ".csv",
    ".xlsx",
    ".xls",
    "analyze spreadsheet",
    "analyse spreadsheet",
    "analyze the spreadsheet",
    "analyse the spreadsheet",
    "analyze excel",
    "analyse excel",
    "analyze the excel",
    "analyse the excel",
    "spreadsheet analysis",
    "spreadsheet statistics",
    "excel analysis",
    "calculate from spreadsheet",
    "calculate from excel",
    "total revenue from",
    "average revenue from",
    "sales analysis",
    "analyze sales",
    "analyse sales",

    "create a docx",
    "create docx",
    "generate a docx",
    "generate docx",
    "write a docx",
    "write docx",
    "make a docx",
    "create a word document",
    "create word document",
    "generate a word document",
    "generate word document",
    "write a word document",
    "write word document",
    "create a word file",
    "create word file",
    "generate a word file",
    "generate word file",
    "make a word document",
    ".docx",

    "create a pdf",
    "generate a pdf",
    "write a pdf",
    ".pdf",

    "create an excel",
    "create excel",
    "generate an excel",
    "generate excel",

    "create a powerpoint",
    "create powerpoint",
    "generate a powerpoint",
    "generate powerpoint",
    "make a powerpoint",
    "make powerpoint",
    "prepare a powerpoint",
    "prepare powerpoint",
    "write a powerpoint",
    "write powerpoint",
    "build a powerpoint",
    "build powerpoint",
    "create a pptx",
    "generate a pptx",
    "make a pptx",
    ".pptx",

    "create a presentation",
    "create presentation",
    "generate a presentation",
    "generate presentation",
    "make a presentation",
    "make presentation",
    "prepare a presentation",
    "prepare presentation",
    "build a presentation",
    "build presentation",
    "write a presentation",
    "write presentation",

    "create a slide deck",
    "create slide deck",
    "generate a slide deck",
    "generate slide deck",
    "make a slide deck",
    "make slide deck",
    "prepare a slide deck",
    "prepare slide deck",
    "build a slide deck",
    "build slide deck",

    "create slides",
    "generate slides",
    "make slides",
    "prepare slides",
    "build slides",

    "create a chart",
    "create chart",
    "generate a chart",
    "generate chart",
    "bar chart",
    "line chart",
    "pie chart",
    "scatter plot",
    "visual summary",
    "plot the data",
    "visualize",
    "visualise",

    "create a file",
    "create file",
    "generate a file",
    "generate file",
    "write a file",
    "write file",
    "save this to",
    "save it to",
  ];

  const naturalDocumentPattern =
    /\b(create|generate|write|make|prepare|draft|produce|build)\b[\s\S]{0,120}\b(document|docx|word document|word file|report|proposal|letter|summary|notes|documentation)\b/i;

  const naturalComputationPattern =
    /\b(calculate|compute|solve|evaluate|find)\b[\s\S]{0,120}\b(factorial|fibonacci|equation|average|sum|total|maximum|minimum|percentage|prime|power|square|cube|using python|with python|in python)\b/i;

  const naturalSpreadsheetPattern =
    /\b(analyze|analyse|inspect|read|review|summarize|summarise|calculate|compute|find|compare|identify|show)\b[\s\S]{0,120}\b(spreadsheet|excel|workbook|worksheet|csv|xlsx|xls|sales data|sales sheet|sales file|table)\b/i;

  const naturalChartPattern =
    /\b(create|generate|make|draw|plot|show)\b[\s\S]{0,120}\b(chart|graph|plot|bar chart|line chart|pie chart|scatter plot|visual summary|visualization)\b/i;

  return (
    agentSignals.some(
      (signal) =>
        text.includes(signal)
    ) ||
    naturalDocumentPattern.test(
      text
    ) ||
    naturalComputationPattern.test(
      text
    ) ||
    naturalSpreadsheetPattern.test(
      text
    ) ||
    naturalChartPattern.test(
      text
    ) ||
    isPresentationGenerationRequest(
      text
    )
  );
}

function isDocumentGenerationRequest(
  message
) {
  const text = String(
    message || ""
  )
    .toLowerCase()
    .trim();

  const explicitDocumentSignals = [
    "create a docx",
    "create docx",
    "generate a docx",
    "generate docx",
    "write a docx",
    "write docx",
    "make a docx",
    "create a word document",
    "create word document",
    "generate a word document",
    "generate word document",
    "write a word document",
    "write word document",
    "create a word file",
    "create word file",
    "generate a word file",
    "generate word file",
    "make a word document",
    ".docx",
  ];

  const naturalDocumentPattern =
    /\b(create|generate|write|make|prepare|draft|produce|build)\b[\s\S]{0,120}\b(document|docx|word document|word file|report|proposal|letter|summary|notes|documentation)\b/i;

  return (
    explicitDocumentSignals.some(
      (signal) =>
        text.includes(signal)
    ) ||
    naturalDocumentPattern.test(
      text
    )
  );
}

function isCodeExecutionRequest(
  message
) {
  const text = String(
    message || ""
  )
    .toLowerCase()
    .trim();

  const directSignals = [
    "execute python",
    "run python",
    "using python",
    "with python",
    "in python",
    "calculate using python",
    "calculate in python",
    "compute using python",
    "compute in python",
    "solve using python",
    "solve in python",
    "execute code",
    "run code",
    "run this code",
    "execute this code",
    "code execution",
    "python calculation",
    "python computation",
    "python program",
    "factorial",
    "fibonacci",
  ];

  const calculationPattern =
    /\b(calculate|compute|solve|evaluate|find)\b[\s\S]{0,100}\b(sum|average|total|factorial|fibonacci|equation|percentage|maximum|minimum|prime|power|square|cube|using python|with python|in python)\b/i;

  return (
    directSignals.some(
      (signal) =>
        text.includes(signal)
    ) ||
    calculationPattern.test(
      text
    )
  );
}

function isSpreadsheetRequest(
  message
) {
  const text = String(
    message || ""
  )
    .toLowerCase()
    .trim();

  const directSignals = [
    "spreadsheet",
    "excel",
    "excel file",
    "excel sheet",
    "excel workbook",
    "workbook",
    "worksheet",
    "csv",
    ".csv",
    ".xlsx",
    ".xls",
    "spreadsheet analysis",
    "spreadsheet statistics",
    "excel analysis",
    "analyze spreadsheet",
    "analyse spreadsheet",
    "analyze the spreadsheet",
    "analyse the spreadsheet",
    "analyze excel",
    "analyse excel",
    "analyze the excel",
    "analyse the excel",
    "calculate from spreadsheet",
    "calculate from excel",
    "sales analysis",
    "analyze sales",
    "analyse sales",
    "analyze sales data",
    "analyse sales data",
  ];

  const naturalPattern =
    /\b(analyze|analyse|inspect|read|review|summarize|summarise|calculate|compute|find|compare|identify|show)\b[\s\S]{0,120}\b(spreadsheet|excel|workbook|worksheet|csv|xlsx|xls|sales data|sales sheet|sales file|table)\b/i;

  return (
    directSignals.some(
      (signal) =>
        text.includes(signal)
    ) ||
    naturalPattern.test(
      text
    )
  );
}

function getStepStatusIcon(
  status
) {
  const norm = String(
    status || ""
  ).toLowerCase();

  if (
    norm === "completed" ||
    norm === "success"
  ) {
    return (
      <CheckCircle2
        size={13}
        {...ICON_PROPS}
      />
    );
  }

  if (
    norm === "failed" ||
    norm === "error"
  ) {
    return (
      <AlertCircle
        size={13}
        {...ICON_PROPS}
      />
    );
  }

  return (
    <Activity
      size={13}
      {...ICON_PROPS}
    />
  );
}

function getWorkflowTitle(
  plan,
  execution,
  artifacts = []
) {
  if (
    plan?.title &&
    typeof plan.title ===
      "string"
  ) {
    return plan.title;
  }

  const steps =
    plan?.steps || [];

  const hasDocWriter =
    steps.some(
      (step) =>
        step.tool ===
          "document_writer" ||
        step.tool ===
          "pdf_writer" ||
        step.tool ===
          "pptx_writer" ||
        step.title
          ?.toLowerCase()
          .includes(
            "document"
          ) ||
        step.title
          ?.toLowerCase()
          .includes(
            "docx"
          )
    );

  const hasDocArtifact =
    artifacts.some(
      (artifact) =>
        artifact.extension ===
          ".docx" ||
        artifact.extension ===
          ".pdf" ||
        artifact.extension ===
          ".txt" ||
        artifact.extension ===
          ".md" ||
        artifact.extension ===
          ".pptx"
    );

  if (
    hasDocWriter ||
    hasDocArtifact
  ) {
    return "Document generation";
  }

  const hasVault =
    steps.some(
      (step) =>
        step.tool
          ?.toLowerCase()
          .includes(
            "vault"
          ) ||
        step.tool
          ?.toLowerCase()
          .includes(
            "search"
          ) ||
        step.title
          ?.toLowerCase()
          .includes(
            "retrieval"
          ) ||
        step.title
          ?.toLowerCase()
          .includes(
            "search"
          )
    );

  if (hasVault) {
    return "Knowledge retrieval";
  }

  const hasSpreadsheet =
    steps.some(
      (step) =>
        step.tool
          ?.toLowerCase()
          .includes(
            "excel"
          ) ||
        step.tool
          ?.toLowerCase()
          .includes(
            "csv"
          ) ||
        step.tool
          ?.toLowerCase()
          .includes(
            "spreadsheet"
          ) ||
        step.title
          ?.toLowerCase()
          .includes(
            "spreadsheet"
          ) ||
        step.title
          ?.toLowerCase()
          .includes(
            "excel"
          )
    );

  if (hasSpreadsheet) {
    return "Spreadsheet workflow";
  }

  const hasCode =
    steps.some(
      (step) =>
        step.tool
          ?.toLowerCase()
          .includes(
            "python"
          ) ||
        step.tool
          ?.toLowerCase()
          .includes(
            "code"
          ) ||
        step.tool
          ?.toLowerCase()
          .includes(
            "calculator"
          ) ||
        step.title
          ?.toLowerCase()
          .includes(
            "compute"
          ) ||
        step.title
          ?.toLowerCase()
          .includes(
            "python"
          ) ||
        step.title
          ?.toLowerCase()
          .includes(
            "execute"
          )
    );

  if (hasCode) {
    return "Computation workflow";
  }

  return "Agent workflow";
}

function getWorkflowSubtitle(
  status = ""
) {
  const norm = String(
    status || ""
  ).toLowerCase();

  if (
    norm === "completed" ||
    norm === "success"
  ) {
    return "Task completed successfully";
  }

  if (
    norm === "failed" ||
    norm === "error"
  ) {
    return "Task execution encountered errors";
  }

  if (
    norm === "blocked"
  ) {
    return "Task execution was blocked";
  }

  if (
    norm === "executing" ||
    norm === "in_progress" ||
    norm === "running"
  ) {
    return "NOVA is executing the workflow";
  }

  if (
    norm === "cancelled" ||
    norm === "canceled" ||
    norm === "stopped"
  ) {
    return "Task execution was stopped";
  }

  return "Workflow in progress";
}

function getDownloadUrl(
  filePath
) {
  if (!filePath) {
    return null;
  }

  const normalizedPath =
    String(filePath)
      .replace(
        /\\/g,
        "/"
      )
      .replace(
        /^\/+/,
        ""
      );

  if (!normalizedPath) {
    return null;
  }

  const normalized =
    normalizedPath.toLowerCase();

  if (
    normalized.startsWith(
      "input/"
    ) ||
    normalized.startsWith(
      "workspace/input/"
    ) ||
    normalized.includes(
      "/input/"
    )
  ) {
    return null;
  }

  if (
    !normalized.startsWith(
      "output/"
    ) &&
    !normalized.startsWith(
      "workspace/output/"
    )
  ) {
    return null;
  }

  const pathParts =
    normalizedPath
      .split("/")
      .filter(Boolean)
      .map(
        (part) =>
          encodeURIComponent(
            part
          )
      );

  return `${API_URL}/api/chat/download/${pathParts.join(
    "/"
  )}`;
}

function getAgentArtifacts(
  execution
) {
  if (!execution?.context) {
    return [];
  }

  return Object.entries(
    execution.context
  )
    .map(
      ([stepId, result]) => {
        if (
          !result ||
          typeof result !==
            "object" ||
          !result.file_path
        ) {
          return null;
        }

        const artifact =
          normalizeArtifact(
            {
              ...result,
              step_id:
                stepId,
            }
          );

        if (
          !artifact.downloadUrl
        ) {
          return null;
        }

        return artifact;
      }
    )
    .filter(Boolean);
}

function formatArtifactSize(
  sizeBytes
) {
  if (
    typeof sizeBytes !==
      "number" ||
    sizeBytes <= 0
  ) {
    return "";
  }

  if (
    sizeBytes < 1024
  ) {
    return `${sizeBytes} B`;
  }

  if (
    sizeBytes <
    1024 * 1024
  ) {
    return `${(
      sizeBytes / 1024
    ).toFixed(1)} KB`;
  }

  return `${(
    sizeBytes /
    (1024 * 1024)
  ).toFixed(2)} MB`;
}

function normalizeVaultList(
  payload
) {
  if (Array.isArray(payload)) {
    return payload;
  }

  if (
    Array.isArray(
      payload?.vaults
    )
  ) {
    return payload.vaults;
  }

  if (
    Array.isArray(
      payload?.items
    )
  ) {
    return payload.items;
  }

  if (
    Array.isArray(
      payload?.data
    )
  ) {
    return payload.data;
  }

  return [];
}

function normalizeVaultFiles(
  payload
) {
  const rawFiles = Array.isArray(
    payload
  )
    ? payload
    : Array.isArray(
        payload?.files
      )
      ? payload.files
      : Array.isArray(
          payload?.items
        )
        ? payload.items
        : Array.isArray(
            payload?.data
          )
          ? payload.data
          : [];

  return rawFiles.filter(
    (file) =>
      file &&
      (
        !file.status ||
        file.status ===
          "active"
      )
  );
}

function getVaultId(
  vault
) {
  return String(
    vault?.vault_id ||
      vault?.id ||
      ""
  ).trim();
}

function getVaultName(
  vault
) {
  return String(
    vault?.name ||
      vault?.vault_name ||
      vault?.title ||
      getVaultId(vault) ||
      "Unnamed vault"
  ).trim();
}

function getVaultFileId(
  file
) {
  return String(
    file?.file_id ||
      file?.id ||
      ""
  ).trim();
}

function getVaultFileName(
  file
) {
  return String(
    file?.filename ||
      file?.name ||
      file?.original_filename ||
      getVaultFileId(file) ||
      "Unnamed file"
  ).trim();
}

function NovaMarkdown({
  content,
}) {
  return (
    <div className="nova-markdown">
      <ReactMarkdown
        components={{
          h1: ({
            children,
          }) => (
            <h1>
              {children}
            </h1>
          ),

          h2: ({
            children,
          }) => (
            <h2>
              {children}
            </h2>
          ),

          h3: ({
            children,
          }) => (
            <h3>
              {children}
            </h3>
          ),

          h4: ({
            children,
          }) => (
            <h4>
              {children}
            </h4>
          ),

          p: ({
            children,
          }) => (
            <p>
              {children}
            </p>
          ),

          strong: ({
            children,
          }) => (
            <strong>
              {children}
            </strong>
          ),

          em: ({
            children,
          }) => (
            <em>
              {children}
            </em>
          ),

          ul: ({
            children,
          }) => (
            <ul>
              {children}
            </ul>
          ),

          ol: ({
            children,
          }) => (
            <ol>
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

          blockquote: ({
            children,
          }) => (
            <blockquote>
              {children}
            </blockquote>
          ),

          hr: () => (
            <hr />
          ),

          a: ({
            href,
            children,
          }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
            >
              {children}
            </a>
          ),

          code: ({
            inline,
            className,
            children,
          }) => {
            if (inline) {
              return (
                <code
                  className={
                    className
                  }
                >
                  {children}
                </code>
              );
            }

            return (
              <pre className="nova-markdown-code-block">
                <code
                  className={
                    className
                  }
                >
                  {children}
                </code>
              </pre>
            );
          },

          table: ({
            children,
          }) => (
            <div className="nova-markdown-table-wrap">
              <table>
                {children}
              </table>
            </div>
          ),

          thead: ({
            children,
          }) => (
            <thead>
              {children}
            </thead>
          ),

          tbody: ({
            children,
          }) => (
            <tbody>
              {children}
            </tbody>
          ),

          tr: ({
            children,
          }) => (
            <tr>
              {children}
            </tr>
          ),

          th: ({
            children,
          }) => (
            <th>
              {children}
            </th>
          ),

          td: ({
            children,
          }) => (
            <td>
              {children}
            </td>
          ),
        }}
      >
        {content || ""}
      </ReactMarkdown>
    </div>
  );
}

export default function ChatWindow({
  conversationId,
  onConversationChange,
  onConversationSaved,
  onNewConversation,
}) {
  const [
    messages,
    setMessages,
  ] = useState([
    welcomeMessage,
  ]);

  const [
    input,
    setInput,
  ] = useState("");

  const [
    status,
    setStatus,
  ] = useState("IDLE");

  const [
    error,
    setError,
  ] = useState("");

  const [
    isSending,
    setIsSending,
  ] = useState(false);

  const [
    selectedFiles,
    setSelectedFiles,
  ] = useState([]);

  const [
    isLoadingConversation,
    setIsLoadingConversation,
  ] = useState(false);

  const [
    activeModel,
    setActiveModel,
  ] = useState(null);

  const [
    vaults,
    setVaults,
  ] = useState([]);

  const [
    selectedVaultId,
    setSelectedVaultId,
  ] = useState("");

  const [
    vaultFiles,
    setVaultFiles,
  ] = useState([]);

  const [
    selectedVaultFileIds,
    setSelectedVaultFileIds,
  ] = useState([]);

  const [
    isLoadingVaults,
    setIsLoadingVaults,
  ] = useState(false);

  const [
    isLoadingVaultFiles,
    setIsLoadingVaultFiles,
  ] = useState(false);

  const [
    vaultContextOpen,
    setVaultContextOpen,
  ] = useState(false);

  const [
    vaultError,
    setVaultError,
  ] = useState("");

  const messagesEndRef =
    useRef(null);

  const textareaRef =
    useRef(null);

  const fileInputRef =
    useRef(null);

  const idleTimerRef =
    useRef(null);

  useEffect(() => {
    return () => {
      if (
        idleTimerRef.current
      ) {
        window.clearTimeout(
          idleTimerRef.current
        );
      }
    };
  }, []);

  useEffect(() => {
    let cancelled =
      false;

    const loadVaults =
      async () => {
        setIsLoadingVaults(
          true
        );

        setVaultError("");

        try {
          const response =
            await fetch(
              `${API_URL}/api/knowledge/vaults`
            );

          if (!response.ok) {
            throw new Error(
              "Unable to load Knowledge Vaults."
            );
          }

          const data =
            await response.json();

          const normalized =
            normalizeVaultList(
              data
            );

          if (
            cancelled
          ) {
            return;
          }

          setVaults(
            normalized
          );
        } catch (
          requestError
        ) {
          if (
            cancelled
          ) {
            return;
          }

          console.error(
            "Knowledge Vault loading error:",
            requestError
          );

          setVaultError(
            requestError?.message ||
              "Unable to load Knowledge Vaults."
          );

          setVaults([]);
        } finally {
          if (
            !cancelled
          ) {
            setIsLoadingVaults(
              false
            );
          }
        }
      };

    loadVaults();

    return () => {
      cancelled =
        true;
    };
  }, []);

  useEffect(() => {
    let cancelled =
      false;

    const loadVaultFiles =
      async () => {
        setSelectedVaultFileIds(
          []
        );

        setVaultFiles(
          []
        );

        setVaultError("");

        if (
          !selectedVaultId
        ) {
          setIsLoadingVaultFiles(
            false
          );

          return;
        }

        setIsLoadingVaultFiles(
          true
        );

        try {
          const response =
            await fetch(
              `${API_URL}/api/knowledge/vaults/${encodeURIComponent(
                selectedVaultId
              )}/files`
            );

          if (!response.ok) {
            const errorText =
              await response.text();

            throw new Error(
              errorText ||
                "Unable to load files from the selected vault."
            );
          }

          const data =
            await response.json();

          const normalized =
            normalizeVaultFiles(
              data
            );

          if (
            cancelled
          ) {
            return;
          }

          setVaultFiles(
            normalized
          );
        } catch (
          requestError
        ) {
          if (
            cancelled
          ) {
            return;
          }

          console.error(
            "Knowledge Vault file loading error:",
            requestError
          );

          setVaultError(
            requestError?.message ||
              "Unable to load files from the selected vault."
          );

          setVaultFiles([]);
        } finally {
          if (
            !cancelled
          ) {
            setIsLoadingVaultFiles(
              false
            );
          }
        }
      };

    loadVaultFiles();

    return () => {
      cancelled =
        true;
    };
  }, [
    selectedVaultId,
  ]);

  useEffect(() => {
    let cancelled =
      false;

    const loadConversation =
      async () => {
        if (!conversationId) {
          setMessages([
            welcomeMessage,
          ]);

          setStatus(
            "IDLE"
          );

          setError("");

          setActiveModel(
            null
          );

          emitAvatarState(
            "idle"
          );

          return;
        }

        setIsLoadingConversation(
          true
        );

        setError("");

        emitAvatarState(
          "idle"
        );

        try {
          const response =
            await fetch(
              `${API_URL}/api/history/conversations/${encodeURIComponent(
                conversationId
              )}`
            );

          if (!response.ok) {
            throw new Error(
              "Unable to load this conversation."
            );
          }

          const data =
            await response.json();

          if (cancelled) {
            return;
          }

          setMessages(
            data.messages?.length
              ? data.messages.map(
                  mapHistoryMessage
                )
              : [
                  welcomeMessage,
                ]
          );

          setStatus(
            "IDLE"
          );

          emitAvatarState(
            "idle"
          );
        } catch (
          requestError
        ) {
          if (cancelled) {
            return;
          }

          console.error(
            "Conversation loading error:",
            requestError
          );

          setError(
            requestError?.message ||
              "Unable to load conversation."
          );

          setMessages([
            welcomeMessage,
          ]);

          emitAvatarState(
            "idle"
          );
        } finally {
          if (!cancelled) {
            setIsLoadingConversation(
              false
            );
          }
        }
      };

    loadConversation();

    return () => {
      cancelled =
        true;
    };
  }, [
    conversationId,
  ]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView(
      {
        behavior:
          "smooth",
        block:
          "end",
      }
    );
  }, [
    messages,
    status,
    isLoadingConversation,
  ]);

  const autoResize =
    () => {
      const textarea =
        textareaRef.current;

      if (!textarea) {
        return;
      }

      textarea.style.height =
        "auto";

      textarea.style.height =
        `${Math.min(
          textarea.scrollHeight,
          180
        )}px`;
    };

  const handleInputChange =
    (
      event
    ) => {
      setInput(
        event.target.value
      );

      requestAnimationFrame(
        autoResize
      );
    };

  const handleVaultChange =
    (
      event
    ) => {
      const nextVaultId =
        String(
          event.target.value ||
            ""
        ).trim();

      setSelectedVaultId(
        nextVaultId
      );

      setSelectedVaultFileIds(
        []
      );

      setVaultError("");

      if (
        !nextVaultId
      ) {
        setVaultContextOpen(
          false
        );
      }
    };

  const toggleVaultFile =
    (
      fileId
    ) => {
      const normalizedId =
        String(
          fileId || ""
        ).trim();

      if (
        !normalizedId
      ) {
        return;
      }

      setSelectedVaultFileIds(
        (current) =>
          current.includes(
            normalizedId
          )
            ? current.filter(
                (id) =>
                  id !==
                  normalizedId
              )
            : [
                ...current,
                normalizedId,
              ]
      );

      setVaultError("");
    };

  const clearKnowledgeScope =
    () => {
      setSelectedVaultId(
        ""
      );

      setSelectedVaultFileIds(
        []
      );

      setVaultFiles(
        []
      );

      setVaultContextOpen(
        false
      );

      setVaultError("");
    };

  const handleFileSelection =
    (
      event
    ) => {
      const files =
        Array.from(
          event.target.files ||
            []
        );

      if (!files.length) {
        return;
      }

      setError("");

      const maxSize =
        20 *
        1024 *
        1024;

      const validFiles =
        files.filter(
          (file) =>
            file.size <=
            maxSize
        );

      const oversizedFiles =
        files.filter(
          (file) =>
            file.size >
            maxSize
        );

      if (
        oversizedFiles.length
      ) {
        setError(
          "One or more files exceed the 20 MB limit."
        );
      }

      setSelectedFiles(
        (current) => {
          const existing =
            new Set(
              current.map(
                (file) =>
                  `${file.name}-${file.size}`
              )
            );

          const next = [
            ...current,
          ];

          for (
            const file of
              validFiles
          ) {
            const key =
              `${file.name}-${file.size}`;

            if (
              !existing.has(
                key
              )
            ) {
              next.push(
                file
              );
            }
          }

          return next;
        }
      );

      event.target.value =
        "";
    };

  const removeFile = (
    fileToRemove
  ) => {
    setSelectedFiles(
      (current) =>
        current.filter(
          (file) =>
            !(
              file.name ===
                fileToRemove.name &&
              file.size ===
                fileToRemove.size
            )
        )
    );
  };

  const uploadSelectedFiles =
    async () => {
      if (
        !selectedFiles.length
      ) {
        return [];
      }

      const uploaded =
        [];

      for (
        const file of
          selectedFiles
      ) {
        const formData =
          new FormData();

        formData.append(
          "file",
          file
        );

        const response =
          await fetch(
            `${API_URL}/api/chat/upload`,
            {
              method:
                "POST",
              body:
                formData,
            }
          );

        if (!response.ok) {
          const errorText =
            await response.text();

          throw new Error(
            errorText ||
              `Failed to upload ${file.name}`
          );
        }

        const data =
          await response.json();

        if (
          !data.file?.file_id
        ) {
          throw new Error(
            `Backend did not return a file ID for ${file.name}.`
          );
        }

        uploaded.push({
          file_id:
            data.file.file_id,

          filename:
            data.file.filename ||
            file.name,

          content_type:
            data.file
              .content_type ||
            file.type,

          extension:
            data.file.extension ||
            (
              file.name.includes(
                "."
              )
                ? `.${file.name
                    .split(".")
                    .pop()
                    ?.toLowerCase()}`
                : ""
            ),

          file_type:
            data.file.file_type ||
            "",

          size:
            Number(
              data.file.size ||
                file.size ||
                0
            ),
        });
      }

      return uploaded;
    };

  const runAgent =
    async (
      message,
      uploadedFiles = []
    ) => {
      const directDocumentGeneration =
        isDocumentGenerationRequest(
          message
        );

      const directCodeExecution =
        isCodeExecutionRequest(
          message
        );

      const directSpreadsheetAnalysis =
        isSpreadsheetRequest(
          message
        ) ||
        uploadedFiles.some(
          (file) =>
            isSpreadsheetFile(
              file
            )
        );

      const directPresentationGeneration =
        isPresentationGenerationRequest(
          message
        );

      const response =
        await fetch(
          `${API_URL}/api/agents/run`,
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
                  message ||
                  "Analyze the attached spreadsheet.",

                context: {
                  conversation_id:
                    conversationId ||
                    null,

                  source:
                    "nova-local-chat",

                  attachments:
                    uploadedFiles,

                  knowledge_vault_id:
                    selectedVaultId ||
                    null,

                  knowledge_file_ids:
                    selectedVaultFileIds,
                },

                auto_confirm:
                  directDocumentGeneration ||
                  directCodeExecution ||
                  directSpreadsheetAnalysis ||
                  directPresentationGeneration,
              }),
          }
        );

      const data =
        await response.json();

      if (!response.ok) {
        throw new Error(
          data?.detail ||
            "NOVA agent could not process the request."
        );
      }

      return data;
    };

  const runNormalChat =
    async (
      message,
      uploadedFiles
    ) => {
      const response =
        await fetch(
          `${API_URL}/api/chat/`,
          {
            method:
              "POST",

            headers: {
              "Content-Type":
                "application/json",
            },

            body:
              JSON.stringify({
                message,

                model:
                  MODEL,

                conversation_id:
                  conversationId ||
                  null,

                attachments:
                  uploadedFiles,

                vault_id:
                  selectedVaultId ||
                  null,

                file_ids:
                  selectedVaultFileIds,
              }),
          }
        );

      if (!response.ok) {
        const errorText =
          await response.text();

        throw new Error(
          errorText ||
            "NOVA could not process the request."
        );
      }

      return response.json();
    };

  const sendMessage =
    async () => {
      const message =
        input.trim();

      const hasDirectFiles =
        selectedFiles.length >
        0;

      const hasSelectedVaultFiles =
        selectedVaultFileIds.length >
        0;

      const hasSelectedVault =
        Boolean(
          selectedVaultId
        );

      const hasText =
        Boolean(message);

      if (
        isSending
      ) {
        return;
      }

      if (
        !hasText &&
        !hasDirectFiles &&
        !hasSelectedVaultFiles
      ) {
        if (
          hasSelectedVault
        ) {
          setError(
            "Enter a question or select specific Knowledge Vault files before sending."
          );
        }

        return;
      }

      setError("");

      setIsSending(
        true
      );

      const useAgent =
        selectedFiles.length > 0 ||
        isAgentRequest(
          message
        );

      const initialStatus =
        useAgent
          ? "PLANNING"
          : "THINKING";

      setStatus(
        initialStatus
      );

      setActiveModel(
        null
      );

      emitAvatarState(
        "thinking"
      );

      const attachedFileMetadata =
        selectedFiles.map(
          (file) => ({
            name:
              file.name,

            size:
              file.size,

            type:
              file.type,
          })
        );

      const selectedVaultNames =
        vaults.filter(
          (vault) =>
            getVaultId(
              vault
            ) ===
            selectedVaultId
        );

      const selectedVaultName =
        selectedVaultNames.length
          ? getVaultName(
              selectedVaultNames[0]
            )
          : "";

      const selectedKnowledgeFiles =
        vaultFiles
          .filter(
            (file) =>
              selectedVaultFileIds.includes(
                getVaultFileId(
                  file
                )
              )
          )
          .map(
            (file) =>
              getVaultFileName(
                file
              )
          );

      const userMessage = {
        id:
          createId(
            "user"
          ),

        role:
          "user",

        content:
          message ||
          (
            selectedVaultFileIds.length
              ? "Please analyze the selected Knowledge Vault files."
              : "Please analyze the attached file."
          ),

        time:
          new Date(),

        attachments:
          attachedFileMetadata,

        knowledgeScope:
          selectedVaultId
            ? {
                vaultName:
                  selectedVaultName,

                vaultId:
                  selectedVaultId,

                fileNames:
                  selectedKnowledgeFiles,
              }
            : null,

        agent:
          null,
      };

      setMessages(
        (current) => [
          ...current,
          userMessage,
        ]
      );

      setInput("");

      requestAnimationFrame(
        () => {
          if (
            textareaRef.current
          ) {
            textareaRef.current.style.height =
              "auto";
          }
        }
      );

      try {
        if (useAgent) {
          setStatus(
            "ANALYZING"
          );

          const uploadedFiles =
            selectedFiles.length
              ? await uploadSelectedFiles()
              : [];

          setStatus(
            "PLANNING"
          );

          const hasSpreadsheetAttachment =
            uploadedFiles.some(
              (file) =>
                isSpreadsheetFile(
                  file
                )
            );

          const agentMessage =
            message ||
            (
              hasSpreadsheetAttachment
                ? "Analyze the attached spreadsheet and provide a useful summary."
                : selectedVaultFileIds.length
                  ? "Analyze the selected Knowledge Vault files and provide a useful summary."
                  : "Process this agent task."
            );

          const agentData =
            await runAgent(
              agentMessage,
              uploadedFiles
            );

          if (
            agentData.conversation_id &&
            agentData.conversation_id !==
              conversationId
          ) {
            onConversationChange(
              agentData.conversation_id
            );
          }

          onConversationSaved();

          setStatus(
            "EXECUTING"
          );

          const assistantText =
            agentData.response ||
            "NOVA completed the agent workflow.";

          const backendArtifacts =
            Array.isArray(
              agentData.artifacts
            )
              ? agentData.artifacts
              : [];

          const assistantArtifacts =
            backendArtifacts
              .map(
                normalizeArtifact
              )
              .filter(
                (artifact) =>
                  Boolean(
                    artifact.downloadUrl
                  )
              );

          const executionArtifacts =
            assistantArtifacts.length
              ? assistantArtifacts
              : getAgentArtifacts(
                  agentData.execution
                );

          const assistantMessage =
            {
              id:
                createId(
                  "nova"
                ),

              role:
                "assistant",

              content:
                assistantText,

              time:
                new Date(),

              attachments:
                [],

              agent: {
                plan:
                  agentData.plan ||
                  null,

                execution:
                  agentData.execution ||
                  null,

                artifacts:
                  executionArtifacts,
              },
            };

          setMessages(
            (current) => [
              ...current,
              assistantMessage,
            ]
          );

          const returnedModel =
            agentData.model ||
            agentData.model_name ||
            agentData.active_model ||
            agentData.routing
              ?.model_name ||
            null;

          setActiveModel(
            returnedModel
              ? String(
                  returnedModel
                )
              : null
          );

          window.dispatchEvent(
            new CustomEvent(
              "nova:speak",
              {
                detail: {
                  text:
                    assistantText,
                },
              }
            )
          );

          setStatus(
            "RESPONDING"
          );

          emitAvatarState(
            "speaking",
            0.7
          );

          setSelectedFiles(
            []
          );

          if (
            agentData.plan?.status ===
              "failed" ||
            agentData.execution?.status ===
              "failed"
          ) {
            setStatus(
              "ERROR"
            );
          }

          if (
            idleTimerRef.current
          ) {
            window.clearTimeout(
              idleTimerRef.current
            );
          }

          idleTimerRef.current =
            window.setTimeout(
              () => {
                setStatus(
                  "IDLE"
                );

                emitAvatarState(
                  "idle",
                  0
                );
              },
              900
            );

          return;
        }

        const uploadedFiles =
          await uploadSelectedFiles();

        emitAvatarState(
          "thinking"
        );

        const normalChatMessage =
          message ||
          (
            selectedVaultFileIds.length
              ? "Analyze the selected Knowledge Vault files and provide a useful summary."
              : "Analyze the attached file."
          );

        const data =
          await runNormalChat(
            normalChatMessage,
            uploadedFiles
          );

        setStatus(
          "RESPONDING"
        );

        emitAvatarState(
          "speaking",
          0.7
        );

        const responseText =
          data.response ||
          "NOVA did not return a response.";

        const assistantMessage =
          {
            id:
              createId(
                "nova"
              ),

            role:
              "assistant",

            content:
              responseText,

            time:
              new Date(),

            attachments:
              [],

            agent:
              null,
          };

        const returnedModel =
          data.model ||
          data.model_name ||
          data.active_model ||
          null;

        setActiveModel(
          returnedModel
            ? String(
                returnedModel
              )
              : null
        );

        window.dispatchEvent(
          new CustomEvent(
            "nova:speak",
            {
              detail: {
                text:
                  responseText,
              },
            }
          )
        );

        setMessages(
          (current) => [
            ...current,
            assistantMessage,
          ]
        );

        setSelectedFiles(
          []
        );

        if (
          data.conversation_id &&
          data.conversation_id !==
            conversationId
        ) {
          onConversationChange(
            data.conversation_id
          );
        }

        onConversationSaved();

        setStatus(
          "COMPLETE"
        );

        if (
          idleTimerRef.current
        ) {
          window.clearTimeout(
            idleTimerRef.current
          );
        }

        idleTimerRef.current =
          window.setTimeout(
            () => {
              setStatus(
                "IDLE"
              );

              emitAvatarState(
                "idle",
                0
              );
            },
            900
          );
      } catch (
        requestError
      ) {
        console.error(
          "NOVA request error:",
          requestError
        );

        setError(
          requestError?.message ||
            "Something went wrong while contacting NOVA."
        );

        setStatus(
          "ERROR"
        );

        emitAvatarState(
          "idle",
          0
        );
      } finally {
        setIsSending(
          false
        );
      }
    };

  const handleKeyDown =
    (
      event
    ) => {
      if (
        event.key ===
          "Enter" &&
        !event.shiftKey
      ) {
        event.preventDefault();

        sendMessage();
      }
    };

  const handleNewConversation =
    () => {
      setInput("");

      setSelectedFiles(
        []
      );

      setSelectedVaultFileIds(
        []
      );

      setVaultContextOpen(
        false
      );

      setError("");

      setStatus(
        "IDLE"
      );

      setActiveModel(
        null
      );

      emitAvatarState(
        "idle",
        0
      );

      onNewConversation();
    };

  const selectedVault =
    vaults.find(
      (vault) =>
        getVaultId(
          vault
        ) ===
        selectedVaultId
    );

  const selectedVaultDisplay =
    selectedVault
      ? getVaultName(
          selectedVault
        )
      : "ALL KNOWLEDGE";

  const knowledgeScopeActive =
    Boolean(
      selectedVaultId ||
        selectedVaultFileIds.length
    );

  const canSend =
    !isSending &&
    !isLoadingConversation &&
    (
      input.trim() ||
      selectedFiles.length > 0 ||
      selectedVaultFileIds.length > 0
    );

  const displayedModel =
    activeModel ||
    "LOCAL ROUTER";

  return (
    <div className="nova-chat-page">
      {/* HERO */}

      <motion.section
        className="nova-chat-hero"
        initial={{
          opacity: 0,
          y: 30,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
        transition={{
          duration:
            0.55,
          ease:
            "easeOut",
        }}
      >
        <div className="nova-chat-hero-copy">
          <div className="nova-chat-eyebrow">
            <span />
            LOCAL INTELLIGENCE WORKSPACE
          </div>

          <div className="nova-chat-title-row">
            <h1>
              NOVA
              <span>
                LOCAL CHAT
              </span>
            </h1>

            <div className="nova-chat-live-badge">
              <i />
              LOCAL RUNTIME
            </div>
          </div>

          <p>
            Private AI interaction powered by
            your local inference runtime.
          </p>
        </div>

        <div className="nova-chat-hero-side">
          <div className="nova-chat-runtime-mark">
            <span>
              <Sparkles
                size={13}
                {...ICON_PROPS}
              />
            </span>

            <div>
              <small>
                ACTIVE ROUTING
              </small>

              <strong>
                {displayedModel}
              </strong>
            </div>
          </div>
        </div>
      </motion.section>

      {/* RUNTIME STRIP */}

      <motion.section
        className="nova-chat-command-strip"
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
            0.5,
          delay:
            0.08,
        }}
      >
        <div className="nova-chat-command-item">
          <Cpu
            size={15}
            {...ICON_PROPS}
          />

          <div>
            <small>
              MODEL
            </small>

            <strong>
              {displayedModel}
            </strong>
          </div>
        </div>

        <div className="nova-chat-command-item">
          <LockKeyhole
            size={15}
            {...ICON_PROPS}
          />

          <div>
            <small>
              MODE
            </small>

            <strong>
              LOCAL
            </strong>
          </div>
        </div>

        <div className="nova-chat-command-item">
          <Activity
            size={15}
            {...ICON_PROPS}
          />

          <div>
            <small>
              STATE
            </small>

            <strong>
              {status}
            </strong>
          </div>
        </div>

        <div className="nova-chat-command-item">
          <BrainCircuit
            size={15}
            {...ICON_PROPS}
          />

          <div>
            <small>
              AGENT
            </small>

            <strong>
              {isSending
                ? "WORKING"
                : "READY"}
            </strong>
          </div>
        </div>

        <div className="nova-chat-command-item">
          <Sparkles
            size={15}
            {...ICON_PROPS}
          />

          <div>
            <small>
              ENGINE
            </small>

            <strong>
              {activeModel
                ? "LOCAL"
                : "ROUTED LOCALLY"}
            </strong>
          </div>
        </div>

        <div className="nova-chat-security">
          <span className="nova-chat-security-line" />

          LOCAL CHAT BOUNDARY
        </div>
      </motion.section>

      {/* MAIN CHAT SHELL */}

      <motion.section
        className="nova-chat-shell"
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
          delay:
            0.15,
        }}
      >
        <div className="nova-chat-shell-top">
          <div className="nova-chat-session-info">
            <div className="nova-chat-session-icon">
              <MessageSquare
                size={15}
                {...ICON_PROPS}
              />
            </div>

            <div>
              <small>
                CONVERSATION
              </small>

              <strong>
                {conversationId
                  ? "SAVED SESSION"
                  : "NEW SESSION"}
              </strong>
            </div>
          </div>

          <button
            type="button"
            className="nova-chat-clear-button"
            onClick={
              handleNewConversation
            }
          >
            <RotateCcw
              size={13}
              {...ICON_PROPS}
            />

            NEW CHAT
          </button>
        </div>

        <div className="nova-chat-body">
          <div className="nova-chat-body-grid" />

          <div className="nova-chat-messages">
            {isLoadingConversation ? (
              <div className="nova-chat-loading">
                <span className="nova-thinking-pulse" />
                LOADING CONVERSATION...
              </div>
            ) : (
              messages.map(
                (message) => (
                  <motion.div
                    key={
                      message.id
                    }
                    className={`nova-chat-message ${
                      message.role ===
                      "user"
                        ? "is-user"
                        : "is-assistant"
                    }`}
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
                        0.3,
                      ease:
                        "easeOut",
                    }}
                  >
                    <div className="nova-chat-message-top">
                      <div className="nova-chat-message-author">
                        <span className="nova-chat-avatar">
                          {message.role ===
                          "user"
                            ? "U"
                            : "N"}
                        </span>

                        <span>
                          {message.role ===
                          "user"
                            ? "YOU"
                            : "NOVA"}
                        </span>
                      </div>

                      <time>
                        {formatTime(
                          message.time
                        )}
                      </time>
                    </div>

                    {message.attachments?.length >
                      0 && (
                      <div className="nova-chat-message-files">
                        {message.attachments.map(
                          (
                            file
                          ) => (
                            <div
                              className="nova-chat-message-file"
                              key={`${file.name}-${file.file_id || file.size}`}
                            >
                              {getFileIcon(
                                file.type
                              )}

                              <span>
                                {
                                  file.name
                                }
                              </span>
                            </div>
                          )
                        )}
                      </div>
                    )}

                    {message.role ===
                      "user" &&
                      message.knowledgeScope && (
                        <div className="nova-chat-message-files nova-chat-knowledge-message-ref">
                          <div className="nova-chat-message-file">
                            <Database
                              size={14}
                              {...ICON_PROPS}
                            />

                            <span>
                              KNOWLEDGE SCOPE ·{" "}
                              {
                                message
                                  .knowledgeScope
                                  .vaultName
                              }

                              {message
                                .knowledgeScope
                                .fileNames
                                ?.length > 0
                                ? ` · ${message.knowledgeScope.fileNames.length} FILE${
                                    message
                                      .knowledgeScope
                                      .fileNames
                                      .length ===
                                    1
                                      ? ""
                                      : "S"
                                  }`
                                : ""}
                            </span>
                          </div>
                        </div>
                      )}

                    <div className="nova-chat-message-content">
                      {message.role ===
                      "assistant" ? (
                        <NovaMarkdown
                          content={
                            message.content
                          }
                        />
                      ) : (
                        message.content
                      )}
                    </div>

                    {message.agent?.plan && (
                      <motion.div
                        className="nova-workflow-panel"
                        initial={{
                          opacity: 0,
                          y: 6,
                        }}
                        animate={{
                          opacity: 1,
                          y: 0,
                        }}
                        transition={{
                          duration:
                            0.3,
                          ease:
                            "easeOut",
                        }}
                      >
                        <div className="nova-workflow-header">
                          <div className="nova-workflow-header-title">
                            <BrainCircuit
                              size={14}
                              className="nova-workflow-icon"
                              {...ICON_PROPS}
                            />

                            <span>
                              NOVA WORKFLOW
                            </span>
                          </div>

                          <span
                            className={`nova-workflow-status-badge status-${(
                              message.agent.plan.status ||
                              "completed"
                            ).toLowerCase()}`}
                          >
                            <span className="nova-workflow-status-dot" />

                            <span>
                              {(
                                message.agent
                                  .plan
                                  .status ||
                                "COMPLETED"
                              ).toUpperCase()}
                            </span>
                          </span>
                        </div>

                        <div className="nova-workflow-meta">
                          <h4 className="nova-workflow-name">
                            {getWorkflowTitle(
                              message.agent.plan,
                              message.agent.execution,
                              message.agent.artifacts
                            )}
                          </h4>

                          <p className="nova-workflow-subtitle">
                            {getWorkflowSubtitle(
                              message.agent.plan.status
                            )}
                          </p>
                        </div>

                        {message.agent
                          .plan.steps?.length >
                          0 && (
                          <div className="nova-workflow-steps">
                            {message.agent.plan.steps.map(
                              (
                                step,
                                idx
                              ) => {
                                const stepNum =
                                  String(
                                    idx + 1
                                  ).padStart(
                                    2,
                                    "0"
                                  );

                                const stepStatus =
                                  (
                                    step.status ||
                                    "completed"
                                  ).toLowerCase();

                                return (
                                  <motion.div
                                    className="nova-workflow-step"
                                    key={
                                      step.id ||
                                      idx
                                    }
                                    initial={{
                                      opacity:
                                        0,
                                      x:
                                        -5,
                                    }}
                                    animate={{
                                      opacity:
                                        1,
                                      x:
                                        0,
                                    }}
                                    transition={{
                                      duration:
                                        0.25,
                                      delay:
                                        idx *
                                        0.05,
                                    }}
                                  >
                                    <span className="nova-workflow-step-num">
                                      {
                                        stepNum
                                      }
                                    </span>

                                    <span
                                      className={`nova-workflow-step-icon status-${stepStatus}`}
                                    >
                                      {getStepStatusIcon(
                                        stepStatus
                                      )}
                                    </span>

                                    <div className="nova-workflow-step-info">
                                      <span className="nova-workflow-step-title">
                                        {
                                          step.title
                                        }
                                      </span>

                                      {step.tool && (
                                        <span className="nova-workflow-step-tool">
                                          {
                                            step.tool
                                          }
                                        </span>
                                      )}
                                    </div>

                                    <span
                                      className={`nova-workflow-step-status status-${stepStatus}`}
                                    >
                                      {(
                                        step.status ||
                                        "COMPLETED"
                                      ).toUpperCase()}
                                    </span>
                                  </motion.div>
                                );
                              }
                            )}
                          </div>
                        )}

                        {message.agent
                          .execution && (
                          <div className="nova-workflow-metrics">
                            <div className="nova-workflow-metric-card metric-completed">
                              <span className="nova-workflow-metric-val">
                                {message.agent.execution.completed_steps?.length ??
                                  0}
                              </span>

                              <span className="nova-workflow-metric-lbl">
                                COMPLETED
                              </span>
                            </div>

                            <div className="nova-workflow-metric-card metric-failed">
                              <span className="nova-workflow-metric-val">
                                {message.agent.execution.failed_steps?.length ??
                                  0}
                              </span>

                              <span className="nova-workflow-metric-lbl">
                                FAILED
                              </span>
                            </div>

                            <div className="nova-workflow-metric-card metric-blocked">
                              <span className="nova-workflow-metric-val">
                                {message.agent.execution.blocked_steps?.length ??
                                  0}
                              </span>

                              <span className="nova-workflow-metric-lbl">
                                BLOCKED
                              </span>
                            </div>
                          </div>
                        )}

                        {message.agent.artifacts?.length >
                          0 && (
                          <div className="nova-agent-artifacts">
                            <div className="nova-agent-artifacts-header">
                              <span>
                                GENERATED ARTIFACTS
                              </span>

                              <small>
                                VERIFIED LOCAL WORKSPACE
                              </small>
                            </div>

                            <div className="nova-agent-artifact-list">
                              {message.agent.artifacts.map(
                                (
                                  artifact
                                ) => (
                                  <div
                                    className="nova-agent-artifact"
                                    key={`${artifact.stepId}-${artifact.filePath}`}
                                  >
                                    <div className="nova-agent-artifact-icon">
                                      <FileText
                                        size={15}
                                        {...ICON_PROPS}
                                      />
                                    </div>

                                    <div className="nova-agent-artifact-info">
                                      <strong>
                                        {
                                          artifact.fileName
                                        }
                                      </strong>

                                      <small>
                                        {
                                          artifact.extension
                                        }

                                        {artifact.sizeBytes
                                          ? ` · ${formatArtifactSize(
                                              artifact.sizeBytes
                                            )}`
                                          : ""}

                                        {" · "}

                                        {artifact.verificationStatus.toUpperCase()}
                                      </small>
                                    </div>

                                    {artifact.available !==
                                      false &&
                                    artifact.downloadUrl ? (
                                      <a
                                        className="nova-agent-artifact-download"
                                        href={
                                          artifact.downloadUrl
                                        }
                                        download={
                                          artifact.fileName
                                        }
                                        title={`Download ${artifact.fileName}`}
                                      >
                                        <Download
                                          size={
                                            14
                                          }
                                          {...ICON_PROPS}
                                        />

                                        <span>
                                          DOWNLOAD
                                        </span>
                                      </a>
                                    ) : (
                                      <div
                                        className="nova-agent-artifact-unavailable"
                                        title="The generated file is no longer present in the local workspace."
                                      >
                                        <span>
                                          ARTIFACT UNAVAILABLE
                                        </span>
                                      </div>
                                    )}
                                  </div>
                                )
                              )}
                            </div>
                          </div>
                        )}
                      </motion.div>
                    )}
                  </motion.div>
                )
              )
            )}

            {isSending && (
              <motion.div
                className="nova-chat-thinking"
                initial={{
                  opacity:
                    0,
                  y:
                    5,
                }}
                animate={{
                  opacity:
                    1,
                  y:
                    0,
                }}
                transition={{
                  duration:
                    0.25,
                  ease:
                    "easeOut",
                }}
              >
                <span className="nova-thinking-pulse" />

                <strong>
                  {status ===
                  "PLANNING"
                    ? "NOVA IS PLANNING..."
                    : status ===
                        "EXECUTING"
                      ? "NOVA IS EXECUTING..."
                      : status ===
                          "ANALYZING"
                        ? "NOVA IS ANALYZING..."
                        : "NOVA IS THINKING..."}
                </strong>

                <span
                  className="nova-thinking-bars"
                  aria-hidden="true"
                >
                  <i />
                  <i />
                  <i />
                </span>
              </motion.div>
            )}

            {error && (
              <div className="nova-chat-runtime-error">
                <strong>
                  NOVA RUNTIME ERROR
                </strong>

                <span>
                  {error}
                </span>
              </div>
            )}

            <div
              ref={
                messagesEndRef
              }
            />
          </div>
        </div>

        {/* COMPOSER */}

        <div className="nova-chat-composer">
          <div className="nova-chat-composer-header">
            <div>
              <span className="composer-indicator" />

              <span>
                LOCAL REQUEST
              </span>
            </div>

            <span>
              AGENT TASKS AUTO-ROUTED · ENTER TO SEND
            </span>
          </div>

          {/* KNOWLEDGE VAULT SCOPE */}

          <div className="nova-chat-knowledge-scope">
            <div className="nova-chat-knowledge-scope-head">
              <div className="nova-chat-knowledge-scope-label">
                <Database
                  size={14}
                  {...ICON_PROPS}
                />

                <div>
                  <strong>
                    KNOWLEDGE VAULT CONTEXT
                  </strong>

                  <small>
                    {knowledgeScopeActive
                      ? selectedVaultDisplay
                      : "GLOBAL KNOWLEDGE"}
                  </small>
                </div>
              </div>

              <button
                type="button"
                className={`nova-chat-knowledge-toggle ${
                  vaultContextOpen
                    ? "is-open"
                    : ""
                }`}
                onClick={() =>
                  setVaultContextOpen(
                    (current) =>
                      !current
                  )
                }
                disabled={
                  isSending
                }
              >
                <span>
                  {knowledgeScopeActive
                    ? selectedVaultFileIds.length
                      ? `${selectedVaultFileIds.length} FILE${
                          selectedVaultFileIds.length ===
                          1
                            ? ""
                            : "S"
                        } SELECTED`
                      : "VAULT SELECTED"
                    : "SELECT SCOPE"}
                </span>

                <ChevronDown
                  size={14}
                  {...ICON_PROPS}
                />
              </button>
            </div>

            {vaultContextOpen && (
              <motion.div
                className="nova-chat-knowledge-panel"
                initial={{
                  opacity: 0,
                  y: -5,
                }}
                animate={{
                  opacity: 1,
                  y: 0,
                }}
                transition={{
                  duration:
                    0.2,
                }}
              >
                <div className="nova-chat-knowledge-vault-row">
                  <div className="nova-chat-knowledge-vault-select-wrap">
                    <FolderOpen
                      size={14}
                      {...ICON_PROPS}
                    />

                    <select
                      className="nova-chat-knowledge-vault-select"
                      value={
                        selectedVaultId
                      }
                      onChange={
                        handleVaultChange
                      }
                      disabled={
                        isSending ||
                        isLoadingVaults
                      }
                    >
                      <option value="">
                        GLOBAL KNOWLEDGE
                      </option>

                      {vaults.map(
                        (
                          vault
                        ) => {
                          const vaultId =
                            getVaultId(
                              vault
                            );

                          if (
                            !vaultId
                          ) {
                            return null;
                          }

                          return (
                            <option
                              key={
                                vaultId
                              }
                              value={
                                vaultId
                              }
                            >
                              {getVaultName(
                                vault
                              )}
                            </option>
                          );
                        }
                      )}
                    </select>

                    {isLoadingVaults && (
                      <LoaderCircle
                        size={14}
                        className="nova-spin"
                        {...ICON_PROPS}
                      />
                    )}
                  </div>

                  {knowledgeScopeActive && (
                    <button
                      type="button"
                      className="nova-chat-knowledge-clear"
                      onClick={
                        clearKnowledgeScope
                      }
                      disabled={
                        isSending
                      }
                    >
                      CLEAR
                    </button>
                  )}
                </div>

                {selectedVaultId && (
                  <>
                    <div className="nova-chat-knowledge-files-header">
                      <div>
                        <strong>
                          FILE FILTER
                        </strong>

                        <small>
                          Leave empty to search the complete selected vault.
                        </small>
                      </div>

                      {isLoadingVaultFiles ? (
                        <LoaderCircle
                          size={14}
                          className="nova-spin"
                          {...ICON_PROPS}
                        />
                      ) : (
                        <span>
                          {
                            vaultFiles.length
                          }{" "}
                          FILE
                          {vaultFiles.length ===
                          1
                            ? ""
                            : "S"}
                        </span>
                      )}
                    </div>

                    {!isLoadingVaultFiles &&
                      vaultFiles.length >
                        0 && (
                        <div className="nova-chat-knowledge-files">
                          {vaultFiles.map(
                            (
                              file
                            ) => {
                              const fileId =
                                getVaultFileId(
                                  file
                                );

                              if (
                                !fileId
                              ) {
                                return null;
                              }

                              const checked =
                                selectedVaultFileIds.includes(
                                  fileId
                                );

                              return (
                                <label
                                  className={`nova-chat-knowledge-file ${
                                    checked
                                      ? "is-selected"
                                      : ""
                                  }`}
                                  key={
                                    fileId
                                  }
                                >
                                  <input
                                    type="checkbox"
                                    checked={
                                      checked
                                    }
                                    onChange={() =>
                                      toggleVaultFile(
                                        fileId
                                      )
                                    }
                                    disabled={
                                      isSending
                                    }
                                  />

                                  <span className="nova-chat-knowledge-file-check">
                                    {checked
                                      ? "✓"
                                      : ""}
                                  </span>

                                  <FileText
                                    size={14}
                                    {...ICON_PROPS}
                                  />

                                  <span className="nova-chat-knowledge-file-name">
                                    {getVaultFileName(
                                      file
                                    )}
                                  </span>
                                </label>
                              );
                            }
                          )}
                        </div>
                      )}

                    {!isLoadingVaultFiles &&
                      vaultFiles.length ===
                        0 && (
                        <div className="nova-chat-knowledge-empty">
                          No active files are available in this vault.
                        </div>
                      )}

                    {selectedVaultFileIds.length >
                      0 && (
                      <div className="nova-chat-knowledge-selection">
                        <Sparkles
                          size={13}
                          {...ICON_PROPS}
                        />

                        <span>
                          Chat will search only the selected files.
                        </span>
                      </div>
                    )}
                  </>
                )}

                {vaultError && (
                  <div className="nova-chat-knowledge-error">
                    <AlertCircle
                      size={13}
                      {...ICON_PROPS}
                    />

                    <span>
                      {vaultError}
                    </span>
                  </div>
                )}
              </motion.div>
            )}
          </div>

          {selectedFiles.length >
            0 && (
            <div className="nova-chat-attachments">
              {selectedFiles.map(
                (file) => (
                  <div
                    className="nova-chat-attachment"
                    key={`${file.name}-${file.size}`}
                  >
                    <span className="nova-chat-attachment-icon">
                      {getFileIcon(
                        file.type
                      )}
                    </span>

                    <div className="nova-chat-attachment-info">
                      <strong>
                        {
                          file.name
                        }
                      </strong>

                      <small>
                        {(
                          file.size /
                          1024 /
                          1024
                        ).toFixed(
                          2
                        )}{" "}
                        MB
                      </small>
                    </div>

                    <button
                      type="button"
                      onClick={() =>
                        removeFile(
                          file
                        )
                      }
                      aria-label={`Remove ${file.name}`}
                    >
                      <X
                        size={
                          13
                        }
                        {...ICON_PROPS}
                      />
                    </button>
                  </div>
                )
              )}
            </div>
          )}

          <div className="nova-chat-input-row">
            <button
              type="button"
              className="nova-chat-attach-button"
              onClick={() =>
                fileInputRef.current?.click()
              }
              disabled={
                isSending
              }
              title="Attach file"
            >
              <Paperclip
                size={
                  17
                }
                {...ICON_PROPS}
              />
            </button>

            <input
              ref={
                fileInputRef
              }
              type="file"
              hidden
              multiple
              accept=".pdf,.txt,.docx,.csv,.xlsx,.xls,image/png,image/jpeg,image/webp"
              onChange={
                handleFileSelection
              }
            />

            <textarea
              ref={
                textareaRef
              }
              className="nova-chat-composer-input"
              value={
                input
              }
              onChange={
                handleInputChange
              }
              onKeyDown={
                handleKeyDown
              }
              placeholder={
                knowledgeScopeActive
                  ? "Ask NOVA about the selected local knowledge..."
                  : "Ask NOVA anything..."
              }
              rows={1}
              disabled={
                isSending ||
                isLoadingConversation
              }
            />

            <button
              type="button"
              className="nova-chat-send"
              onClick={
                sendMessage
              }
              disabled={
                !canSend
              }
              aria-label="Send message"
            >
              {isSending ? (
                <LoaderCircle
                  size={
                    18
                  }
                  className="nova-spin"
                  {...ICON_PROPS}
                />
              ) : (
                <ArrowUp
                  size={
                    18
                  }
                  {...ICON_PROPS}
                />
              )}
            </button>
          </div>

          <div className="nova-chat-composer-footer">
            <span>
              PRIVATE SESSION
            </span>

            <span>
              {knowledgeScopeActive
                ? `LOCAL KNOWLEDGE SCOPE / ${
                    selectedVaultDisplay
                  } / ${
                    selectedVaultFileIds.length
                      ? `${selectedVaultFileIds.length} FILE FILTER`
                      : "VAULT SEARCH"
                  }`
                : "LOCAL MODEL ROUTING / AGENT READY / NO EXTERNAL CHAT"}
            </span>
          </div>
        </div>
      </motion.section>

      <div className="nova-chat-footer-signal">
        <span />

        NOVA INTELLIGENCE RUNTIME
      </div>
    </div>
  );
}