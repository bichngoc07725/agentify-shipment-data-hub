from fastapi import Header, HTTPException, status

from config.settings import auth_config


async def require_internal_api_key(
    x_internal_api_key: str | None = Header(
        default=None, alias=auth_config.API_KEY_NAME
    ),
) -> str:
    if x_internal_api_key != auth_config.API_KEY_VALUE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )
    return x_internal_api_key
