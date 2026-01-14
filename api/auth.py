"""
API Key авторизация для cvgorod-hub.
"""


from fastapi import Header, HTTPException, status

from config import settings


async def verify_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None, alias="Authorization"),
) -> str:
    """
    Проверка API ключа в заголовке.

    Поддерживает два формата:
    - X-API-Key: <key>
    - Authorization: Bearer <key>
    """
    api_key = x_api_key

    # Пробуем Authorization заголовок
    if not api_key and authorization and authorization.startswith("Bearer "):
        api_key = authorization[7:]

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Use X-API-Key header or Authorization: Bearer <key>",
        )

    if api_key != settings.HUB_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return api_key
