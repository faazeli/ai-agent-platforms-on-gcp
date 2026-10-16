package com.costpilot.ledger.domain;

import java.math.BigDecimal;
import java.util.Map;

/**
 * How to split a shared cost (a platform team's cluster, a support contract) across teams.
 *
 * A sealed interface lists every allowed rule in one place. The compiler then checks
 * that every {@code switch} over rules handles all of them: add a new rule and each
 * switch that forgets it stops compiling. That is the "design that survives change"
 * this lab is about.
 */
public sealed interface AllocationRule permits AllocationRule.Even, AllocationRule.Fixed, AllocationRule.Proportional {

    /** Split equally between the listed teams. */
    record Even(java.util.List<String> teams) implements AllocationRule {
    }

    /** Fixed percentages per team, which must add up to 100. */
    record Fixed(Map<String, BigDecimal> percentByTeam) implements AllocationRule {
    }

    /** In proportion to each team's own direct spend (the "fair share" rule). */
    record Proportional(Map<String, BigDecimal> directSpendByTeam) implements AllocationRule {
    }
}
