package com.costpilot.ledger.config;

import com.costpilot.ledger.domain.Budget;
import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;

/** Budgets seeded from configuration. A real service would keep them in a database. */
@ConfigurationProperties("costpilot")
public record BudgetProperties(List<Budget> budgets) {

    public BudgetProperties {
        budgets = budgets == null ? List.of() : List.copyOf(budgets);
    }
}
