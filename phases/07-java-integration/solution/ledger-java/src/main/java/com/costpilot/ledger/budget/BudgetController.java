package com.costpilot.ledger.budget;

import com.costpilot.ledger.security.TeamAccess;
import jakarta.validation.constraints.Pattern;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/v1/budgets")
public class BudgetController {

    private final BudgetService service;

    public BudgetController(BudgetService service) {
        this.service = service;
    }

    /** Is a team on track against its budget this month? */
    @GetMapping("/{teamId}/status")
    public BudgetStatusResponse status(
            @PathVariable @Pattern(regexp = "^[a-z0-9-]{2,40}$") String teamId,
            @RequestParam @Pattern(regexp = "^\\d{4}-(0[1-9]|1[0-2])$") String month,
            JwtAuthenticationToken authentication) {
        // Same rule as cost-api (Phase 6): authorize before touching data.
        TeamAccess.check(authentication, teamId);
        return BudgetStatusResponse.from(service.status(teamId, month));
    }
}
