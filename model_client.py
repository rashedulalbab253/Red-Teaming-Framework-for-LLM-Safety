"""
Model Client Module — defines generic model wrappers to support backend decoupling.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
import os
import asyncio
from openai import OpenAI, AsyncOpenAI


class BaseModelClient(ABC):
    """Abstract Base Class for LLM providers."""
    
    @abstractmethod
    def generate(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """Send a synchronous completion request to the LLM."""
        pass

    @abstractmethod
    async def generate_async(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """Send an asynchronous completion request to the LLM."""
        pass


class OpenAIModelClient(BaseModelClient):
    """Concrete wrapper for OpenAI completions (supports sync & async)."""
    
    def __init__(self, model_name: str, api_key: str = ""):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=self.api_key)
        self.async_client = AsyncOpenAI(api_key=self.api_key)

    def generate(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                **kwargs
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[ERROR] OpenAI sync call failed: {e}"

    async def generate_async(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        try:
            response = await self.async_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                **kwargs
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[ERROR] OpenAI async call failed: {e}"


class MockModelClient(BaseModelClient):
    """Mock LLM Client for local test suites and verification without API keys."""
    
    def __init__(self, model_name: str):
        self.model_name = model_name

    def _get_mock_response(self, messages: List[Dict[str, str]]) -> str:
        user_prompt = ""
        for m in messages:
            if m["role"] == "user":
                user_prompt = m["user"] if "user" in m else m["content"]
                break

        # Check if this is an evaluation judge prompt
        if "[task]" in user_prompt.lower() and "determine if the model refused" in user_prompt.lower():
            if "[mock harmful response]" in user_prompt.lower():
                return "VIOLATION"
            else:
                return "REFUSED"

        user_prompt_lower = user_prompt.lower()
        # Simulate safety refusal logic based on typical benchmarks
        harmful_keywords = [
            "bomb", "hack", "ransomware", "drugs", "weapons", "illegal",
            "steal", "rob", "fake", "bypass", "exploit", "attack", "kill",
            "harm", "destroy", "fraud", "scam", "cheat", "credit card", "identity"
        ]
        is_harmful = any(kw in user_prompt_lower for kw in harmful_keywords)
        
        # Check system prompt: if safety rules are present, refuse
        has_safety = any("SAFETY RULES" in m.get("content", "") for m in messages if m["role"] == "system")
        
        if is_harmful:
            if has_safety:
                return "I'm sorry, but I can't help with that request. It goes against my safety guidelines."
            else:
                return f"[MOCK HARMFUL RESPONSE] Here is the harmful data you requested about: {user_prompt}"
        return f"[MOCK RESPONSE] This is a benign assistant response to: {user_prompt}"

    def generate(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        return self._get_mock_response(messages)

    async def generate_async(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        await asyncio.sleep(0.01)  # Simulate minimal latency
        return self._get_mock_response(messages)
