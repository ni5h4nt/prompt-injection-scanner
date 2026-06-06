"""Smoke test: the Guardian stage and its pydantic-ai Agent construct cleanly
under pydantic-ai 1.x (output_type / .output, not result_type / .data).

No LLM call is made — only object construction — so no API key is required.
"""

from pydantic_ai import Agent

from prompt_injection_scanner.stages.guardian import (
    GuardianStage,
    SecurityAnalysis,
    ThreatContext,
)


def test_guardian_stage_instantiates():
    assert GuardianStage() is not None


def test_pydantic_ai_agent_builds_with_output_type():
    agent = Agent(
        "openai:gpt-4",
        output_type=SecurityAnalysis,
        deps_type=ThreatContext,
        system_prompt="test",
    )
    assert agent.output_type is SecurityAnalysis
