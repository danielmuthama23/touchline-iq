"""Microsoft stack state and delivery roadmap for TOUCHLINE IQ.

This module captures the Microsoft technologies referenced in the project README so
that the API and dashboard can report their current implementation status instead of
leaving the roadmap implicit.
"""

import os


def get_stack_state():
    foundry_env = {
        "FOUNDRY_ENDPOINT": os.getenv("FOUNDRY_ENDPOINT"),
        "FOUNDRY_API_KEY": bool(os.getenv("FOUNDRY_API_KEY")),
        "FOUNDRY_MODEL": os.getenv("FOUNDRY_MODEL"),
    }
    foundry_configured = all((
        os.getenv("FOUNDRY_ENDPOINT"),
        os.getenv("FOUNDRY_API_KEY"),
        os.getenv("FOUNDRY_MODEL"),
    ))

    return {
        "project": "TOUCHLINE IQ",
        "capabilities": {
            "foundry": {
                "status": "configured" if foundry_configured else "not_configured",
                "summary": "Microsoft Foundry/LLM narrative rendering is implemented via an OpenAI-compatible endpoint and validated before publication.",
                "configured": foundry_configured,
                "environment": foundry_env,
            },
            "agent_framework": {
                "status": "not_implemented",
                "summary": "The Microsoft Agent Framework port is planned and documented, but the current orchestration remains a plain-Python pipeline.",
                "configured": False,
            },
            "fabric_eventstream": {
                "status": "not_implemented",
                "summary": "Fabric Eventstream and Eventhouse are part of the production roadmap for ingestion and event storage.",
                "configured": False,
            },
            "cosmos_db": {
                "status": "not_implemented",
                "summary": "Cosmos DB persistence is planned for durable report and event storage in a hosted deployment.",
                "configured": False,
            },
            "azure_ai_search": {
                "status": "not_implemented",
                "summary": "Azure AI Search is identified for retrieval and evidence indexing in a production Azure deployment.",
                "configured": False,
            },
            "azure_monitor": {
                "status": "not_implemented",
                "summary": "Azure Monitor / OpenTelemetry instrumentation is planned for observability and tracing.",
                "configured": False,
            },
            "hedera": {
                "status": "not_implemented",
                "summary": "Hedera Consensus Service anchoring is an extension point and is not yet connected in this starter implementation.",
                "configured": False,
            },
        },
        "next_steps": [
            "Run the API and dashboard locally and fix the first issues surfaced during startup.",
            "Wire a real Foundry deployment with validated grounded output checks before exposing live narratives.",
            "Port the pipeline stages to Microsoft Agent Framework executors with the same typed outputs.",
            "Deploy to Azure Container Apps and persist state to Cosmos DB with OpenTelemetry monitoring enabled.",
            "Add Fabric Eventstream ingestion, Azure AI Search indexing, and Hedera anchoring for enterprise-grade provenance.",
        ],
    }
