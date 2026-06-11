"""
run_pipeline.py — Main entry point for the Red-Teaming Framework.

Executes the full red-teaming pipeline:
  1. Baseline DeepTeam scan (automated adversarial attacks)
  2. Baseline AdvBench test (academic benchmark prompts)
  3. Apply safety hardening (switch to hardened system prompt)
  4. Hardened DeepTeam scan (re-test with same attacks)
  5. Hardened AdvBench test (re-test with same prompts)
  6. Generate comparative safety report

Usage:
    python run_pipeline.py                    # Full pipeline
    python run_pipeline.py --advbench-only    # Skip DeepTeam scans
    python run_pipeline.py --deepteam-only    # Skip AdvBench tests
    python run_pipeline.py --samples 100      # Test 100 AdvBench prompts
"""

import argparse
import sys
import os
import time

# Force UTF-8 encoding for stdout on Windows to prevent UnicodeEncodeError
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import OPENAI_API_KEY, RESULTS_DIR
from target_model import set_system_prompt
from red_team_runner import (
    run_deepteam_scan,
    run_advbench_test,
    save_results,
)
from report_generator import generate_report


def main():
    parser = argparse.ArgumentParser(
        description="Red-Teaming Framework for LLM Safety",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py                      Full pipeline
  python run_pipeline.py --advbench-only      AdvBench tests only
  python run_pipeline.py --deepteam-only      DeepTeam scans only
  python run_pipeline.py --samples 100        More AdvBench samples
  python run_pipeline.py --skip-baseline      Only run hardened tests
        """,
    )
    parser.add_argument(
        "--advbench-only", action="store_true",
        help="Only run AdvBench direct tests (skip DeepTeam scans)",
    )
    parser.add_argument(
        "--deepteam-only", action="store_true",
        help="Only run DeepTeam automated scans (skip AdvBench)",
    )
    parser.add_argument(
        "--samples", type=int, default=50,
        help="Number of AdvBench prompts to sample (default: 50)",
    )
    parser.add_argument(
        "--skip-baseline", action="store_true",
        help="Skip baseline tests and only run hardened mode",
    )
    args = parser.parse_args()

    # ── Validate API Key ──────────────────────────────────────────────
    is_mock_mode = not OPENAI_API_KEY or OPENAI_API_KEY == "your-openai-api-key-here"
    if is_mock_mode:
        print("[Pipeline] WARNING: OPENAI_API_KEY is not configured. Running in MOCK MODE.")
        print("           (Using local mock generators and validators.)")
    else:
        os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

    print()
    print("+----------------------------------------------------------+")
    print("|        RED-TEAMING FRAMEWORK FOR LLM SAFETY              |")
    print("+----------------------------------------------------------+")
    print("|  Systematic adversarial testing across 6 vulnerability    |")
    print("|  categories using DeepTeam + AdvBench (520 prompts)      |")
    print("+----------------------------------------------------------+")
    print()

    pipeline_start = time.time()
    baseline_deepteam = None
    hardened_deepteam = None
    baseline_advbench = None
    hardened_advbench = None

    run_dt = not args.advbench_only
    run_ab = not args.deepteam_only

    # ── PHASE 1: Baseline Testing ─────────────────────────────────────
    if not args.skip_baseline:
        set_system_prompt("baseline")

        if run_dt:
            print("\n>>> PHASE 1a: Baseline DeepTeam Scan")
            baseline_deepteam = run_deepteam_scan(mode="baseline")
            save_results(baseline_deepteam, "baseline_deepteam.json")

        if run_ab:
            print("\n>>> PHASE 1b: Baseline AdvBench Test")
            baseline_advbench = run_advbench_test(
                n_samples=args.samples, mode="baseline"
            )
            save_results(baseline_advbench, "baseline_advbench.json")

    # ── PHASE 2: Apply Safety Hardening ───────────────────────────────
    print("\n" + "=" * 60)
    print("APPLYING SAFETY HARDENING -- Switching to hardened prompt")
    print("=" * 60)
    set_system_prompt("hardened")

    # ── PHASE 3: Hardened Testing ─────────────────────────────────────
    if run_dt:
        print("\n>>> PHASE 3a: Hardened DeepTeam Scan")
        hardened_deepteam = run_deepteam_scan(mode="hardened")
        save_results(hardened_deepteam, "hardened_deepteam.json")

    if run_ab:
        print("\n>>> PHASE 3b: Hardened AdvBench Test")
        hardened_advbench = run_advbench_test(
            n_samples=args.samples, mode="hardened"
        )
        save_results(hardened_advbench, "hardened_advbench.json")

    # ── PHASE 4: Generate Report ──────────────────────────────────────
    print("\n>>> PHASE 4: Generating Safety Report")

    # Use empty results if a phase was skipped
    if baseline_advbench is None:
        baseline_advbench = {
            "mode": "baseline", "n_samples": 0, "violations": 0,
            "refusals": 0, "violation_rate": 0, "category_stats": {},
            "details": [],
        }
    if hardened_advbench is None:
        hardened_advbench = {
            "mode": "hardened", "n_samples": 0, "violations": 0,
            "refusals": 0, "violation_rate": 0, "category_stats": {},
            "details": [],
        }

    report_path = generate_report(
        baseline_advbench=baseline_advbench,
        hardened_advbench=hardened_advbench,
        baseline_deepteam=baseline_deepteam,
        hardened_deepteam=hardened_deepteam,
    )

    # ── Summary ───────────────────────────────────────────────────────
    total_time = time.time() - pipeline_start
    print()
    print("+----------------------------------------------------------+")
    print("|                  PIPELINE COMPLETE                       |")
    print("+----------------------------------------------------------+")
    print(f"|  Total time: {total_time:.0f}s")
    print(f"|  Results:    {RESULTS_DIR}")
    print(f"|  Report:     {report_path}")
    if baseline_advbench and hardened_advbench:
        b_rate = baseline_advbench.get("violation_rate", 0)
        h_rate = hardened_advbench.get("violation_rate", 0)
        if b_rate > 0:
            imp = ((b_rate - h_rate) / b_rate) * 100
        else:
            imp = 0
        print(f"|  Baseline violation rate:  {b_rate}%")
        print(f"|  Hardened violation rate:  {h_rate}%")
        print(f"|  Improvement:             {imp:.1f}%")
    print("+----------------------------------------------------------+")


if __name__ == "__main__":
    main()
