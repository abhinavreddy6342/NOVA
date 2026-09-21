const API_URL =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8001";

function buildHeaders(
  options = {}
) {
  const headers = {
    ...(options.headers || {}),
  };

  if (
    options.body !== undefined &&
    options.body !== null &&
    !(options.body instanceof FormData) &&
    !headers["Content-Type"]
  ) {
    headers["Content-Type"] =
      "application/json";
  }

  return headers;
}

async function request(
  endpoint,
  options = {}
) {
  const response =
    await fetch(
      `${API_URL}${endpoint}`,
      {
        ...options,
        credentials: "include",
        headers:
          buildHeaders(options),
      }
    );

  let data = null;

  try {
    data =
      await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    if (
      response.status === 401
    ) {
      throw new Error(
        "Your NOVA session has expired. Please sign in again."
      );
    }

    if (
      response.status === 404
    ) {
      throw new Error(
        data?.detail ||
          "The requested NOVA resource was not found."
      );
    }

    throw new Error(
      data?.detail ||
        data?.message ||
        `NOVA request failed with status ${response.status}.`
    );
  }

  return data;
}



// =========================================
// AGENTS / MISSIONS
// =========================================

export async function runAgent(
  objective,
  options = {}
) {
  const cleanObjective =
    String(
      objective || ""
    ).trim();

  if (!cleanObjective) {
    throw new Error(
      "Agent objective cannot be empty."
    );
  }

  return request(
    "/api/agents/run",
    {
      method: "POST",

      body:
        JSON.stringify({
          objective:
            cleanObjective,

          context:
            options.context ||
            null,

          auto_confirm:
            options.autoConfirm ||
            false,
        }),
    }
  );
}



export async function runMission(
  mission
) {
  if (!mission) {
    throw new Error(
      "Mission is required."
    );
  }

  return request(
    "/api/agents/mission/run",
    {
      method: "POST",

      body:
        JSON.stringify({
          mission_id:
            mission.id ||
            null,

          title:
            mission.title,

          objective:
            mission.objective,

          context: {
            source:
              "nova-mission-control",

            mission_type:
              mission.type,

            priority:
              mission.priority,

            autonomy:
              mission.autonomy,

            attachments:
              mission.attachments ||
              [],

            mission_sources:
              mission.sources ||
              [],
          },

          auto_confirm:
            true,
        }),
    }
  );
}



export async function runMissionChat(
  mission,
  message,
  conversationHistory = []
) {
  if (!mission) {
    throw new Error(
      "Mission is required."
    );
  }

  const cleanMessage =
    String(
      message || ""
    ).trim();

  if (!cleanMessage) {
    throw new Error(
      "Mission message cannot be empty."
    );
  }

  return request(
    "/api/agents/run",
    {
      method: "POST",

      body:
        JSON.stringify({
          objective:
            `MISSION FOLLOW-UP:\n${cleanMessage}`,

          context: {
            source:
              "nova-mission-chat",

            conversation_id:
              mission.conversationId ||
              null,

            mission_id:
              mission.id ||
              null,

            mission: {
              mission_id:
                mission.id ||
                null,

              title:
                mission.title,

              objective:
                mission.objective,

              mission_type:
                mission.type,

              priority:
                mission.priority,

              autonomy:
                mission.autonomy,
            },

            attachments:
              mission.attachments ||
              [],

            mission_sources:
              mission.sources ||
              [],

            mission_plan:
              mission.plan ||
              null,

            mission_execution:
              mission.execution ||
              null,

            last_mission_result:
              mission.response ||
              "",

            conversation_history:
              Array.isArray(
                conversationHistory
              )
                ? conversationHistory
                : [],
          },

          auto_confirm:
            true,
        }),
    }
  );
}



// =========================================
// LOCAL CHAT
// =========================================

export async function sendChatMessage(
  payload
) {
  return request(
    "/api/chat/",
    {
      method: "POST",

      body:
        JSON.stringify(
          payload
        ),
    }
  );
}



// =========================================
// CONVERSATION HISTORY
// =========================================

export async function getConversations() {
  return request(
    "/api/history/conversations",
    {
      method: "GET",
    }
  );
}



export async function getConversation(
  conversationId
) {
  if (!conversationId) {
    throw new Error(
      "Conversation ID is required."
    );
  }

  return request(
    `/api/history/conversations/${conversationId}`,
    {
      method: "GET",
    }
  );
}



export async function createConversation() {
  return request(
    "/api/history/conversations",
    {
      method: "POST",
    }
  );
}



export async function deleteConversation(
  conversationId
) {
  if (!conversationId) {
    throw new Error(
      "Conversation ID is required."
    );
  }

  return request(
    `/api/history/conversations/${conversationId}`,
    {
      method: "DELETE",
    }
  );
}



// =========================================
// KNOWLEDGE
// =========================================

export async function searchKnowledge(
  query,
  topK = 5
) {
  const cleanQuery =
    String(
      query || ""
    ).trim();

  if (!cleanQuery) {
    throw new Error(
      "Knowledge search query cannot be empty."
    );
  }

  return request(
    "/api/knowledge/search",
    {
      method: "POST",

      body:
        JSON.stringify({
          query:
            cleanQuery,

          top_k:
            topK,
        }),
    }
  );
}



// =========================================
// AI MODELS
// =========================================

export async function getModels() {
  return request(
    "/api/models",
    {
      method: "GET",
    }
  );
}



export async function getModelStatus() {
  return request(
    "/api/models/status",
    {
      method: "GET",
    }
  );
}



export async function getActiveModel() {
  return request(
    "/api/models/active",
    {
      method: "GET",
    }
  );
}



export async function setActiveModel(
  model
) {
  return request(
    "/api/models/active",
    {
      method: "POST",

      body:
        JSON.stringify({
          model,
        }),
    }
  );
}



export async function testModel({
  model,
  prompt,
  system,
}) {
  return request(
    "/api/models/test",
    {
      method: "POST",

      body:
        JSON.stringify({
          model,
          prompt,
          system,
        }),
    }
  );
}



export async function getTaskRouting() {
  return request(
    "/api/models/routing",
    {
      method: "GET",
    }
  );
}



export async function saveTaskRouting(
  routing
) {
  return request(
    "/api/models/routing",
    {
      method: "POST",

      body:
        JSON.stringify({
          routing,
        }),
    }
  );
}



export async function getModelActivity() {
  return request(
    "/api/models/activity",
    {
      method: "GET",
    }
  );
}



// =========================================
// SOVEREIGNTY
// =========================================

export async function getSovereignty() {
  return request(
    "/api/sovereignty",
    {
      method: "GET",
    }
  );
}



export async function getSovereigntyNetwork() {
  return request(
    "/api/sovereignty/network",
    {
      method: "GET",
    }
  );
}



export async function getSovereigntyVerification() {
  return request(
    "/api/sovereignty/verification",
    {
      method: "GET",
    }
  );
}



// =========================================
// AUDIT TRAIL
// =========================================

function buildAuditQuery(
  filters = {}
) {
  const params =
    new URLSearchParams();

  const values = {
    query:
      filters.query ??
      filters.search,

    category:
      filters.category,

    action:
      filters.action,

    service:
      filters.service,

    status:
      filters.status,

    model:
      filters.model,

    task_type:
      filters.taskType ??
      filters.task_type,

    start_time:
      filters.start ??
      filters.startDate ??
      filters.start_date,

    end_time:
      filters.end ??
      filters.endDate ??
      filters.end_date,

    limit:
      filters.limit,

    offset:
      filters.offset,
  };

  Object.entries(
    values
  ).forEach(
    ([
      key,
      value,
    ]) => {
      if (
        value === undefined ||
        value === null ||
        String(
          value
        ).trim() === ""
      ) {
        return;
      }

      params.set(
        key,
        String(value)
      );
    }
  );

  const serialized =
    params.toString();

  return serialized
    ? `?${serialized}`
    : "";
}



export async function getAuditEvents(
  filters = {}
) {
  return request(
    `/api/audit${buildAuditQuery(
      filters
    )}`,
    {
      method: "GET",
    }
  );
}



export async function getAuditSummary() {
  return request(
    "/api/audit/summary",
    {
      method: "GET",
    }
  );
}



export async function getAuditEvent(
  eventId
) {
  const normalizedEventId =
    String(
      eventId || ""
    ).trim();

  if (!normalizedEventId) {
    throw new Error(
      "Audit event ID is required."
    );
  }

  return request(
    `/api/audit/${encodeURIComponent(
      normalizedEventId
    )}`,
    {
      method: "GET",
    }
  );
}



async function fetchAuditExport(
  format,
  filters = {}
) {
  const normalizedFormat =
    String(
      format || ""
    )
      .trim()
      .toLowerCase();

  if (
    normalizedFormat !== "json" &&
    normalizedFormat !== "csv"
  ) {
    throw new Error(
      "Audit export format must be JSON or CSV."
    );
  }

  const response =
    await fetch(
      `${API_URL}/api/audit/export/${normalizedFormat}${buildAuditQuery(
        filters
      )}`,
      {
        method: "GET",

        credentials:
          "include",

        headers:
          buildHeaders({
            headers: {
              Accept:
                normalizedFormat ===
                "json"
                  ? "application/json"
                  : "text/csv",
            },
          }),
      }
    );

  if (!response.ok) {
    let message =
      `NOVA audit export failed with status ${response.status}.`;

    try {
      const data =
        await response.json();

      message =
        data?.detail ||
        message;
    } catch {
      // Preserve fallback error message.
    }

    throw new Error(
      message
    );
  }

  const blob =
    await response.blob();

  const contentDisposition =
    response.headers.get(
      "Content-Disposition"
    );

  let filename =
    `nova-audit.${normalizedFormat}`;

  if (
    contentDisposition
  ) {
    const match =
      contentDisposition.match(
        /filename\*?=(?:UTF-8'')?["']?([^"';]+)["']?/i
      );

    if (
      match &&
      match[1]
    ) {
      filename =
        match[1];
    }
  }

  return {
    blob,
    filename,
    contentType:
      response.headers.get(
        "Content-Type"
      ) || "",
  };
}



export async function exportAuditJSON(
  filters = {}
) {
  return fetchAuditExport(
    "json",
    filters
  );
}



export async function exportAuditCSV(
  filters = {}
) {
  return fetchAuditExport(
    "csv",
    filters
  );
}



export async function downloadAuditExport(
  format,
  filters = {}
) {
  const {
    blob,
    filename,
  } =
    await fetchAuditExport(
      format,
      filters
    );

  const url =
    window.URL.createObjectURL(
      blob
    );

  const anchor =
    document.createElement(
      "a"
    );

  anchor.href =
    url;

  anchor.download =
    filename;

  document.body.appendChild(
    anchor
  );

  anchor.click();

  anchor.remove();

  window.URL.revokeObjectURL(
    url
  );

  return {
    filename,
  };
}



// =========================================
// ANALYTICS CENTER
// =========================================

function buildAnalyticsQuery(
  filters = {}
) {
  const params =
    new URLSearchParams();

  const range =
    filters.range_key ||
    filters.range ||
    "24h";

  params.set(
    "range",
    String(range)
  );

  if (
    filters.query ||
    filters.search
  ) {
    params.set(
      "query",
      String(
        filters.query ||
          filters.search
      )
    );
  }

  if (filters.category) {
    params.set(
      "category",
      String(
        filters.category
      )
    );
  }

  if (filters.service) {
    params.set(
      "service",
      String(
        filters.service
      )
    );
  }

  if (filters.status) {
    params.set(
      "status",
      String(
        filters.status
      )
    );
  }

  if (filters.model) {
    params.set(
      "model",
      String(
        filters.model
      )
    );
  }

  if (
    filters.task_type ||
    filters.taskType
  ) {
    params.set(
      "task_type",
      String(
        filters.task_type ||
          filters.taskType
      )
    );
  }

  if (
    filters.start ||
    filters.custom_start ||
    filters.startDate
  ) {
    params.set(
      "start",
      String(
        filters.start ||
          filters.custom_start ||
          filters.startDate
      )
    );
  }

  if (
    filters.end ||
    filters.custom_end ||
    filters.endDate
  ) {
    params.set(
      "end",
      String(
        filters.end ||
          filters.custom_end ||
          filters.endDate
      )
    );
  }

  const queryStr =
    params.toString();

  return queryStr
    ? `?${queryStr}`
    : "";
}



export async function getAnalyticsDashboard(
  filters = {}
) {
  return request(
    `/api/analytics${buildAnalyticsQuery(
      filters
    )}`,
    {
      method: "GET",
    }
  );
}



export async function getAnalyticsSummary(
  filters = {}
) {
  return request(
    `/api/analytics/summary${buildAnalyticsQuery(
      filters
    )}`,
    {
      method: "GET",
    }
  );
}



export async function getAnalyticsTrends(
  filters = {}
) {
  return request(
    `/api/analytics/trends${buildAnalyticsQuery(
      filters
    )}`,
    {
      method: "GET",
    }
  );
}



export async function getAnalyticsCategories(
  filters = {}
) {
  return request(
    `/api/analytics/categories${buildAnalyticsQuery(
      filters
    )}`,
    {
      method: "GET",
    }
  );
}



export async function getAnalyticsServices(
  filters = {}
) {
  return request(
    `/api/analytics/services${buildAnalyticsQuery(
      filters
    )}`,
    {
      method: "GET",
    }
  );
}



export async function getAnalyticsModels(
  filters = {}
) {
  return request(
    `/api/analytics/models${buildAnalyticsQuery(
      filters
    )}`,
    {
      method: "GET",
    }
  );
}



export async function getAnalyticsLatency(
  filters = {}
) {
  return request(
    `/api/analytics/latency${buildAnalyticsQuery(
      filters
    )}`,
    {
      method: "GET",
    }
  );
}



export async function getAnalyticsNetwork() {
  return request(
    "/api/analytics/network",
    {
      method: "GET",
    }
  );
}



export async function getAnalyticsResources() {
  return request(
    "/api/analytics/resources",
    {
      method: "GET",
    }
  );
}



async function fetchAnalyticsExport(
  format,
  filters = {}
) {
  const normalizedFormat =
    String(
      format || ""
    )
      .trim()
      .toLowerCase();

  if (
    normalizedFormat !== "json" &&
    normalizedFormat !== "csv"
  ) {
    throw new Error(
      "Analytics export format must be JSON or CSV."
    );
  }

  const response =
    await fetch(
      `${API_URL}/api/analytics/export/${normalizedFormat}${buildAnalyticsQuery(
        filters
      )}`,
      {
        method: "GET",

        credentials:
          "include",

        headers:
          buildHeaders({
            headers: {
              Accept:
                normalizedFormat ===
                "json"
                  ? "application/json"
                  : "text/csv",
            },
          }),
      }
    );

  if (!response.ok) {
    let message =
      `NOVA analytics export failed with status ${response.status}.`;

    try {
      const data =
        await response.json();

      message =
        data?.detail ||
        message;
    } catch {
      // Keep default.
    }

    throw new Error(
      message
    );
  }

  const blob =
    await response.blob();

  const contentDisposition =
    response.headers.get(
      "Content-Disposition"
    );

  let filename =
    `nova-analytics.${normalizedFormat}`;

  if (
    contentDisposition
  ) {
    const match =
      contentDisposition.match(
        /filename\*?=(?:UTF-8'')?["']?([^"';]+)["']?/i
      );

    if (
      match &&
      match[1]
    ) {
      filename =
        match[1];
    }
  }

  return {
    blob,
    filename,
    contentType:
      response.headers.get(
        "Content-Type"
      ) || "",
  };
}



export async function downloadAnalyticsExport(
  format,
  filters = {}
) {
  const {
    blob,
    filename,
  } =
    await fetchAnalyticsExport(
      format,
      filters
    );

  const url =
    window.URL.createObjectURL(
      blob
    );

  const anchor =
    document.createElement(
      "a"
    );

  anchor.href =
    url;

  anchor.download =
    filename;

  document.body.appendChild(
    anchor
  );

  anchor.click();

  anchor.remove();

  window.URL.revokeObjectURL(
    url
  );

  return {
    filename,
  };
}



// =========================================
// AUTHENTICATION
// =========================================

export async function login(
  email,
  password,
  rememberMe = false
) {
  return request(
    "/api/auth/login",
    {
      method: "POST",

      body:
        JSON.stringify({
          email,
          password,
          remember_me:
            rememberMe,
        }),
    }
  );
}



export async function register(
  email,
  password
) {
  return request(
    "/api/auth/register",
    {
      method: "POST",

      body:
        JSON.stringify({
          email,
          password,
        }),
    }
  );
}



export async function getCurrentUser() {
  return request(
    "/api/auth/me",
    {
      method: "GET",
    }
  );
}



export async function logout() {
  return request(
    "/api/auth/logout",
    {
      method: "POST",
    }
  );
}



// =========================================
// EXPORTS
// =========================================

export {
  API_URL,
};
