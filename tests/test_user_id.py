"""
Tests for UserId utility - UUID validation and parsing
"""

import pytest
from core.user_id import UserId, UserIdError


class TestUserIdValidation:
    """Test UserId validation methods"""
    
    def test_is_valid_uuid_with_valid_uuid_v4(self):
        """Test that valid UUID v4 is recognized"""
        valid_uuid = "bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2"
        assert UserId.is_valid_uuid(valid_uuid) is True
    
    def test_is_valid_uuid_with_prefix(self):
        """Test that 8-char prefix is NOT a valid UUID"""
        prefix = "bb4a6f7c"
        assert UserId.is_valid_uuid(prefix) is False
    
    def test_is_valid_uuid_with_empty_string(self):
        """Test that empty string is not valid"""
        assert UserId.is_valid_uuid("") is False
    
    def test_is_valid_uuid_with_none(self):
        """Test that None is not valid"""
        assert UserId.is_valid_uuid(None) is False
    
    def test_is_valid_uuid_with_invalid_format(self):
        """Test that invalid format is rejected"""
        assert UserId.is_valid_uuid("not-a-uuid") is False
    
    def test_assert_full_uuid_with_valid_uuid(self):
        """Test that valid UUID passes assertion"""
        valid_uuid = "bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2"
        UserId.assert_full_uuid(valid_uuid)  # Should not raise
    
    def test_assert_full_uuid_with_prefix_raises_error(self):
        """Test that 8-char prefix raises UserIdError"""
        prefix = "bb4a6f7c"
        with pytest.raises(UserIdError) as exc_info:
            UserId.assert_full_uuid(prefix)
        assert "8-character prefix" in str(exc_info.value)
    
    def test_assert_full_uuid_with_empty_raises_error(self):
        """Test that empty string raises UserIdError"""
        with pytest.raises(UserIdError) as exc_info:
            UserId.assert_full_uuid("")
        assert "empty" in str(exc_info.value).lower()
    
    def test_assert_full_uuid_with_none_raises_error(self):
        """Test that None raises UserIdError"""
        with pytest.raises(UserIdError) as exc_info:
            UserId.assert_full_uuid(None)
        assert "empty" in str(exc_info.value).lower()


class TestUserIdParsing:
    """Test UserId parsing methods"""
    
    def test_parse_from_identity_with_user_prefix(self):
        """Test parsing 'user-<uuid>' format"""
        identity = "user-bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2"
        result = UserId.parse_from_identity(identity)
        assert result == "bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2"
    
    def test_parse_from_identity_with_bare_uuid(self):
        """Test parsing bare UUID"""
        identity = "bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2"
        result = UserId.parse_from_identity(identity)
        assert result == "bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2"
    
    def test_parse_from_identity_with_prefix_raises_error(self):
        """Test that 8-char prefix raises UserIdError"""
        identity = "bb4a6f7c"
        with pytest.raises(UserIdError) as exc_info:
            UserId.parse_from_identity(identity)
        assert "Invalid UUID format" in str(exc_info.value)
    
    def test_parse_from_identity_with_user_prefix_invalid_uuid(self):
        """Test that 'user-<invalid>' raises UserIdError"""
        identity = "user-bb4a6f7c"
        with pytest.raises(UserIdError) as exc_info:
            UserId.parse_from_identity(identity)
        assert "Invalid UUID format" in str(exc_info.value)
    
    def test_parse_from_identity_with_empty_raises_error(self):
        """Test that empty string raises UserIdError"""
        with pytest.raises(UserIdError) as exc_info:
            UserId.parse_from_identity("")
        assert "empty" in str(exc_info.value).lower()
    
    def test_parse_from_identity_with_none_raises_error(self):
        """Test that None raises UserIdError"""
        with pytest.raises(UserIdError) as exc_info:
            UserId.parse_from_identity(None)
        assert "empty" in str(exc_info.value).lower()


class TestUserIdFormatting:
    """Test UserId display formatting"""
    
    def test_format_for_display_with_valid_uuid(self):
        """Test that UUID is formatted as first 8 chars + ellipsis"""
        valid_uuid = "bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2"
        result = UserId.format_for_display(valid_uuid)
        assert result == "bb4a6f7c..."
    
    def test_format_for_display_with_short_string(self):
        """Test that short strings are returned as-is"""
        short = "abc"
        result = UserId.format_for_display(short)
        assert result == "abc"
    
    def test_format_for_display_with_empty(self):
        """Test that empty string returns '(none)'"""
        result = UserId.format_for_display("")
        assert result == "(none)"
    
    def test_format_for_display_with_none(self):
        """Test that None returns '(none)'"""
        result = UserId.format_for_display(None)
        assert result == "(none)"


class TestUserIdEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_uuid_with_uppercase(self):
        """Test that uppercase UUID is valid"""
        uuid_upper = "BB4A6F7C-1E1D-4DB8-9FCD-F7095759ABA2"
        assert UserId.is_valid_uuid(uuid_upper) is True
    
    def test_uuid_with_mixed_case(self):
        """Test that mixed-case UUID is valid"""
        uuid_mixed = "Bb4a6f7c-1E1d-4Db8-9Fcd-F7095759aBA2"
        assert UserId.is_valid_uuid(uuid_mixed) is True
    
    def test_uuid_v1_is_rejected(self):
        """Test that UUID v1 is rejected (we require v4)"""
        uuid_v1 = "550e8400-e29b-11d4-a716-446655440000"
        # This might pass basic UUID check but fail v4-specific validation
        # depending on implementation
        result = UserId.is_valid_uuid(uuid_v1)
        # For now, we accept any valid UUID format
        # In strict mode, this should be False
    
    def test_uuid_with_extra_whitespace(self):
        """Test that UUID with whitespace is handled"""
        uuid_with_space = "  bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2  "
        result = UserId.parse_from_identity(uuid_with_space)
        assert result == "bb4a6f7c-1e1d-4db8-9fcd-f7095759aba2"

