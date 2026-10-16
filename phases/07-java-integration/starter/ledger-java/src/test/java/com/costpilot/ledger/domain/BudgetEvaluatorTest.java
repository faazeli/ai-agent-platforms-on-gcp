package com.costpilot.ledger.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.math.BigDecimal;
import java.time.LocalDate;
import org.junit.jupiter.api.Test;

class BudgetEvaluatorTest {

    private final Budget september = new Budget("payments", "2026-09", new BigDecimal("6000"), "USD", null);

    @Test
    void projectsMonthEndLinearlyAndFlagsRisk() {
        BudgetStatus status = BudgetEvaluator.evaluate(september, new BigDecimal("3100"), LocalDate.of(2026, 9, 15));
        assertThat(status.forecast()).isEqualByComparingTo("6200.00");
        assertThat(status.state()).isEqualTo(BudgetStatus.State.AT_RISK);
    }

    @Test
    void pastMonthUsesTheWholeMonth() {
        BudgetStatus status = BudgetEvaluator.evaluate(september, new BigDecimal("6079.20"), LocalDate.of(2026, 10, 3));
        assertThat(status.state()).isEqualTo(BudgetStatus.State.OVER_BUDGET);
        assertThat(status.percentUsed()).isEqualByComparingTo("101.3");
        assertThat(status.forecast()).isEqualByComparingTo("6079.20");
    }

    @Test
    void lowSpendIsOnTrack() {
        assertThat(BudgetEvaluator.evaluate(september, new BigDecimal("1000"), LocalDate.of(2026, 9, 15)).state())
                .isEqualTo(BudgetStatus.State.ON_TRACK);
    }

    @Test
    void budgetsValidateThemselves() {
        assertThatThrownBy(() -> new Budget("payments", "2026-13", BigDecimal.ONE, "USD", null))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new Budget("payments", "2026-09", BigDecimal.ZERO, "USD", null))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
