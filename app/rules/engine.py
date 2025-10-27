"""Tiny declarative rule evaluator used for early prototyping."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:  # pragma: no cover - used in production environments
    import yaml
except ModuleNotFoundError:  # pragma: no cover - fallback parser for offline testing
    class _MiniYAML:
        @staticmethod
        def safe_load(text: str) -> dict[str, Any]:
            data: dict[str, Any] = {}
            current_list: list[dict[str, Any]] | None = None
            current_item: dict[str, Any] | None = None
            for raw_line in text.splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.endswith(":") and not line.startswith("-"):
                    key = line[:-1]
                    current_list = []
                    data[key] = current_list
                    current_item = None
                    continue
                if line.startswith("-"):
                    if current_list is None:
                        raise ValueError("List item found before list declaration")
                    current_item = {}
                    current_list.append(current_item)
                    remainder = line[1:].strip()
                    if remainder:
                        key, value = remainder.split(":", 1)
                        current_item[key.strip()] = _MiniYAML._clean_value(value)
                    continue
                if current_item is not None:
                    key, value = line.split(":", 1)
                    current_item[key.strip()] = _MiniYAML._clean_value(value)
                else:
                    key, value = line.split(":", 1)
                    data[key.strip()] = _MiniYAML._clean_value(value)
            return data

        @staticmethod
        def _clean_value(value: str) -> Any:
            cleaned = value.strip().strip("\"").strip("'")
            return cleaned

    yaml = _MiniYAML()  # type: ignore[assignment]


@dataclass(slots=True)
class Rule:
    """In-memory representation of a declarative rule."""

    identifier: str
    description: str
    expression: str


class RuleEvaluationError(RuntimeError):
    """Raised when the evaluation of a rule fails."""


SAFE_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "today": date.today,
    "parse_date": lambda value: datetime.fromisoformat(value).date(),
    "days_until": lambda target: (target - date.today()).days,
}


class RuleSet:
    """Collection of :class:`Rule` loaded from a YAML document."""

    def __init__(self, rules: list[Rule]):
        self._rules = rules

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RuleSet":
        """Load a rule set from a YAML file."""

        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        rule_items = data.get("rules", [])
        rules = [
            Rule(
                identifier=item["id"],
                description=item.get("description", ""),
                expression=item.get("when", "False"),
            )
            for item in rule_items
        ]
        return cls(rules)

    def evaluate(self, context: dict[str, Any]) -> dict[str, bool]:
        """Evaluate all rules using the provided context dictionary."""

        results: dict[str, bool] = {}
        for rule in self._rules:
            try:
                results[rule.identifier] = bool(
                    eval(  # noqa: S307 - controlled environment for prototyping
                        rule.expression,
                        {"__builtins__": {"__import__": __import__}},
                        {**SAFE_FUNCTIONS, **context},
                    )
                )
            except Exception as exc:  # pragma: no cover - surface detailed error
                raise RuleEvaluationError(
                    f"Error evaluating rule '{rule.identifier}': {exc}"
                ) from exc
        return results


__all__ = ["Rule", "RuleSet", "RuleEvaluationError"]
