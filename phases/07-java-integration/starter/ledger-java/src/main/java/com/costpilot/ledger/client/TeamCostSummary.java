package com.costpilot.ledger.client;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.math.BigDecimal;
import java.util.List;

/**
 * Mirror of cost-api's Pydantic TeamCostSummary. The @JsonProperty names are the
 * wire contract (snake_case); the Java names are idiomatic. A contract test
 * (CostApiContractTest) fails the build if the two sides drift apart.
 */
public record TeamCostSummary(
        @JsonProperty("team_id") String teamId,
        @JsonProperty("month") String month,
        @JsonProperty("currency") String currency,
        @JsonProperty("total_effective_cost") BigDecimal totalEffectiveCost,
        @JsonProperty("total_billed_cost") BigDecimal totalBilledCost,
        @JsonProperty("top_services") List<ServiceCost> topServices) {

    public record ServiceCost(
            @JsonProperty("service_name") String serviceName,
            @JsonProperty("effective_cost") BigDecimal effectiveCost) {
    }
}
