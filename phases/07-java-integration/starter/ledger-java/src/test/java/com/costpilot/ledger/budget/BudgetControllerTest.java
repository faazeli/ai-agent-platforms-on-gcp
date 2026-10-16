package com.costpilot.ledger.budget;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.costpilot.ledger.client.CostApiClient;
import com.costpilot.ledger.client.CostApiException;
import com.costpilot.ledger.client.TeamCostSummary;
import com.costpilot.ledger.config.BudgetProperties;
import com.costpilot.ledger.domain.Budget;
import com.costpilot.ledger.web.ApiErrors;
import java.math.BigDecimal;
import java.net.URI;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ProblemDetail;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

/** Standalone MockMvc: the controller, its error handling and our domain, with a fake cost-api. */
class BudgetControllerTest {

    private final CostApiClient costApi = mock(CostApiClient.class);
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        BudgetRepository repo = new BudgetRepository(new BudgetProperties(List.of(
                new Budget("payments", "2026-09", new BigDecimal("6000"), "USD", null))));
        Clock afterSeptember = Clock.fixed(Instant.parse("2026-10-03T00:00:00Z"), ZoneOffset.UTC);
        BudgetController controller = new BudgetController(new BudgetService(repo, costApi, afterSeptember));
        mvc = MockMvcBuilders.standaloneSetup(controller).setControllerAdvice(new ApiErrors()).build();
    }

    static JwtAuthenticationToken user(String role, String... teams) {
        Jwt jwt = Jwt.withTokenValue("t").header("alg", "RS256").subject("ana")
                .claim("role", role).claim("teams", List.of(teams)).build();
        return new JwtAuthenticationToken(jwt);
    }

    @Test
    void reportsStatusInSnakeCase() throws Exception {
        when(costApi.teamSummary("payments", "2026-09")).thenReturn(new TeamCostSummary(
                "payments", "2026-09", "USD", new BigDecimal("6079.20"), new BigDecimal("6323.70"), List.of()));
        mvc.perform(get("/v1/budgets/payments/status").param("month", "2026-09").principal(user("viewer", "payments")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.state").value("over_budget"))
                .andExpect(jsonPath("$.percent_used").value(101.3));
    }

    @Test
    void otherTeamsAreForbiddenBeforeAnyUpstreamCall() throws Exception {
        mvc.perform(get("/v1/budgets/search/status").param("month", "2026-09").principal(user("viewer", "payments")))
                .andExpect(status().isForbidden())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.type").value("https://example.com/problems/forbidden"));
        verifyNoInteractions(costApi);
    }

    @Test
    void missingBudgetIsAProblem() throws Exception {
        mvc.perform(get("/v1/budgets/payments/status").param("month", "2026-08").principal(user("finops_admin")))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.type").value("https://example.com/problems/budget-not-found"));
    }

    @Test
    void upstreamServerErrorsBecome502() throws Exception {
        ProblemDetail upstream = ProblemDetail.forStatus(HttpStatus.INTERNAL_SERVER_ERROR);
        upstream.setType(URI.create("https://example.com/problems/internal-error"));
        when(costApi.teamSummary(anyString(), anyString())).thenThrow(new CostApiException(upstream));
        mvc.perform(get("/v1/budgets/payments/status").param("month", "2026-09").principal(user("finops_admin")))
                .andExpect(status().isBadGateway())
                .andExpect(jsonPath("$.upstream_type").value("https://example.com/problems/internal-error"));
    }
}
