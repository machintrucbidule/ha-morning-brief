# DECISIONS.md — home-assistant-morning-brief

Append-only architectural decision log. Any architectural change to the spec requires an entry here. Newest entries at the bottom (chronological).

---

## 2026-05-14 — Initial spec lock

**Context**: Project kickoff. The spec was produced collaboratively by the user and a planning AI session.
**Decision**: Lock all architecture decisions D1–D25 as defined in `MORNING_BRIEF_SPEC.md` Section 4.
**Consequence**: Implementation must follow these decisions strictly. Any deviation requires a new entry in this file with explicit user approval.
**Approved by**: User (initial project setup)

---

## 2026-05-16 — D12 override: shared pool for fields & categories (planned rc.9)

**Context**: After the first live HA install passes (rc.4 through rc.7), the user reported that re-creating all fields and categories for each instance (morning / evening / weekly) is unworkable. They want a **single shared pool** where each field/category declares which instances it applies to — not per-instance duplicated subentries.

**Original decision (D12)**: "One instance per type, independent config flow, options, fields, categories, AI provider, etc. To share fields across reports, the 'copy fields/categories' mechanism is offered at instance creation (one-shot duplication, not a live link)."

**New decision (rc.9 target)**: Architecture migrates to a **shared pool**:
- New module `pool.py` with a domain-level `Store` for `fields` and `categories` (keyed by uuid).
- Each pool entry carries `applicable_to: list[entry_id]` (empty list = all instances).
- The existing HA subentry flows (Add Field / Add Category buttons on the integration page) become pool editors — they read/write the pool, not subentries.
- Runtime: each instance reads the pool and filters by `entry_id in applicable_to OR applicable_to == []`.
- Migration: at first rc.9 setup, aggregate every existing subentry (across all existing instances) into the pool, computing `applicable_to` per-entry. Old subentries are removed after migration.

**Consequence**:
- D12 "copy fields/categories on creation" becomes obsolete (no need — fields are shared by default).
- Section 19 step 6 (copy_from_instance) is replaced by an automatic "apply to this instance" check on every existing pool item, on instance creation.
- Section 21 (subentry flows) and Section 22 (reorder) need refactor.
- The `_attach_subentries` runtime helper is replaced by `_attach_pool_view(entry, pool)`.

**Approved by**: User (2026-05-16 chat — explicit "Pool global (Recommended)" pick after the question I asked).

**Status**: Planned for rc.9. rc.8 keeps the current per-instance subentry model with bug fixes only.

---
