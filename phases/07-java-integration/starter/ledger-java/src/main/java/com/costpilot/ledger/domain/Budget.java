package com.costpilot.ledger.domain;

import java.math.BigDecimal;
import java.util.Objects;

/** A team's monthly budget. Records are immutable values: no setters, no surprises. */
public record Budget(String teamId, String month, BigDecimal amount, String currency, BigDecimal warnAtFraction) {

    public Budget {
        Objects.requireNonNull(teamId, "teamId");
        Objects.requireNonNull(month, "month");
        if (!month.matches("\\d{4}-(0[1-9]|1[0-2])")) {
            throw new IllegalArgumentException("month must be YYYY-MM, got " + month);
        }
        if (amount == null || amount.signum() <= 0) {
            throw new IllegalArgumentException("amount must be positive");
        }
        if (warnAtFraction == null) {
            warnAtFraction = new BigDecimal("0.80");
        }
    }
}
