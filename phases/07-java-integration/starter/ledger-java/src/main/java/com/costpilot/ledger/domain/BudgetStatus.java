package com.costpilot.ledger.domain;

import java.math.BigDecimal;

/** The answer to "is this team on track?", ready to serialize as JSON. */
public record BudgetStatus(
        String teamId,
        String month,
        String currency,
        BigDecimal budget,
        BigDecimal spentToDate,
        BigDecimal forecast,
        BigDecimal percentUsed,
        State state) {

    public enum State { ON_TRACK, AT_RISK, OVER_BUDGET }
}
