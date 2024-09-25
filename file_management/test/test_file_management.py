import unittest
import asyncio
from main import upload_file

class TestFileManagement(unittest.TestCase):
    """
    A class for testing File Management Endpoints
    """

    def test_upload_file_returns_success_response(self):
        """
        Test upload_file
        """
        file = "test.md"
        response = asyncio.run(upload_file(file))
        self.assertIsInstance(response, dict)
    
    def test_upload_file_returns_file_name_in_success_response(self):
        """
        Test upload_file
        """
        file = "test.md"
        response = asyncio.run(upload_file(file))
        self.assertIsInstance(response, dict)
        self.assertIn('file_name', response)
        self.assertIsInstance(response['file_name'], str)
        self.assertTrue(response['file_name'])
    
    def test_upload_file_returns_file_path_in_success_response(self):
        """
        Test upload_file
        """
        file = "test.md"
        response = asyncio.run(upload_file(file))
        self.assertIsInstance(response, dict)
        self.assertIn('file_path', response)
        self.assertIsInstance(response['file_path'], str)
        self.assertTrue(response['file_path'])
    
    def test_upload_file_returns_error_response_if_file_is_not_markdown(self):
        """
        Test upload_file with file that is not markdown
        """
        file = "test.txt"
        response = asyncio.run(upload_file(file))
        self.assertIsInstance(response, dict)
        self.assertEqual(response, {"error": "File must be a markdown file"})

    def test_upload_file_returns_error_response_if_no_file_provided(self):
        """
        Test upload_file without file
        """
        response = asyncio.run(upload_file(file=None))
        self.assertIsInstance(response, dict)
        self.assertEqual(response, {"error": "No file provided"})