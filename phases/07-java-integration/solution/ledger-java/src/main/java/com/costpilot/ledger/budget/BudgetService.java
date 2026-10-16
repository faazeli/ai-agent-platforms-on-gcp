package com.costpilot.ledger.budget;

import com.costpilot.ledger.client.CostApiClient;
import com.costpilot.ledger.client.TeamCostSummary;
import com.costpilot.ledger.domain.Budget;
import com.costpilot.ledger.domain.BudgetEvaluator;
import com.costpilot.ledger.domain.BudgetStatus;
import java.time.Clock;
import java.time.LocalDate;
import org.springframework.stereotype.Service;

/** Orchestration only: fetch the budget, fetch the spend, let the domain decide. */
@Service
public class BudgetService {

    private final BudgetRepository budgets;
    private final CostApiClient costApi;
    private final Clock clock;

    public BudgetService(BudgetRepository budgets, CostApiClient costApi, Clock clock) {
        this.budgets = budgets;
        this.costApi = costApi;
        this.clock = clock;
    }

    public BudgetStatus status(String teamId, String month) {
        Budget budget = budgets.find(teamId, month).orElseThrow(() -> new BudgetNotFoundException(teamId, month));
        TeamCostSummary spend = costApi.teamSummary(teamId, month);
        return BudgetEvaluator.evaluate(budget, spend.totalEffectiveCost(), LocalDate.now(clock));
    }
}
