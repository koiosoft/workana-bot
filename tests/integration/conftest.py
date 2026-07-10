import os
import pytest
import pytest_asyncio
import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient
from app.config.database import get_mongo_config

# database.py loads .env + .env.local at import time, which may
# clobber values set by pytest-dotenv from .env.test.
# Re-apply .env.test with override=True so it always wins for tests.
from dotenv import load_dotenv
load_dotenv(".env.test", override=True)

# Skip all integration tests if MONGO_URI is not set, adhering to CONVENTIONS.md
pytestmark = pytest.mark.skipif(
    not os.getenv("MONGO_URI"),
    reason="MONGO_URI not set"
)

@pytest_asyncio.fixture(scope="function")
async def test_db():
    """
    Establish a connection to a dedicated test MongoDB database instance.
    Ensures isolation from production data by using a '_test' suffixed database name.
    Also patches the application's database connection to point to the test database.
    """
    import app.database.mongo as app_mongo
    
    uri, db_name = get_mongo_config()
    test_db_name = f"{db_name}_test" if not db_name.endswith("_test") else db_name
    
    client = AsyncIOMotorClient(uri)
    db = client[test_db_name]
    
    # Override the app's database to use the test database
    app_mongo._db = db
    
    yield db
    
    # Restore app database to None so next connection is re-established
    app_mongo._db = None
    client.close()

@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup_test_database(test_db):
    """
    Automated database cleanup fixture with per-function lifecycle and automatic usage.
    Clears all collections within the test database immediately before each test 
    function begins execution, guaranteeing a pristine database state and eliminating 
    cross-test contamination.
    
    Depends on test_db to ensure only one client is created and closed per test,
    preventing event loop closure conflicts (RuntimeError: Event loop is closed).
    """
    # Clear all collections in the test database before the test starts
    collection_names = await test_db.list_collection_names()
    for collection_name in collection_names:
        await test_db[collection_name].delete_many({})
        
    yield

@pytest_asyncio.fixture(scope="function")
async def seed_test_data(test_db):
    """
    Seed the test database with required initial data for integration tests.
    - A test user in the 'users' collection with email "admin@example.com" and hashed password "SecurePassword123!".
    - A test project in the 'projects' collection with a specific title and proposal_status.
    Returns the generated project identifier for subsequent test steps.
    Cleans up the data after the test to guarantee database cleanliness.
    """
    # Hash the password securely as required by the API contract
    password_bytes = "SecurePassword123!".encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

    # Insert test user
    await test_db.users.insert_one({
        "email": "admin@example.com",
        "passwordHash": hashed_password,
        "name": "Test Admin",
        "role": "admin",
    })
    
    # Insert test project
    project_data = {
        "title": "Test Project Title",
        "proposal_status": "proposal_generated",
        "ai_score": 8
    }
    project_result = await test_db.projects.insert_one(project_data)
    project_id = str(project_result.inserted_id)
    
    yield {
        "project_id": project_id
    }
    
    # Teardown: Clean up the test data after the session
    await test_db.users.delete_one({"email": "admin@example.com"})
    await test_db.projects.delete_one({"_id": project_result.inserted_id})
