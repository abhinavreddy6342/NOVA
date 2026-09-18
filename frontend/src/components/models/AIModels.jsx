import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Cpu,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Play,
  Shield,
  Server,
  Activity,
  Zap,
  Check,
  Terminal,
  Layers,
  HardDrive,
  Database,
  Clock3,
} from "lucide-react";

import {
  getModels,
  getModelStatus,
  getActiveModel,
  setActiveModel,
  testModel,
  getTaskRouting,
  saveTaskRouting,
  getModelActivity,
} from "../../services/api";


function formatCapability(capability) {
  return String(capability || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) =>
      character.toUpperCase()
    );
}


function formatTimestamp(value) {
  if (!value) {
    return "NOT AVAILABLE";
  }

  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return "NOT AVAILABLE";
  }

  return parsed.toLocaleString();
}


export default function AIModels() {
  // -------------------------------------------------------------------------
  // RUNTIME
  // -------------------------------------------------------------------------

  const [runtimeStatus, setRuntimeStatus] =
    useState("CHECKING");

  const [endpoint, setEndpoint] =
    useState("CHECKING");

  const [modelsList, setModelsList] =
    useState([]);

  const [activeModel, setActiveModelName] =
    useState("");

  const [installedCount, setInstalledCount] =
    useState(0);

  const [loading, setLoading] =
    useState(true);

  const [refreshing, setRefreshing] =
    useState(false);


  // -------------------------------------------------------------------------
  // ACTIVE MODEL
  // -------------------------------------------------------------------------

  const [switchingActive, setSwitchingActive] =
    useState(false);

  const [switchMessage, setSwitchMessage] =
    useState(null);


  // -------------------------------------------------------------------------
  // TEST CONSOLE
  // -------------------------------------------------------------------------

  const [testModelSelected, setTestModelSelected] =
    useState("");

  const [testPrompt, setTestPrompt] =
    useState("");

  const [testRunning, setTestRunning] =
    useState(false);

  const [testResult, setTestResult] =
    useState(null);

  const [testError, setTestError] =
    useState(null);


  // -------------------------------------------------------------------------
  // ROUTING
  // -------------------------------------------------------------------------

  const [routingConfig, setRoutingConfig] =
    useState({});

  const [savingRouting, setSavingRouting] =
    useState(false);

  const [routingMessage, setRoutingMessage] =
    useState(null);


  // -------------------------------------------------------------------------
  // ACTIVITY
  // -------------------------------------------------------------------------

  const [latestActivity, setLatestActivity] =
    useState(null);


  // -------------------------------------------------------------------------
  // DATA LOADING
  // -------------------------------------------------------------------------

  const fetchData = useCallback(
    async (isRefresh = false) => {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      try {
        // ---------------------------------------------------------------
        // 1. REAL RUNTIME STATUS
        // ---------------------------------------------------------------

        let statusRes = null;

        try {
          statusRes =
            await getModelStatus();
        } catch (error) {
          console.error(
            "Model runtime health check failed:",
            error
          );
        }

        const isOnline =
          statusRes?.status === "online" ||
          statusRes?.state === "READY";

        setRuntimeStatus(
          isOnline ? "READY" : "OFFLINE"
        );

        setEndpoint(
          statusRes?.endpoint ||
            "NOT AVAILABLE"
        );


        // ---------------------------------------------------------------
        // 2. REAL MODEL DISCOVERY
        // ---------------------------------------------------------------

        let modelsRes = null;

        try {
          modelsRes =
            await getModels();
        } catch (error) {
          console.error(
            "Model discovery failed:",
            error
          );

          modelsRes = {
            models: [],
            active_model: "",
            installed_count: 0,
          };
        }

        const discoveredModels =
          Array.isArray(
            modelsRes?.models
          )
            ? modelsRes.models
            : [];

        setModelsList(
          discoveredModels
        );

        setInstalledCount(
          Number.isFinite(
            modelsRes?.installed_count
          )
            ? modelsRes.installed_count
            : discoveredModels.filter(
                (model) => model.installed
              ).length
        );


        // ---------------------------------------------------------------
        // 3. REAL ACTIVE MODEL
        // ---------------------------------------------------------------

        let activeRes = null;

        try {
          activeRes =
            await getActiveModel();
        } catch (error) {
          console.error(
            "Active model lookup failed:",
            error
          );
        }

        const currentActive =
          activeRes?.active_model ||
          modelsRes?.active_model ||
          "";

        setActiveModelName(
          currentActive
        );


        // ---------------------------------------------------------------
        // 4. TEST CONSOLE DEFAULT
        // ---------------------------------------------------------------

        const installed =
          discoveredModels.filter(
            (model) =>
              model.installed
          );

        setTestModelSelected(
          (previous) => {
            if (
              previous &&
              installed.some(
                (model) =>
                  model.name === previous
              )
            ) {
              return previous;
            }

            if (
              currentActive &&
              installed.some(
                (model) =>
                  model.name === currentActive
              )
            ) {
              return currentActive;
            }

            return (
              installed[0]?.name ||
              ""
            );
          }
        );


        // ---------------------------------------------------------------
        // 5. REAL ROUTING CONFIGURATION
        // ---------------------------------------------------------------

        try {
          const routingRes =
            await getTaskRouting();

          setRoutingConfig(
            routingRes?.routing || {}
          );
        } catch (error) {
          console.error(
            "Task routing lookup failed:",
            error
          );
        }


        // ---------------------------------------------------------------
        // 6. VERIFIED ACTIVITY
        // ---------------------------------------------------------------

        try {
          const activityRes =
            await getModelActivity();

          setLatestActivity(
            activityRes?.activity ||
              null
          );
        } catch (error) {
          console.error(
            "Model activity lookup failed:",
            error
          );
        }

      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    []
  );


  useEffect(() => {
    fetchData(false);
  }, [fetchData]);


  // -------------------------------------------------------------------------
  // ACTIVE MODEL CHANGE
  // -------------------------------------------------------------------------

  const handleSetActiveModel =
    async (modelName) => {
      if (
        !modelName ||
        modelName === activeModel
      ) {
        return;
      }

      setSwitchingActive(true);
      setSwitchMessage(null);

      try {
        const result =
          await setActiveModel(
            modelName
          );

        if (
          result?.status !==
            "success" ||
          !result?.active_model
        ) {
          throw new Error(
            result?.detail ||
              "Failed to change active model."
          );
        }

        setActiveModelName(
          result.active_model
        );

        setSwitchMessage({
          type: "success",
          text:
            `Active model confirmed: ` +
            result.active_model,
        });

        await fetchData(true);

      } catch (error) {
        console.error(
          "Active model switch error:",
          error
        );

        setSwitchMessage({
          type: "error",
          text:
            error?.message ||
            "Failed to change active model.",
        });

      } finally {
        setSwitchingActive(false);
      }
    };


  // -------------------------------------------------------------------------
  // TEST MODEL
  // -------------------------------------------------------------------------

  const handleRunTest =
    async (event) => {
      event?.preventDefault();

      if (
        !testPrompt.trim() ||
        !testModelSelected
      ) {
        return;
      }

      setTestRunning(true);
      setTestResult(null);
      setTestError(null);

      try {
        const result =
          await testModel({
            model: testModelSelected,
            prompt: testPrompt,
          });

        if (
          result?.status !==
          "SUCCESS"
        ) {
          throw new Error(
            result?.detail ||
              "Local inference test failed."
          );
        }

        setTestResult({
          response:
            result.response || "",
          model_used:
            result.model_used ||
            testModelSelected,
          latency_ms:
            result.latency_ms ??
            null,
          status:
            "SUCCESS",
        });


        try {
          const activityRes =
            await getModelActivity();

          setLatestActivity(
            activityRes?.activity ||
              null
          );
        } catch (error) {
          console.error(
            "Failed to refresh verified activity:",
            error
          );
        }

      } catch (error) {
        console.error(
          "Model test error:",
          error
        );

        setTestError(
          error?.message ||
            "Inference test failed."
        );

        setTestResult({
          response: "",
          model_used:
            testModelSelected,
          latency_ms: null,
          status: "FAILED",
        });

      } finally {
        setTestRunning(false);
      }
    };


  // -------------------------------------------------------------------------
  // ROUTING SAVE
  // -------------------------------------------------------------------------

  const handleSaveRouting =
    async (
      taskKey,
      targetModel
    ) => {
      const previousValue =
        routingConfig[taskKey];

      const updated = {
        ...routingConfig,
        [taskKey]:
          targetModel,
      };

      setSavingRouting(true);
      setRoutingMessage(null);

      try {
        const result =
          await saveTaskRouting(
            updated
          );

        if (
          result?.status !==
          "success"
        ) {
          throw new Error(
            result?.detail ||
              "Failed to save routing."
          );
        }

        setRoutingConfig(
          result.routing ||
            updated
        );

        setRoutingMessage({
          type: "success",
          text:
            "Task routing saved and confirmed by NOVA backend.",
        });

      } catch (error) {
        console.error(
          "Routing save error:",
          error
        );

        setRoutingConfig(
          (current) => {
            const restored = {
              ...current,
            };

            if (
              previousValue ===
              undefined
            ) {
              delete restored[
                taskKey
              ];
            } else {
              restored[
                taskKey
              ] = previousValue;
            }

            return restored;
          }
        );

        setRoutingMessage({
          type: "error",
          text:
            error?.message ||
            "Failed to update routing.",
        });

      } finally {
        setSavingRouting(false);
      }
    };


  // -------------------------------------------------------------------------
  // DERIVED STATE
  // -------------------------------------------------------------------------

  const installedModels =
    modelsList.filter(
      (model) =>
        model.installed
    );

  const activeInstalledModel =
    installedModels.find(
      (model) =>
        model.name ===
        activeModel
    );

  const activeReady =
    runtimeStatus === "READY" &&
    Boolean(activeInstalledModel);


  // -------------------------------------------------------------------------
  // RENDER
  // -------------------------------------------------------------------------

  return (
    <motion.div
      className="nova-models-container"
      initial={{
        opacity: 0,
        y: 12,
      }}
      animate={{
        opacity: 1,
        y: 0,
      }}
      exit={{
        opacity: 0,
        y: -10,
      }}
      transition={{
        duration: 0.4,
        ease: "easeOut",
      }}
    >

      {/* ================================================================
          HEADER
      ================================================================ */}

      <div className="models-section-header">

        <div className="models-header-titles">

          <span className="models-eyebrow">
            NOVA WORKBENCH
          </span>

          <h1 className="models-title">
            LOCAL MODEL CONTROL CENTER
          </h1>

        </div>

        <button
          className="models-refresh-btn"
          onClick={() =>
            fetchData(true)
          }
          disabled={
            refreshing ||
            loading
          }
          type="button"
        >

          <RefreshCw
            size={14}
            className={
              refreshing
                ? "spin-icon"
                : ""
            }
          />

          <span>
            {refreshing
              ? "DISCOVERING MODELS..."
              : "REFRESH MODELS"}
          </span>

        </button>

      </div>


      {/* ================================================================
          RUNTIME
      ================================================================ */}

      <div className="models-runtime-card">

        <div className="runtime-badge-group">

          <div className="runtime-label">

            <Server size={16} />

            <span>
              LOCAL MODEL RUNTIME:
            </span>

            <strong>
              Ollama
            </strong>

          </div>

          <div
            className={
              `runtime-status-badge ` +
              `status-${runtimeStatus.toLowerCase()}`
            }
          >

            {runtimeStatus ===
              "READY" && (
              <CheckCircle2 size={14} />
            )}

            {runtimeStatus ===
              "OFFLINE" && (
              <AlertCircle size={14} />
            )}

            {runtimeStatus ===
              "CHECKING" && (
              <RefreshCw
                size={14}
                className="spin-icon"
              />
            )}

            <span>
              {runtimeStatus}
            </span>

          </div>

        </div>


        <div className="runtime-details-grid">

          <div className="runtime-detail-item">

            <span className="detail-key">
              ENDPOINT URL
            </span>

            <span className="detail-val font-mono">
              {endpoint}
            </span>

          </div>


          <div className="runtime-detail-item">

            <span className="detail-key">
              INSTALLED MODELS
            </span>

            <span className="detail-val">
              {installedCount} MODELS
            </span>

          </div>


          <div className="runtime-detail-item">

            <span className="detail-key">
              ACTIVE MODEL
            </span>

            <span className="detail-val font-accent">
              {activeModel ||
                "NOT AVAILABLE"}
            </span>

          </div>


          <div className="runtime-detail-item">

            <span className="detail-key">
              EXECUTION MODE
            </span>

            <span className="detail-val">
              LOCAL MODEL EXECUTION
            </span>

          </div>

        </div>

      </div>


      {/* ================================================================
          ACTIVE MODEL
      ================================================================ */}

      <div className="models-active-banner">

        <div className="active-banner-info">

          <div className="active-banner-label">

            <Zap
              size={16}
              className="text-cyan"
            />

            <span>
              CURRENT CONFIRMED ACTIVE MODEL
            </span>

          </div>

          <h2 className="active-model-name">

            {activeModel ||
              "No Active Model"}

          </h2>

          <span className="active-model-status">

            STATUS:{" "}
            {activeReady
              ? "LOCAL / READY"
              : runtimeStatus ===
                "OFFLINE"
              ? "RUNTIME OFFLINE"
              : activeInstalledModel
              ? "LOCAL / NOT READY"
              : "UNAVAILABLE"}

          </span>

        </div>


        <div className="active-model-switch-control">

          <label htmlFor="active-model-select">
            CHANGE ACTIVE MODEL:
          </label>

          <div className="select-with-btn">

            <select
              id="active-model-select"
              value={activeModel}
              onChange={(event) =>
                handleSetActiveModel(
                  event.target.value
                )
              }
              disabled={
                switchingActive ||
                installedModels.length ===
                  0 ||
                runtimeStatus !==
                  "READY"
              }
            >

              {installedModels.length ===
              0 ? (
                <option value="">
                  No verified local models
                </option>
              ) : (
                installedModels.map(
                  (model) => (
                    <option
                      key={model.name}
                      value={model.name}
                    >
                      {model.name}
                      {model.name ===
                      activeModel
                        ? " (ACTIVE)"
                        : ""}
                    </option>
                  )
                )
              )}

            </select>

          </div>

          {switchMessage && (
            <span
              className={
                `switch-msg msg-` +
                switchMessage.type
              }
            >
              {switchMessage.text}
            </span>
          )}

        </div>

      </div>


      {/* ================================================================
          INSTALLED MODELS
      ================================================================ */}

      <div className="models-section">

        <div className="section-title-row">

          <Cpu size={18} />

          <h2>
            INSTALLED MODELS (
            {installedModels.length}
            )
          </h2>

        </div>


        {loading ? (
          <div className="models-loading-state">

            <RefreshCw
              size={20}
              className="spin-icon"
            />

            <span>
              DISCOVERING LOCAL MODELS...
            </span>

          </div>
        ) : installedModels.length ===
          0 ? (
          <div className="models-empty-state">

            <AlertCircle size={24} />

            <p>
              {runtimeStatus ===
              "OFFLINE"
                ? "LOCAL OLLAMA RUNTIME OFFLINE"
                : "NO LOCAL OLLAMA MODELS DETECTED"}
            </p>

            <span className="sub-text">

              {runtimeStatus ===
              "OFFLINE"
                ? "NOVA cannot verify local models until the Ollama runtime becomes reachable."
                : "Install an Ollama model locally and click Refresh Models."}

            </span>

          </div>
        ) : (
          <div className="models-cards-grid">

            {installedModels.map(
              (model) => {

                const isActive =
                  model.name ===
                  activeModel;

                return (
                  <motion.div
                    key={model.name}
                    className={
                      `model-card ` +
                      `${
                        isActive
                          ? "card-active"
                          : ""
                      }`
                    }
                    whileHover={{
                      y: -2,
                    }}
                    transition={{
                      duration: 0.18,
                    }}
                  >

                    <div className="card-header">

                      <div className="card-title-group">

                        <span className="model-id-badge font-mono">
                          {model.name}
                        </span>

                        <h3 className="card-model-name">
                          {model.name}
                        </h3>

                      </div>


                      <div
                        className={
                          `card-status-pill ` +
                          `${
                            isActive
                              ? "pill-active"
                              : "pill-installed"
                          }`
                        }
                      >
                        {isActive
                          ? "ACTIVE"
                          : "INSTALLED"}
                      </div>

                    </div>


                    <p className="card-description">
                      {model.description ||
                        "NOT AVAILABLE"}
                    </p>


                    <div className="card-capabilities">

                      <span className="cap-label">
                        NOVA CAPABILITY PROFILE
                      </span>

                      <div className="cap-tags">

                        {Array.isArray(
                          model.capabilities
                        ) &&
                        model.capabilities.length >
                          0 ? (
                          model.capabilities.map(
                            (capability) => (
                              <span
                                key={
                                  capability
                                }
                                className="cap-tag"
                              >
                                {formatCapability(
                                  capability
                                )}
                              </span>
                            )
                          )
                        ) : (
                          <span className="cap-tag">
                            NOT AVAILABLE
                          </span>
                        )}

                      </div>

                    </div>


                    <div className="card-details-table">

                      <div className="detail-row">
                        <span>
                          <HardDrive
                            size={11}
                            style={{
                              verticalAlign:
                                "middle",
                              marginRight:
                                5,
                            }}
                          />
                          Size
                        </span>

                        <strong>
                          {model.size_human ||
                            "NOT AVAILABLE"}
                        </strong>
                      </div>


                      <div className="detail-row">
                        <span>
                          <Database
                            size={11}
                            style={{
                              verticalAlign:
                                "middle",
                              marginRight:
                                5,
                            }}
                          />
                          Parameters
                        </span>

                        <strong>
                          {model.parameter_size ||
                            "NOT AVAILABLE"}
                        </strong>
                      </div>


                      <div className="detail-row">
                        <span>
                          Format
                        </span>

                        <strong>
                          {model.format ||
                            "NOT AVAILABLE"}
                        </strong>
                      </div>


                      <div className="detail-row">
                        <span>
                          Family
                        </span>

                        <strong>
                          {model.family ||
                            "NOT AVAILABLE"}
                        </strong>
                      </div>


                      <div className="detail-row">
                        <span>
                          Quantization
                        </span>

                        <strong>
                          {model.quantization_level ||
                            "NOT AVAILABLE"}
                        </strong>
                      </div>


                      <div className="detail-row">
                        <span>
                          Context Length
                        </span>

                        <strong>
                          {model.context_length ||
                            "NOT AVAILABLE"}
                        </strong>
                      </div>

                    </div>


                    <div className="card-actions">

                      {!isActive && (
                        <button
                          type="button"
                          className="btn-select-active"
                          onClick={() =>
                            handleSetActiveModel(
                              model.name
                            )
                          }
                          disabled={
                            switchingActive ||
                            runtimeStatus !==
                              "READY"
                          }
                        >
                          <Check size={14} />
                          <span>
                            SELECT AS ACTIVE
                          </span>
                        </button>
                      )}


                      <button
                        type="button"
                        className="btn-test-model"
                        onClick={() => {

                          setTestModelSelected(
                            model.name
                          );

                          const consoleElement =
                            document.getElementById(
                              "model-test-console"
                            );

                          consoleElement?.scrollIntoView(
                            {
                              behavior:
                                "smooth",
                            }
                          );
                        }}
                        disabled={
                          runtimeStatus !==
                          "READY"
                        }
                      >
                        <Play size={13} />
                        <span>
                          TEST CONSOLE
                        </span>
                      </button>

                    </div>

                  </motion.div>
                );
              }
            )}

          </div>
        )}

      </div>


      {/* ================================================================
          MODEL TEST CONSOLE
      ================================================================ */}

      <div
        id="model-test-console"
        className="models-section test-console-section"
      >

        <div className="section-title-row">

          <Terminal size={18} />

          <h2>
            MODEL TEST CONSOLE
          </h2>

        </div>


        <form
          className="test-form"
          onSubmit={handleRunTest}
        >

          <div className="form-group-row">

            <div className="form-group">

              <label htmlFor="test-model-select">
                TARGET LOCAL MODEL
              </label>

              <select
                id="test-model-select"
                value={
                  testModelSelected
                }
                onChange={(event) =>
                  setTestModelSelected(
                    event.target.value
                  )
                }
                disabled={
                  testRunning ||
                  installedModels.length ===
                    0 ||
                  runtimeStatus !==
                    "READY"
                }
              >

                {installedModels.length ===
                0 ? (
                  <option value="">
                    No verified local models
                  </option>
                ) : (
                  installedModels.map(
                    (model) => (
                      <option
                        key={model.name}
                        value={model.name}
                      >
                        {model.name}
                      </option>
                    )
                  )
                )}

              </select>

            </div>

          </div>


          <div className="form-group">

            <label htmlFor="test-prompt">
              PROMPT
            </label>

            <textarea
              id="test-prompt"
              rows={4}
              placeholder="Enter a real test prompt for the selected local model..."
              value={
                testPrompt
              }
              onChange={(event) =>
                setTestPrompt(
                  event.target.value
                )
              }
              disabled={
                testRunning ||
                runtimeStatus !==
                  "READY"
              }
            />

          </div>


          <button
            type="submit"
            className="btn-run-test"
            disabled={
              testRunning ||
              runtimeStatus !==
                "READY" ||
              !testPrompt.trim() ||
              !testModelSelected
            }
          >

            {testRunning ? (
              <>
                <RefreshCw
                  size={14}
                  className="spin-icon"
                />

                <span>
                  EXECUTING LOCAL INFERENCE...
                </span>
              </>
            ) : (
              <>
                <Play size={14} />

                <span>
                  RUN TEST
                </span>
              </>
            )}

          </button>

        </form>


        {(testResult ||
          testError) && (

          <div className="test-output-card">

            <div className="test-output-header">

              <div className="meta-badge-group">

                <span className="meta-item">

                  MODEL USED:{" "}

                  <strong>
                    {testResult?.model_used ||
                      testModelSelected ||
                      "NOT AVAILABLE"}
                  </strong>

                </span>


                <span className="meta-item">

                  <Clock3
                    size={12}
                    style={{
                      verticalAlign:
                        "middle",
                      marginRight:
                        4,
                    }}
                  />

                  LATENCY:{" "}

                  <strong>
                    {testResult?.latency_ms !=
                    null
                      ? `${testResult.latency_ms} ms`
                      : "NOT AVAILABLE"}
                  </strong>

                </span>


                <span
                  className={
                    `status-pill ` +
                    `${
                      testResult?.status ===
                      "SUCCESS"
                        ? "pill-success"
                        : "pill-failed"
                    }`
                  }
                >
                  {testResult?.status ||
                    "FAILED"}
                </span>

              </div>

            </div>


            {testError ? (
              <div className="test-error-box">

                <AlertCircle size={16} />

                <span>
                  {testError}
                </span>

              </div>
            ) : (
              <div className="test-response-box font-mono">

                {testResult?.response ||
                  "NO RESPONSE RETURNED"}

              </div>
            )}

          </div>
        )}

      </div>


      {/* ================================================================
          TASK ROUTING
      ================================================================ */}

      <div className="models-section">

        <div className="section-title-row">

          <Layers size={18} />

          <h2>
            TASK ROUTING CONFIGURATION
          </h2>

        </div>


        <p className="section-desc">
          Configure which verified local model executes each NOVA task type.
        </p>


        <div className="routing-grid">

          {[
            {
              id: "general",
              label: "General Chat",
              desc:
                "Standard conversational requests",
            },
            {
              id: "coding",
              label: "Coding & Technical",
              desc:
                "Software development, debugging and scripts",
            },
            {
              id: "document",
              label: "Document Analysis",
              desc:
                "Local document processing and analysis",
            },
            {
              id: "reasoning",
              label: "Reasoning & Math",
              desc:
                "Analytical and logical reasoning tasks",
            },
            {
              id: "knowledge",
              label: "Knowledge / RAG",
              desc:
                "Responses grounded in selected local knowledge",
            },
            {
              id: "mission",
              label: "Mission Execution",
              desc:
                "Autonomous multi-step NOVA missions",
            },
          ].map(
            (task) => {

              const selectedModel =
                routingConfig[
                  task.id
                ] ||
                activeModel ||
                installedModels[0]
                  ?.name ||
                "";

              return (
                <div
                  key={task.id}
                  className="routing-item"
                >

                  <div className="routing-task-info">

                    <strong>
                      {task.label}
                    </strong>

                    <span>
                      {task.desc}
                    </span>

                  </div>


                  <select
                    value={
                      selectedModel
                    }
                    onChange={(
                      event
                    ) =>
                      handleSaveRouting(
                        task.id,
                        event.target
                          .value
                      )
                    }
                    disabled={
                      savingRouting ||
                      runtimeStatus !==
                        "READY" ||
                      installedModels.length ===
                        0
                    }
                  >

                    {installedModels.map(
                      (model) => (
                        <option
                          key={
                            model.name
                          }
                          value={
                            model.name
                          }
                        >
                          {model.name}
                        </option>
                      )
                    )}

                  </select>

                </div>
              );
            }
          )}

        </div>


        {savingRouting && (
          <div className="routing-msg">
            Saving routing configuration...
          </div>
        )}


        {routingMessage && (
          <div
            className={
              `routing-msg msg-` +
              routingMessage.type
            }
          >
            {routingMessage.text}
          </div>
        )}

      </div>


      {/* ================================================================
          VERIFIED ACTIVITY
      ================================================================ */}

      <div className="models-section">

        <div className="section-title-row">

          <Activity size={18} />

          <h2>
            VERIFIED MODEL ACTIVITY
          </h2>

        </div>


        {latestActivity ? (

          <div className="activity-card">

            <div className="activity-row">
              <span>
                LATEST MODEL USED:
              </span>

              <strong className="font-mono">
                {latestActivity.latest_model_used ||
                  "NOT AVAILABLE"}
              </strong>
            </div>


            <div className="activity-row">
              <span>
                LAST TASK:
              </span>

              <strong>
                {latestActivity.last_task ||
                  "NOT AVAILABLE"}
              </strong>
            </div>


            <div className="activity-row">
              <span>
                LAST STATUS:
              </span>

              <strong
                className={
                  `status-text-` +
                  `${
                    latestActivity.last_status
                      ?.toLowerCase() ||
                    "failed"
                  }`
                }
              >
                {latestActivity.last_status ||
                  "NOT AVAILABLE"}
              </strong>
            </div>


            <div className="activity-row">
              <span>
                LAST LATENCY:
              </span>

              <strong>
                {latestActivity.latency_ms !=
                null
                  ? `${latestActivity.latency_ms} ms`
                  : "NOT AVAILABLE"}
              </strong>
            </div>


            <div className="activity-row">
              <span>
                LAST USED TIMESTAMP:
              </span>

              <strong className="font-mono">
                {formatTimestamp(
                  latestActivity.last_used
                )}
              </strong>
            </div>

          </div>

        ) : (

          <div className="activity-empty font-mono">
            NO VERIFIED ACTIVITY
          </div>

        )}

      </div>


      {/* ================================================================
          SOVEREIGNTY
      ================================================================ */}

      <div className="models-sovereignty-footer">

        <Shield
          size={16}
          className="text-cyan"
        />

        <span>
          LOCAL MODEL EXECUTION — RUNTIME:
          OLLAMA — INFERENCE REQUESTS STAY
          WITHIN THE CONFIGURED LOCAL MODEL
          RUNTIME
        </span>

      </div>

    </motion.div>
  );
}