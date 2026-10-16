package com.costpilot.ledger.client;

import org.springframework.http.ProblemDetail;

/** cost-api answered with an RFC 9457 problem. We keep the whole document, not just a message. */
public class CostApiException extends RuntimeException {

    private final ProblemDetail problem;

    public CostApiException(ProblemDetail problem) {
        super(problem.getTitle() + ": " + problem.getDetail());
        this.problem = problem;
    }

    public ProblemDetail problem() {
        return problem;
    }

    /** The last path segment of the problem type, e.g. "team-not-found". */
    public String slug() {
        String type = problem.getType() == null ? "" : problem.getType().toString();
        return type.substring(type.lastIndexOf('/') + 1);
    }
}
