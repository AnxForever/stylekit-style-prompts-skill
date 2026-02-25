"""Hard/soft prompt generation from style data and design brief."""

from __future__ import annotations

import re
from typing import Any

from _brief_constants import (
    ANTI_PATTERN_BLACKLIST,
    DEFAULT_DONT_LIST,
    DEFAULT_DO_LIST,
    STACK_HINTS,
    VALIDATION_TESTS,
    dedupe_ordered,
    has_cjk,
    language_filter_rules,
)
from blend_engine import blend_directive
from reference_handler import (
    build_reference_guidelines,
    reference_signal_prompt_block,
    refine_mode_strategy,
)


def build_localized_rule_list(items: list[str], lang: str, kind: str) -> list[str]:
    cleaned = language_filter_rules([str(item).strip() for item in items if str(item).strip()], lang)
    if cleaned:
        return cleaned[:6]
    if kind == "do":
        return DEFAULT_DO_LIST[lang][:6]
    return DEFAULT_DONT_LIST[lang][:6]


def style_anchor_terms(style: dict[str, Any], lang: str) -> list[str]:
    keywords = [str(x).strip() for x in style.get("keywords", []) if str(x).strip()]
    tags = [str(x).strip() for x in style.get("tags", []) if str(x).strip()]

    if lang == "zh":
        zh_terms = [term for term in keywords + tags if has_cjk(term)]
        if zh_terms:
            return dedupe_ordered(zh_terms)[:5]
        return dedupe_ordered(keywords + tags)[:5]

    en_terms: list[str] = []
    for term in keywords + tags:
        if not has_cjk(term):
            en_terms.append(term)
    name_en_tokens = re.findall(r"[a-zA-Z]{3,}", str(style.get("nameEn", "")))
    slug_tokens = [tok for tok in str(style.get("slug", "")).replace("-", " ").split() if len(tok) >= 3]
    en_terms.extend(name_en_tokens)
    en_terms.extend(slug_tokens)
    return dedupe_ordered(en_terms)[:6]


def make_prompts(
    query: str,
    style: dict[str, Any],
    ai_rules: list[str],
    stack: str,
    lang: str,
    blend_plan: dict[str, Any],
    intent: dict[str, str],
    anti_generic: list[str],
    refine_mode: str,
    reference_type: str,
    reference_notes: str,
    reference_signals: dict[str, Any],
    interaction_script: list[str],
) -> tuple[str, str]:
    stack_hint = STACK_HINTS.get(stack, STACK_HINTS["html-tailwind"])[lang]
    validation_tests = VALIDATION_TESTS[lang]
    anti_patterns = ANTI_PATTERN_BLACKLIST[lang]
    do_list = build_localized_rule_list(style.get("doList", []), lang, kind="do")
    dont_list = build_localized_rule_list(style.get("dontList", []), lang, kind="dont")
    anchor_terms = style_anchor_terms(style, lang)
    anchor_line_zh = "、".join(anchor_terms) if anchor_terms else style.get("slug", "")
    anchor_line_en = ", ".join(anchor_terms) if anchor_terms else style.get("slug", "")
    refine_strategy = refine_mode_strategy(refine_mode, lang)
    reference_guidelines = build_reference_guidelines(reference_type, lang)
    reference_signal_block = reference_signal_prompt_block(reference_signals, lang)
    interaction_script = [str(item).strip() for item in interaction_script if str(item).strip()]
    if lang == "zh":
        interaction_script_block = (
            "AI 交互设计脚本：\n" + "\n".join([f"- {line}" for line in interaction_script]) + "\n\n"
            if interaction_script
            else ""
        )
    else:
        interaction_script_block = (
            "AI interaction design script:\n" + "\n".join([f"- {line}" for line in interaction_script]) + "\n\n"
            if interaction_script
            else ""
        )

    if lang == "zh":
        refine_block = (
            f"迭代模式：{refine_strategy.get('mode')}\n"
            + f"- 本轮目标：{refine_strategy.get('objective')}\n"
            + "模式约束：\n"
            + "\n".join([f"- {item}" for item in refine_strategy.get("constraints", [])])
            + "\n\n"
        )
        reference_block = ""
        if reference_guidelines:
            reference_block = (
                f"参考输入类型：{reference_type}\n"
                + "参考输入约束：\n"
                + "\n".join([f"- {item}" for item in reference_guidelines])
                + ("\n" + f"- 参考备注：{reference_notes.strip()}" if reference_notes.strip() else "")
                + "\n\n"
            )
        reference_block = reference_block + reference_signal_block
    else:
        refine_block = (
            f"Refinement mode: {refine_strategy.get('mode')}\n"
            + f"- Objective: {refine_strategy.get('objective')}\n"
            + "Mode constraints:\n"
            + "\n".join([f"- {item}" for item in refine_strategy.get("constraints", [])])
            + "\n\n"
        )
        reference_block = ""
        if reference_guidelines:
            reference_block = (
                f"Reference input type: {reference_type}\n"
                + "Reference handling constraints:\n"
                + "\n".join([f"- {item}" for item in reference_guidelines])
                + ("\n" + f"- Reference notes: {reference_notes.strip()}" if reference_notes.strip() else "")
                + "\n\n"
            )
        reference_block = reference_block + reference_signal_block

    if lang == "zh":
        hard = (
            f"你是高级前端设计工程师。请严格按照 StyleKit 风格 `{style.get('slug')}` 生成界面。\n"
            f"需求：{query}\n\n"
            + "设计意图：\n"
            + f"- 目标：{intent.get('purpose')}\n"
            + f"- 受众：{intent.get('audience')}\n"
            + f"- 调性：{intent.get('tone')}\n"
            + f"- 记忆点：{intent.get('memorable_hook')}\n\n"
            + refine_block
            + reference_block
            + interaction_script_block
            + "硬性约束：\n"
            + "\n".join([f"- {rule}" for rule in ai_rules])
            + "\n\n"
            + "必须遵守 Do：\n"
            + "\n".join([f"- {item}" for item in do_list])
            + "\n\n"
            + "必须避免 Don't：\n"
            + "\n".join([f"- {item}" for item in dont_list])
            + "\n\n"
            + f"技术栈约束：{stack_hint}\n"
            + "组件覆盖：至少提供 button、card、input，并补充 nav、hero、footer 中至少两个。\n"
            + "可访问性基线：保持 WCAG 2.1 AA（4.5:1）对比度、44x44px 触控目标，并确保键盘可达性。\n"
            + "反模板化约束：\n"
            + "\n".join([f"- {item}" for item in anti_generic])
            + "\n"
            + "设计系统约束：使用 primary/surface/text 语义 token，统一 spacing scale 与 radius，并明确 variant/state 层级。\n"
            + f"风格锚点词：{anchor_line_zh}（需在视觉语言、排版和组件语义中体现）。\n"
            + "提案前校验（必须自检）：\n"
            + "\n".join([f"- {item}" for item in validation_tests])
            + "\n"
            + "反模式禁令：\n"
            + "\n".join([f"- {item}" for item in anti_patterns])
            + "\n"
            + "输出要求：提供语义化结构、响应式布局、可访问状态（hover/active/focus-visible/disabled），并保持视觉一致。"
        )
        blend_hint = blend_directive(blend_plan, lang)
        if blend_hint:
            hard = hard + "\n\n" + blend_hint

        soft = (
            f"请基于 StyleKit 风格 `{style.get('slug')}` 生成一个美观且可实现的前端方案。\n"
            f"需求：{query}\n"
            "保持风格核心（配色、层级、节奏、交互反馈），允许在版式和细节上做创造性调整。\n"
            + "设计意图：\n"
            + f"- 目标：{intent.get('purpose')}\n"
            + f"- 受众：{intent.get('audience')}\n"
            + f"- 调性：{intent.get('tone')}\n"
            + refine_block
            + reference_block
            + interaction_script_block
            + "优先规则：\n"
            + "\n".join([f"- {rule}" for rule in ai_rules[:4]])
            + f"\n技术栈建议：{stack_hint}\n"
            + "建议组件：button、card、input，并补充 nav/hero/footer 中至少两个。\n"
            + "最低可访问性：WCAG 对比度目标（建议 4.5:1）与 44x44px 触控尺寸基线。\n"
            + "建议采用设计 token：primary/secondary/text、spacing scale、radius、variant/state。\n"
            + f"风格锚点词：{anchor_line_zh}。\n"
            + "请在提交前执行替换测试、眯眼测试、签名测试、Token 测试，并避开绝对定位整页、嵌套滚动和焦点样式缺失等反模式。"
        )
        blend_hint = blend_directive(blend_plan, lang)
        if blend_hint:
            soft = soft + "\n" + blend_hint
        return hard, soft

    hard = (
        f"You are a senior frontend design engineer. Strictly implement StyleKit style `{style.get('slug')}`.\n"
        f"Requirement: {query}\n\n"
        + "Design intent:\n"
        + f"- Purpose: {intent.get('purpose')}\n"
        + f"- Audience: {intent.get('audience')}\n"
        + f"- Tone: {intent.get('tone')}\n"
        + f"- Memorable hook: {intent.get('memorable_hook')}\n\n"
        + refine_block
        + reference_block
        + interaction_script_block
        + "Hard constraints:\n"
        + "\n".join([f"- {rule}" for rule in ai_rules])
        + "\n\n"
        + "Must-do constraints:\n"
        + "\n".join([f"- {item}" for item in do_list])
        + "\n\n"
        + "Must-avoid constraints:\n"
        + "\n".join([f"- {item}" for item in dont_list])
        + "\n\n"
        + f"Stack hint: {stack_hint}\n"
        + "Component coverage: include button, card, input, and at least two of nav/hero/footer.\n"
        + "Accessibility baseline: maintain WCAG 2.1 AA (4.5:1) contrast, 44x44px touch targets, and keyboard-ready focus states.\n"
        + "Anti-generic constraints:\n"
        + "\n".join([f"- {item}" for item in anti_generic])
        + "\n"
        + "Design system constraints: use semantic design tokens (primary/surface/text), a unified spacing scale + radius scale, and explicit variant/state hierarchy.\n"
        + f"Style anchor terms: {anchor_line_en} (must appear in visual language, typography, and component semantics).\n"
        + "Pre-delivery validation tests:\n"
        + "\n".join([f"- {item}" for item in validation_tests])
        + "\n"
        + "Anti-pattern blacklist:\n"
        + "\n".join([f"- {item}" for item in anti_patterns])
        + "\n"
        + "Output semantic structure, responsive layout, and full interaction states (hover/active/focus-visible/disabled)."
    )
    blend_hint = blend_directive(blend_plan, lang)
    if blend_hint:
        hard = hard + "\n\n" + blend_hint

    soft = (
        f"Generate a beautiful and production-feasible frontend concept in StyleKit style `{style.get('slug')}`.\n"
        f"Requirement: {query}\n"
        "Preserve the style DNA (color, hierarchy, rhythm, interaction feedback) while allowing creative layout variation.\n"
        + "Design intent:\n"
        + f"- Purpose: {intent.get('purpose')}\n"
        + f"- Audience: {intent.get('audience')}\n"
        + f"- Tone: {intent.get('tone')}\n"
        + refine_block
        + reference_block
        + interaction_script_block
        + "Priority rules:\n"
        + "\n".join([f"- {rule}" for rule in ai_rules[:4]])
        + f"\nStack hint: {stack_hint}\n"
        + "Suggested components: button, card, input, plus at least two of nav/hero/footer.\n"
        + "Accessibility minimum: WCAG contrast target (e.g. 4.5:1) and 44x44px touch-target baseline.\n"
        + "Prefer tokenized implementation: semantic tokens, spacing/radius scales, and explicit variants/states.\n"
        + f"Style anchor terms: {anchor_line_en}.\n"
        + "Run swap/squint/signature/token tests before final output and avoid anti-patterns (absolute layout, nested scroll, missing focus styles)."
    )
    blend_hint = blend_directive(blend_plan, lang)
    if blend_hint:
        soft = soft + "\n" + blend_hint

    return hard, soft
