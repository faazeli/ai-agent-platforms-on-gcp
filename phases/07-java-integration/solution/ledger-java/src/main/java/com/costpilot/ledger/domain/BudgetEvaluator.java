package com.costpilot.ledger.domain;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.YearMonth;

/**
 * Compares spend with a budget and projects the month-end total linearly.
 * Pure logic: no Spring, no HTTP, so it is trivial to test and to reuse.
 */
public final class BudgetEvaluator {

    private BudgetEvaluator() {
    }

    /**
     * @param asOf the date the spend figure is current to; for a past month, use any date after it
     */
    public static BudgetStatus evaluate(Budget budget, BigDecimal spentToDate, LocalDate asOf) {
        YearMonth month = YearMonth.parse(budget.month());
        int daysInMonth = month.lengthOfMonth();
        int daysElapsed;
        if (asOf.isBefore(month.atDay(1))) {
            daysElapsed = 0;
        } else if (asOf.isAfter(month.atEndOfMonth())) {
            daysElapsed = daysInMonth;
        } else {
            daysElapsed = asOf.getDayOfMonth();
        }

        BigDecimal forecast = daysElapsed == 0
                ? BigDecimal.ZERO
                : spentToDate.multiply(BigDecimal.valueOf(daysInMonth))
                        .divide(BigDecimal.valueOf(daysElapsed), 2, RoundingMode.HALF_UP);
        BigDecimal percentUsed = spentToDate.multiply(BigDecimal.valueOf(100))
                .divide(budget.amount(), 1, RoundingMode.HALF_UP);

        BudgetStatus.State state;
        if (spentToDate.compareTo(budget.amount()) > 0) {
            state = BudgetStatus.State.OVER_BUDGET;
        } else if (forecast.compareTo(budget.amount()) > 0
                || spentToDate.compareTo(budget.amount().multiply(budget.warnAtFraction())) >= 0) {
            state = BudgetStatus.State.AT_RISK;
        } else {
            state = BudgetStatus.State.ON_TRACK;
        }
        return new BudgetStatus(budget.teamId(), budget.month(), budget.currency(), budget.amount(),
                spentToDate.setScale(2, RoundingMode.HALF_UP), forecast, percentUsed, state);
    }
}
