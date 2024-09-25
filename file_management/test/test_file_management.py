import unittest
import asyncio
from unittest.mock import AsyncMock, patch
from starlette.datastructures import UploadFile as StarletteUploadFile
from io import BytesIO
from fastapi.testclient import TestClient
from main import upload_file, app, get_session
from file_management.source_db import SourceFileModel
from file_management.utils import save_file_to_db


class TestFileManagement(unittest.TestCase):
    """
    A class for testing File Management Endpoints
    """
    @classmethod
    def setup_class(cls):
        """
        Setup Test Class
        """
        cls.client = TestClient(app)
    
    def _create_mock_txt_file(self, filename):
        """
        Create a mock text file
        """
        return StarletteUploadFile(filename=filename, file=b"mock file content")
    
    def _create_mock_md_file(self, filename):
        """
        Create a mock markdown file
        """
        file_content = b"# Sample Markdown Content\nThis is a test markdown file."
        file_stream = BytesIO(file_content)
        return StarletteUploadFile(filename=filename, file=file_stream)

    def test_upload_file_returns_success_response(self):
        """
        Test upload_file
        """
        file = self._create_mock_txt_file("test.md")
        response = asyncio.run(upload_file(file))
        self.assertIsInstance(response, dict)
    
    def test_upload_file_returns_file_name_in_success_response(self):
        """
        Test upload_file
        """
        file = self._create_mock_md_file("test.md")
        response = asyncio.run(upload_file(file))
        self.assertIsInstance(response, dict)
        self.assertIn('file_name', response)
        self.assertIsInstance(response['file_name'], str)
        self.assertTrue(response['file_name'])
    
    def test_upload_file_returns_file_path_in_success_response(self):
        """
        Test upload_file
        """
        file = self._create_mock_md_file("test.md")
        response = asyncio.run(upload_file(file))
        self.assertIsInstance(response, dict)
        self.assertIn('file_path', response)
        self.assertIsInstance(response['file_path'], str)
        self.assertTrue(response['file_path'])
    
    def test_upload_file_returns_file_id_in_success_response(self):
        """
        Test upload_file
        """

        file = self._create_mock_md_file("test.md")
        response = asyncio.run(upload_file(file))
        self.assertIsInstance(response, dict)
        self.assertIn('file_id', response)
        self.assertIsInstance(response['file_id'], int)
        self.assertTrue(response['file_id'])
    
    def test_upload_file_returns_error_response_if_file_is_not_markdown(self):
        """
        Test upload_file with file that is not markdown
        """
        file = self._create_mock_txt_file("test.txt")
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

    def test_get_files_returns_files_when_found(self):
        """
        Test get_files
        """
        response = self.client.get("/api/v1/get-files")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), dict)
        self.assertIn('response', response.json())
        self.assertEqual(response.json()['response'], 'success')

