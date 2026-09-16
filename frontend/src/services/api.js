const API_URL =
  "http://127.0.0.1:8001";

async function request(
  endpoint,
  options = {}
) {
  const response =
    await fetch(
      `${API_URL}${endpoint}`,
      {
        ...options,
        headers: {
          "Content-Type":
            "application/json",
          ...(options.headers || {}),
        },
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
    throw new Error(
      data?.detail ||
        `NOVA request failed with status ${response.status}.`
    );
  }

  return data;
}

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
      method:
        "POST",

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
      method:
        "POST",

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
      method:
        "POST",

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

export async function sendChatMessage(
  payload
) {
  return request(
    "/api/chat/",
    {
      method:
        "POST",

      body:
        JSON.stringify(
          payload
        ),
    }
  );
}

export async function getConversations() {
  return request(
    "/api/history/conversations",
    {
      method:
        "GET",
      headers: {},
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
      method:
        "GET",
      headers: {},
    }
  );
}

export async function createConversation() {
  return request(
    "/api/history/conversations",
    {
      method:
        "POST",
      headers: {},
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
      method:
        "DELETE",
      headers: {},
    }
  );
}

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
      method:
        "POST",

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

export async function getModels() {
  return request(
    "/api/models",
    {
      method:
        "GET",
      headers: {},
    }
  );
}

export async function getModelStatus() {
  return request(
    "/api/models/status",
    {
      method:
        "GET",
      headers: {},
    }
  );
}

export {
  API_URL,
};