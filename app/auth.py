import os
from fastapi.security import APIKeyHeader
from fastapi import HTTPException, Security, status


AUTH_KEY = os.getenv("AUTH_KEY", "dev-secret-key-12345")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    """
    Dependency function to verify API key authentication.

    Internal Working:
    1. FastAPI extracts the X-API-Key header value
    2. Passes it to this function as the api_key parameter
    3. We compare it against the expected AUTH_KEY
    4. If invalid, raise HTTPException (stops request processing)
    5. If valid, function returns (endpoint handler proceeds)

    Usage in endpoints:
    @app.post("/books", dependencies=[Depends(verify_api_key)])

    Args:
        api_key: The API key from the request header (injected by FastAPI)

    Raises:
        HTTPException: 401 if key is missing, 403 if key is invalid

    Returns:
        True if authentication succeeds
    """
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key is missing. Include it in the 'X-API-Key' header.",
        )

    if api_key != AUTH_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key. Access denied.",
        )

    return True
