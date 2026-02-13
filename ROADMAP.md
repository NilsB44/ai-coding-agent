# 🤖 RAG: Strategic Roadmap

This roadmap outlines the plan to transform the local AI coding agent into a highly scalable, multi-agent autonomous system.

## Phase 1: Enable Parallel Agents ✅
*   **Git Worktrees for Agent Isolation:** ✅ Integrated `WorktreeManager` to allow multiple agents to operate concurrently on isolated branches.
*   **Parallel Validation Pipeline:** ✅ Implemented `ParallelValidator` to run multiple code variants and tests in parallel using concurrent execution.
*   **Gemini 2.0 Flash Integration:** ✅ Transitioned from local Ollama to Gemini 2.0 Flash for superior reasoning and schema extraction.

## Phase 2: Intelligence & Context
*   **Advanced RAG Logic:** Implement a more sophisticated retrieval system using vector databases to provide the agent with deep repository context.
*   **Agentic Self-Correction:** Enhance the self-healing loop to allow agents to reflect on test failures and plan multi-step fixes across files.

## Phase 3: Reliability & Safety
*   **Sandboxed Execution:** Strengthen the sandbox environment to ensure safe execution of agent-generated code across parallel runs.
*   **Automated Regression Testing:** Implement a suite of baseline coding tasks to measure and improve agent performance over time.
