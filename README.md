# NOVA — Sovereign Industrial Intelligence

<p align="center">
  <strong>Private AI. Local Intelligence. Controlled Execution. Auditable Workflows.</strong>
</p>

<p align="center">
  A sovereign, on-premise, agentic AI workbench for confidential industrial workflows using open-weight models and local execution.
</p>

<p align="center">

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-Frontend-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Ollama](https://img.shields.io/badge/Ollama-Local%20AI-111111?style=for-the-badge)
![ChromaDB](https://img.shields.io/badge/ChromaDB-RAG-FF6B35?style=for-the-badge)
![SQLite](https://img.shields.io/badge/SQLite-Local%20Storage-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

</p>

---

## Overview

**NOVA — Sovereign Industrial Intelligence** is an on-premise, privacy-first AI workbench designed for confidential industrial and enterprise environments where sensitive documents, operational data, engineering information, internal workflows, and organizational knowledge should remain under local control.

NOVA combines **local large language models, retrieval-augmented generation, agentic planning, mission execution, document understanding, multimodal processing, artifact generation, authentication, auditability, analytics, and runtime visibility** into a single modular platform.

The core philosophy is simple:

> **Sensitive information should not need to leave its environment just to become useful.**

### NOVA at a glance

```text
                 ┌─────────────────────────┐
                 │        USER / TEAM      │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │      NOVA WORKSPACE     │
                 └────────────┬────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
   │  LOCAL CHAT │     │  KNOWLEDGE  │     │  MISSIONS   │
   │             │     │    VAULT    │     │             │
   └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
                 ┌─────────────────────────┐
                 │   LOCAL AI + AGENTS     │
                 │                         │
                 │ Ollama • LLMs • RAG    │
                 │ Planner • Executor     │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │   VERIFIED EXECUTION    │
                 │                         │
                 │ Artifacts • Reports    │
                 │ Outputs • Results       │
                 └────────────┬────────────┘
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
      ┌─────────────────┐           ┌─────────────────┐
      │   AUDIT TRAIL   │           │ ANALYTICS       │
      │ Append-only     │           │ Runtime insights│
      └─────────────────┘           └─────────────────┘
