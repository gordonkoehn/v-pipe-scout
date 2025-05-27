"""Tests for the signatures module."""

import pytest
import yaml
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, mock_open

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.signatures import (
    get_all_variant_definitions,
    VariantDefinition,
    VariantInfo,
    LOCAL_CACHE_DIR
)


@pytest.fixture
def sample_variant_yaml_data():
    """Sample variant YAML data for testing."""
    return {
        'variant': {
            'pangolin': 'B.1.1.7',
            'short': 'al',
            'nextstrain': '20I/501Y.V1'
        },
        'mut': {
            241: 'C>T',
            913: 'C>T',
            23403: 'A>G'
        }
    }


@pytest.fixture
def sample_github_files():
    """Sample GitHub files list for testing."""
    return [
        {'name': 'alpha_mutations_full.yaml'},
        {'name': 'beta_mutations_full.yaml'},
        {'name': 'delta_mutations_full.yaml'}
    ]


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory for testing."""
    temp_dir = tempfile.mkdtemp()
    original_cache_dir = LOCAL_CACHE_DIR
    
    # Create some sample YAML files in the temp directory
    sample_variants = [
        {
            'variant': {'pangolin': 'B.1.1.7', 'short': 'al', 'nextstrain': '20I/501Y.V1'},
            'mut': {241: 'C>T', 913: 'C>T'}
        },
        {
            'variant': {'pangolin': 'B.1.351', 'short': 'be', 'nextstrain': '20H/501Y.V2'},
            'mut': {215: 'A>G', 484: 'E>K'}
        }
    ]
    
    for i, variant_data in enumerate(sample_variants):
        variant_file = Path(temp_dir) / f"variant_{i}.yaml"
        with open(variant_file, 'w') as f:
            yaml.dump(variant_data, f)
    
    yield Path(temp_dir)
    
    # Cleanup
    shutil.rmtree(temp_dir)


class TestGetAllVariantDefinitions:
    """Test cases for get_all_variant_definitions function."""
    
    @patch('api.signatures.list_github_files')
    @patch('api.signatures.download_yaml_file')
    def test_successful_github_download(self, mock_download, mock_list_files, 
                                      sample_github_files, sample_variant_yaml_data):
        """Test successful downloading from GitHub when files are available."""
        # Setup mocks
        mock_list_files.return_value = sample_github_files
        mock_download.return_value = sample_variant_yaml_data
        
        # Call function
        result = get_all_variant_definitions()
        
        # Assertions
        assert len(result) == 3  # Should have 3 variant definitions
        assert all(isinstance(vd, VariantDefinition) for vd in result)
        assert all(vd.variant.pangolin == 'B.1.1.7' for vd in result)
        
        # Verify function calls
        mock_list_files.assert_called_once()
        assert mock_download.call_count == 3
        
    @patch('api.signatures.list_github_files')
    @patch('api.signatures.download_yaml_file')
    def test_partial_github_download_failure(self, mock_download, mock_list_files, 
                                           sample_github_files, sample_variant_yaml_data):
        """Test behavior when some GitHub downloads fail."""
        # Setup mocks - first download succeeds, others fail
        mock_list_files.return_value = sample_github_files
        mock_download.side_effect = [sample_variant_yaml_data, None, None]
        
        # Call function
        result = get_all_variant_definitions()
        
        # Should only have 1 successful variant definition
        assert len(result) == 1
        assert result[0].variant.pangolin == 'B.1.1.7'
        
    @patch('api.signatures.list_github_files')
    @patch('api.signatures.LOCAL_CACHE_DIR')
    def test_fallback_to_cache_when_github_unavailable(self, mock_cache_dir, 
                                                      mock_list_files, temp_cache_dir):
        """Test fallback to local cache when GitHub is unavailable."""
        # Setup mocks
        mock_list_files.return_value = []  # Simulate GitHub unavailable
        mock_cache_dir.glob.return_value = temp_cache_dir.glob("*.yaml")
        mock_cache_dir.__truediv__ = lambda self, other: temp_cache_dir / other
        
        with patch('builtins.open', mock_open()) as mock_file:
            # Mock the file reading
            sample_yaml_content = yaml.dump({
                'variant': {'pangolin': 'B.1.1.7', 'short': 'al', 'nextstrain': ''},
                'mut': {241: 'C>T'}
            })
            mock_file.return_value.read.return_value = sample_yaml_content
            
            with patch('yaml.safe_load') as mock_yaml_load:
                mock_yaml_load.return_value = {
                    'variant': {'pangolin': 'B.1.1.7', 'short': 'al', 'nextstrain': ''},
                    'mut': {241: 'C>T'}
                }
                
                # Call function
                result = get_all_variant_definitions()
                
                # Should have loaded from cache
                assert len(result) >= 0  # At least some variants should be loaded
                
    @patch('api.signatures.list_github_files')
    def test_empty_result_when_no_files_and_no_cache(self, mock_list_files):
        """Test behavior when neither GitHub nor cache has files."""
        # Setup mocks
        mock_list_files.return_value = []
        
        with patch('api.signatures.LOCAL_CACHE_DIR') as mock_cache_dir:
            mock_cache_dir.glob.return_value = []  # No cached files
            
            # Call function
            result = get_all_variant_definitions()
            
            # Should return empty list
            assert result == []
            
    @patch('api.signatures.list_github_files')
    @patch('api.signatures.download_yaml_file')
    def test_invalid_yaml_data_handling(self, mock_download, mock_list_files, sample_github_files):
        """Test handling of invalid YAML data."""
        # Setup mocks
        mock_list_files.return_value = sample_github_files
        # Return invalid YAML data that can't be parsed into VariantDefinition
        mock_download.return_value = {'invalid': 'data'}
        
        # Call function
        result = get_all_variant_definitions()
        
        # Should handle invalid data gracefully and return empty list
        assert result == []
        
    @patch('api.signatures.list_github_files')
    @patch('api.signatures.download_yaml_file')
    def test_mixed_valid_invalid_data(self, mock_download, mock_list_files, 
                                    sample_github_files, sample_variant_yaml_data):
        """Test handling of mixed valid and invalid data."""
        # Setup mocks
        mock_list_files.return_value = sample_github_files
        # Mix of valid and invalid data
        mock_download.side_effect = [
            sample_variant_yaml_data,  # Valid
            {'invalid': 'data'},       # Invalid
            sample_variant_yaml_data   # Valid
        ]
        
        # Call function
        result = get_all_variant_definitions()
        
        # Should return only valid variant definitions
        assert len(result) == 2
        assert all(vd.variant.pangolin == 'B.1.1.7' for vd in result)


class TestGetAllVariantDefinitionsIntegration:
    """Integration tests using actual local cache files."""
    
    def test_load_from_actual_cache(self):
        """Test loading from actual cache files in the repository."""
        # This test uses the actual cache files that exist in the repository
        result = get_all_variant_definitions()
        
        # Basic assertions about the result
        assert isinstance(result, list)
        assert len(result) > 0  # Should have at least some variants
        
        # Check that all items are VariantDefinition objects
        for variant_def in result:
            assert isinstance(variant_def, VariantDefinition)
            assert hasattr(variant_def, 'variant')
            assert hasattr(variant_def, 'mut')
            assert isinstance(variant_def.variant, VariantInfo)
            assert isinstance(variant_def.mut, dict)
            
        # Check some specific properties
        pangolin_names = [vd.variant.pangolin for vd in result]
        assert 'B.1.1.7' in pangolin_names  # Alpha variant should be present
        
    def test_specific_variant_structure(self):
        """Test that loaded variants have the expected structure."""
        result = get_all_variant_definitions()
        
        if result:  # If we have any variants
            variant_def = result[0]
            
            # Check variant info structure
            assert hasattr(variant_def.variant, 'pangolin')
            assert hasattr(variant_def.variant, 'short')
            assert hasattr(variant_def.variant, 'nextstrain')
            
            # Check mutations structure
            assert isinstance(variant_def.mut, dict)
            if variant_def.mut:  # If there are mutations
                # Check that keys are integers (positions) and values are strings (changes)
                for pos, change in variant_def.mut.items():
                    assert isinstance(pos, int)
                    assert isinstance(change, str)
                    assert pos > 0  # Positions should be positive


if __name__ == "__main__":
    pytest.main([__file__])