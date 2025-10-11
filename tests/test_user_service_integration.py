"""
Integration tests for user service with full UUID handling
"""

import pytest
import uuid
from unittest.mock import MagicMock, Mock
from services.user_service import UserService
from core.user_id import UserId, UserIdError


class TestUserServiceIntegration:
    """Integration tests for UserService UUID handling"""
    
    @pytest.fixture
    def mock_supabase(self):
        """Create a mock Supabase client"""
        mock = MagicMock()
        return mock
    
    @pytest.fixture
    def valid_user_id(self):
        """Generate a valid UUID v4 for testing"""
        return str(uuid.uuid4())
    
    @pytest.fixture
    def user_service(self, mock_supabase):
        """Create UserService instance with mock Supabase"""
        return UserService(mock_supabase)
    
    def test_ensure_profile_exists_with_valid_uuid(self, user_service, mock_supabase, valid_user_id):
        """Test that ensure_profile_exists works with full UUID"""
        # Mock profile doesn't exist
        mock_response = Mock()
        mock_response.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        
        # Mock successful insert
        mock_insert_response = Mock()
        mock_insert_response.data = [{"id": valid_user_id, "email": "test@test.com"}]
        mock_insert_response.error = None
        mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_insert_response
        
        result = user_service.ensure_profile_exists(valid_user_id)
        
        assert result is True
        # Verify it queried by 'id' column
        mock_supabase.table.assert_called_with("profiles")
    
    def test_ensure_profile_exists_with_prefix_fails(self, user_service):
        """Test that ensure_profile_exists rejects 8-char prefix"""
        prefix = "bb4a6f7c"
        
        result = user_service.ensure_profile_exists(prefix)
        
        # Should fail validation and return False
        assert result is False
    
    def test_profile_exists_with_valid_uuid(self, user_service, mock_supabase, valid_user_id):
        """Test that profile_exists works with full UUID"""
        # Mock profile exists
        mock_response = Mock()
        mock_response.data = [{"id": valid_user_id}]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        
        result = user_service.profile_exists(valid_user_id)
        
        assert result is True
    
    def test_profile_exists_with_prefix_fails(self, user_service):
        """Test that profile_exists rejects 8-char prefix"""
        prefix = "bb4a6f7c"
        
        result = user_service.profile_exists(prefix)
        
        # Should fail validation and return False
        assert result is False
    
    def test_get_user_info_with_valid_uuid(self, user_service, mock_supabase, valid_user_id):
        """Test that get_user_info works with full UUID"""
        # Mock user data
        mock_response = Mock()
        mock_response.data = [{"id": valid_user_id, "email": "test@test.com"}]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        
        result = user_service.get_user_info(valid_user_id)
        
        assert result is not None
        assert result["id"] == valid_user_id
    
    def test_get_user_info_with_prefix_fails(self, user_service):
        """Test that get_user_info rejects 8-char prefix"""
        prefix = "bb4a6f7c"
        
        result = user_service.get_user_info(prefix)
        
        # Should fail validation and return None
        assert result is None
    
    def test_update_user_profile_with_valid_uuid(self, user_service, mock_supabase, valid_user_id):
        """Test that update_user_profile works with full UUID"""
        # Mock successful update
        mock_response = Mock()
        mock_response.error = None
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_response
        
        updates = {"email": "newemail@test.com"}
        result = user_service.update_user_profile(valid_user_id, updates)
        
        assert result is True
    
    def test_update_user_profile_with_prefix_fails(self, user_service):
        """Test that update_user_profile rejects 8-char prefix"""
        prefix = "bb4a6f7c"
        updates = {"email": "newemail@test.com"}
        
        result = user_service.update_user_profile(prefix, updates)
        
        # Should fail validation and return False
        assert result is False

