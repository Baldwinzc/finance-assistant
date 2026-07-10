"""Chinese valuation analysis agent."""

__all__ = ["ValuationAgent"]


def __getattr__(name: str):
    if name == "ValuationAgent":
        from valuation_agent.agent import ValuationAgent

        return ValuationAgent
    raise AttributeError(name)
