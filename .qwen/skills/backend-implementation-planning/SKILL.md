---
name: backend-implementation-planning
description: Systematic approach to analyzing a partially-implemented Python backend and creating a phased implementation plan
source: auto-skill
extracted_at: '2026-05-30T20:47:49.031Z'
---

# Backend Implementation Planning Method

When reviewing a partially-implemented backend and creating a completion plan, follow this systematic approach:

## Step 1: Comprehensive Codebase Audit

**Explore all backend files systematically:**
- Read all Python files in the main app directory
- Read all files in subdirectories (agents, api, services, brokers)
- Check requirements.txt for dependencies
- Check .env.example for configuration variables
- Look for test files or their absence

**For each file, document:**
1. What functionality is fully implemented
2. What's partially implemented (stubs, TODOs, placeholders)
3. What's missing entirely
4. Any imports that reference non-existent modules

## Step 2: Categorize by Component Type

Group findings into logical categories:

**Infrastructure:** Config, database, models, logging, main app setup
**Core Logic:** Agents, services, business logic
**API Layer:** Endpoint implementations vs stubs
**Integrations:** Broker APIs, external services
**Quality:** Tests, migrations, documentation

## Step 3: Identify Critical Gaps

Priority red flags to look for:
- Stub functions that return placeholder data
- Missing broker/service integrations (key for functionality)
- API endpoints returning hardcoded responses
- No test coverage
- Missing database migrations
- Unused dependencies (potential cleanup)

## Step 4: Create Phased Implementation Plan

Organize remaining work into phases with clear priorities:

**Critical Path (Phases 1-3):** Core functionality needed for MVP
**High Priority (Phases 4-5):** Important features that differentiate the product
**Medium Priority (Phases 6-7):** Security, testing, polish
**Low Priority (Phases 8-10):** Nice-to-have enhancements

### Phase Structure Template

For each phase, document:

```markdown
## Phase X: {Name} ({Priority})

**Goal:** {One-sentence objective}

### X.1 {Specific Component}
**File:** `path/to/file.py`

**Tasks:**
- [ ] Specific, actionable task
- [ ] Another specific task
- [ ] Implementation detail to address

**Dependencies:** {Required packages or other phases}

**Estimated Effort:** {Hours}

**Testing:** {What to verify}
```

## Step 5: Provide Effort Estimates

For each phase, estimate hours:
- **Low:** 1-3 hours (single file, straightforward)
- **Medium:** 4-8 hours (multiple files, some complexity)
- **High:** 8-15 hours (complex integration, multiple dependencies)
- **Very High:** 15-30 hours (major feature, extensive testing)

## Step 6: Define Success Criteria

For MVP and full completion:
- **MVP Criteria:** 3-5 measurable outcomes (e.g., "Can execute paper trades")
- **Production Criteria:** Comprehensive list of working features

## Step 7: Recommend Next Steps

Provide:
1. Immediate next actions (first 2-3 tasks)
2. Quick wins (high value, low effort)
3. What can be deferred to later
4. Estimated timeline (full-time vs part-time)

## Key Principles

- **Be specific:** Name exact files and functions to implement
- **Be actionable:** Each task should be clear enough to start coding
- **Be realistic:** Account for integration complexity, testing time
- **Be prioritized:** Critical path first, defer nice-to-haves
- **Be measurable:** Define what "done" looks like for each phase

## Example Output Structure

```
# Project Backend - Completion Plan

**Current Status:** ~X% Complete
**Goal:** {Objective}

## Phase Overview Table

| Phase | Name | Focus | Effort | Priority |
|-------|------|-------|--------|----------|
| P1 | ... | ... | ... | ... |

## Phase 1: {Name}

### 1.1 {Component}
**File:** `...`
**Tasks:** [...]
**Effort:** X hours

...

## Summary

**Critical Path:** Phases 1-3, ~X hours
**Full Completion:** ~X hours
**Recommended Starting Point:** Phase 1.1
```

This approach was successfully used to analyze the Jasper Trades backend (a multi-agent AI trading system) and create a 130-170 hour implementation plan broken into 10 phases, identifying that the core architecture was 60% complete with broker integrations, portfolio services, and signal services as the critical remaining work.