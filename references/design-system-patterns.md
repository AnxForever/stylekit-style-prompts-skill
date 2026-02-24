# Design System Patterns

## Token Hierarchy

1. Brand tokens
2. Semantic tokens (primary/surface/text/border)
3. Component tokens (button/card/input)
4. State tokens (hover/active/focus/disabled)

## Component Architecture

Use a predictable layering model:

- Base -> Variant -> Size -> State -> Override

## Prompt Requirements

When generating prompts, include:

- semantic color ownership
- spacing/radius scale constraints
- component variant rules
- explicit interaction state expectations
