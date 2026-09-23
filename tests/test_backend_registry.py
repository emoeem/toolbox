import unittest
from unittest.mock import patch
from backends.registry import inspect_backends

class TestBackendRegistry(unittest.TestCase):
    def test_missing_backend_is_explicitly_unavailable(self):
        with patch('backends.registry.shutil.which', return_value=None):
            infos = inspect_backends()
        self.assertTrue(all(not x.available for x in infos))
        self.assertTrue(all(x.path == '' for x in infos))
