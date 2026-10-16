package com.costpilot.ledger.client;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import com.fasterxml.jackson.annotation.JsonProperty;
import org.junit.jupiter.api.Test;
import org.springframework.boot.json.JsonParserFactory;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

/**
 * Contract test against a response captured from the REAL Python cost-api
 * (scripts/export_contract_fixtures.py writes src/test/resources/contract/).
 * If either side renames or adds a field, this test fails, before production does.
 */
class CostApiContractTest {

    @Test
    void javaRecordCoversExactlyThePythonFields() throws IOException {
        String json = new ClassPathResource("contract/team_summary.json").getContentAsString(StandardCharsets.UTF_8);
        Set<String> pythonFields = JsonParserFactory.getJsonParser().parseMap(json).keySet();
        Set<String> javaFields = Arrays.stream(TeamCostSummary.class.getRecordComponents())
                .map(c -> c.getAccessor().getAnnotation(JsonProperty.class) != null
                        ? c.getAccessor().getAnnotation(JsonProperty.class).value()
                        : c.getName())
                .collect(Collectors.toSet());
        assertThat(javaFields).isEqualTo(pythonFields);
    }

    @Test
    void capturedResponseDeserializes() throws IOException {
        String json = new ClassPathResource("contract/team_summary.json").getContentAsString(StandardCharsets.UTF_8);
        Map<String, Object> raw = JsonParserFactory.getJsonParser().parseMap(json);
        RestClient.Builder builder = RestClient.builder().baseUrl("http://cost-api");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        server.expect(requestTo("http://cost-api/v1/teams/payments/summary?month=2026-09"))
                .andRespond(withSuccess(json, MediaType.APPLICATION_JSON));
        TeamCostSummary summary = new CostApiClient(builder.build()).teamSummary("payments", "2026-09");
        assertThat(summary.teamId()).isEqualTo(raw.get("team_id"));
        assertThat(summary.totalEffectiveCost()).isEqualByComparingTo(raw.get("total_effective_cost").toString());
    }
}
