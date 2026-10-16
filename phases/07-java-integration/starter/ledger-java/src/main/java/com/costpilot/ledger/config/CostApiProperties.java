package com.costpilot.ledger.config;

import java.net.URI;
import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

/** Typed configuration: the Java twin of pydantic-settings. Bound from costpilot.cost-api.* */
@ConfigurationProperties("costpilot.cost-api")
public record CostApiProperties(URI baseUrl, String audience, boolean workloadAuth, Duration timeout) {
}
