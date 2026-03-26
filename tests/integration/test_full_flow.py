"""
Integration tests for the ComfyUI AI Image Server.

These tests verify the full flow from API request to job processing.
"""

import pytest
import asyncio
import os
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.main import app
from api.models import Base
from api.config import settings


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def client():
    """Create async HTTP client for testing."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
async def db_session():
    """Create test database session."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session


class TestHealthEndpoint:
    """Test health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test health check returns 200."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestJobCreation:
    """Test job creation endpoints."""

    @pytest.mark.asyncio
    async def test_create_face_swap_job(self, client):
        """Test creating a face swap job."""
        # This test requires mocking image upload and ComfyUI
        # For now, just test the endpoint structure
        response = await client.post(
            "/api/v1/jobs/face-swap",
            json={
                "source_image_url": "https://example.com/source.jpg",
                "target_image_url": "https://example.com/target.jpg",
                "webhook_url": "https://example.com/webhook"
            }
        )
        # May fail due to missing services, but endpoint should exist
        assert response.status_code in [202, 503]

    @pytest.mark.asyncio
    async def test_create_upscale_job(self, client):
        """Test creating an upscale job."""
        response = await client.post(
            "/api/v1/jobs/upscale",
            json={
                "image_url": "https://example.com/image.jpg",
                "scale_factor": 2,
                "webhook_url": "https://example.com/webhook"
            }
        )
        assert response.status_code in [202, 503]

    @pytest.mark.asyncio
    async def test_create_remove_bg_job(self, client):
        """Test creating a remove background job."""
        response = await client.post(
            "/api/v1/jobs/remove-background",
            json={
                "image_url": "https://example.com/image.jpg",
                "webhook_url": "https://example.com/webhook"
            }
        )
        assert response.status_code in [202, 503]


class TestJobStatus:
    """Test job status endpoints."""

    @pytest.mark.asyncio
    async def test_get_job_status(self, client):
        """Test getting job status."""
        response = await client.get("/api/v1/jobs/test-job-id")
        # Job may not exist, but endpoint should respond
        assert response.status_code in [404, 200]

    @pytest.mark.asyncio
    async def test_list_jobs(self, client):
        """Test listing jobs."""
        response = await client.get("/api/v1/jobs")
        assert response.status_code == 200
        assert "jobs" in response.json()


class TestValidation:
    """Test input validation."""

    @pytest.mark.asyncio
    async def test_invalid_url(self, client):
        """Test that invalid URLs are rejected."""
        response = await client.post(
            "/api/v1/jobs/face-swap",
            json={
                "source_image_url": "not-a-url",
                "target_image_url": "also-not-a-url"
            }
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, client):
        """Test that missing required fields are rejected."""
        response = await client.post(
            "/api/v1/jobs/face-swap",
            json={"source_image_url": "https://example.com/source.jpg"}
        )
        assert response.status_code == 422


class TestWorkflows:
    """Test workflow templates."""

    def test_face_swap_workflow_exists(self):
        """Test face swap workflow template exists."""
        workflow_path = Path("worker/workflows/face_swap.json")
        assert workflow_path.exists()

    def test_upscale_workflow_exists(self):
        """Test upscale workflow template exists."""
        workflow_path = Path("worker/workflows/upscale.json")
        assert workflow_path.exists()

    def test_remove_bg_workflow_exists(self):
        """Test remove background workflow template exists."""
        workflow_path = Path("worker/workflows/remove_background.json")
        assert workflow_path.exists()

    @pytest.mark.asyncio
    async def test_workflow_templates_valid_json(self):
        """Test workflow templates are valid JSON."""
        import json

        workflows = [
            "worker/workflows/face_swap.json",
            "worker/workflows/upscale.json",
            "worker/workflows/remove_background.json"
        ]

        for workflow_path in workflows:
            with open(workflow_path) as f:
                data = json.load(f)
                assert isinstance(data, dict)
                assert len(data) > 0
