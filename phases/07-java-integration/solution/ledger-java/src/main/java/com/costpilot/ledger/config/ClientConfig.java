package com.costpilot.ledger.config;

import com.costpilot.ledger.client.GoogleIdTokenInterceptor;
import java.time.Clock;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

@Configuration(proxyBeanMethods = false)
public class ClientConfig {

    /** One RestClient for cost-api, with timeouts and (on GKE) our workload identity attached. */
    @Bean
    RestClient costApiRestClient(CostApiProperties props) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(props.timeout());
        factory.setReadTimeout(props.timeout());
        RestClient.Builder builder = RestClient.builder().baseUrl(props.baseUrl().toString()).requestFactory(factory);
        if (props.workloadAuth()) {
            builder.requestInterceptor(new GoogleIdTokenInterceptor(props.audience()));
        }
        return builder.build();
    }

    /** Injecting the clock makes "today" testable. */
    @Bean
    Clock clock() {
        return Clock.systemUTC();
    }
}
