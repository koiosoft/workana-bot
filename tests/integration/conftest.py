import os
import pytest
import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient
from app.config.database import get_mongo_config

# Skip all integration tests if MONGODB_URI is not set, adhering to CONVENTIONS.md
pytestmark = pytest.mark.skipif(
    not os.getenv("MONGODB_URI"),
    reason="MONGODB_URI not set"
)

@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_db():
    """
    Establish a connection to a dedicated test MongoDB database instance.
    Ensures isolation from production data by using a '_test' suffixed database name.
    """
    uri, db_name = get_mongo_config()
    test_db_name = f"{db_name}_test" if not db_name.endswith("_test") else db_name
    
    client = AsyncIOMotorClient(uri)
    db = client[test_db_name]
    
    yield db
    
    client.close()

@pytest.fixture(scope="session")
async def seed_test_data(test_db):
    """
    Seed the test database with required initial data strictly for API integration tests,
    as defined in PYTHON-MIGRATION-NEXTJS-API-INTEGRATION-TEST.md:
    - A test user in the 'users' collection with email "admin@example.com" and hashed password "SecurePassword123!".
    - A test project in the 'projects' collection with a specific title and proposal_status.
    Returns the generated project identifier for subsequent API endpoint test steps.
    Cleans up the data after the test session to guarantee database cleanliness.
    """
    # Hash the password securely as required by the API contract
    password_bytes = "SecurePassword123!".encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

    # Insert test user
    await test_db.users.insert_one({
        "email": "admin@example.com",
        "password": hashed_password
    })
    
    # Insert test project
    project_data = {
        "title": "Test Project Title",
        "proposal_status": "pending"
    }
    project_result = await test_db.projects.insert_one(project_data)
    project_id = str(project_result.inserted_id)
    
    yield {
        "project_id": project_id
    }
    
    # Teardown: Clean up the test data after the session
    await test_db.users.delete_one({"email": "admin@example.com"})
    await test_db.projects.delete_one({"_id": project_result.inserted_id})
