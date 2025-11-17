from httpx import AsyncClient
from starlette import status


async def test_health_check_returns_ok(test_client: AsyncClient):
    """Проверяет, что эндпоинт /healthcheck возвращает 200 OK и сообщает о доступности базы данных."""

    # Arrange
    url = "/healthcheck"

    # Act
    response = await test_client.get(url)

    # Assert
    assert response.status_code == status.HTTP_200_OK

    response_json = response.json()
    assert response_json["api_status"] == "ok"
    assert response_json["dependencies"]["database"] == "ok"
