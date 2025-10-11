"""
Integration tests for complete memory flow: connect → ensure_profile → save → load
"""

import pytest
import uuid
from unittest.mock import MagicMock, Mock, AsyncMock, patch
from services.memory_service import MemoryService
from services.user_service import UserService
from core.validators import set_current_user_id, set_supabase_client
from core.user_id import UserId


class TestMemoryFlowIntegration:
    """
    Integration tests for the complete memory flow.
    Tests the scenario: connect → ensure profile → save memory → load memories
    """
    
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
    def setup_session(self, mock_supabase, valid_user_id):
        """Setup a mock session with user_id and supabase client"""
        set_supabase_client(mock_supabase)
        set_current_user_id(valid_user_id)
        return valid_user_id
    
    def test_complete_flow_profile_exists(self, mock_supabase, valid_user_id, setup_session):
        """
        Test complete flow when profile already exists:
        1. Check/create profile
        2. Save memory
        3. Load memories
        """
        # Step 1: Mock profile exists
        mock_profile_response = Mock()
        mock_profile_response.data = [{"id": valid_user_id}]
        
        # Step 2: Mock memory save success
        mock_save_response = Mock()
        mock_save_response.data = [{"user_id": valid_user_id, "category": "FACT", "key": "test_key", "value": "test_value"}]
        mock_save_response.error = None
        
        # Step 3: Mock memory load success
        mock_load_response = Mock()
        mock_load_response.data = [
            {"user_id": valid_user_id, "category": "FACT", "key": "test_key", "value": "test_value"}
        ]
        
        # Setup mock to return appropriate responses
        def table_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "profiles":
                mock_table.select.return_value.eq.return_value.execute.return_value = mock_profile_response
                mock_table.insert.return_value.execute.return_value = mock_profile_response
            elif table_name == "memory":
                mock_table.upsert.return_value.execute.return_value = mock_save_response
                mock_table.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_load_response
            return mock_table
        
        mock_supabase.table.side_effect = table_side_effect
        
        # Execute flow
        user_service = UserService(mock_supabase)
        memory_service = MemoryService(mock_supabase)
        
        # 1. Ensure profile exists
        profile_exists = user_service.ensure_profile_exists(valid_user_id)
        assert profile_exists is True
        
        # 2. Save memory
        save_success = memory_service.save_memory("FACT", "test_key", "test_value", valid_user_id)
        assert save_success is True
        
        # 3. Load memory
        loaded_value = memory_service.get_memory("FACT", "test_key", valid_user_id)
        assert loaded_value == "test_value"
    
    def test_complete_flow_profile_created(self, mock_supabase, valid_user_id, setup_session):
        """
        Test complete flow when profile needs to be created:
        1. Profile doesn't exist, create it
        2. Save memory
        3. Verify no FK errors
        """
        # Step 1: Mock profile doesn't exist initially
        mock_not_exists_response = Mock()
        mock_not_exists_response.data = []
        
        # Mock profile creation
        mock_create_response = Mock()
        mock_create_response.data = [{"id": valid_user_id, "email": f"user_{valid_user_id[:8]}@companion.local"}]
        mock_create_response.error = None
        
        # Mock profile exists after creation
        mock_exists_response = Mock()
        mock_exists_response.data = [{"id": valid_user_id}]
        
        # Step 2: Mock memory save success
        mock_save_response = Mock()
        mock_save_response.data = [{"user_id": valid_user_id, "category": "FACT", "key": "favorite_food", "value": "biryani"}]
        mock_save_response.error = None
        
        call_count = {"profile_check": 0}
        
        def table_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "profiles":
                # First call: check if exists (returns not exists)
                # Second call: check again (returns exists)
                def select_side_effect():
                    mock_select = MagicMock()
                    if call_count["profile_check"] == 0:
                        call_count["profile_check"] += 1
                        mock_select.eq.return_value.execute.return_value = mock_not_exists_response
                    else:
                        mock_select.eq.return_value.execute.return_value = mock_exists_response
                    return mock_select
                
                mock_table.select.side_effect = select_side_effect
                mock_table.insert.return_value.execute.return_value = mock_create_response
            elif table_name == "memory":
                mock_table.upsert.return_value.execute.return_value = mock_save_response
            return mock_table
        
        mock_supabase.table.side_effect = table_side_effect
        
        # Execute flow
        user_service = UserService(mock_supabase)
        memory_service = MemoryService(mock_supabase)
        
        # 1. Ensure profile exists (should create it)
        profile_exists = user_service.ensure_profile_exists(valid_user_id)
        assert profile_exists is True
        
        # 2. Save memory (should succeed without FK errors)
        save_success = memory_service.save_memory("FACT", "favorite_food", "biryani", valid_user_id)
        assert save_success is True
    
    def test_flow_rejects_prefix_user_id(self, mock_supabase):
        """
        Test that flow rejects 8-char prefix at every step
        """
        prefix = "bb4a6f7c"
        
        # Should fail to set as current user
        with pytest.raises(Exception):  # UserIdError
            set_current_user_id(prefix)
    
    def test_memory_service_ensures_profile_before_save(self, mock_supabase, valid_user_id):
        """
        Test that MemoryService calls ensure_profile_exists before saving
        """
        # Mock profile check to fail
        mock_profile_response = Mock()
        mock_profile_response.data = []
        
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_profile_response
        mock_supabase.table.return_value.insert.return_value.execute.return_value.error = "Failed to create"
        
        # Setup session
        set_supabase_client(mock_supabase)
        set_current_user_id(valid_user_id)
        
        memory_service = MemoryService(mock_supabase)
        
        # This should fail because profile creation fails
        result = memory_service.save_memory("FACT", "test_key", "test_value", valid_user_id)
        
        # Should return False because ensure_profile_exists failed
        # (depending on implementation, it might fail at profile check)
        assert result is False


class TestRAGIntegration:
    """Test RAG system with full UUID"""
    
    @pytest.fixture
    def valid_user_id(self):
        """Generate a valid UUID v4 for testing"""
        return str(uuid.uuid4())
    
    def test_rag_rejects_prefix_user_id(self):
        """Test that RAG system rejects 8-char prefix"""
        from rag_system import get_or_create_rag
        
        prefix = "bb4a6f7c"
        
        with pytest.raises(Exception):  # UserIdError
            get_or_create_rag(prefix, "test_api_key")
    
    def test_rag_accepts_full_uuid(self, valid_user_id):
        """Test that RAG system accepts full UUID"""
        from rag_system import get_or_create_rag
        
        # Should not raise
        rag = get_or_create_rag(valid_user_id, "test_api_key")
        assert rag is not None
        assert rag.user_id == valid_user_id

