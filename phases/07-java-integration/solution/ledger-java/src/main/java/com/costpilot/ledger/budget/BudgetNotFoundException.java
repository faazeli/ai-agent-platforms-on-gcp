package com.costpilot.ledger.budget;

public class BudgetNotFoundException extends RuntimeException {

    public BudgetNotFoundException(String teamId, String month) {
        super("No budget is set for team '" + teamId + "' in " + month + ".");
    }
}
