BUILTIN_AUTH_DECORATORS = frozenset({
    "login_required", "fresh_login_required",
    "jwt_required", "jwt_optional",
    "auth_required", "auth_token_required", "roles_required", "roles_accepted",
    "permissions_required", "permissions_accepted",
    "oidc_auth", "require_login",
    "permission_required",
    "require_auth", "requires_auth", "authenticated", "requires_login",
    "login_required_api",
})

AUTH_FUNCTION_NAME_PATTERNS = frozenset({
    "auth", "permission", "authenticate", "authorize", "check_login",
    "require_auth", "verify_token", "validate_session",
})
