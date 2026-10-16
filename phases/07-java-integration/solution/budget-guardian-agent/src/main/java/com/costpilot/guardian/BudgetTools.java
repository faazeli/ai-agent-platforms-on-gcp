package com.costpilot.guardian;

import com.google.adk.tools.Annotations.Schema;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Map;

/**
 * Tools are plain static methods. ADK builds the function schema from the method
 * signature and the @Schema descriptions: the Java twin of a Python docstring.
 */
public final class BudgetTools {

    private static final HttpClient HTTP = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
    private static final String LEDGER = System.getenv().getOrDefault("LEDGER_URL", "http://localhost:8080");

    private BudgetTools() {
    }

    @Schema(description = "Check whether a team is on track against its monthly budget. Returns the budget, "
            + "spend to date, month-end forecast and a state: on_track, at_risk or over_budget.")
    public static Map<String, Object> getBudgetStatus(
            @Schema(name = "team_id", description = "Team id, e.g. payments") String teamId,
            @Schema(name = "month", description = "Calendar month as YYYY-MM") String month) {
        if (!teamId.matches("[a-z0-9-]{2,40}") || !month.matches("\\d{4}-(0[1-9]|1[0-2])")) {
            return Map.of("error", "invalid arguments: team_id must be a team id and month YYYY-MM");
        }
        HttpRequest request = HttpRequest.newBuilder(URI.create(LEDGER + "/v1/budgets/" + teamId + "/status?month=" + month))
                .header("Authorization", "Bearer " + System.getenv().getOrDefault("LEDGER_TOKEN", ""))
                .timeout(Duration.ofSeconds(10))
                .GET().build();
        try {
            HttpResponse<String> response = HTTP.send(request, HttpResponse.BodyHandlers.ofString());
            // Success or Problem Details, the body is JSON the model can read; the status tells it which.
            return Map.of("http_status", response.statusCode(), "body", response.body());
        } catch (IOException e) {
            return Map.of("error", "ledger-java unreachable: " + e.getClass().getSimpleName());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return Map.of("error", "interrupted");
        }
    }
}
