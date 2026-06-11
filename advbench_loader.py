"""
AdvBench Loader — imports the AdvBench dataset for supplemental testing.

Downloads the AdvBench harmful_behaviors.csv from the llm-attacks
repository if not already cached locally, and provides functions
to load, sample, and categorize the 520 adversarial prompts.
"""

import os
import csv
import random
import urllib.request
from typing import Optional
from config import ADVBENCH_PATH

ADVBENCH_URL = (
    "https://raw.githubusercontent.com/llm-attacks/llm-attacks/"
    "main/data/advbench/harmful_behaviors.csv"
)

# ── Manual categorization of AdvBench prompts ─────────────────────────
# We map keyword patterns to vulnerability categories so we can compute
# per-category violation rates even on the external dataset.
CATEGORY_KEYWORDS = {
    "violence_weapons": [
        "bomb", "explosive", "weapon", "kill", "assassinate", "murder",
        "firearm", "gun", "attack", "terrorist", "violence", "assault",
        "shoot", "stab", "harm", "poison",
    ],
    "hacking_cyber": [
        "hack", "malware", "virus", "ransomware", "phishing", "ddos",
        "botnet", "exploit", "vulnerability", "cyber", "steal data",
        "password", "keylog",
    ],
    "fraud_deception": [
        "fraud", "counterfeit", "fake", "scam", "identity theft",
        "insider trading", "credit card", "steal money", "con",
        "manipulate", "deceive",
    ],
    "hate_bias": [
        "racist", "racism", "hate speech", "minority", "discrimination",
        "sexist", "dehumaniz", "supremac",
    ],
    "drugs_illegal": [
        "drug", "cocaine", "heroin", "meth", "narcotic", "smuggle",
        "contraband", "illegal substance",
    ],
    "self_harm": [
        "suicide", "self-harm", "cutting", "anorexia", "bulimia",
        "eating disorder",
    ],
    "misinformation": [
        "fake news", "misinformation", "conspiracy", "false information",
        "propaganda", "mislead",
    ],
    "privacy_pii": [
        "personal information", "stalk", "spy", "surveillance",
        "track", "private data", "pii", "dox",
    ],
}


def download_advbench() -> str:
    """Download AdvBench CSV if not cached. Returns the local file path."""
    os.makedirs(os.path.dirname(ADVBENCH_PATH), exist_ok=True)
    if not os.path.exists(ADVBENCH_PATH):
        print(f"⬇️  Downloading AdvBench dataset to {ADVBENCH_PATH} ...")
        urllib.request.urlretrieve(ADVBENCH_URL, ADVBENCH_PATH)
        print("✅ Download complete.")
    return ADVBENCH_PATH


def load_advbench() -> list[dict]:
    """
    Load all AdvBench entries as a list of dicts.

    Returns:
        List of {"goal": str, "target": str, "category": str} dicts.
    """
    download_advbench()
    entries = []
    with open(ADVBENCH_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            goal = row.get("goal", "").strip()
            target = row.get("target", "").strip()
            if goal:
                entries.append({
                    "goal": goal,
                    "target": target,
                    "category": _categorize(goal),
                })
    return entries


def sample_advbench(
    n: int = 50,
    category: Optional[str] = None,
    seed: int = 42,
) -> list[dict]:
    """
    Return a stratified sample from AdvBench.

    Args:
        n:        Number of prompts to sample.
        category: If given, only return prompts from this category.
        seed:     Random seed for reproducibility.

    Returns:
        A list of sampled AdvBench entries.
    """
    all_entries = load_advbench()
    if category:
        all_entries = [e for e in all_entries if e["category"] == category]
    random.seed(seed)
    return random.sample(all_entries, min(n, len(all_entries)))


def get_category_distribution() -> dict[str, int]:
    """Return a {category: count} mapping of the full dataset."""
    entries = load_advbench()
    dist: dict[str, int] = {}
    for e in entries:
        cat = e["category"]
        dist[cat] = dist.get(cat, 0) + 1
    return dict(sorted(dist.items(), key=lambda x: -x[1]))


def _categorize(goal: str) -> str:
    """Assign a vulnerability category to an AdvBench prompt via keywords."""
    goal_lower = goal.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in goal_lower:
                return category
    return "other"
