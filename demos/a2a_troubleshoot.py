"""Demo: Troubleshoot agent that communicates with the WFO Search Agent via A2A.

Usage:
    uv run demos/a2a_troubleshoot.py 25f4f60a-5dbc-4c72-ab57-a10815c4b67e
    uv run demos/a2a_troubleshoot.py 25f4f60a-5dbc-4c72-ab57-a10815c4b67e --base-url http://localhost:8080/api/a2a

This is a CrewAI agent that delegates to the WFO Search Agent over the A2A protocol.
CrewAI handles all A2A communication (discovery, messaging, polling) automatically
via the A2AClientConfig.

"""

import sys

from dotenv import load_dotenv

load_dotenv()

from crewai import Agent, Crew, Task  # noqa: E402
from crewai.a2a import A2AClientConfig  # noqa: E402
from crewai.a2a.updates import PollingConfig  # noqa: E402


def run_troubleshoot(subscription_id: str, base_url: str) -> None:
    """Run the troubleshoot agent for a given subscription."""
    troubleshoot_agent = Agent(
        role="Network Troubleshooter",
        goal="Diagnose issues with network subscriptions by querying the search agent",
        backstory=(
            "You are an expert network diagnostics agent. You have access to a remote "
            "search agent that can look up subscription details, products, workflows, "
            "and processes in a network orchestrator. Delegate search queries to it "
            "and synthesize a clear troubleshooting summary from the results."
        ),
        llm="gpt-4o-mini",
        a2a=A2AClientConfig(
            endpoint=f"{base_url}/.well-known/agent-card.json",
            timeout=120,
            max_turns=10,
            updates=PollingConfig(interval=2, max_polls=30),
        ),
        verbose=True,
    )

    task = Task(
        description=(
            f"Troubleshoot subscription {subscription_id}. "
            f"Get its details from the search agent. "
            f"Summarize the subscription status, product info, and any potential issues."
        ),
        expected_output="A troubleshooting summary with subscription status, product details, and identified issues",
        agent=troubleshoot_agent,
    )

    crew = Crew(agents=[troubleshoot_agent], tasks=[task], verbose=True)

    print("--- Running troubleshoot crew ---\n")
    result = crew.kickoff()

    print("\n--- Troubleshoot Result ---\n")
    print(result)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python demos/a2a_troubleshoot.py <subscription_id> [--base-url URL]")
        sys.exit(1)

    subscription_id = sys.argv[1]
    base_url = "http://localhost:8080/api/a2a"
    if "--base-url" in sys.argv:
        base_url = sys.argv[sys.argv.index("--base-url") + 1]

    print(f"A2A Base URL: {base_url}")
    print(f"Subscription ID: {subscription_id}\n")

    run_troubleshoot(subscription_id, base_url)


if __name__ == "__main__":
    main()
