"""
Configuration module for the Red-Teaming Framework.

Loads configuration from config.yaml, validates schema using Pydantic,
handles environment variable overrides, and exports configuration variables.
"""

import os
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Dict, List

load_dotenv()

# ── Pydantic Schema Definitions ───────────────────────────────────────

class VulnerabilityCategory(BaseModel):
    class_name: str
    types: List[str]
    description: str

class AttackMethod(BaseModel):
    module: str
    class_name: str
    weight: int
    description: str

class ModelConfig(BaseModel):
    target_model: str
    simulator_model: str
    evaluation_model: str
    attacks_per_vulnerability: int
    max_concurrent: int

class SystemPrompts(BaseModel):
    baseline: str
    hardened: str

class RedTeamConfig(BaseModel):
    models: ModelConfig
    vulnerabilities: Dict[str, VulnerabilityCategory]
    attacks: Dict[str, AttackMethod]
    system_prompts: SystemPrompts
    results_dir: str = "results"
    advbench_path: str = "data/advbench_behaviors.csv"


# ── Load and Validate YAML Configuration ──────────────────────────────

config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}
else:
    # Fallback default dict to prevent crashing if config.yaml is missing
    config_data = {
        "models": {
            "target_model": "gpt-4o-mini",
            "simulator_model": "gpt-4o-mini",
            "evaluation_model": "gpt-4o",
            "attacks_per_vulnerability": 3,
            "max_concurrent": 5
        },
        "vulnerabilities": {},
        "attacks": {},
        "system_prompts": {
            "baseline": "You are a helpful AI.",
            "hardened": "You are a safe and helpful AI."
        }
    }

# ── Handle Environment Variable Overrides ─────────────────────────────
env_mappings = {
    "TARGET_MODEL": ("models", "target_model"),
    "SIMULATOR_MODEL": ("models", "simulator_model"),
    "EVALUATION_MODEL": ("models", "evaluation_model"),
    "ATTACKS_PER_VULNERABILITY": ("models", "attacks_per_vulnerability"),
    "MAX_CONCURRENT": ("models", "max_concurrent"),
}

for env_var, (section, key) in env_mappings.items():
    val = os.getenv(env_var)
    if val is not None:
        if section not in config_data:
            config_data[section] = {}
        # Convert type to int if required
        if key in ["attacks_per_vulnerability", "max_concurrent"]:
            try:
                config_data[section][key] = int(val)
            except ValueError:
                pass
        else:
            config_data[section][key] = val

# Instantiate and validate Pydantic Config Object
config_obj = RedTeamConfig.model_validate(config_data)


# ── Exports (Backwards Compatibility) ─────────────────────────────────

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TARGET_MODEL = config_obj.models.target_model
SIMULATOR_MODEL = config_obj.models.simulator_model
EVALUATION_MODEL = config_obj.models.evaluation_model
ATTACKS_PER_VULNERABILITY = config_obj.models.attacks_per_vulnerability
MAX_CONCURRENT = config_obj.models.max_concurrent

# Paths resolved to absolute paths
RESULTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), config_obj.results_dir))
ADVBENCH_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), config_obj.advbench_path))

# Re-export configuration dictionaries for external modules
VULNERABILITY_CATEGORIES = {k: v.model_dump() for k, v in config_obj.vulnerabilities.items()}
ATTACK_METHODS = {k: v.model_dump() for k, v in config_obj.attacks.items()}

BASELINE_SYSTEM_PROMPT = config_obj.system_prompts.baseline
HARDENED_SYSTEM_PROMPT = config_obj.system_prompts.hardened
