# App Starter Kit: Pre-Implementation Specification Process

This document outlines the structured process for building a **Starter Kit** (initial review package) prior to developing a new application. The goal of this process is to establish core data models, service patterns, functional requirements, user interface flows, and visual look-and-feel before writing any production application code.

---

## 1. Database Schema & Relational Models
The foundation of the starter kit begins with defining the primary data domain structures.

*   **Database Table Inventory:** Compile a comprehensive list of all proposed database tables required for the application.
*   **Domain Relational Charts:** Diagram the relationships between major data domain objects.
*   **Scope & Focus:**
    *   **Prioritize core domain relationships:** Focus on key business-entity relationships (e.g., the relationship between `Events`, `Comments`, `Attachments`, and `Files`).
    *   **Exclude auxiliary system relations:** Do not map low-level infrastructure or cross-cutting concerns (e.g., mapping `User` to permission rules or access control tables) in this initial stage. Keep the focus entirely on primary data structures.

---

## 2. Service Architecture Patterns (DTOs, Contexts, & Managers)
Once data structures are defined, specify the patterns for accessing and manipulating them.

*   **Data Transfer Objects (DTOs / Structs):** Establish clean, read/write representations (Structs) based on the database tables.
*   **Service Classes & Managers:** Service classes will manage business logic and delegate operations to dedicated sub-managers.
*   **Context Objects:** Create a Context Object for each major Struct. The Context manages and instantiates sub-managers for performing complex actions.
    *   *Example Pattern:*
        *   An `EventContext` provides access to an `EventCommentManager`.
        *   The `EventCommentManager` handles fetching and attaching comments or files related to the event.
        *   *Flow:* `EventContext` $\rightarrow$ Instantiates `CommentManager` $\rightarrow$ Passes DTO/Struct to Manager $\rightarrow$ User/View interacts via the manager.

---

## 3. Core Functionality & Features Document
Separate the business capability from the technical data model.

*   **High-Level Feature Catalog:** Maintain a dedicated document summarizing key capabilities and functionality.
*   **No Technical Details:** This document must be free of database tables, service classes, or structure details. It is purely a functional overview of what the application achieves for the user.

---

## 4. Page Inventory & Classifications
List every interface page, its objective, and its role in the overall user flow.

*   **Goal Definition:** Clearly state the primary objective of each page.
*   **Page Classifications:**
    *   **User View:** Read-only or detail screens presenting information.
    *   **Work Portal:** Action-oriented interfaces designed for inputting data or executing workflows.
    *   **Navigation Page:** Entrypoints, dashboards, or hubs to orient the user and route them to other workflows.

---

## 5. Flask Static HTML Prototyping
Before writing the final templates in the target framework, build a quick interactive prototype.

*   **Technology:** Use a lightweight, simple Flask application.
*   **Content:** Static HTML pages with dummy data.
*   **Objective:** Validate visual style, user experience, typography, hierarchy, and overall look-and-feel of the listed pages before any backend logic is implemented.
