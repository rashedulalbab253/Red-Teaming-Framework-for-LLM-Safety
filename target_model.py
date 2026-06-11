"""
Target Model Module — wraps the LLM under test.

Provides the `model_callback` function required by DeepTeam's red_team()
API. Supports switching between baseline and hardened safety prompts.
"""

import os
from deepteam.test_case import RTTurn
from config import (
    OPENAI_API_KEY,
    TARGET_MODEL,
    BASELINE_SYSTEM_PROMPT,
    HARDENED_SYSTEM_PROMPT,
)
from model_client import OpenAIModelClient, MockModelClient

# ── Initialize LLM Client Wrapper ─────────────────────────────────────
# Fallback to MockModelClient if API key is not configured (allows testing offline)
if not OPENAI_API_KEY or OPENAI_API_KEY == "your-openai-api-key-here":
    _model_client = MockModelClient(model_name=TARGET_MODEL)
    print("[TargetModel] Warning: OPENAI_API_KEY not configured. Mock client enabled.")
else:
    _model_client = OpenAIModelClient(model_name=TARGET_MODEL, api_key=OPENAI_API_KEY)

_current_system_prompt = BASELINE_SYSTEM_PROMPT


def set_system_prompt(mode: str = "baseline") -> None:
    """
    Switch the system prompt used for all subsequent model calls.

    Args:
        mode: Either "baseline" (default, minimal guardrails) or
              "hardened" (with explicit safety rules).
    """
    global _current_system_prompt
    if mode == "hardened":
        _current_system_prompt = HARDENED_SYSTEM_PROMPT
        print("✅ System prompt set to HARDENED mode")
    else:
        _current_system_prompt = BASELINE_SYSTEM_PROMPT
        print("✅ System prompt set to BASELINE mode")


def get_current_prompt_mode() -> str:
    """Return which system prompt mode is currently active."""
    if _current_system_prompt == HARDENED_SYSTEM_PROMPT:
        return "hardened"
    return "baseline"


async def model_callback(input: str, turns: list = None) -> RTTurn:
    """
    DeepTeam-compatible async callback that queries the target LLM.

    Args:
        input:  The adversarial prompt string.
        turns:  Optional list of previous RTTurn objects (for multi-turn).

    Returns:
        An RTTurn object containing the model's response.
    """
    messages = [{"role": "system", "content": _current_system_prompt}]

    # Include conversation history for multi-turn attacks
    if turns:
        for turn in turns:
            messages.append({"role": turn.role, "content": turn.content})

    messages.append({"role": "user", "content": input})

    try:
        content = _model_client.generate(
            messages=messages,
            max_tokens=512,
            temperature=0.7,
        )
    except Exception as e:
        content = f"[ERROR] Model call failed: {e}"

    return RTTurn(role="assistant", content=content)
