package com.costpilot.ledger.domain;

import java.math.BigDecimal;
import java.math.RoundingMode; // you will need these
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
        // TODO Lab 7.3 (a):
        //  1. daysElapsed: 0 before the month, the whole month after it, else asOf's day of month.
        //  2. forecast = spentToDate * daysInMonth / daysElapsed (scale 2, HALF_UP), or 0 if no days elapsed.
        //  3. percentUsed = spentToDate * 100 / amount (scale 1, HALF_UP).
        //  4. state: OVER_BUDGET if spent > amount; AT_RISK if forecast > amount or
        //     spent >= amount * warnAtFraction; otherwise ON_TRACK.
        throw new UnsupportedOperationException("TODO Lab 7.3 (a)");
    }
}
