import pytest
from fastapi.testclient import TestClient
from app.main import app
import uuid

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_unauthorized_chat():
    response = client.post("/chat/query", json={"query": "Hello"})
    assert response.status_code == 401

def test_invalid_login():
    response = client.post("/auth/login", json={"email": "wrong@example.com", "password": "password"})
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_chat_validation():
    # Test with empty query
    response = client.post("/chat/query", json={"query": ""})
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_quiz_generation():
    # Test quiz generation validation
    response = client.post("/quiz/generate", json={
        "topic": "Python",
        "difficulty": "easy",
        "num_questions": 5
    })
    # Should be 401 as we are not logged in
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_health_detailed():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "database" in data
    assert "redis" in data
    assert "service" in data
