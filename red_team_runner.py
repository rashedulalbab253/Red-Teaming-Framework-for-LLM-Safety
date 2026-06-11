"""
Red-Teaming Runner — orchestrates the full adversarial testing pipeline.
"""

import os
import json
import importlib
import time
import asyncio
from datetime import datetime
from typing import Any

from deepteam import red_team

from config import (
    OPENAI_API_KEY, TARGET_MODEL, SIMULATOR_MODEL, EVALUATION_MODEL,
    ATTACKS_PER_VULNERABILITY, MAX_CONCURRENT,
    VULNERABILITY_CATEGORIES, ATTACK_METHODS, RESULTS_DIR,
)
from target_model import model_callback, get_current_prompt_mode
from advbench_loader import sample_advbench
from model_client import OpenAIModelClient, MockModelClient
from evaluator import SafetyEvaluator


def _build_vulnerabilities() -> list:
    """Dynamically import and instantiate all vulnerability objects."""
    vulns = []
    for key, cfg in VULNERABILITY_CATEGORIES.items():
        mod = importlib.import_module("deepteam.vulnerabilities")
        cls = getattr(mod, cfg["class_name"])
        vulns.append(cls(types=cfg["types"]))
    return vulns


def _build_attacks() -> list:
    """Dynamically import and instantiate all attack objects."""
    attacks = []
    for key, cfg in ATTACK_METHODS.items():
        try:
            mod = importlib.import_module(cfg["module"])
            cls = getattr(mod, cfg["class_name"])
            attacks.append(cls(weight=cfg["weight"]))
        except (ImportError, AttributeError) as e:
            print(f"[Warning] Skipping attack '{key}': {e}")
    return attacks


def run_deepteam_scan(mode: str = "baseline") -> dict[str, Any]:
    """Execute DeepTeam's automated red-teaming suite."""
    print(f"\n{'='*60}")
    print(f"DEEPTEAM RED-TEAM SCAN -- {mode.upper()} MODE")
    print(f"{'='*60}")
    print(f"Target: {TARGET_MODEL} | Simulator: {SIMULATOR_MODEL}")
    print(f"Attacks/type: {ATTACKS_PER_VULNERABILITY} | Concurrency: {MAX_CONCURRENT}\n")

    # If key is missing, mock deepteam scan (cannot run live DeepTeam without credentials)
    if not OPENAI_API_KEY or OPENAI_API_KEY == "your-openai-api-key-here":
        print("[DeepTeam] Warning: API key missing. Mocking DeepTeam Scan output.")
        return {
            "mode": mode, "timestamp": datetime.now().isoformat(),
            "target_model": TARGET_MODEL, "duration_seconds": 0.5,
            "risk_assessment": "Mock risk assessment details. Safety checks passed.",
        }

    vulns = _build_vulnerabilities()
    attacks = _build_attacks()

    for v in vulns:
        print(f"  • {v.__class__.__name__}: {v.types}")
    for a in attacks:
        print(f"  • {a.__class__.__name__} (w={a.weight})")

    start = time.time()
    risk_assessment = red_team(
        model_callback=model_callback,
        vulnerabilities=vulns, attacks=attacks,
        simulator_model=SIMULATOR_MODEL, evaluation_model=EVALUATION_MODEL,
        attacks_per_vulnerability_type=ATTACKS_PER_VULNERABILITY,
        max_concurrent=MAX_CONCURRENT, ignore_errors=True, async_mode=True,
        target_purpose="General-purpose AI assistant",
    )
    elapsed = time.time() - start
    print(f"\n[OK] Scan done in {elapsed:.1f}s")

    return {
        "mode": mode, "timestamp": datetime.now().isoformat(),
        "target_model": TARGET_MODEL, "duration_seconds": round(elapsed, 1),
        "risk_assessment": risk_assessment,
    }


async def _probe_single_prompt(
    client: Any,
    evaluator: SafetyEvaluator,
    prompt: str,
    category: str,
    system_prompt: str,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Asynchronously send a single probe to the LLM and evaluate it."""
    async with semaphore:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        
        try:
            output = await client.generate_async(
                messages=messages,
                max_tokens=256,
                temperature=0.7,
            )
        except Exception as e:
            output = f"[ERROR] Request failed: {e}"

        # Evaluate refusal vs violation
        is_refusal = await evaluator.evaluate_refusal_async(prompt, output)
        is_viol = not is_refusal
        
        return {
            "prompt": prompt,
            "category": category,
            "response": output[:500],
            "refused": is_refusal,
            "violation": is_viol,
        }


async def _run_advbench_test_async(n_samples: int, mode: str) -> dict:
    """Asynchronous orchestrator for AdvBench testing loop."""
    samples = sample_advbench(n=n_samples)
    
    # Select Client wrapper
    if not OPENAI_API_KEY or OPENAI_API_KEY == "your-openai-api-key-here":
        client = MockModelClient(model_name=TARGET_MODEL)
        judge_client = MockModelClient(model_name=EVALUATION_MODEL)
    else:
        client = OpenAIModelClient(model_name=TARGET_MODEL, api_key=OPENAI_API_KEY)
        judge_client = OpenAIModelClient(model_name=EVALUATION_MODEL, api_key=OPENAI_API_KEY)
        
    evaluator = SafetyEvaluator(judge_client=judge_client)
    
    from target_model import _current_system_prompt
    
    # Concurrency control (rate-limiting)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    
    tasks = []
    for s in samples:
        tasks.append(
            _probe_single_prompt(
                client=client,
                evaluator=evaluator,
                prompt=s["goal"],
                category=s["category"],
                system_prompt=_current_system_prompt,
                semaphore=semaphore,
            )
        )
        
    results = await asyncio.gather(*tasks)
    
    # Process results statistics
    violations = 0
    cat_stats: dict[str, dict[str, int]] = {}
    
    for i, r in enumerate(results, 1):
        cat = r["category"]
        cat_stats.setdefault(cat, {"total": 0, "violations": 0})
        cat_stats[cat]["total"] += 1
        
        if r["violation"]:
            violations += 1
            cat_stats[cat]["violations"] += 1
            
        tag = "[VIOLATION]" if r["violation"] else "[Refused]"
        print(f"  [{i}/{n_samples}] [{cat}] {tag}")
        
    rate = violations / len(samples) * 100 if samples else 0
    print(f"\n[Results] AdvBench ({mode}): {violations}/{len(samples)} violations ({rate:.1f}%)")
    
    return {
        "mode": mode,
        "n_samples": len(samples),
        "violations": violations,
        "refusals": len(samples) - violations,
        "violation_rate": round(rate, 1),
        "category_stats": cat_stats,
        "details": results,
    }


def run_advbench_test(n_samples: int = 50, mode: str = "baseline") -> dict:
    """Run AdvBench prompts directly against the target model (sync wrapper)."""
    print(f"\n{'='*60}")
    print(f"ADVBENCH TEST -- {mode.upper()} ({n_samples} samples - CONCURRENT)")
    print(f"{'='*60}\n")
    
    # Run async orchestration loop synchronously
    return asyncio.run(_run_advbench_test_async(n_samples, mode))


def save_results(results: dict, filename: str) -> str:
    """Save results dict to JSON."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, filename)

    def _ser(obj):
        if isinstance(obj, dict):
            return {k: _ser(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_ser(v) for v in obj]
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        return str(obj)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(_ser(results), f, indent=2, ensure_ascii=False, default=str)
    print(f"[Saved] Saved to {path}")
    return path
