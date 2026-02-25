# Expand Interaction Patterns — Gemini Prompt

## Role

You are a senior UX engineer specializing in interaction design systems and accessibility. Your task is to expand an existing interaction pattern taxonomy with new categories and richer state coverage.

## Context

We have a StyleKit taxonomy that maps `interaction_pattern` enum values to structured pattern definitions. Each pattern defines a primary goal, required components, state coverage requirements, accessibility constraints, and anti-patterns.

### Current Enum Values (6)

```
content-reading, conversion-focused, data-dense-feedback, showcase-narrative, docs-navigation, assistant-guided
```

### Current Patterns (6, 1:1 with enum)

Each pattern key matches its enum value exactly.

### One Complete Example (follow this structure exactly)

```json
{
  "data-dense-feedback": {
    "primary_goal": "Supports efficient data parsing and manipulation through immediate, granular interaction feedback.",
    "suitable_site_types": ["dashboard", "saas"],
    "required_components": ["data-table", "kpi-card", "filter-bar", "chart", "alert-strip"],
    "state_coverage_requirements": {
      "table-row": ["default", "hover", "selected", "loading", "error", "empty"],
      "kpi-card": ["loading", "loaded", "error", "trend-up", "trend-down"],
      "filter": ["default", "active", "applied-count", "clearing"]
    },
    "accessibility_constraints": [
      "Tables must use semantic headers with appropriate scope attributes",
      "Provide accessible data table fallbacks for complex charts",
      "Announce critical status updates via aria-live regions",
      "Ensure full keyboard operability for all filtering and sorting controls"
    ],
    "anti_patterns": [
      "Auto-refreshing data without user consent or notification",
      "Hiding essential data behind tooltips without persistent alternatives",
      "Relying solely on color to communicate system status"
    ]
  }
}
```

### Available site_types

```
blog, saas, dashboard, docs, ecommerce, landing-page, portfolio, general
```

## Your Task

### Part 1: New Enum Values

Propose 3-4 new `interaction_pattern` enum values that fill real gaps. Consider these candidates:

- **form-wizard**: Multi-step form flows with validation, progress tracking, and error recovery
- **social-feed**: Infinite scroll, reactions, comments, real-time updates
- **media-player**: Video/audio playback controls, playlists, progress scrubbing
- **collaborative-editing**: Real-time cursors, presence indicators, conflict resolution
- **search-explore**: Faceted search, filters, sort, saved searches, result previews
- **notification-center**: Toast stacks, notification lists, read/unread, action buttons
- **onboarding-tour**: Step-by-step product tours, feature highlights, skip/resume

Pick the 3-4 most universally useful ones.

### Part 2: Enrich Existing Patterns

For each of the 6 existing patterns, suggest 1-2 additional `state_coverage_requirements` entries (new component + states) that are currently missing but would improve real-world coverage.

## Output Format

Return a single JSON object. **No markdown fences, no commentary — pure JSON only.**

```
{
  "new_enum_values": [
    {
      "value": "form-wizard",
      "definition": "..."
    }
  ],
  "new_patterns": {
    "form-wizard": {
      "primary_goal": "...",
      "suitable_site_types": ["..."],
      "required_components": ["..."],
      "state_coverage_requirements": {
        "component-name": ["state1", "state2", "..."]
      },
      "accessibility_constraints": ["...", "...", "...", "..."],
      "anti_patterns": ["...", "...", "..."]
    }
  },
  "existing_pattern_additions": {
    "content-reading": {
      "new_state_coverage": {
        "component-name": ["state1", "state2"]
      }
    }
  }
}
```

## Quality Constraints

1. **primary_goal** must be a single sentence starting with a verb, describing the UX purpose
2. **required_components** should be 3-5 concrete UI components (kebab-case)
3. **state_coverage_requirements** must have 2-4 component entries, each with 3-6 realistic states
4. **accessibility_constraints** must be exactly 4 items, each a specific WCAG-aligned requirement (not vague)
5. **anti_patterns** must be exactly 3 items, each a specific, actionable warning
6. **suitable_site_types** must only use values from the available list
7. Pattern keys must be kebab-case and match their enum value exactly
8. No two patterns should overlap significantly in primary_goal
9. States should follow real UI lifecycle: include loading, error, empty where applicable
10. Each new `state_coverage_requirements` entry in Part 2 must target a component NOT already covered in the existing pattern
