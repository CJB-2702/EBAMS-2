---
type: "Domain Doc"
title: "Asset Application - UI Routes and Pages Inventory"
description: "1."
tags: [applications, domain-doc, assets]
context_tier: 2
---

# Asset Application - UI Routes and Pages Inventory

## 1. Asset & AssetModel Management (The Core)

| Page | Classification | Goal / Workflow | Route (Proposed) |
| :--- | :--- | :--- | :--- |
| **Asset Directory Dashboard** | Navigation Page | High-level overview of all assets, search/filter, and quick links to asset categories. | `/assets/` |
| **Asset Detail View** | User View | Read-only view of a single asset's details, specs, parent/child tree, and meter history. | `/assets/<int:pk>/` |
| **Asset Creation Portal** | Work Portal | Form-based interface to create a new asset. | `/assets/new/` |
| **Asset Edit Portal** | Work Portal | Form-based interface to edit existing asset details. | `/assets/<int:pk>/edit/` |
| **Asset Hierarchy Portal** | Work Portal | Interface to assign/modify parent-child asset relationships. | `/assets/<int:pk>/hierarchy/edit/` |
| **Meter History Portal** | Work Portal | Interface to view and submit new meter readings for an asset. | `/assets/<int:pk>/meter-history/` |
| **Asset Models Dashboard** | Navigation Page | Directory of Asset Models, Asset Classes, and Manufacturers. | `/assets/models/` |
| **Asset Model Detail View** | User View | View specifications and details for a specific asset model. | `/assets/models/<int:pk>/` |
| **Asset Model Edit Portal** | Work Portal | Form to create/edit asset models. | `/assets/models/<int:pk>/edit/` |

## 2. Configuration Lifecycle

| Page | Classification | Goal / Workflow | Route (Proposed) |
| :--- | :--- | :--- | :--- |
| **Templates Directory** | Navigation Page | List of all Configuration Templates. | `/assets/configurations/templates/` |
| **Template Detail View** | User View | View a configuration template, its defined modifications, and template children. | `/assets/configurations/templates/<int:pk>/` |
| **Template Builder Portal** | Work Portal | Interface to create/edit a Configuration Template and its baseline requirements. | `/assets/configurations/templates/<int:pk>/edit/` |
| **Asset Configuration Portal** | Work Portal | Interface to assign a configuration template to a specific asset. | `/assets/<int:pk>/configuration/assign/` |
| **Actual Modifications Portal** | Work Portal | Interface for tracking actual modifications against the assigned template for an asset. | `/assets/<int:pk>/configuration/modifications/` |

## 3. Capabilities Engine

| Page | Classification | Goal / Workflow | Route (Proposed) |
| :--- | :--- | :--- | :--- |
| **Capability Catalog** | Navigation Page | Master list of all capability definitions. | `/assets/capabilities/catalog/` |
| **Capability Definition Portal** | Work Portal | Create/edit a capability definition. | `/assets/capabilities/catalog/<int:pk>/edit/` |
| **Class Capability Portal** | Work Portal | Assign capabilities to an entire Asset Class. | `/assets/classes/<int:pk>/capabilities/edit/` |
| **Model Capability Portal** | Work Portal | Assign or override capabilities at the Asset Model level. | `/assets/models/<int:pk>/capabilities/edit/` |
| **Asset Capability Portal** | Work Portal | Assign or override capabilities at the individual Asset level. | `/assets/<int:pk>/capabilities/edit/` |

## Workflow Mapping Example

**Workflow:** *Assigning a Configuration Template to an Asset and Tracking a Modification*
1.  **Entrypoint:** User navigates to the **Asset Detail View** (`/assets/123/`).
2.  **Action:** User clicks "Manage Configuration", routing to the **Asset Configuration Portal** (`/assets/123/configuration/assign/`).
3.  **Process:** User selects a template (e.g., "Standard Fleet Vehicle") and saves.
4.  **Action:** User wants to log a change, routing to the **Actual Modifications Portal** (`/assets/123/configuration/modifications/`).
5.  **Completion:** User submits the modification form and is returned to the **Asset Detail View** with updated configuration history.
