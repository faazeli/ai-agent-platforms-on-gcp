package com.costpilot.ledger.client;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class CostApiClientTest {

    private MockRestServiceServer server;
    private CostApiClient client;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://cost-api");
        server = MockRestServiceServer.bindTo(builder).build();
        client = new CostApiClient(builder.build());
    }

    @Test
    void parsesSnakeCaseSummaryIntoARecord() {
        server.expect(requestTo("http://cost-api/v1/teams/payments/summary?month=2026-09"))
                .andRespond(withSuccess("""
                        {"team_id": "payments", "month": "2026-09", "currency": "USD",
                         "total_effective_cost": "6079.2000", "total_billed_cost": "6323.7000",
                         "top_services": [{"service_name": "Compute Engine", "effective_cost": "2400.0000"}]}
                        """, MediaType.APPLICATION_JSON));
        TeamCostSummary summary = client.teamSummary("payments", "2026-09");
        assertThat(summary.totalEffectiveCost()).isEqualByComparingTo("6079.20");
        assertThat(summary.topServices().getFirst().serviceName()).isEqualTo("Compute Engine");
    }

    @Test
    void pythonProblemDetailsBecomeTypedExceptions() {
        server.expect(requestTo("http://cost-api/v1/teams/marketing/summary?month=2026-09"))
                .andRespond(withStatus(HttpStatus.NOT_FOUND).contentType(MediaType.APPLICATION_PROBLEM_JSON).body("""
                        {"type": "https://example.com/problems/team-not-found", "title": "Unknown team",
                         "status": 404, "detail": "No cost data exists for team 'marketing'.",
                         "instance": "/v1/teams/marketing/summary"}
                        """));
        assertThatThrownBy(() -> client.teamSummary("marketing", "2026-09"))
                .isInstanceOfSatisfying(CostApiException.class, ex -> {
                    assertThat(ex.slug()).isEqualTo("team-not-found");
                    assertThat(ex.problem().getStatus()).isEqualTo(404);
                });
    }

    @Test
    void nonProblemErrorsStillBecomeProblems() {
        server.expect(requestTo("http://cost-api/v1/teams/payments/summary?month=2026-09"))
                .andRespond(withStatus(HttpStatus.BAD_GATEWAY).contentType(MediaType.TEXT_HTML).body("<h1>oops</h1>"));
        assertThatThrownBy(() -> client.teamSummary("payments", "2026-09"))
                .isInstanceOfSatisfying(CostApiException.class,
                        ex -> assertThat(ex.problem().getStatus()).isEqualTo(502));
    }
}
