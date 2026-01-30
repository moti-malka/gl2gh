"""Tests for user mapper"""

import pytest
from app.utils.transformers import UserMapper


class TestUserMapper:
    """Test cases for GitLab to GitHub user mapping"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mapper = UserMapper()
    
    def test_email_match_high_confidence(self):
        """Test email-based matching (high confidence)"""
        gitlab_users = [
            {
                "id": 1,
                "username": "johndoe",
                "email": "john@example.com",
                "name": "John Doe"
            }
        ]
        
        github_users = [
            {
                "login": "johndoe",
                "id": 101,
                "email": "john@example.com",
                "name": "John Doe"
            }
        ]
        
        result = self.mapper.transform({
            "gitlab_users": gitlab_users,
            "github_users": github_users
        })
        
        assert result.success
        mappings = result.data["mappings"]
        assert len(mappings) == 1
        
        mapping = mappings[0]
        assert mapping["confidence"] == "high"
        assert mapping["method"] == "email"
        assert mapping["github"]["login"] == "johndoe"
    
    def test_username_match_medium_confidence(self):
        """Test username-based matching (medium confidence)"""
        gitlab_users = [
            {
                "id": 1,
                "username": "johndoe",
                "email": "john.gitlab@example.com",
                "name": "John Doe"
            }
        ]
        
        github_users = [
            {
                "login": "johndoe",
                "id": 101,
                "email": "john.github@example.com",
                "name": "John Doe"
            }
        ]
        
        result = self.mapper.transform({
            "gitlab_users": gitlab_users,
            "github_users": github_users
        })
        
        assert result.success
        mappings = result.data["mappings"]
        assert len(mappings) == 1
        
        mapping = mappings[0]
        assert mapping["confidence"] == "medium"
        assert mapping["method"] == "username"
        assert mapping["github"]["login"] == "johndoe"
    
    def test_name_match_low_confidence(self):
        """Test name-based matching (low confidence)"""
        gitlab_users = [
            {
                "id": 1,
                "username": "jdoe",
                "email": "jd@example.com",
                "name": "John Doe"
            }
        ]
        
        github_users = [
            {
                "login": "john-doe",
                "id": 101,
                "email": "john@example.com",
                "name": "John Doe"
            }
        ]
        
        result = self.mapper.transform({
            "gitlab_users": gitlab_users,
            "github_users": github_users
        })
        
        assert result.success
        mappings = result.data["mappings"]
        assert len(mappings) == 1
        
        mapping = mappings[0]
        assert mapping["confidence"] == "low"
        assert mapping["method"] == "name"
        assert mapping["github"]["login"] == "john-doe"
    
    def test_no_match_unmapped(self):
        """Test unmapped user when no match found"""
        gitlab_users = [
            {
                "id": 1,
                "username": "olduser",
                "email": "old@example.com",
                "name": "Old User"
            }
        ]
        
        github_users = [
            {
                "login": "newuser",
                "id": 101,
                "email": "new@example.com",
                "name": "New User"
            }
        ]
        
        result = self.mapper.transform({
            "gitlab_users": gitlab_users,
            "github_users": github_users
        })
        
        assert result.success
        mappings = result.data["mappings"]
        assert len(mappings) == 1
        
        mapping = mappings[0]
        assert mapping["confidence"] == "unmapped"
        assert mapping["method"] == "none"
        assert mapping["github"] is None
        
        # Check warnings for unmapped users
        assert len(result.warnings) > 0
    
    def test_case_insensitive_username_matching(self):
        """Test case-insensitive username matching"""
        gitlab_users = [
            {
                "id": 1,
                "username": "JohnDoe",
                "email": "john1@example.com",
                "name": "John"
            }
        ]
        
        github_users = [
            {
                "login": "johndoe",
                "id": 101,
                "email": "john2@example.com",
                "name": "John"
            }
        ]
        
        result = self.mapper.transform({
            "gitlab_users": gitlab_users,
            "github_users": github_users
        })
        
        assert result.success
        mappings = result.data["mappings"]
        mapping = mappings[0]
        
        # Should match despite case difference
        assert mapping["confidence"] in ["medium", "low"]
        assert mapping["github"]["login"] == "johndoe"
    
    def test_multiple_users_mapping(self):
        """Test mapping multiple users at once"""
        gitlab_users = [
            {"id": 1, "username": "user1", "email": "user1@example.com", "name": "User One"},
            {"id": 2, "username": "user2", "email": "user2@example.com", "name": "User Two"},
            {"id": 3, "username": "olduser", "email": "user3@other.com", "name": "Old User"}  # Changed to avoid fuzzy match
        ]
        
        github_users = [
            {"login": "user1", "id": 101, "email": "user1@example.com", "name": "User One"},
            {"login": "user2", "id": 102, "email": "user2@example.com", "name": "User Two"}
        ]
        
        result = self.mapper.transform({
            "gitlab_users": gitlab_users,
            "github_users": github_users
        })
        
        assert result.success
        mappings = result.data["mappings"]
        assert len(mappings) == 3
        
        stats = result.data["stats"]
        assert stats["total"] == 3
        assert stats["high_confidence"] == 2  # user1, user2 matched by email
        assert stats["unmapped"] == 1  # olduser unmapped
    
    def test_org_members_included(self):
        """Test that GitHub org members are included in matching"""
        gitlab_users = [
            {"id": 1, "username": "orguser", "email": "org@example.com", "name": "Org User"}
        ]
        
        github_org_members = [
            {"login": "orguser", "id": 201, "email": "org@example.com", "name": "Org User"}
        ]
        
        result = self.mapper.transform({
            "gitlab_users": gitlab_users,
            "github_org_members": github_org_members
        })
        
        assert result.success
        mappings = result.data["mappings"]
        assert len(mappings) == 1
        assert mappings[0]["github"]["login"] == "orguser"
    
    def test_mapping_summary(self):
        """Test mapping summary generation"""
        mappings = [
            {"confidence": "high", "method": "email", "github": {"login": "user1"}},
            {"confidence": "medium", "method": "username", "github": {"login": "user2"}},
            {"confidence": "low", "method": "name", "github": {"login": "user3"}},
            {"confidence": "unmapped", "method": "none", "github": None}
        ]
        
        summary = self.mapper.get_mapping_summary(mappings)
        
        assert summary["total_users"] == 4
        assert summary["mapped"] == 3
        assert summary["unmapped"] == 1
        assert summary["high_confidence"] == 1
        assert summary["medium_confidence"] == 1
        assert summary["low_confidence"] == 1
        assert summary["by_method"]["email"] == 1
        assert summary["by_method"]["username"] == 1
        assert summary["by_method"]["name"] == 1
        assert summary["by_method"]["none"] == 1
    
    def test_fuzzy_username_match(self):
        """Test fuzzy username matching"""
        gitlab_users = [
            {
                "id": 1,
                "username": "john.doe",
                "email": "john1@example.com",
                "name": "John Doe"
            }
        ]
        
        github_users = [
            {
                "login": "johndoe",  # Similar but not exact
                "id": 101,
                "email": "john2@example.com",
                "name": "John Doe"
            }
        ]
        
        result = self.mapper.transform({
            "gitlab_users": gitlab_users,
            "github_users": github_users
        })
        
        assert result.success
        mappings = result.data["mappings"]
        assert len(mappings) == 1
        
        mapping = mappings[0]
        # Should match via fuzzy username matching
        assert mapping["github"] is not None
        assert mapping["github"]["login"] == "johndoe"
        assert mapping["confidence"] in ["medium", "low"]  # Fuzzy match is medium/low confidence
    
    def test_fuzzy_name_match(self):
        """Test fuzzy name matching"""
        gitlab_users = [
            {
                "id": 1,
                "username": "jdoe123",
                "email": "jd@example.com",
                "name": "John-Michael Doe"
            }
        ]
        
        github_users = [
            {
                "login": "jmdoe",
                "id": 101,
                "email": "jm@example.com",
                "name": "John Michael Doe"  # Similar name without hyphen
            }
        ]
        
        result = self.mapper.transform({
            "gitlab_users": gitlab_users,
            "github_users": github_users
        })
        
        assert result.success
        mappings = result.data["mappings"]
        assert len(mappings) == 1
        
        mapping = mappings[0]
        # Should match via fuzzy name matching
        assert mapping["github"] is not None
        assert mapping["github"]["login"] == "jmdoe"
        assert mapping["confidence"] == "low"  # Name fuzzy match is low confidence
    
    def test_normalization_helpers(self):
        """Test name and username normalization"""
        # Test name normalization
        assert self.mapper._normalize_name("John-Michael.Doe") == "john michael doe"
        assert self.mapper._normalize_name("  John  Doe  ") == "john doe"
        assert self.mapper._normalize_name("John_Doe") == "john doe"
        
        # Test username normalization
        assert self.mapper._normalize_username("john.doe") == "johndoe"
        assert self.mapper._normalize_username("john-doe") == "johndoe"
        assert self.mapper._normalize_username("john_doe") == "johndoe"
    
    def test_similarity_calculation(self):
        """Test similarity calculation"""
        # Identical strings
        assert self.mapper._calculate_similarity("johndoe", "johndoe") == 1.0
        
        # Very similar strings
        similarity = self.mapper._calculate_similarity("johndoe", "john.doe")
        assert similarity > 0.7  # Should be high similarity
        
        # Different strings
        similarity = self.mapper._calculate_similarity("johndoe", "janedoe")
        assert 0.5 < similarity < 0.9  # Moderate similarity
        
        # Empty strings
        assert self.mapper._calculate_similarity("", "") == 0.0
        assert self.mapper._calculate_similarity("test", "") == 0.0
