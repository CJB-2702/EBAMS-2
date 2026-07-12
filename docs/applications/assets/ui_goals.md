---
type: "Domain Doc"
title: "Asset Application - UI Goals"
description: "The Assets application provides a comprehensive system for managing physical assets, their hierarchical models, lifecycle configurations, and defined capabilities."
tags: [applications, domain-doc, assets]
context_tier: 2
---

# Asset Application - UI Goals

**Core Value Proposition:**
The Assets application provides a comprehensive system for managing physical assets, their hierarchical models, lifecycle configurations, and defined capabilities. It serves as the single source of truth for an organization's physical inventory, tracking what an asset is, how it is configured, what it can do, and its operational history.

## Domain Models Identified
- **Core Entities:** Asset, AssetModel, AssetClass, Manufacturer
- **History & Tracking:** AssetParentHistory, MeterHistory, AssetEvent, AssetImage
- **Configurations:** ConfigurationTemplate, TemplateChild, DefinedModification, TemplateModification, AssetConfiguration, ActualModification
- **Capabilities:** CapabilityDefinition, AssetClassCapability, ModelCapability, AssetCapability

## Core Business Goals

### 1. Asset & AssetModel Management (The Core)
*   **Goal:** Establish the foundational directory of equipment.
*   **Value:** Users must be able to view, create, and manage `Asset` and `AssetModel` records. They need clear navigation to understand parent/child asset relationships (the tree) and access historical data like meter readings and lifecycle events.

### 2. Configuration Lifecycle
*   **Goal:** Manage how assets are structured and modified over time.
*   **Value:** Users need interfaces for defining Configuration Templates (and their children/defined modifications). They must be able to assign these templates to specific assets and track "Actual Modifications" against the template baselines to ensure compliance and track drift.

### 3. Capabilities Engine
*   **Goal:** Track what assets are capable of performing.
*   **Value:** Users need screens to view the complete catalog of capabilities. They must be able to assign and manage capability layers across the cascade: from broad `AssetClass` assignments, down to specific `AssetModel` overrides, and finally individual `Asset` assignments.
