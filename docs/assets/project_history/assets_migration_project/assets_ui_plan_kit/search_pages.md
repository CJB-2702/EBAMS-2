# Search Pages Inventory

This document defines the full set of search and list pages for the assets application. It specifies the available filters and the columns displayed on each page, emphasizing the inclusion of related domain information to provide rich context without requiring the user to click into individual records.

---

## 1. Search Assets (`/assets/`)
The primary directory for physical assets.

**Filters:**
*   **Text Search:** Name or Serial Number
*   **Data Domain:** The organizational scope (e.g., North Fleet Ops)
*   **Asset Class:** The broad category of the asset
*   **Asset Model:** The specific model (filters down based on Class)
*   **Manufacturer:** The maker of the asset (filters Model)
*   **Status:** Active, Down, Inactive
*   **Capability Status:** Operational, Limited, Down

**Columns:**
1.  **Name** (Link to Asset-360)
2.  **Serial Number** (Monospace)
3.  **Asset Class** (Related domain info)
4.  **Asset Model** (Related domain info)
5.  **Manufacturer** (Related domain info)
6.  **Data Domain** (Related domain info)
7.  **Status** (Status Tag)
8.  **Capability Status** (Status Tag)
9.  **Actions** (View, Edit)

---

## 2. Search Asset Models (`/assets/models/`)
The catalog of available equipment models.

**Filters:**
*   **Text Search:** Model Name or Subtype
*   **Asset Class:** The class this model belongs to
*   **Manufacturer:** The manufacturer(s) producing this model
*   **Data Domain:** Domains where this model is authorized
*   **Is Base Model:** Toggle (Base vs. Revision)

**Columns:**
1.  **Display Name** (Model Name + Subtype + Revision, Link to Detail)
2.  **Asset Class** (Related domain info)
3.  **Manufacturers** (Comma-separated list, Related domain info)
4.  **Base Model** (If applicable, Link to Base Model)
5.  **Authorized Domains** (Count or list of Data Domains)
6.  **Active** (Yes/No)
7.  **Actions** (View, Edit)

---

## 3. Search Asset Classes (`/assets/classes/`)
The broad categories of equipment managed by the organization.

**Filters:**
*   **Text Search:** Name or Description
*   **Category:** High-level grouping (e.g., Heavy Equipment)
*   **Data Domain:** Domains where this class is authorized

**Columns:**
1.  **Name** (Link to Detail)
2.  **Category**
3.  **Total Models** (Rollup count)
4.  **Total Assets** (Rollup count)
5.  **Authorized Domains** (List of Data Domains)
6.  **Active** (Yes/No)
7.  **Actions** (View, Edit)

---

## 4. Search Manufacturers (`/assets/manufacturers/`)
The companies that produce the models.

**Filters:**
*   **Text Search:** Name or Code
*   **Active Status:** Active, Inactive

**Columns:**
1.  **Name** (Link to Detail)
2.  **Code**
3.  **Total Models** (Rollup count)
4.  **Website** (External Link)
5.  **Active** (Yes/No)
6.  **Actions** (View, Edit)

---

## 5. Search Config Templates (`/assets/configurations/templates/`)
The baseline configuration templates for assets.

**Filters:**
*   **Text Search:** Template Name or Description
*   **Asset Model:** The model this template applies to
*   **Modifications**: Multi-select filter for specific modifications


**Columns:**
1.  **Template Name** (Link to Detail)
2.  **Revision**
3.  **Target Asset Model** (Related domain info)
4.  **Child Assets Required** (Rollup count)
5.  **Active** (Yes/No)
6.  **Actions** (View, Edit)

---

## 6. Search Capability Definitions (`/assets/capabilities/definitions/`)
The catalog of system capabilities.

**Filters:**
*   **Text Search:** Name or Code
*   **Active Status:** Active, Inactive

**Columns:**
1.  **Name** (Link to Detail)
2.  **Code** (Monospace)
3.  **Description**
4.  **Class Assignments** (Rollup count)
5.  **Model Assignments** (Rollup count)
6.  **Asset Overrides** (Rollup count)
7.  **Active** (Yes/No)
8.  **Actions** (View, Edit)

---

## 7. Capabilities by Asset Class (`/assets/capabilities/by-class/`)
The baseline capabilities assigned at the broad class level.

**Filters:**
*   **Asset Class:** The class the capability is assigned to
*   **Capability Definition:** The capability being assigned
*   **Active Status:** Active, Inactive

**Columns:**
1.  **Asset Class** (Related domain info, Link to Detail)
2.  **Capability Definition** (Related domain info)
3.  **Active** (Yes/No)
4.  **Actions** (Edit Assignment)

---

## 8. Capabilities by Model (`/assets/capabilities/by-model/`)
The capabilities assigned or overridden at the specific model level.

**Filters:**
*   **Asset Model:** The model the capability is assigned to
*   **Asset Class:** The class of the model
*   **Capability Definition:** The capability being assigned
*   **Active Status:** Active, Inactive

**Columns:**
1.  **Asset Model** (Related domain info, Link to Detail)
2.  **Asset Class** (Related domain info)
3.  **Capability Definition** (Related domain info)
4.  **Active** (Yes/No)
5.  **Actions** (Edit Assignment)

---

## 9. Capabilities by Asset (`/assets/capabilities/by-asset/`)
The granular capability overrides and adjustments for individual physical assets.

**Filters:**
*   **Asset Name or Serial:** Text search for the specific unit
*   **Asset Model:** The model of the unit
*   **Capability Definition:** The capability assigned
*   **Active Status:** Active, Inactive

**Columns:**
1.  **Asset Name** (Link to Asset-360)
2.  **Asset Model** (Related domain info)
3.  **Capability Definition** (Related domain info)
4.  **Quantity** (If applicable)
5.  **Notes** (Snippet of technician notes)
6.  **Active** (Yes/No)
7.  **Actions** (Edit Assignment)
