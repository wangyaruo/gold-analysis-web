import os
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.core.config import load_config


bearer_scheme = HTTPBearer(auto_error=False)


def require_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> str:
    config = load_config()
    security_config = config.get("security", {})
    token_env = security_config.get("bearer_token_env", "API_AUTH_TOKEN")
    expected_token = os.getenv(token_env)

    if not expected_token and security_config.get("allow_insecure_dev_token", False):
        expected_token = security_config.get("development_token")

    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API authentication token is not configured",
        )
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    if credentials.credentials != expected_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid bearer token")
    return "authenticated"
