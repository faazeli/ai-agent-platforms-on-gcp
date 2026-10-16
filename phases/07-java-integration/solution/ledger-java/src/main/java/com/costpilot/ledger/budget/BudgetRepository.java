package com.costpilot.ledger.budget;

import com.costpilot.ledger.config.BudgetProperties;
import com.costpilot.ledger.domain.Budget;
import java.util.Optional;
import org.springframework.stereotype.Repository;

/** Budgets by team and month. Backed by configuration; swap for a database without touching callers. */
@Repository
public class BudgetRepository {

    private final BudgetProperties properties;

    public BudgetRepository(BudgetProperties properties) {
        this.properties = properties;
    }

    public Optional<Budget> find(String teamId, String month) {
        return properties.budgets().stream()
                .filter(b -> b.teamId().equals(teamId) && b.month().equals(month))
                .findFirst();
    }
}
