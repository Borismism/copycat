"""Tests for main API endpoints."""

import os

import pytest
from fastapi.testclient import TestClient

# Set required environment variables before importing app
os.environ["GCP_PROJECT_ID"] = "test-project"
os.environ["GCP_REGION"] = "europe-west4"
os.environ["ENVIRONMENT"] = "test"

from app.main import app

client = TestClient(app)


def test_root():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "api-service"
    assert data["status"] == "healthy"


def test_health():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "api-service"
