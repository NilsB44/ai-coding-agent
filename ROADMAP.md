# 🤖 RAG: Strategic Roadmap

This roadmap outlines the plan to transform the local AI coding agent into a highly scalable, multi-agent autonomous system.

## Phase 1: Enable Parallel Agents
*   **Git Worktrees for Agent Isolation:** Integrate git worktrees to allow multiple "Surgeon" and "Architect" agents to operate concurrently on isolated branches within the repository.
*   **Parallel Validation Pipeline:** Optimize the self-healing loop to run multiple code variants and tests in parallel.

## Phase 2: Model & Reasoning Upgrades
*   **Gemini 2.0 Flash Integration:** transition from local Llama 3 to Gemini 2.0 Flash to leverage 1M+ token context and advanced tool-calling capabilities.
*   **Advanced RAG Logic:** Implement a more sophisticated retrieval system using vector databases to provide the agent with deep repository context.

## Phase 3: Reliability & Safety
*   **Sandboxed Execution:** Strengthen the sandbox environment to ensure safe execution of agent-generated code across parallel runs.
*   **Automated Regression Testing:** Implement a suite of baseline coding tasks to measure and improve agent performance over time.
