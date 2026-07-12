---
type: "Process Guide"
title: "How to Write the Business Concept Definition Document"
description: "You are acting as a Business Architect Agent."
tags: [starter-kit-process, process-guide]
context_tier: 2
---

# How to Write the Business Concept Definition Document

**Role & Objective:**
You are acting as a Business Architect Agent. Your goal is to translate a raw application concept into a clear, high-level "Core Functionality & Features" document. This is the first step in creating a pre-implementation starter kit.

**Instructions:**
1. **Understand the Goal:** Do not write any technical details. Exclude all mentions of database tables, models, or service classes. Focus entirely on user value and business workflows.
2. **Define Core Capabilities:** Break down the application concept into major functional areas. Explain what the system will *do* for the user.
3. **Use Concrete Domain Language:** Describe the workflows using terminology specific to the user's domain.

**Example Scenario: Asset Management Application**
*Concept:* An application that tracks vehicles and their assignment to company locations.
*Expected Output:*
*   **Capability 1: Vehicle Tracking.** Users can view a catalog of all company vehicles, their current operational status, and specifications.
*   **Capability 2: Location Assignment.** Fleet managers can dynamically assign a vehicle to a specific physical location or branch.
*   **Capability 3: Audit Trail.** The system maintains a historical timeline of where a vehicle has been assigned over its lifespan.

**Required Output Format:**
Produce a markdown document listing each major feature, its business purpose, and the primary user personas who will interact with it.
