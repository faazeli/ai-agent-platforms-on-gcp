package com.costpilot.ledger.web;

import com.costpilot.ledger.budget.BudgetNotFoundException;
import com.costpilot.ledger.client.CostApiException;
import com.costpilot.ledger.security.TeamAccess;
import java.net.URI;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler;

/**
 * Every error leaves this service as RFC 9457 Problem Details, with the same
 * type URIs as the Python services. Extending ResponseEntityExceptionHandler makes
 * Spring's own errors (validation, 404, 405) Problem Details too.
 */
@RestControllerAdvice
public class ApiErrors extends ResponseEntityExceptionHandler {

    static final String BASE = "https://example.com/problems/";

    static ProblemDetail problem(HttpStatus status, String slug, String title, String detail) {
        ProblemDetail pd = ProblemDetail.forStatusAndDetail(status, detail);
        pd.setType(URI.create(BASE + slug));
        pd.setTitle(title);
        return pd;
    }

    @ExceptionHandler(BudgetNotFoundException.class)
    ProblemDetail budgetNotFound(BudgetNotFoundException ex) {
        return problem(HttpStatus.NOT_FOUND, "budget-not-found", "No budget", ex.getMessage());
    }

    @ExceptionHandler(TeamAccess.ForbiddenException.class)
    ProblemDetail forbidden(TeamAccess.ForbiddenException ex) {
        return problem(HttpStatus.FORBIDDEN, "forbidden", "Not allowed", ex.getMessage());
    }

    /**
     * Upstream client errors (404 team-not-found, 403 forbidden) pass through with
     * their own type, because they describe the caller's request. Upstream server
     * errors become our 502: the caller did nothing wrong, a dependency failed.
     */
    @ExceptionHandler(CostApiException.class)
    ProblemDetail upstream(CostApiException ex) {
        // TODO Lab 7.2: upstream 4xx -> same status, type, title and detail (the caller's request
        //   was wrong); upstream 5xx -> 502 "upstream-error" with property upstream_type.
        throw new UnsupportedOperationException("TODO Lab 7.2");
    }
}
