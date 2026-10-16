package com.costpilot.ledger.security;

import java.util.List; // you will need these
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

/** The Java twin of costpilot_security.rbac.check_team: same claims, same rule. */
public final class TeamAccess {

    private TeamAccess() {
    }

    public static void check(JwtAuthenticationToken authentication, String teamId) {
        // TODO Lab 7.4: the same rule as Phase 6's check_team. Read the JWT's "role" and
        //   "teams" claims; finops_admin sees all teams; anyone else needs the team in "teams".
        //   Throw ForbiddenException otherwise (and when authentication is null).
        throw new UnsupportedOperationException("TODO Lab 7.4");
    }

    public static class ForbiddenException extends RuntimeException {
        public ForbiddenException(String message) {
            super(message);
        }
    }
}
