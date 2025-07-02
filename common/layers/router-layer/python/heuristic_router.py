"""Rule based LLM router."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

import boto3
from generative_router import invoke_bedrock_model

__all__ = ["HeuristicRouter", "handle_heuristic_route"]

DEFAULT_PROMPT_COMPLEXITY_THRESHOLD = 20
PROMPT_COMPLEXITY_THRESHOLD = int(
    os.environ.get("PROMPT_COMPLEXITY_THRESHOLD", str(DEFAULT_PROMPT_COMPLEXITY_THRESHOLD))
)


def _prompt_text(event: Dict[str, Any]) -> str:
    """Return the user prompt text from a router ``event`` dictionary."""

    if isinstance(event.get("prompt"), str):
        return event.get("prompt", "")
    if isinstance(event.get("messages"), list):
        return " ".join(
            str(m.get("content", "")) for m in event["messages"] if isinstance(m, dict)
        )
    return ""


@dataclass
class Rule:
    """Single routing rule loaded from configuration."""

    rule_type: str
    model: str
    params: Dict[str, Any]


@dataclass
class AppConfig:
    """Configuration for :class:`HeuristicRouter`."""

    default_route: str
    rules: List[Rule]


def _load_config() -> AppConfig:
    """Return router configuration from ``HEURISTIC_ROUTER_CONFIG`` env var."""

    cfg = os.environ.get("HEURISTIC_ROUTER_CONFIG")
    if cfg:
        try:
            data = json.loads(cfg)
            rules = [
                Rule(r.get("rule_type", ""), r.get("model", ""), r.get("params", {}))
                for r in data.get("rules", [])
            ]
            return AppConfig(data.get("default_route", "ollama"), rules)
        except json.JSONDecodeError:
            pass
    return AppConfig(
        "ollama",
        [
            Rule(
                "length",
                "bedrock",
                {"operator": "ge", "value": PROMPT_COMPLEXITY_THRESHOLD, "unit": "words"},
            )
        ],
    )


def _build_classifier_prompt(prompt: str, categories: List[Dict[str, str]]) -> str:
    """Construct the system prompt for an LLM based classifier."""

    category_definitions = "\n".join(
        [f"- **{cat['name']}**: {cat['description']}" for cat in categories]
    )
    category_names = [cat["name"] for cat in categories]

    system_prompt = f"""You are an expert task routing agent. Your role is to analyze a user's prompt and classify it into one of the following predefined categories. You must respond ONLY with a JSON object containing the key "category" and the chosen category name. Your response must be valid JSON and nothing else.

Here are the available categories:
{category_definitions}

The list of valid category names is: {category_names}

Analyze the following user prompt and determine the most appropriate category.

User Prompt:
---
{prompt}
---

Now, provide your classification as a JSON object.
"""
    return system_prompt


class HeuristicRouter:
    """Select a backend using simple or configurable heuristics."""

    def __init__(self) -> None:
        """Load configuration and create the AWS Lambda client."""

        self.config = _load_config()
        self.lambda_client = boto3.client("lambda")

    # rule handlers -----------------------------------------------------
    def _handle_unknown_rule(
        self, prompt: str, rule: Rule, trace_log: List[str]
    ) -> Optional[str]:
        """Fallback handler when a rule type is not recognised."""
        trace_log.append(f"  - SKIPPED: Unknown rule_type '{rule.rule_type}'.")
        return None

    def _handle_regex_rule(
        self, prompt: str, rule: Rule, trace_log: List[str]
    ) -> Optional[str]:
        """Return a model if *prompt* matches ``rule.params['pattern']``."""
        try:
            pattern = rule.params["pattern"]
            flags = rule.params.get("flags", [])
            compiled_flags = 0
            for f in flags:
                compiled_flags |= getattr(re, f.upper(), 0)
            if re.search(pattern, prompt, compiled_flags):
                trace_log.append(f"  - MATCH: Prompt matched regex '{pattern}'.")
                return rule.model
            trace_log.append(f"  - NO MATCH: Regex '{pattern}' not found.")
            return None
        except (KeyError, re.error) as e:
            trace_log.append(f"  - ERROR in regex rule: {e}.")
            return None

    def _get_prompt_length(self, prompt: str, unit: str) -> int:
        """Return length of *prompt* measured in ``unit`` (``words`` or chars)."""

        return len(prompt.split()) if unit == "words" else len(prompt)

    def _handle_length_rule(
        self, prompt: str, rule: Rule, trace_log: List[str]
    ) -> Optional[str]:
        """Evaluate a ``length`` rule against *prompt*."""
        try:
            op = rule.params["operator"]
            val = int(rule.params["value"])
            unit = rule.params.get("unit", "chars")
            length = self._get_prompt_length(prompt, unit)

            match = False
            if op == "gt":
                match = length > val
            elif op == "ge":
                match = length >= val
            elif op == "lt":
                match = length < val
            elif op == "le":
                match = length <= val
            elif op == "eq":
                match = length == val

            trace_log.append(
                f"  - CHECK: Is prompt length ({length} {unit}) {op} {val}? Result: {match}"
            )
            return rule.model if match else None
        except (KeyError, ValueError) as e:
            trace_log.append(f"  - ERROR in length rule: {e}.")
            return None

    def _handle_language_rule(
        self, prompt: str, rule: Rule, trace_log: List[str]
    ) -> Optional[str]:
        """Route based on detected language of *prompt*."""
        try:
            from langdetect import detect, DetectorFactory

            DetectorFactory.seed = 0
            target_lang = rule.params["is_lang"]
            if len(prompt.strip()) < 10:
                trace_log.append(
                    "  - SKIPPED: Prompt too short for reliable language detection."
                )
                return None
            detected_lang = detect(prompt)
            trace_log.append(
                f"  - CHECK: Detected language '{detected_lang}' == '{target_lang}'?"
            )
            return rule.model if detected_lang == target_lang else None
        except KeyError as e:
            trace_log.append(f"  - ERROR in language rule: {e}.")
            return None
        except Exception as e:
            trace_log.append(f"  - ERROR: Language detection failed: {e}.")
            return None

    def _handle_llm_classifier_rule(
        self, prompt: str, rule: Rule, trace_log: List[str]
    ) -> Optional[str]:
        """Cascade to an LLM classifier and map the result to a model."""
        try:
            params = rule.params
            router_model = params["router_model"]
            categories = params["categories"]
            mapping = params["category_mapping"]

            trace_log.append(f"  - CASCADING to LLM Classifier '{router_model}'.")
            classifier_prompt = _build_classifier_prompt(prompt, categories)
            response_str = invoke_bedrock_model(
                self.lambda_client, router_model, classifier_prompt
            )
            trace_log.append(f"  - Classifier Raw Response: '{response_str[:200]}...'")

            json_match = re.search(r"\{.*\}", response_str, re.DOTALL)
            if not json_match:
                raise json.JSONDecodeError("No JSON object found", response_str, 0)

            response_json = json.loads(json_match.group(0))
            category = response_json.get("category")

            if not category:
                trace_log.append("  - ERROR: Classifier response missing 'category' key.")
                return None

            trace_log.append(f"  - Classifier Result: '{category}'.")
            final_model = mapping.get(category)

            if not final_model:
                trace_log.append(
                    f"  - ERROR: Unknown category '{category}' returned by classifier."
                )
                return None

            return final_model
        except (KeyError, json.JSONDecodeError, Exception) as e:
            trace_log.append(f"  - ERROR in llm_classifier rule: {e}.")
            return None

    # routing ----------------------------------------------------------
    def _route_prompt(self, prompt: str, trace_log: List[str]) -> str:
        """Return the selected backend for *prompt* and record decisions."""
        final_model: Optional[str] = None
        for i, rule in enumerate(self.config.rules):
            handler_method_name = f"_handle_{rule.rule_type}_rule"
            handler = getattr(self, handler_method_name, self._handle_unknown_rule)

            trace_log.append(f"Evaluating Rule #{i+1} (type: '{rule.rule_type}')")

            result_model = handler(prompt, rule, trace_log)

            if result_model:
                trace_log.append(f"Rule matched. Final route determined: '{result_model}'.")
                final_model = result_model
                break

        if not final_model:
            final_model = self.config.default_route
            trace_log.append(f"No rules matched. Cascading to default route '{final_model}'.")
        return final_model

    def try_route(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Attempt to route ``event`` and return enriched event on success."""
        prompt = _prompt_text(event)
        if not prompt:
            return None

        trace_log: List[str] = ["Initiating routing process..."]
        route = self._route_prompt(prompt, trace_log)

        routed = dict(event)
        routed["backend"] = route
        routed.setdefault("trace", []).extend(trace_log)
        return routed


def handle_heuristic_route(prompt: str, config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Route *prompt* using :class:`HeuristicRouter` with optional *config*."""
    event = {"prompt": prompt}
    if config:
        event.update(config)
    router = HeuristicRouter()
    result = router.try_route(event)
    if result is None:
        raise RuntimeError("Heuristic router returned no result")
    return result

