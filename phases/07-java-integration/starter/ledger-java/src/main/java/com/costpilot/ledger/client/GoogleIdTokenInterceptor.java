package com.costpilot.ledger.client;

import com.google.auth.oauth2.GoogleCredentials;
import com.google.auth.oauth2.IdTokenCredentials;
import com.google.auth.oauth2.IdTokenProvider;
import java.io.IOException;
import java.io.UncheckedIOException;
import org.springframework.http.HttpRequest;
import org.springframework.http.client.ClientHttpRequestExecution;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.ClientHttpResponse;

/**
 * Adds a Google-signed ID token for {@code audience} to every request.
 * On GKE, Application Default Credentials come from Workload Identity: no key file.
 * The credentials object caches the token and refreshes it before it expires.
 */
public class GoogleIdTokenInterceptor implements ClientHttpRequestInterceptor {

    private final IdTokenCredentials credentials;

    public GoogleIdTokenInterceptor(String audience) {
        try {
            GoogleCredentials source = GoogleCredentials.getApplicationDefault();
            if (!(source instanceof IdTokenProvider provider)) {
                throw new IllegalStateException("These credentials cannot mint ID tokens: " + source.getClass());
            }
            this.credentials = IdTokenCredentials.newBuilder()
                    .setIdTokenProvider(provider)
                    .setTargetAudience(audience)
                    .build();
        } catch (IOException e) {
            throw new UncheckedIOException("No Application Default Credentials", e);
        }
    }

    @Override
    public ClientHttpResponse intercept(HttpRequest request, byte[] body, ClientHttpRequestExecution execution)
            throws IOException {
        credentials.refreshIfExpired();
        request.getHeaders().setBearerAuth(credentials.getIdToken().getTokenValue());
        return execution.execute(request, body);
    }
}
