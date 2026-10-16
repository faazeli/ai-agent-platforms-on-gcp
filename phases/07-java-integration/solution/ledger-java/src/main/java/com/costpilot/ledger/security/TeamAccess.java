package com.costpilot.ledger.security;

import java.util.List;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

/** The Java twin of costpilot_security.rbac.check_team: same claims, same rule. */
public final class TeamAccess {

    private TeamAccess() {
    }

    public static void check(JwtAuthenticationToken authentication, String teamId) {
        if (authentication == null) {
            throw new ForbiddenException("Authentication required.");
        }
        Jwt jwt = authentication.getToken();
        if ("finops_admin".equals(jwt.getClaimAsString("role"))) {
            return;
        }
        List<String> teams = jwt.getClaimAsStringList("teams");
        if (teams == null || !teams.contains(teamId)) {
            throw new ForbiddenException("You are not a member of this team.");
        }
    }

    public static class ForbiddenException extends RuntimeException {
        public ForbiddenException(String message) {
            super(message);
        }
    }
}
