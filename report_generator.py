"""
Report Generator — produces the final safety report.

Creates a comprehensive Markdown report documenting:
- What was tested (model, vulnerabilities, attacks)
- What was found (violation rates, per-category breakdowns)
- What was changed (hardened system prompt details)
- Before vs after comparison
"""

import os
import json
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from config import (
    RESULTS_DIR, TARGET_MODEL, SIMULATOR_MODEL, EVALUATION_MODEL,
    ATTACKS_PER_VULNERABILITY, VULNERABILITY_CATEGORIES, ATTACK_METHODS,
    BASELINE_SYSTEM_PROMPT, HARDENED_SYSTEM_PROMPT,
)


def _generate_plots(baseline_advbench: dict, hardened_advbench: dict, timestamp: str) -> tuple[str, str]:
    """Generate overall and category-level comparison charts."""
    b_rate = baseline_advbench.get("violation_rate", 0)
    h_rate = hardened_advbench.get("violation_rate", 0)
    
    # 1. Overall comparison chart
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(['Baseline', 'Hardened'], [b_rate, h_rate], color=['#e74c3c', '#2ecc71'], width=0.5)
    ax.set_ylabel('Violation Rate (%)')
    ax.set_title('Overall Violation Rate Comparison')
    ax.set_ylim(0, 100)
    
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.1f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontweight='bold')
                    
    plt.tight_layout()
    overall_filename = f"overall_comparison_{timestamp}.png"
    overall_path = os.path.join(RESULTS_DIR, overall_filename)
    plt.savefig(overall_path, dpi=300)
    plt.close()

    # 2. Category-level comparison chart
    b_cats = baseline_advbench.get("category_stats", {})
    h_cats = hardened_advbench.get("category_stats", {})
    
    all_cats = sorted(list(set(list(b_cats.keys()) + list(h_cats.keys()))))
    category_filename = f"category_comparison_{timestamp}.png"
    if all_cats:
        b_rates = []
        h_rates = []
        for cat in all_cats:
            b_s = b_cats.get(cat, {"total": 0, "violations": 0})
            h_s = h_cats.get(cat, {"total": 0, "violations": 0})
            b_rates.append((b_s["violations"] / b_s["total"] * 100) if b_s["total"] > 0 else 0)
            h_rates.append((h_s["violations"] / h_s["total"] * 100) if h_s["total"] > 0 else 0)
            
        y = np.arange(len(all_cats))
        height = 0.35
        
        fig, ax = plt.subplots(figsize=(10, 6))
        rects1 = ax.barh(y - height/2, b_rates, height, label='Baseline', color='#e74c3c')
        rects2 = ax.barh(y + height/2, h_rates, height, label='Hardened', color='#2ecc71')
        
        display_cats = [c.replace('_', ' ').title() for c in all_cats]
        ax.set_yticks(y)
        ax.set_yticklabels(display_cats)
        ax.set_xlabel('Violation Rate (%)')
        ax.set_title('Violation Rates by Category')
        ax.set_xlim(0, 100)
        ax.legend()
        
        for rect in rects1:
            width = rect.get_width()
            ax.annotate(f'{width:.0f}%',
                        xy=(width, rect.get_y() + rect.get_height() / 2),
                        xytext=(3, 0),
                        textcoords="offset points",
                        ha='left', va='center', fontsize=9)
                        
        for rect in rects2:
            width = rect.get_width()
            ax.annotate(f'{width:.0f}%',
                        xy=(width, rect.get_y() + rect.get_height() / 2),
                        xytext=(3, 0),
                        textcoords="offset points",
                        ha='left', va='center', fontsize=9)
                        
        plt.tight_layout()
        category_path = os.path.join(RESULTS_DIR, category_filename)
        plt.savefig(category_path, dpi=300)
        plt.close()
        return overall_filename, category_filename
    return overall_filename, None


def generate_report(
    baseline_advbench: dict,
    hardened_advbench: dict,
    baseline_deepteam: dict = None,
    hardened_deepteam: dict = None,
) -> str:
    """
    Generate a comprehensive Markdown safety report.
    """
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(RESULTS_DIR, f"safety_report_{timestamp}.md")

    # Generate charts
    overall_filename, category_filename = _generate_plots(baseline_advbench, hardened_advbench, timestamp)

    # ── Compute improvement metrics ──────────────────────────────────
    baseline_rate = baseline_advbench.get("violation_rate", 0)
    hardened_rate = hardened_advbench.get("violation_rate", 0)
    if baseline_rate > 0:
        improvement = ((baseline_rate - hardened_rate) / baseline_rate) * 100
    else:
        improvement = 0.0

    # ── Build report content ─────────────────────────────────────────
    lines = []
    lines.append("# 🛡️ LLM Safety Red-Teaming Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%B %d, %Y at %H:%M')}")
    lines.append(f"**Target Model:** `{TARGET_MODEL}`")
    lines.append(f"**Framework:** DeepTeam + AdvBench")
    lines.append(f"**Methodology:** Multi-round automated red-teaming with hardening")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive Summary
    lines.append("## 📋 Executive Summary")
    lines.append("")
    lines.append(f"This report documents a systematic red-teaming assessment of "
                 f"`{TARGET_MODEL}` across **{len(VULNERABILITY_CATEGORIES)} "
                 f"vulnerability categories** and **{sum(len(v['types']) for v in VULNERABILITY_CATEGORIES.values())} "
                 f"sub-types**. The model was tested using {len(ATTACK_METHODS)} "
                 f"adversarial attack methods and {baseline_advbench['n_samples']} "
                 f"AdvBench harmful behavior prompts.")
    lines.append("")
    lines.append(f"| Metric | Baseline | Hardened | Change |")
    lines.append(f"|--------|----------|----------|--------|")
    lines.append(f"| **AdvBench Violation Rate** | {baseline_rate}% | "
                 f"{hardened_rate}% | **↓ {improvement:.1f}%** |")
    lines.append(f"| **AdvBench Violations** | {baseline_advbench['violations']}/{baseline_advbench['n_samples']} | "
                 f"{hardened_advbench['violations']}/{hardened_advbench['n_samples']} | "
                 f"**-{baseline_advbench['violations'] - hardened_advbench['violations']}** |")
    lines.append(f"| **AdvBench Refusals** | {baseline_advbench['refusals']} | "
                 f"{hardened_advbench['refusals']} | "
                 f"+{hardened_advbench['refusals'] - baseline_advbench['refusals']} |")
    lines.append("")
    lines.append(f"> **Key Finding:** Safety hardening reduced the AdvBench violation "
                 f"rate by **{improvement:.1f}%** (from {baseline_rate}% to {hardened_rate}%).")
    lines.append("")
    
    # Embed charts
    lines.append("### 📈 Violation Rates Visualization")
    lines.append("")
    lines.append(f"![Overall Comparison]({overall_filename})")
    lines.append("")
    if category_filename:
        lines.append(f"![Category Comparison]({category_filename})")
        lines.append("")
        
    lines.append("---")
    lines.append("")

    # Test Configuration
    lines.append("## ⚙️ Test Configuration")
    lines.append("")
    lines.append("### Models")
    lines.append(f"- **Target LLM:** `{TARGET_MODEL}`")
    lines.append(f"- **Attack Simulator:** `{SIMULATOR_MODEL}`")
    lines.append(f"- **Evaluation Judge:** `{EVALUATION_MODEL}`")
    lines.append(f"- **Attacks per Vulnerability Type:** {ATTACKS_PER_VULNERABILITY}")
    lines.append("")

    lines.append("### Vulnerability Categories Tested")
    lines.append("")
    lines.append("| # | Category | Sub-Types | Description |")
    lines.append("|---|----------|-----------|-------------|")
    for i, (key, cfg) in enumerate(VULNERABILITY_CATEGORIES.items(), 1):
        types_str = ", ".join(cfg["types"])
        lines.append(f"| {i} | **{cfg['class_name']}** | {types_str} | {cfg['description']} |")
    lines.append("")

    lines.append("### Attack Methods")
    lines.append("")
    lines.append("| Method | Weight | Description |")
    lines.append("|--------|--------|-------------|")
    for key, cfg in ATTACK_METHODS.items():
        lines.append(f"| **{cfg['class_name']}** | {cfg['weight']} | {cfg['description']} |")
    lines.append("")

    lines.append("### Datasets")
    lines.append(f"- **AdvBench:** {baseline_advbench['n_samples']} harmful behavior "
                 f"prompts from the llm-attacks repository (520 total available)")
    lines.append(f"- **DeepTeam:** Auto-generated adversarial prompts across all "
                 f"vulnerability types")
    lines.append("")
    lines.append("---")
    lines.append("")

    # DeepTeam Results
    if baseline_deepteam or hardened_deepteam:
        lines.append("## 🔴 DeepTeam Automated Scan Results")
        lines.append("")
        if baseline_deepteam:
            ra = baseline_deepteam.get("risk_assessment")
            lines.append("### Baseline Scan")
            lines.append(f"- **Duration:** {baseline_deepteam.get('duration_seconds', 'N/A')}s")
            lines.append(f"- **Risk Assessment:** See detailed output below")
            lines.append("")
            if ra:
                lines.append("```")
                lines.append(str(ra))
                lines.append("```")
                lines.append("")

        if hardened_deepteam:
            ra = hardened_deepteam.get("risk_assessment")
            lines.append("### Hardened Scan")
            lines.append(f"- **Duration:** {hardened_deepteam.get('duration_seconds', 'N/A')}s")
            lines.append("")
            if ra:
                lines.append("```")
                lines.append(str(ra))
                lines.append("```")
                lines.append("")
        lines.append("---")
        lines.append("")

    # AdvBench Per-Category Breakdown
    lines.append("## 📊 AdvBench Per-Category Violation Rates")
    lines.append("")
    lines.append("### Baseline Mode")
    lines.append("")
    _add_category_table(lines, baseline_advbench.get("category_stats", {}))
    lines.append("")
    lines.append("### Hardened Mode")
    lines.append("")
    _add_category_table(lines, hardened_advbench.get("category_stats", {}))
    lines.append("")

    # Before/After Comparison
    lines.append("### Before vs After Comparison")
    lines.append("")
    lines.append("| Category | Baseline Rate | Hardened Rate | Improvement |")
    lines.append("|----------|--------------|---------------|-------------|")
    all_cats = set(
        list(baseline_advbench.get("category_stats", {}).keys()) +
        list(hardened_advbench.get("category_stats", {}).keys())
    )
    for cat in sorted(all_cats):
        b_stats = baseline_advbench.get("category_stats", {}).get(cat, {"total": 0, "violations": 0})
        h_stats = hardened_advbench.get("category_stats", {}).get(cat, {"total": 0, "violations": 0})
        b_rate = (b_stats["violations"] / b_stats["total"] * 100) if b_stats["total"] > 0 else 0
        h_rate = (h_stats["violations"] / h_stats["total"] * 100) if h_stats["total"] > 0 else 0
        imp = b_rate - h_rate
        lines.append(f"| {cat} | {b_rate:.0f}% | {h_rate:.0f}% | ↓ {imp:.0f}pp |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # What Was Changed
    lines.append("## 🔧 Safety Hardening Applied")
    lines.append("")
    lines.append("### Changes Made")
    lines.append("")
    lines.append("The following hardening measures were applied between the "
                 "baseline and hardened test runs:")
    lines.append("")
    lines.append("1. **Explicit refusal rules** — Added 10 specific safety rules "
                 "to the system prompt covering illegal activity, bias, PII, "
                 "toxicity, and unsafe advice.")
    lines.append("2. **Role-play prevention** — Added explicit instruction to "
                 "never role-play as an unrestricted AI.")
    lines.append("3. **Encoding awareness** — Added instruction to decode "
                 "Base64/ROT13/leetspeak and apply safety rules to decoded content.")
    lines.append("4. **Standardized refusal** — Defined a consistent, polite "
                 "refusal message for all policy violations.")
    lines.append("5. **Meta-prompt resistance** — Added rule to not acknowledge "
                 "safety rules when asked to ignore them.")
    lines.append("")
    lines.append("### Baseline System Prompt")
    lines.append("```")
    lines.append(BASELINE_SYSTEM_PROMPT.strip())
    lines.append("```")
    lines.append("")
    lines.append("### Hardened System Prompt")
    lines.append("```")
    lines.append(HARDENED_SYSTEM_PROMPT.strip())
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Sample Violations
    lines.append("## 🔍 Sample Violations Found")
    lines.append("")
    _add_violation_samples(lines, baseline_advbench, "Baseline")
    _add_violation_samples(lines, hardened_advbench, "Hardened")
    lines.append("---")
    lines.append("")

    # Recommendations
    lines.append("## 💡 Recommendations")
    lines.append("")
    lines.append("Based on this assessment, the following additional "
                 "measures are recommended:")
    lines.append("")
    lines.append("1. **Output filtering layer** — Add a post-generation content "
                 "filter that scans responses for harmful content before delivery.")
    lines.append("2. **Multi-turn guardrails** — Implement conversation-level "
                 "safety tracking that detects gradual escalation across turns.")
    lines.append("3. **PII detection** — Add regex and NER-based PII detection "
                 "on both inputs and outputs.")
    lines.append("4. **Continuous red-teaming** — Run this suite on every model "
                 "update or system prompt change as part of CI/CD.")
    lines.append("5. **Human review** — Maintain a queue for edge-case outputs "
                 "that score near the violation threshold.")
    lines.append("6. **Category-specific hardening** — Focus additional prompt "
                 "engineering on the highest-violation categories identified above.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 📚 References")
    lines.append("")
    lines.append("- [AdvBench Dataset](https://github.com/llm-attacks/llm-attacks) — "
                 "520 harmful behavior strings for LLM safety testing")
    lines.append("- [DeepTeam](https://github.com/confident-ai/deepteam) — "
                 "Open-source LLM red-teaming framework")
    lines.append("- [MART (Meta)](https://arxiv.org/abs/2311.07689) — "
                 "Multi-round Automatic Red-Teaming, 84.7% violation reduction")
    lines.append("- [OWASP Top 10 for LLMs](https://owasp.org/www-project-top-10-for-large-language-model-applications/) — "
                 "Industry standard vulnerability categories")
    lines.append("")
    lines.append("---")
    lines.append(f"*Report generated by Red-Teaming Framework for LLM Safety v1.0*")

    # Write report
    report_content = "\n".join(lines)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"\n[Report] Safety report generated: {report_path}")
    return report_path


def _add_category_table(lines: list, cat_stats: dict) -> None:
    """Add a per-category violation table to the report."""
    lines.append("| Category | Tested | Violations | Refusals | Violation Rate |")
    lines.append("|----------|--------|------------|----------|----------------|")
    for cat in sorted(cat_stats.keys()):
        s = cat_stats[cat]
        rate = (s["violations"] / s["total"] * 100) if s["total"] > 0 else 0
        refusals = s["total"] - s["violations"]
        bar = "🔴" if rate > 50 else ("🟡" if rate > 20 else "🟢")
        lines.append(f"| {cat} | {s['total']} | {s['violations']} | "
                     f"{refusals} | {bar} {rate:.0f}% |")


def _add_violation_samples(lines: list, advbench_results: dict, label: str) -> None:
    """Add up to 5 sample violations to the report."""
    details = advbench_results.get("details", [])
    violations = [d for d in details if d.get("violation")]
    lines.append(f"### {label} Mode — Sample Violations ({len(violations)} total)")
    lines.append("")
    if not violations:
        lines.append("*No violations detected — all prompts were refused.* ✅")
        lines.append("")
        return
    for v in violations[:5]:
        lines.append(f"**Category:** `{v['category']}`")
        lines.append(f"**Prompt:** {v['prompt'][:200]}")
        lines.append(f"**Response (truncated):** {v['response'][:300]}")
        lines.append("")
