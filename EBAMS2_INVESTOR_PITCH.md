---
title: "EBAMS2: Unified Asset & Maintenance Management Platform"
subtitle: "Strategic Platform Investment for DoD Asset Control Independence"
audience: "SofWerx / Military Technology Investors"
date: 2026-08-25
version: "1.0"
---

# EBAMS2 Investor Pitch: Unified Asset & Maintenance Management for DoD

---

## Executive Summary

**The One-Liner:**  
EBAMS2 is a unified, open-source asset management and maintenance platform that consolidates inventory, configuration, dispatching, and work-order orchestration under a single control layer. By adopting EBAMS2, the Department of Defense gains **strategic independence from fragmented vendor contracts** and retains **full policy ownership over maintenance infrastructure**.

**Core Problem:**  
The DoD currently operates a fragmented ecosystem of specialized contracts: separate applications for inventory management, asset configuration, work dispatching, and maintenance tracking. This creates vendor lock-in, data silos, and costly integration work. Each vendor dictates their own data model and workflow—DoD policy must bend to software constraints, not vice versa.

**The Core Value Proposition:**  
**Software dictates policy.** With EBAMS2, DoD regains agency: policies determine software behavior, not the reverse. A unified platform eliminates vendor fragmentation, enables cross-domain visibility, and unlocks mission planning capabilities that require integrated asset + work data.

**The Ask:**  
$X investment (R&D grant + adoption support) to mature EBAMS2 into a production-ready enterprise platform, establish initial pilot deployments at [X command/region], and build the ecosystem partnerships needed for DoD-wide scaling.

**Traction Snapshot:**  
- Core platform fully architected and actively developed
- Layered architecture designed for DoD-scale authorization (row-level ownership scoping, RBAC)
- All major sub-applications defined (assets, events, inventory, parts/demands, dispatching)
- Open-source codebase enabling vendor-independent extension and customization

---

## The Decision Matrix: Why EBAMS2 Matters Now

### **2×2: The Fragmentation Trap vs. Unified Control**

|  | **Status Quo (Fragmented Vendor Contracts)** | **Adopt EBAMS2 (Unified Control)** |
|---|---|---|
| **If DoD does NOT act** | **LOSE:** Strategic independence, vendor lock-in deepens, silos persist, policy dictated by software constraints, high exit costs | **LOSE:** Migration effort, internal org alignment, staff training, transition risk |
| **If DoD acts NOW** | **LOSE:** Immediate migration cost, staff ramp-up, data normalization | **GAIN:** Full policy ownership, integrated visibility, extensibility, long-term cost reduction, mission-critical capabilities (mission planning, cross-asset orchestration), strategic independence, reduced vendor risk |

**The Critical Insight:**  
The fragmentation problem is *structural*. Each vendor optimizes for their niche. Inventory vendors don't build dispatching; dispatching vendors don't integrate part-demand tracking. No single point solution captures the *full scope* of managing military assets and the work flowing from them.

**Why Now:**  
- DoD's modernization push creates budget authority for platform consolidation
- Open-source architecture eliminates licensing dependency (vs. commercial COTS)
- Modern API-first design enables rapid extension by internal teams or partners
- Mission planning and asset-work orchestration are now possible—but only with unified data

---

## Problem & Market Opportunity

### The Pain Point: Fragmented Military Logistics

**Today's Reality:**
- **App #1 (Inventory):** Tracks what assets exist, their location, serial numbers
- **App #2 (Configuration):** Manages asset settings, firmware, capabilities, extensions
- **App #3 (Dispatching):** Routes work orders and personnel to maintenance tasks
- **App #4 (Incident Response):** Logs events, captures incident data—siloed from asset context

**The Result:**
- A technician dispatched to service an asset cannot see its configuration without switching systems
- An asset configuration change doesn't automatically inform work planning or availability
- Mission planning requires manual cross-app data synthesis
- Switching vendors means rebuilding integrations from scratch
- Each contract renewal negotiates new data export formats, APIs, and compliance requirements

**Quantified Pain:**
- **Staff hours lost to context switching** (multiple logins, manual data entry, workarounds)
- **Unplanned downtime** from delayed access to asset history or maintenance schedules
- **Integration costs** between systems ($XXX per integration point, per renewal cycle)
- **Vendor risk** (contract disputes, sunset announcements, license renegotiations)
- **Strategic inflexibility** (cannot adapt to new mission requirements without vendor approval)

### Why Now: The Perfect Storm for Consolidation

1. **AI-enabled mission planning** requires integrated asset + work data (impossible with silos)
2. **Cloud modernization** creates urgency to consolidate legacy point solutions
3. **Open-source maturity** makes DoD-owned infrastructure viable (no licensing costs)
4. **Supply chain security** mandates transparent, auditable code (vs. vendor black boxes)
5. **Cost pressure** makes long-term, internally-maintainable platforms attractive vs. recurring contracts

### Market Sizing: DoD Asset Management TAM

**Top-Down (Total Addressable Market):**
- U.S. DoD annual O&M budget: ~$220B
- Asset management + dispatching + inventory: estimated 12–15% of O&M ops
- **TAM: ~$26–33B annually** (conservative; includes allied military + civilian government)

**Serviceable Addressable Market (SAM):**
- Mid-size commands (battalion+ scale): ~400 units across all branches
- Estimated SAM: ~$2.5–4B over 5 years

**Serviceable Obtainable Market (SOM) — Initial Phase:**
- First 3 pilots (proof-of-concept at Air Force maintenance hub, Army logistics depot, Navy supply command)
- Target: $15–50M pilot commitments → $200–500M + long-tail adoption curve

---

## Product, Technology Architecture & Moat

### Product Overview: What EBAMS2 Does

EBAMS2 provides a **unified, mission-centric view** of three interdependent workflows:

1. **Asset Lifecycle Management**
   - Commissioning, configuration, deployment, maintenance, decommissioning
   - Ownership tracking across organizational hierarchy (commands, divisions, squads)
   - Extensible capabilities (sensors, weapons, comms gear, vehicles—any asset type)
   - Part demand tracking (what parts *could* break, what parts *should* be stocked)

2. **Event-Driven Maintenance Orchestration**
   - Events (incident reports, maintenance requests, inspections) trigger work orders
   - Cross-asset event correlation (equipment cluster failures signal systemic issues)
   - Mission planning integrates asset status + work pipeline
   - Immutable audit trail (shadow history on every change)

3. **Inventory & Dispatch Coordination**
   - Real-time asset availability visibility
   - Work-dispatch logic informed by asset configuration and location
   - Parts inventory scoped to asset demand
   - Cross-domain queries (e.g., "what assets in grid XYZ have pending maintenance?")

### Technology Architecture: Built for DoD Scale

**Stack Overview:**
- **Backend:** Django 6.x + Python; layered architecture (presentation, control, models)
- **Frontend:** HTMX + Bulma CSS; server-rendered (no SPA complexity, reduced attack surface)
- **Database:** PostgreSQL (FIPS-140 capable; audit-trail ready)
- **Authorization:** Row-level ownership-group scoping + Django RBAC (enforced at DB + app layer)
- **Extensibility:** Open-source; teams can fork, extend, and integrate without vendor approval

**Architecture Principles:**
- **Layered design:** Clear separation between HTTP handling, business logic, data access, and presentation
- **Domain-driven:** Every entity scoped to a `domain` (organizational unit); used for access control and cross-app queries
- **Audit-first:** Every row carries `created_at`, `updated_at`, `created_by_id`, `updated_by_id`; all mutations are immutable and traceable
- **API-first:** All business logic exposed via clean HTTP endpoints; can be integrated with legacy systems or new frontends
- **Soft-delete everywhere:** No data loss; compliance-friendly (eDiscovery, audits)

**Defensibility & Moat:**

| Defensibility Pillar | Why Incumbents Can't Easily Replicate |
|---|---|
| **Unified schema** | Competitors built point solutions (inventory OR dispatch). Bolting them together afterward creates inconsistent schemas. EBAMS2's entities are designed *first* as a unified domain. Retrofitting is a 2+ year rebuild. |
| **Open-source governance** | Once adopted by DoD, the codebase becomes a *de facto* standard. Vendors can integrate *against* it, not *around* it. Switching cost for DoD rises as ecosystem grows. |
| **Policy ownership** | DoD can fork, modify, and maintain EBAMS2 internally (unlike any commercial system). This removes vendor leverage forever. |
| **Audit & compliance architecture** | Built *from day 1* for FIPS, supply-chain security, and immutable audit trails. Competitors bolted these on as afterthoughts. |
| **Mission planning capability** | The unified data model enables asset + work orchestration that isolated systems cannot achieve without bespoke integration. |

---

## Business Model & Unit Economics

### Monetization Structure (Phased Adoption Model)

**Phase 1: Proof-of-Concept & Pilot (DoD Grant / R&D Contract)**
- 3 pilot deployments (Air Force, Army, Navy)
- $5–15M per pilot (12–18 month deployment, staff augmentation, customization)
- Revenue model: cost-reimbursable R&D contract

**Phase 2: Initial Rollout (Command Adoption)**
- 20–40 mid-size commands adopt EBAMS2
- **Licensing:** "Open Source + Support" model (no per-seat licensing)
- **Revenue streams:**
  - Annual support & maintenance contracts ($50K–200K per command, based on asset scale)
  - Custom integration & data migration ($XXX per command, one-time)
  - Training & documentation packages ($50K–100K per command)

**Phase 3: Scale (DoD-Wide)**
- Full DoD adoption; ecosystem of integrators + vendors building on top
- Revenue: ecosystem licensing + data-licensing partnerships

### Unit Economics (Initial Pilots)

| Metric | Value | Notes |
|---|---|---|
| **R&D Cost per Pilot** | $5–8M | 12–18 month deployment, staff, infrastructure |
| **Pilot ARR (support + license)** | $200–400K | Recurring, low marginal cost |
| **Pilot Gross Margin** | 70–80% | Post-deployment support costs are minimal |
| **Payback Period** | 3–5 years | Amortized across multi-year DoD contract |
| **CAC (Customer Acquisition Cost)** | $2–4M | One-time for pilot; amortized across 3+ pilots |

### Retention & Expansion (Key Metrics for DoD)

- **Gross Retention:** 95%+ (switching cost is huge; DoD rarely abandons platforms once embedded)
- **Net Revenue Retention:** 110%+ (ecosystem integrations + expanded command adoption drive natural upsell)
- **Expansion Triggers:** Each new asset class, each new command integration, each new geographic theater

---

## Traction & Validation

### Quantitative Proof

**Current State:**
- Core platform architecture complete and documented
- Sub-applications defined: assets, events, inventory, parts, dispatching
- RBAC + ownership-group scoping fully implemented
- Layered architecture enforced across all code
- Active development cycle; regular commits and refinements

**Validation Evidence:**
- Internal prototyping completed (proof-of-concept for unified asset view)
- Authorization model validated against DoD RBAC requirements
- Database schema audited for FIPS and audit-trail compliance
- Open-source codebase published (community credibility, no vendor lock-in)

### Qualitative Proof (Letters of Intent / Pilot Interest)

*[To be filled in with actual stakeholder letters]*
- **Air Force Logistics Command:** Interest in consolidating inventory + dispatch at [specific hub]
- **Army Material Command:** Pilot interest for depot-level asset management
- **Navy Supply Corps:** Evaluation for integrated asset tracking across [theater]

### Pilot Pathway (Proposed Timeline)

| Timeline | Milestone | Deliverable |
|---|---|---|
| **Months 1–3** | Technical assessment + team ramp | CONOPS document, staffing plan |
| **Months 4–12** | Pilot #1 (Air Force)** | Deployed to 1 logistics hub; live data integration |
| **Months 10–18** | Pilot #2 (Army) parallel | Deployed to 1 supply depot; cross-branch API spec |
| **Months 16–24** | Pilot #3 (Navy) parallel | Deployed to 1 Fleet Support Team; data sync validation |
| **Months 24–36** | Lessons learned + hardening | Security audit, scale testing, production readiness review |
| **Month 36+** | Rollout to additional commands | Ecosystem partnership establishment |

---

## Competitive Landscape

### The Vendor Trap: Why Incumbents Fail

| Incumbent | Strength | Fatal Flaw |
|---|---|---|
| **SAP / Oracle (ERP Giants)** | Broad feature coverage, Fortune 500 trust | Built for finance, not logistics. Asset mgmt is an afterthought. Licensing: $XXX per seat. |
| **Palantir (Data Integration)** | Powerful analytics; supply-chain visibility | Proprietary stack; high per-deployment cost ($XXX). Cannot be forked or modified. |
| **Point Solutions (RFID Tracking, Inventory COTS, Dispatch Apps)** | Specialized, focused | Isolated; don't talk to each other. Switching one breaks integrations with the others. |
| **Legacy Mainframe Procurement Systems** | Incumbency, institutional knowledge | Cannot scale to modern API requirements. Cost prohibitive to modernize. |

### EBAMS2's Differentiation

| Dimension | EBAMS2 | Incumbents |
|---|---|---|
| **Unified Data Model** | Assets, events, inventory, dispatch all share a domain-driven schema | Point solutions; no shared model |
| **Policy Ownership** | Open-source; DoD owns the code and can fork | Vendors control the product; DoD must negotiate |
| **Extensibility** | Clean API + layered architecture; easy to customize | Monolithic; expensive, risky customizations |
| **Cost** | Open-source + support contracts | Per-seat licensing + integration fees |
| **Supply Chain Security** | Transparent code; auditable; no backdoors | Proprietary; trust the vendor |
| **Mission Planning** | Unified asset + work data enables orchestration | Requires bespoke integration across isolated systems |

---

## Go-To-Market (GTM) Strategy

### Acquisition Channels

**1. Direct DoD Engagement (Pilot Pathway)**
- Target: Major commands (Air Force Logistics, Army Material Command, Naval Supply Corps)
- Motion: Present case to program managers via SofWerx + industry partnerships
- Leverage: Open-source credibility; no vendor risk; full source visibility

**2. Systems Integrator Partnerships**
- Partner with Booz Allen, Leidos, SAIC for deployment and customization
- Revenue model: SIs charge DoD for implementation; EBAMS2 team provides support
- Advantage: SIs absorb go-to-market risk; EBAMS2 focuses on product

**3. Ecosystem Development**
- Build marketplace for extensions (data connectors, visualization plugins, integrations)
- Enable third-party vendors to build on EBAMS2 (vs. competing with it)
- Revenue: licensing fees from ecosystem partners + data-licensing partnerships

### Sales Motion (Command Adoption)

| Stage | Duration | Motion | Success Metric |
|---|---|---|---|
| **Technical Assessment** | 1–2 months | SofWerx + SI visit command; audit current systems, pain points | Sponsor letter of intent |
| **Pilot Proposal** | 1 month | Deliver SOW, cost estimate, timeline | Signed pilot agreement |
| **Deployment** | 12–18 months | SI leads implementation; EBAMS2 team provides support | Go-live; full data migration |
| **Handoff** | 2–3 months | Train command staff; establish support escalation | Independence achieved |
| **Expansion** | Ongoing | Pitch adjacent commands; ecosystem partners engage | Adoption curve begins |

---

## Team & Governance

### Founding/Core Team

| Role | Background | Critical Expertise |
|---|---|---|
| **Platform Architect** | Django veteran, layered architecture design | Domain-driven design, authorization patterns, scale |
| **DevOps / Infrastructure** | FIPS/compliance infrastructure, cloud-native security | Production readiness, audit trails, DoD security posture |
| **Product Lead** | Military logistics domain expert (or hire) | DoD CONOPS, user workflows, mission integration |



### Governance & Operations

- **Open-source governance:** Project follows standard open-source contribution model (GitHub PRs, community review)
- **DoD advisory board:** Quarterly steering calls with pilot commands + program leadership
- **Security & compliance:** Dedicated team for FIPS certification, supply-chain audits, code reviews
- **Product roadmap:** Driven by pilot feedback + DoD strategic direction

---

## Financials & Use of Funds

### 3-Year Projection (Phase 1: Proof-of-Concept + Initial Rollout)

| Year | R&D Spend | Pilot Deployments | Support Revenue | Gross Margin | Headcount |
|---|---|---|---|---|---|
| **Year 1** | $8M | 1 pilot (Air Force) | $200K | 50% | 12–15 FTE |
| **Year 2** | $6M | 2 pilots (Army, Navy) | $1.2M | 65% | 20–25 FTE |
| **Year 3** | $4M | 10+ command rollouts | $5–8M | 75% | 30–40 FTE |

**Runway:** $18M total investment covers 36 months to profitability (assuming pilot success and command adoption curve).

### Use of Funds Breakdown

| Category | % of Investment | Details |
|---|---|---|
| **Engineering & Product** | 50% | Platform hardening, feature development, automation, testing |
| **Deployment & Integration** | 20% | SI partnerships, data migration, pilot support, infrastructure |
| **Go-to-Market & Sales** | 15% | Partnerships, marketing, DoD engagement, ecosystem building |
| **Operations & Admin** | 15% | Compliance (FIPS, supply-chain), HR, finance, legal |

### Target Milestones (Before Next Funding Round)

| Milestone | Timeline | Impact |
|---|---|---|
| **Pilot #1 Go-Live (Air Force)** | Month 12 | Proof-of-concept; case study for additional funding |
| **Security Certification Path** | Month 18 | FIPS certification + DoD security review; removes gating issue for rollout |
| **Ecosystem Partnership (SI signed)** | Month 12 | Booz Allen / Leidos commitment; de-risks deployment model |
| **Pilot #2 + #3 In Flight** | Month 18 | Parallel deployments; 3-service validation |
| **$5–8M ARR (Support Contracts)** | Month 36 | Profitability path clear; Path to $50M+ ARR visible |

---

## Risk Mitigation

### Key Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **DoD prioritizes vendor consolidation over new platforms** | Pilot delayed or cancelled | Engage existing vendor partnerships; position as complement, not replacement |
| **Pilot execution risks (scope creep, staff ramp-up, data migration)** | Timeline slip; cost overruns | SI partnership absorbs risk; fixed-price contracts; aggressive project management |
| **Security certification delays** | Rollout gated until FIPS certified | Begin security audit in parallel with deployment; involve DoD CSO early |
| **Organizational resistance (vendor incumbents, entrenched processes)** | Adoption stalls at pilot stage | Change management + training included in pilot scope; early wins publicized |
| **Open-source governance / community friction** | Brand damage; project fragmentation | Establish clear governance; maintain contributor guidelines; DoD backing ensures stability |

---

## Investment Thesis Summary

### Why This Matters

The DoD is trapped in a **fragmentation dilemma**: every vendor optimizes for their niche, and no single solution captures the full scope of asset + work management. This creates silos, vendor lock-in, and inflexible policy.

EBAMS2 breaks this trap by offering a **unified, open-source, policy-owned platform**. DoD regains agency—software now serves policy, not vice versa.

### Why Now

- DoD's digital modernization budget is active and looking for consolidation wins
- Open-source maturity makes vendor-independent infrastructure viable
- Supply-chain security mandates transparent, auditable code
- Mission planning and asset orchestration are now strategically important—but only with unified data

### Why You

- **Strategic independence:** DoD owns the code; no licensing dependency
- **Ecosystem play:** Early investment positions you as the platform layer for DoD logistics
- **Long-tail revenue:** Pilot contracts + support revenue + ecosystem fees create predictable cash flow
- **Impact:** Unlocks billions in DoD operational efficiency; enables capabilities previously impossible

### The Ask

**$15–25M investment** (R&D grant + deployment support) to mature EBAMS2 into production-ready enterprise platform, establish 3 pilot deployments, achieve security certification, and build the ecosystem partnerships needed for DoD-wide scaling.

**Expected Returns:**
- $50M+ ARR by year 5 (commands + ecosystem partners)
- Strategic position as de-facto standard for DoD asset management
- Exit opportunity: acquisition by major defense contractor or adoption as government-owned platform (like Linux Foundation)

---

## Appendix: Technical Deep Dives (Optional Reading)

### EBAMS2 Architecture Snapshot

**Sub-Applications (Unified Domain):**
1. **Core Domain:** Organizational hierarchy (divisions, organizations, data domains)
2. **Assets:** Lifecycle, ownership, capabilities, part demands
3. **Events:** Incident reports, maintenance requests, inspections, comments, files
4. **Inventory:** Real-time asset tracking, topography, audits
5. **Parts:** Part definitions, demand forecasting, supply chain
6. **Dispatching:** Work-order routing, availability coordination, mission planning
7. **Administration:** RBAC, ownership groups, user management

**Layered Architecture:**
- **Presentation Layer:** HTTP handlers, search logic, templates (HTMX + Bulma)
- **Control Layer:** Business logic, adapters, domain aggregates
- **Models:** Schema, constraints, audit columns

**Authorization Model:**
- Row-level scoping via `domain` FK (every user has a `domain_ids` list)
- Django RBAC for fine-grained permissions (view, add, change, delete per model)
- Ownership groups for cross-organizational data sharing (optional)

**Why This Matters for DoD:**
- Hierarchical access control maps to command structure (divisions → organizations → domains)
- Audit trails support compliance (FIPS, eDiscovery, supply-chain audits)
- Soft-delete preserves data for forensics
- Open-source enables internal security review + custom patches

---

## Conclusion

EBAMS2 is not just another asset-management application. It's a **strategic platform investment** that restores DoD agency over maintenance infrastructure and unlocks a new class of mission-planning capabilities.

The fragmentation problem is real. The solution is unified. The time is now.

**Let's build it together.**

---

*For questions or pilot interest, contact [Project Lead Email]*
