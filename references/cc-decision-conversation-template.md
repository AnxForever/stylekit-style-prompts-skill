# CC Decision Conversation Template

Use this when the user only has a high-level idea (for example: "I want a blog").

## Goal

Help non-frontend users make design decisions first, then generate implementation.

## Phase 1: Clarify Product Context

- Assistant prompt:
  - "I will help narrow direction first. Who is the audience, and is the primary goal reading, conversion, or brand expression?"
- Expected output:
  - product type
  - target audience
  - top 1-2 business goals

## Phase 2: Present Style Choices

- Input source:
  - `manual_assistant.decision_assistant.recommended_style_options`
- Assistant prompt:
  - "Here are 3-4 style options with complexity and risk. Pick A/B/C/D, and I will generate with that style."
- Explain each option in plain language:
  - visual tone
  - implementation complexity
  - readability/risk trade-off

## Phase 3: Ask Guiding Questions

- Input source:
  - `manual_assistant.decision_assistant.decision_questions`
- Ask 2-3 questions max:
  - visual intensity
  - content density preference
  - motion level

## Phase 4: Lock Style and Generate

- After user picks a style option, run:
  - `python scripts/run_pipeline.py --workflow codegen --query "<requirement>" --stack <stack> --style <slug> --blend-mode off --format json`
- Then generate implementation with:
  - homepage
  - detail page (for blog: post page)
  - list page (for blog: article list page)

## Output Rules for Assistant

- Never force a style before user selects.
- Explain style differences in non-technical language first.
- Preserve user language (Chinese in -> Chinese out, English in -> English out).
- Keep decision loop short: propose options -> ask questions -> confirm -> generate.
