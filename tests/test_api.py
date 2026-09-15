from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_fastapi_docs_available():
    """Ensure the FastAPI Swagger UI and OpenAPI schemas are generating correctly."""
    response = client.get("/docs")
    assert response.status_code == 200, "FastAPI Swagger docs are not accessible"