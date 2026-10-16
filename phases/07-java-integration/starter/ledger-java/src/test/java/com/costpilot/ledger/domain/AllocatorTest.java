package com.costpilot.ledger.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class AllocatorTest {

    @Test
    void sharesAlwaysAddUpToTheAmount() {
        Map<String, BigDecimal> shares = Allocator.allocate(new BigDecimal("100.00"),
                new AllocationRule.Even(List.of("payments", "search", "data-platform")));
        assertThat(shares.values().stream().reduce(BigDecimal.ZERO, BigDecimal::add)).isEqualByComparingTo("100.00");
    }

    @Test
    void proportionalFollowsDirectSpend() {
        Map<String, BigDecimal> shares = Allocator.allocate(new BigDecimal("1000"),
                new AllocationRule.Proportional(Map.of("payments", new BigDecimal("300"), "search", new BigDecimal("100"))));
        assertThat(shares.get("payments")).isEqualByComparingTo("750.00");
        assertThat(shares.get("search")).isEqualByComparingTo("250.00");
    }

    @Test
    void fixedPercentagesMustAddUpTo100() {
        assertThatThrownBy(() -> Allocator.allocate(BigDecimal.TEN,
                new AllocationRule.Fixed(Map.of("payments", new BigDecimal("60")))))
                .hasMessageContaining("100");
    }
}
