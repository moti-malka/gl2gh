"""Tests for submodule transformer"""

import pytest
from app.utils.transformers import SubmoduleTransformer


class TestSubmoduleTransformer:
    """Test cases for GitLab to GitHub submodule URL transformation"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.transformer = SubmoduleTransformer()
    
    def test_parse_simple_gitmodules(self):
        """Test parsing a simple .gitmodules file"""
        gitmodules_content = """[submodule "libs/common"]
\tpath = libs/common
\turl = https://gitlab.com/myorg/common-lib.git
"""
        
        result = self.transformer.transform({
            "gitmodules_content": gitmodules_content,
            "url_mappings": {}
        })
        
        assert result.success
        assert len(result.data["submodules"]) == 1
        
        submodule = result.data["submodules"][0]
        assert submodule["name"] == "libs/common"
        assert submodule["path"] == "libs/common"
        assert submodule["url"] == "https://gitlab.com/myorg/common-lib.git"
    
    def test_parse_multiple_submodules(self):
        """Test parsing multiple submodules"""
        gitmodules_content = """[submodule "libs/common"]
\tpath = libs/common
\turl = https://gitlab.com/myorg/common-lib.git

[submodule "vendor/tool"]
\tpath = vendor/tool
\turl = git@gitlab.com:myorg/tool.git
"""
        
        result = self.transformer.transform({
            "gitmodules_content": gitmodules_content,
            "url_mappings": {}
        })
        
        assert result.success
        assert len(result.data["submodules"]) == 2
    
    def test_rewrite_https_url(self):
        """Test rewriting HTTPS URLs"""
        gitmodules_content = """[submodule "libs/common"]
\tpath = libs/common
\turl = https://gitlab.com/myorg/common-lib.git
"""
        
        url_mappings = {
            "https://gitlab.com/myorg/common-lib": "https://github.com/myorg/common-lib"
        }
        
        result = self.transformer.transform({
            "gitmodules_content": gitmodules_content,
            "url_mappings": url_mappings
        })
        
        assert result.success
        submodule = result.data["submodules"][0]
        assert submodule["url"] == "https://github.com/myorg/common-lib.git"
        assert submodule["rewritten"] is True
        assert submodule["original_url"] == "https://gitlab.com/myorg/common-lib.git"
    
    def test_rewrite_ssh_url(self):
        """Test rewriting SSH URLs"""
        gitmodules_content = """[submodule "vendor/tool"]
\tpath = vendor/tool
\turl = git@gitlab.com:myorg/tool.git
"""
        
        url_mappings = {
            "git@gitlab.com:myorg/tool": "https://github.com/myorg/tool"
        }
        
        result = self.transformer.transform({
            "gitmodules_content": gitmodules_content,
            "url_mappings": url_mappings
        })
        
        assert result.success
        submodule = result.data["submodules"][0]
        assert submodule["url"] == "git@github.com:myorg/tool.git"
        assert submodule["rewritten"] is True
    
    def test_preserve_url_format(self):
        """Test that URL format (SSH/HTTPS) is preserved"""
        gitmodules_content = """[submodule "lib1"]
\tpath = lib1
\turl = https://gitlab.com/myorg/lib1.git

[submodule "lib2"]
\tpath = lib2
\turl = git@gitlab.com:myorg/lib2.git
"""
        
        url_mappings = {
            "gitlab.com/myorg/lib1": "github.com/myorg/lib1",
            "gitlab.com/myorg/lib2": "github.com/myorg/lib2"
        }
        
        result = self.transformer.transform({
            "gitmodules_content": gitmodules_content,
            "url_mappings": url_mappings
        })
        
        assert result.success
        submodules = result.data["submodules"]
        
        # HTTPS should remain HTTPS
        assert submodules[0]["url"].startswith("https://")
        assert "github.com" in submodules[0]["url"]
        
        # SSH should remain SSH
        assert submodules[1]["url"].startswith("git@")
        assert "github.com" in submodules[1]["url"]
    
    def test_external_submodule_warning(self):
        """Test that external submodules (not being migrated) generate warnings"""
        gitmodules_content = """[submodule "external"]
\tpath = external
\turl = https://gitlab.com/external/lib.git
"""
        
        url_mappings = {}  # No mapping for this repo
        
        result = self.transformer.transform({
            "gitmodules_content": gitmodules_content,
            "url_mappings": url_mappings
        })
        
        assert result.success
        assert len(result.warnings) > 0
        
        submodule = result.data["submodules"][0]
        assert submodule["rewritten"] is False
        assert "warning" in submodule
    
    def test_mixed_migrated_and_external(self):
        """Test mix of migrated and external submodules"""
        gitmodules_content = """[submodule "internal"]
\tpath = internal
\turl = https://gitlab.com/myorg/internal.git

[submodule "external"]
\tpath = external
\turl = https://gitlab.com/external/lib.git
"""
        
        url_mappings = {
            "gitlab.com/myorg/internal": "github.com/myorg/internal"
        }
        
        result = self.transformer.transform({
            "gitmodules_content": gitmodules_content,
            "url_mappings": url_mappings
        })
        
        assert result.success
        assert result.data["rewrite_count"] == 1
        assert result.data["external_count"] == 1
        assert result.data["total_count"] == 2
        
        # One warning for external submodule
        assert len(result.warnings) == 1
    
    def test_generate_updated_gitmodules(self):
        """Test generation of updated .gitmodules content"""
        gitmodules_content = """[submodule "libs/common"]
\tpath = libs/common
\turl = https://gitlab.com/myorg/common-lib.git
"""
        
        url_mappings = {
            "gitlab.com/myorg/common-lib": "github.com/myorg/common-lib"
        }
        
        result = self.transformer.transform({
            "gitmodules_content": gitmodules_content,
            "url_mappings": url_mappings
        })
        
        assert result.success
        updated_content = result.data["gitmodules_content"]
        
        # Check that updated content contains GitHub URL
        assert "github.com" in updated_content
        assert "gitlab.com" not in updated_content
        assert '[submodule "libs/common"]' in updated_content
        assert "path = libs/common" in updated_content
    
    def test_url_normalization(self):
        """Test that URL normalization handles various formats"""
        test_cases = [
            ("https://gitlab.com/org/repo.git", "gitlab.com/org/repo"),
            ("git@gitlab.com:org/repo.git", "gitlab.com/org/repo"),
            ("ssh://git@gitlab.com/org/repo.git", "gitlab.com/org/repo"),
            ("https://gitlab.com/org/repo", "gitlab.com/org/repo"),
        ]
        
        for url, expected_normalized in test_cases:
            normalized = self.transformer._normalize_url(url)
            assert normalized == expected_normalized
    
    def test_empty_gitmodules(self):
        """Test handling of empty .gitmodules file"""
        result = self.transformer.transform({
            "gitmodules_content": "",
            "url_mappings": {}
        })
        
        assert result.success
        assert len(result.data["submodules"]) == 0
        assert len(result.warnings) > 0  # Should warn about no submodules
    
    def test_preserve_additional_properties(self):
        """Test that additional properties in submodules are preserved"""
        gitmodules_content = """[submodule "libs/common"]
\tpath = libs/common
\turl = https://gitlab.com/myorg/common-lib.git
\tbranch = main
\tupdate = rebase
"""
        
        url_mappings = {
            "gitlab.com/myorg/common-lib": "github.com/myorg/common-lib"
        }
        
        result = self.transformer.transform({
            "gitmodules_content": gitmodules_content,
            "url_mappings": url_mappings
        })
        
        assert result.success
        submodule = result.data["submodules"][0]
        assert submodule.get("branch") == "main"
        assert submodule.get("update") == "rebase"
        
        # Check generated content includes these properties
        updated_content = result.data["gitmodules_content"]
        assert "branch = main" in updated_content
        assert "update = rebase" in updated_content
    
    def test_missing_required_field(self):
        """Test validation of required input fields"""
        result = self.transformer.transform({
            "url_mappings": {}
            # Missing gitmodules_content
        })
        
        assert not result.success
        assert len(result.errors) > 0
