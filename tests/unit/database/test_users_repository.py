import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.database.users_repository import UsersRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_mock_collection():
    """Return a fresh AsyncMock collection with default async methods."""
    col = MagicMock()
    col.create_index = AsyncMock()
    col.find_one = AsyncMock()
    col.insert_one = AsyncMock()
    col.update_one = AsyncMock()
    return col


# ---------------------------------------------------------------------------
# hash_password
# ---------------------------------------------------------------------------
class TestHashPassword:
    def test_returns_different_hash_for_same_password(self):
        """Each call to hash_password should produce a unique salt and hash."""
        repo = UsersRepository()
        h1 = repo.hash_password("secret123")
        h2 = repo.hash_password("secret123")
        assert h1 != h2  # Different salts
        assert h1.startswith("$2b$")  # bcrypt prefix
        assert h2.startswith("$2b$")

    def test_hash_is_valid_bcrypt(self):
        """Hash should be a valid bcrypt string."""
        repo = UsersRepository()
        h = repo.hash_password("mypassword")
        assert isinstance(h, str)
        assert len(h) > 20


# ---------------------------------------------------------------------------
# verify_password
# ---------------------------------------------------------------------------
class TestVerifyPassword:
    @pytest.mark.asyncio
    async def test_correct_password_returns_true(self):
        repo = UsersRepository()
        hashed = repo.hash_password("correct")
        result = await repo.verify_password("correct", hashed)
        assert result is True

    @pytest.mark.asyncio
    async def test_wrong_password_returns_false(self):
        repo = UsersRepository()
        hashed = repo.hash_password("real_password")
        result = await repo.verify_password("wrong_password", hashed)
        assert result is False

    @pytest.mark.asyncio
    async def test_invalid_hash_returns_false(self):
        repo = UsersRepository()
        result = await repo.verify_password("anything", "not-a-valid-hash")
        assert result is False


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------
class TestCreateUser:
    @pytest.mark.asyncio
    async def test_creates_user_successfully(self):
        repo = UsersRepository()
        with patch("app.database.users_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"users": mock_col}
            mock_col.insert_one.return_value.inserted_id = "fake_object_id_123"

            user_id = await repo.create_user(
                email="test@example.com",
                password="secure123",
                name="Test User",
                role="admin"
            )

            assert user_id == "fake_object_id_123"
            mock_col.insert_one.assert_called_once()

            # Verify the document was created with correct fields
            call_args, _ = mock_col.insert_one.call_args
            doc = call_args[0]
            assert doc["email"] == "test@example.com"
            assert doc["name"] == "Test User"
            assert doc["role"] == "admin"
            assert "passwordHash" in doc
            assert doc["passwordHash"] != "secure123"  # Should be hashed
            assert "createdAt" in doc

    @pytest.mark.asyncio
    async def test_normalizes_email_to_lowercase(self):
        repo = UsersRepository()
        with patch("app.database.users_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"users": mock_col}
            mock_col.insert_one.return_value.inserted_id = "id_456"

            await repo.create_user(
                email="  Test@Example.COM  ",
                password="pass",
                name="User"
            )

            call_args, _ = mock_col.insert_one.call_args
            doc = call_args[0]
            assert doc["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_strips_name_whitespace(self):
        repo = UsersRepository()
        with patch("app.database.users_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"users": mock_col}
            mock_col.insert_one.return_value.inserted_id = "id_789"

            await repo.create_user(
                email="a@b.com",
                password="pass",
                name="   John Doe   "
            )

            call_args, _ = mock_col.insert_one.call_args
            doc = call_args[0]
            assert doc["name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_default_role_is_user(self):
        repo = UsersRepository()
        with patch("app.database.users_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"users": mock_col}
            mock_col.insert_one.return_value.inserted_id = "id_role"

            await repo.create_user(
                email="role@test.com",
                password="pass",
                name="Role Test"
            )

            call_args, _ = mock_col.insert_one.call_args
            doc = call_args[0]
            assert doc["role"] == "user"

    @pytest.mark.asyncio
    async def test_returns_none_on_duplicate_email(self):
        repo = UsersRepository()
        with patch("app.database.users_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"users": mock_col}
            # Simulate duplicate key error
            mock_col.insert_one.side_effect = Exception("E11000 duplicate key error")

            user_id = await repo.create_user(
                email="duplicate@test.com",
                password="pass",
                name="Dup"
            )

            assert user_id is None


# ---------------------------------------------------------------------------
# update_password
# ---------------------------------------------------------------------------
class TestUpdatePassword:
    @pytest.mark.asyncio
    async def test_updates_password_successfully(self):
        repo = UsersRepository()
        with patch("app.database.users_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"users": mock_col}
            mock_col.update_one.return_value.modified_count = 1

            result = await repo.update_password(
                user_id="507f1f77bcf86cd799439011",
                new_password="new_secure_password"
            )

            assert result is True
            mock_col.update_one.assert_called_once()
            call_args, _ = mock_col.update_one.call_args
            query, update = call_args
            assert "passwordHash" in update["$set"]
            assert update["$set"]["passwordHash"] != "new_secure_password"
            assert "updatedAt" in update["$set"]

    @pytest.mark.asyncio
    async def test_returns_false_when_user_not_found(self):
        repo = UsersRepository()
        with patch("app.database.users_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"users": mock_col}
            mock_col.update_one.return_value.modified_count = 0

            result = await repo.update_password(
                user_id="507f1f77bcf86cd799439011",
                new_password="newpass"
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_invalid_objectid(self):
        repo = UsersRepository()
        result = await repo.update_password(
            user_id="not-a-valid-objectid",
            new_password="pass"
        )
        assert result is False


# ---------------------------------------------------------------------------
# get_user_by_email
# ---------------------------------------------------------------------------
class TestGetUserByEmail:
    @pytest.mark.asyncio
    async def test_returns_user_when_found(self):
        repo = UsersRepository()
        expected = {"_id": "obj1", "email": "found@test.com", "name": "Found"}

        with patch("app.database.users_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"users": mock_col}
            mock_col.find_one.return_value = expected

            result = await repo.get_user_by_email("found@test.com")
            assert result == expected

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        repo = UsersRepository()
        with patch("app.database.users_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"users": mock_col}
            mock_col.find_one.return_value = None

            result = await repo.get_user_by_email("missing@test.com")
            assert result is None


# ---------------------------------------------------------------------------
# get_user_by_id
# ---------------------------------------------------------------------------
class TestGetUserById:
    @pytest.mark.asyncio
    async def test_returns_user_when_found(self):
        repo = UsersRepository()
        expected = {"_id": "obj123", "email": "iduser@test.com", "name": "ID User"}

        with patch("app.database.users_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"users": mock_col}
            mock_col.find_one.return_value = expected

            result = await repo.get_user_by_id("507f1f77bcf86cd799439011")
            assert result == expected

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        repo = UsersRepository()
        with patch("app.database.users_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"users": mock_col}
            mock_col.find_one.return_value = None

            result = await repo.get_user_by_id("507f1f77bcf86cd799439011")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_invalid_objectid(self):
        repo = UsersRepository()
        result = await repo.get_user_by_id("not-valid")
        assert result is None


# ---------------------------------------------------------------------------
# ensure_indexes
# ---------------------------------------------------------------------------
class TestEnsureIndexes:
    @pytest.mark.asyncio
    async def test_creates_index_only_once(self):
        repo = UsersRepository()
        with patch("app.database.users_repository.get_database") as mock_get_db:
            mock_col = _make_mock_collection()
            mock_get_db.return_value = {"users": mock_col}

            await repo.ensure_indexes()
            await repo.ensure_indexes()

            # Should only call create_index once (idempotent via _indexes_ready flag)
            assert mock_col.create_index.call_count == 1