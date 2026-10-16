package com.costpilot.ledger.client;

import java.io.IOException;
import org.springframework.http.ProblemDetail;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClient.RequestHeadersSpec.ConvertibleClientHttpResponse;

/**
 * Typed client for the Python cost-api.
 *
 * Errors come back as Problem Details (Phase 1). Instead of a generic
 * "HTTP 404", callers get a CostApiException carrying the upstream problem, so
 * they can branch on its type ("team-not-found") exactly like Python clients do.
 */
@Component
public class CostApiClient {

    private final RestClient rest;

    public CostApiClient(RestClient costApiRestClient) {
        this.rest = costApiRestClient;
    }

    public TeamCostSummary teamSummary(String teamId, String month) {
        return rest.get()
                .uri("/v1/teams/{teamId}/summary?month={month}", teamId, month)
                .exchange((request, response) -> {
                    if (response.getStatusCode().isError()) {
                        throw toException(response);
                    }
                    return response.bodyTo(TeamCostSummary.class);
                });
    }

    static CostApiException toException(ConvertibleClientHttpResponse response) throws IOException {
        ProblemDetail problem = null;
        try {
            problem = response.bodyTo(ProblemDetail.class);
        } catch (RuntimeException notJson) {
            // fall through: upstream sent something that isn't a problem document
        }
        if (problem == null) {
            problem = ProblemDetail.forStatus(statusOf(response));
            problem.setTitle("Unexpected upstream response");
            problem.setDetail("cost-api returned a non-problem error body.");
        }
        return new CostApiException(problem);
    }

    private static int statusOf(ClientHttpResponse response) throws IOException {
        return response.getStatusCode().value();
    }
}
