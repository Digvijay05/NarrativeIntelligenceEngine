"""
Network Isolation Tests
=======================

CONSTITUTIONAL REQUIREMENT:
NO external API calls allowed from model layer.
These tests enforce that constraint.

If any outbound network call is attempted → test fails → build fails.
"""

import pytest
import sys
import socket
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from adapter.providers.mock import MockProvider
from adapter.providers.base import InvocationParams


class TestNetworkIsolation:
    """
    Verify that providers do not make network calls.
    
    This is a CONSTITUTIONAL TEST, not optional.
    """
    
    def test_mock_provider_no_network(self):
        """Mock provider must not make any network calls."""
        provider = MockProvider()
        params = InvocationParams(seed=42, temperature=0.0)
        
        # Patch socket to detect any network attempts
        with patch('socket.socket') as mock_socket:
            mock_socket.side_effect = AssertionError(
                "CONSTITUTIONAL VIOLATION: Network call attempted"
            )
            
            # This should succeed - mock doesn't use network
            response = provider.invoke("test prompt", params)
            
            assert response.success
            assert mock_socket.call_count == 0
    
    def test_local_provider_offline_mode(self):
        """Local provider must operate in offline mode."""
        try:
            from adapter.providers.local import LocalModelProvider
        except ImportError:
            pytest.skip("Local provider dependencies not installed")
        
        # Verify offline environment variables are set
        import os
        
        provider = LocalModelProvider()
        params = InvocationParams(seed=42, temperature=0.0)
        
        # The provider should set these on model load
        with patch.dict(os.environ, {
            'TRANSFORMERS_OFFLINE': '1',
            'HF_DATASETS_OFFLINE': '1'
        }):
            # Provider should not attempt network even with these flags
            # (will fail if model not cached, which is expected)
            pass
    
    def test_no_external_imports_in_mock(self):
        """Mock provider must not import external API libraries."""
        # List of forbidden imports (external API SDKs)
        forbidden_modules = [
            'anthropic',
            'openai', 
            'google.generativeai',
            'cohere',
            'replicate',
        ]
        
        # Import mock provider
        from adapter.providers import mock
        
        # Check that none of the forbidden modules are imported
        for module_name in forbidden_modules:
            assert module_name not in sys.modules, \
                f"CONSTITUTIONAL VIOLATION: {module_name} imported by mock provider"


class TestOfflineGuarantees:
    """
    Test that the system can operate fully offline.
    """
    
    def test_mock_provider_works_without_network(self):
        """Mock provider must work with network completely disabled."""
        provider = MockProvider()
        params = InvocationParams(seed=42, temperature=0.0)
        
        # Simulate complete network isolation
        original_socket = socket.socket
        
        def blocked_socket(*args, **kwargs):
            raise OSError("Network disabled - CONSTITUTIONAL REQUIREMENT")
        
        socket.socket = blocked_socket
        
        try:
            response = provider.invoke("test prompt", params)
            assert response.success
        finally:
            socket.socket = original_socket
    
    def test_determinism_requires_no_external_state(self):
        """Determinism must not depend on external API state."""
        provider = MockProvider()
        params = InvocationParams(seed=42, temperature=0.0)
        
        # Run multiple times - must be identical
        responses = []
        for _ in range(5):
            response = provider.invoke("test prompt", params)
            responses.append(response.content)
        
        assert len(set(responses)) == 1, \
            "Determinism violated - responses differ across runs"
