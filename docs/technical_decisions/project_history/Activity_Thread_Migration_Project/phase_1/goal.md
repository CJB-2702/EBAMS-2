---
type: "Technical Decision"
title: "Phase 1 — Goal: Class Name Cleanup"
description: "The events application uses names tied to a specific entity type (EventComment,."
tags: [technical-decisions, technical-decision, project-history, activity-thread-migration-project, phase-1]
context_tier: 2
---

# Phase 1 — Goal: Class Name Cleanup

## Problem

The events application uses names tied to a specific entity type (`EventComment`,
`EventFile`, `CommentAttachment`). These names no longer describe the domain correctly:
comments and files are not inherently event-specific, and "CommentAttachment" conflates
two concepts (the attachment and its link to a comment).

## What this phase does

Rename classes, tables, managers, and QuerySets to domain-neutral equivalents. Update
every import site in the codebase. No new columns are added. No FK targets change. No
business logic changes.

## What this phase does NOT do

- No new columns or tables
- No FK field renames (Comment still has an `event` FK column pointing at `Event`)
- No behavioral changes — all existing functionality works identically after the rename
- No ActivityThread concept introduced
- No Asset model changes

## Success criteria

- All renamed classes resolve without import errors
- All existing tests pass (names aside)
- `python manage.py check` reports no errors
- DB reset + seed completes cleanly

## Sequencing

This is Phase 1 because naming cleanup makes all subsequent schema changes easier to
read, review, and diff. Doing it first means Phases 2 and 3 operate on clean names.
