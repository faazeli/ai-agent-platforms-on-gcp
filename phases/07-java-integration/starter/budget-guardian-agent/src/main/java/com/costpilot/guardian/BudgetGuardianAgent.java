package com.costpilot.guardian;

import com.google.adk.agents.BaseAgent;
import com.google.adk.agents.LlmAgent;
import com.google.adk.tools.FunctionTool;

/**
 * budget_guardian: answers "is team X on budget?" using ledger-java.
 *
 * The model is a Gemini model on Vertex AI, configured by environment:
 *   GOOGLE_GENAI_USE_VERTEXAI=TRUE GOOGLE_CLOUD_PROJECT=... GOOGLE_CLOUD_LOCATION=global
 * This bypasses the LiteLLM gateway, which is a deliberate trade-off you will
 * write an ADR about in Lab 7.5.
 */
public final class BudgetGuardianAgent {

    public static final String NAME = "budget_guardian";

    // TODO Lab 7.5: build the agent with LlmAgent.builder(): name NAME, a one-line description
    //   (the Python coordinator routes on it), model from GUARDIAN_MODEL (default
    //   "gemini-3.5-flash"), an instruction, and tools(FunctionTool.create(BudgetTools.class, "getBudgetStatus")).
    public static final BaseAgent ROOT_AGENT = null;

    private BudgetGuardianAgent() {
    }
}
