# Expand Animation Profiles — Gemini Prompt

## Role

You are a senior motion design engineer specializing in web UI animation systems. Your task is to expand an existing animation profile taxonomy with new categories and variants.

## Context

We have a StyleKit taxonomy that maps `motion_profile` enum values to concrete animation profiles. Each profile defines intent, timing, easing, states, and anti-patterns for a specific animation behavior.

### Current Enum Values (5)

```
minimal, subtle, smooth, energetic, cinematic
```

### Current Profiles (12)

```json
{
  "minimal-static": { "motion_profile": "minimal", ... },
  "minimal-functional": { "motion_profile": "minimal", ... },
  "subtle-fade": { "motion_profile": "subtle", ... },
  "subtle-slide": { "motion_profile": "subtle", ... },
  "smooth-morph": { "motion_profile": "smooth", ... },
  "smooth-flow": { "motion_profile": "smooth", ... },
  "smooth-reveal": { "motion_profile": "smooth", ... },
  "energetic-bounce": { "motion_profile": "energetic", ... },
  "energetic-stagger": { "motion_profile": "energetic", ... },
  "energetic-pulse": { "motion_profile": "energetic", ... },
  "cinematic-parallax": { "motion_profile": "cinematic", ... },
  "cinematic-sequence": { "motion_profile": "cinematic", ... }
}
```

### One Complete Example (follow this structure exactly)

```json
{
  "smooth-morph": {
    "motion_profile": "smooth",
    "intent": "Facilitates fluid transitions between geometric states to maintain visual continuity during layout changes.",
    "trigger": "user-interaction",
    "states": ["default", "expanded", "collapsed", "hover"],
    "duration_range_ms": [250, 450],
    "easing": "cubic-bezier(0.4, 0, 0.2, 1)",
    "reduced_motion_fallback": "instant-state-swap",
    "suitable_site_types": ["saas", "ecommerce", "landing-page"],
    "anti_patterns": ["Unexpected layout shifts during morphing", "Morphing without will-change optimization"]
  }
}
```

### Available site_types

```
blog, saas, dashboard, docs, ecommerce, landing-page, portfolio, general
```

## Your Task

### Part 1: New Enum Values

Propose 2-3 new `motion_profile` enum values that fill gaps in the current taxonomy. Consider:
- **playful**: bouncy, whimsical, toy-like motion for kids/casual apps
- **functional**: purely utilitarian micro-interactions (loading spinners, progress bars, skeleton screens)
- **ambient**: slow, atmospheric, background-only motion (floating particles, gradient shifts)

For each new enum value, provide:
1. A short definition (1 sentence)
2. 2-3 concrete profiles following the exact schema below

### Part 2: New Variants for Existing Enums

Add 1-2 new profiles for each existing enum value that cover gaps:
- `minimal`: consider a "minimal-skeleton" for loading states
- `subtle`: consider a "subtle-scale" for hover micro-feedback
- `smooth`: consider a "smooth-spring" using spring physics
- `energetic`: consider an "energetic-flip" for card interactions
- `cinematic`: consider a "cinematic-morph" for page transitions

## Output Format

Return a single JSON object. **No markdown fences, no commentary — pure JSON only.**

```
{
  "new_enum_values": [
    {
      "value": "playful",
      "definition": "..."
    }
  ],
  "new_profiles": {
    "playful-wobble": {
      "motion_profile": "playful",
      "intent": "...",
      "trigger": "user-interaction | viewport-enter | scroll-progress | page-load | attention-needed | state-change-only",
      "states": ["..."],
      "duration_range_ms": [min, max],
      "easing": "css easing string or cubic-bezier(...)",
      "reduced_motion_fallback": "none | instant-state-swap | instant-visible | fade-only | static-position | static-layers | scale-only | color-highlight-only",
      "suitable_site_types": ["..."],
      "anti_patterns": ["...", "..."]
    }
  }
}
```

## Quality Constraints

1. **intent** must be a single sentence starting with a verb, describing the UX purpose (not the CSS implementation)
2. **duration_range_ms** must be realistic: [min, max] where min >= 0 and max <= 2000
3. **easing** must be a valid CSS easing value
4. **anti_patterns** must be 2-3 specific, actionable warnings (not vague "don't overuse")
5. **reduced_motion_fallback** must be one of the allowed values listed above
6. **suitable_site_types** must only use values from the available list
7. Each profile name must follow the pattern `{enum-value}-{variant}` (kebab-case)
8. No two profiles should have identical intent — each must serve a distinct UX purpose
9. Total new profiles: aim for 10-15 across all categories
