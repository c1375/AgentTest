from agenttest.agents.factory import AgentClientFactory
from agenttest.agents.role import AgentRole
from agenttest.config import settings


def test_factory_loads_all_expected_roles() -> None:
    factory = AgentClientFactory.from_settings(settings)
    roles = factory.list_roles()

    expected = {
        AgentRole.TEST_SYNTHESIZER,
        AgentRole.BASELINE,
        AgentRole.JUDGE,
    }
    assert expected.issubset(set(roles))


def test_each_client_has_resolved_config() -> None:
    factory = AgentClientFactory.from_settings(settings)
    for role in factory.list_roles():
        client = factory.get(role)
        assert client.config.model
        assert client.config.max_tokens > 0
        assert 0.0 <= client.config.temperature <= 2.0
        assert client.config.is_anthropic


def test_test_synthesizer_uses_sonnet() -> None:
    # prompt_cache_enabled is intentionally False in S2 — the system
    # prompt is below Anthropic's ~1024-token cache minimum until the
    # OWASP catalog grows past 4 entries (see docs/plan/sprint-2.md
    # § "Locked decision 5"). Re-flip in S3 and reinstate the assertion.
    factory = AgentClientFactory.from_settings(settings)
    synth = factory.get(AgentRole.TEST_SYNTHESIZER)
    assert "sonnet" in synth.config.model.lower()
    assert synth.config.prompt_cache_enabled is False


def test_baseline_uses_sonnet() -> None:
    factory = AgentClientFactory.from_settings(settings)
    baseline = factory.get(AgentRole.BASELINE)
    assert "sonnet" in baseline.config.model.lower()


def test_judge_uses_haiku() -> None:
    factory = AgentClientFactory.from_settings(settings)
    judge = factory.get(AgentRole.JUDGE)
    assert "haiku" in judge.config.model.lower()
