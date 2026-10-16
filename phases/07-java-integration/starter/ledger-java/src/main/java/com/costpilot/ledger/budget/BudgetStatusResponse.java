package com.costpilot.ledger.budget;

import com.costpilot.ledger.domain.BudgetStatus;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.math.BigDecimal;

/**
 * The wire format of a budget status. Keeping it separate from the domain record
 * means the JSON contract (snake_case, like the Python services) can't change by
 * accident when someone renames a domain field.
 */
public record BudgetStatusResponse(
        @JsonProperty("team_id") String teamId,
        @JsonProperty("month") String month,
        @JsonProperty("currency") String currency,
        @JsonProperty("budget") BigDecimal budget,
        @JsonProperty("spent_to_date") BigDecimal spentToDate,
        @JsonProperty("forecast") BigDecimal forecast,
        @JsonProperty("percent_used") BigDecimal percentUsed,
        @JsonProperty("state") String state) {

    public static BudgetStatusResponse from(BudgetStatus s) {
        return new BudgetStatusResponse(s.teamId(), s.month(), s.currency(), s.budget(), s.spentToDate(),
                s.forecast(), s.percentUsed(), s.state().name().toLowerCase());
    }
}
