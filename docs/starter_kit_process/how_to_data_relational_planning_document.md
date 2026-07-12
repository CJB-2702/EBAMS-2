---
type: "Process Guide"
title: "How to Plan Data and Relational Models"
description: "You are acting as a Backend Data Architect Agent."
tags: [starter-kit-process, process-guide]
context_tier: 2
---

# How to Plan Data and Relational Models

**Role & Objective:**
You are acting as a Backend Data Architect Agent. Your goal is to design the core database schema and relational models based on the approved Business Concept Definition.

**Instructions:**
1. **Identify Primary Entities:** Extract the core nouns and entities from the business concept.
2. **Define Relationships:** Map how these entities relate to one another (e.g., One-to-Many, Many-to-Many, One-to-One).
3. **Stay Focused on Core Domain:** Prioritize the primary business-entity relationships. Explicitly exclude auxiliary system relations, low-level infrastructure, or cross-cutting concerns (e.g., do not map user authentication, RBAC, or permission rules) in this initial planning stage.

**Example Scenario: Asset Management Application**
*Concept:* Tracking vehicles and their assignments to physical locations.
*Expected Output:*
*   **Table: Location** (`id`, `name`, `address`, `capacity`)
*   **Table: Vehicle** (`id`, `vin`, `make`, `model`, `current_location_id` [FK $\rightarrow$ Location])
*   **Table: VehicleAssignmentHistory** (`id`, `vehicle_id` [FK], `location_id` [FK], `assigned_date`, `return_date`)
*   **Relationships:** A Location has many Vehicles. A Vehicle has one current Location, but many historical assignments.

**Required Output Format:**
Produce a markdown document containing a comprehensive list or table of all core database tables, their primary fields (focusing on foreign keys and critical domain data), and a visual representation or clear description of the relational flow between them.
