"""Simple tests for the signatures module."""

import pytest
import yaml
from unittest.mock import patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.signatures import get_all_variant_definitions, VariantDefinition


class TestGetAllVariantDefinitions:
    """Simple test cases for get_all_variant_definitions function."""
    
    @patch('api.signatures.list_github_files')
    @patch('api.signatures.download_yaml_file')
    def test_get_all_variant_definitions_github_works(self, mock_download, mock_list_files):
        """Test when GitHub is available and working."""
        # Mock GitHub files list
        mock_list_files.return_value = [{'name': 'alpha_mutations_full.yaml'}]
        
        # Mock successful download with valid variant data
        mock_download.return_value = {
            'variant': {
                'pangolin': 'B.1.1.7',
                'short': 'al',
                'nextstrain': '20I/501Y.V1'
            },
            'mut': {
                241: 'C>T',
                913: 'C>T'
            }
        }
        
        # Call function
        result = get_all_variant_definitions()
        
        # Should get variant definitions from GitHub
        assert len(result) == 1
        assert isinstance(result[0], VariantDefinition)
        assert result[0].variant.pangolin == 'B.1.1.7'
        
        # Verify GitHub functions were called
        mock_list_files.assert_called_once()
        mock_download.assert_called_once()
    
    @patch('api.signatures.list_github_files')
    @patch('api.signatures.LOCAL_CACHE_DIR')
    @patch('builtins.open')
    @patch('yaml.safe_load')
    def test_get_all_variant_definitions_github_unavailable_fallback_to_cache(self, mock_yaml_load, mock_open, mock_cache_dir, mock_list_files):
        """Test when GitHub doesn't work, falls back to local cache."""
        # Mock GitHub unavailable (returns empty list)
        mock_list_files.return_value = []
        
        # Mock cache directory with some YAML files
        from pathlib import Path
        mock_cache_files = [
            Path('alpha_mutations_full.yaml'),
            Path('beta_mutations_full.yaml')
        ]
        mock_cache_dir.glob.return_value = mock_cache_files
        
        # Mock YAML content for cached files
        mock_yaml_data = [
            {
                'variant': {'pangolin': 'B.1.1.7', 'short': 'al', 'nextstrain': '20I/501Y.V1'},
                'mut': {241: 'C>T', 913: 'C>T'}
            },
            {
                'variant': {'pangolin': 'B.1.351', 'short': 'be', 'nextstrain': '20H/501Y.V2'},
                'mut': {484: 'E>K', 501: 'N>Y'}
            }
        ]
        mock_yaml_load.side_effect = mock_yaml_data
        
        # Call function - should fallback to loading from local cache
        result = get_all_variant_definitions()
        
        # Should get variant definitions from local cache
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(vd, VariantDefinition) for vd in result)
        
        # Check specific variants were loaded
        pangolin_names = [vd.variant.pangolin for vd in result]
        assert 'B.1.1.7' in pangolin_names
        assert 'B.1.351' in pangolin_names
        
        # Verify GitHub was tried but failed
        mock_list_files.assert_called_once()
        
        # Verify cache was accessed
        mock_cache_dir.glob.assert_called_once_with("*.yaml")
        assert mock_yaml_load.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__])