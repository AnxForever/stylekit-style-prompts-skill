# Frontend Design Principles

## Intent First

Before generating prompts, define:

- purpose (what this UI must achieve)
- audience (who uses it and what they value)
- tone (aesthetic direction)
- memorable hook (one unforgettable visual decision)

## Iteration Modes

- `new`: create complete structure from scratch with full state coverage.
- `polish`: keep structure stable, improve typography/spacing/consistency first.
- `debug`: prioritize overflow/clipping/z-index/state regressions with minimal structural changes.
- `contrast-fix`: enforce WCAG contrast and readability without breaking brand tone.
- `layout-fix`: fix grid/flex rhythm, responsive breakpoints, and viewport overflow.
- `component-fill`: complete missing components and interaction states before adding effects.

## Reference-driven Generation

- Screenshot input: extract layout hierarchy and spacing first, then map to semantic components.
- Figma input: align frame structure and token cues (color/type/spacing) with code architecture.
- Mixed input: keep one source-of-truth per decision (layout/color/type/motion) to avoid conflicts.
- Never copy visual reference blindly; explicitly restore missing states (hover/focus/loading/error).

## Anti-generic Heuristics

- Avoid interchangeable templates with no style point-of-view.
- Avoid default purple-on-white gradient clichés unless style explicitly requires it.
- Avoid relying only on generic fonts (Inter/Roboto/Arial/system-ui).
- Build atmosphere through layered backgrounds (gradient, texture, shape, depth).

## Pre-delivery Validation Tests

- Swap test: if replacing your key choices with defaults still looks similar, identity is weak.
- Squint test: hierarchy should remain clear when details are blurred.
- Signature test: identify 3+ concrete UI elements that carry the style signature.
- Token test: token names/values should reflect product semantics, not generic template language.

## Anti-pattern Blacklist

- Do not use absolute positioning as the main page layout strategy.
- Do not rely on nested scrolling containers for core content flow.
- Do not remove focus styles without visible focus-visible replacements.
- Do not ship forms without loading/disabled/error-recovery states.
- Avoid god components and deep prop drilling for basic UI assembly.

## Typography Direction

- Pair one expressive display font with one readable body font.
- Use scale/weight/spacing contrast to drive hierarchy.
- Keep type rhythm consistent across breakpoints.
