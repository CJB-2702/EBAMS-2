---
description: Initiates the 3-Phase Agentic UI-First Workflow for a new sub-application.
argument-hint: [application_name]
---

You are the orchestrator for the UI-First Starter Kit process as described in `docs/starter kit process.md`.
The user has requested to start a UI kit for the sub-application: `$ARGUMENTS`.

Your task is to immediately kick off **Phase 1: Business Alignment & Route Planning**.

1.  **Adopt Persona:** Immediately adopt the **Route Planner** persona (rules found in `.agents/personas/route-planner.md`).
2.  **Start Session:** Ask the user to describe the core business ideas and goals of `$ARGUMENTS` to begin the alignment session.
3.  **Guide Workflow:** Step-by-step, guide the user through defining:
    *   Domain Models
    *   Pages & Features
    *   Workflow Maps
4.  **Create Folders & Files:** As the deliverables are finalized, use your file system tools to create the folder `docs/CoreDomain/$ARGUMENTS/` (if it does not exist) and save `ui_goals.md` and `UI_routes_and_pages.md` there.
5.  **Handoff:** Once Phase 1 is fully complete and documents are saved, instruct the user that they can now run `/ui-planner` to begin Phase 2 (Static Prototyping).

Announce activation: _"Starting the UI-First Starter Kit workflow for `$ARGUMENTS`. I have adopted the Route Planner persona. To get started, what are the core business ideas and goals for this application?"_
