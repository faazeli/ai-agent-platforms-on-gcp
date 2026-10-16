package com.costpilot.ledger.domain;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Applies an {@link AllocationRule} to a shared amount. Shares always add up to the amount. */
public final class Allocator {

    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);

    private Allocator() {
    }

    public static Map<String, BigDecimal> allocate(BigDecimal sharedCost, AllocationRule rule) {
        // TODO Lab 7.3 (b): a switch over the sealed AllocationRule producing a weight per team:
        //   Even -> weight 1 for each team; Fixed -> its percentages (reject if they don't sum to 100);
        //   Proportional -> each team's direct spend. No default branch: let the compiler check coverage.
        Map<String, BigDecimal> weights = null;
        return split(sharedCost, weights);
    }

    /** Splits by weight, rounding to cents, and gives any rounding remainder to the largest share. */
    private static Map<String, BigDecimal> split(BigDecimal amount, Map<String, BigDecimal> weights) {
        BigDecimal totalWeight = weights.values().stream().reduce(BigDecimal.ZERO, BigDecimal::add);
        if (weights.isEmpty() || totalWeight.signum() == 0) {
            throw new IllegalArgumentException("Nothing to allocate to");
        }
        Map<String, BigDecimal> shares = new LinkedHashMap<>();
        weights.forEach((team, weight) -> shares.put(team,
                amount.multiply(weight).divide(totalWeight, 2, RoundingMode.HALF_DOWN)));

        BigDecimal remainder = amount.setScale(2, RoundingMode.HALF_UP)
                .subtract(shares.values().stream().reduce(BigDecimal.ZERO, BigDecimal::add));
        String largest = List.copyOf(shares.keySet()).stream()
                .max((a, b) -> shares.get(a).compareTo(shares.get(b))).orElseThrow();
        shares.merge(largest, remainder, BigDecimal::add);
        return shares;
    }
}
