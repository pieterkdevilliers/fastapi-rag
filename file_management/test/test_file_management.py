import unittest
import asyncio
from unittest.mock import AsyncMock, patch
from starlette.datastructures import UploadFile
from io import BytesIO
from fastapi.testclient import TestClient
from main import upload_files, app, get_session, get_files
from file_management.models import SourceFile
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
    
    async def async_get_files(self):
        """
        Create an async function to get files
        """
        files = await self.client.get("/api/v1/files/{account_unique_id}")
        return files.json()
    
    def _create_mock_txt_file(self, filename):
        """
        Create a mock text file
        """
        return UploadFile(filename=filename, file=b"mock file content")

    def _create_mock_md_file(self, filename):
        """
        Create a mock markdown file
        """
        file_content = b"# Sample Markdown Content\nThis is a test markdown file."
        files = [UploadFile(filename="test.md", file=BytesIO(file_content))]
        return files

    def test_upload_files_returns_success_response(self):
        """
        Test upload_file
        """
        files = self._create_mock_md_file("test.md")
        response = response = asyncio.run(upload_files("18a318b688b04fa4", files))
        self.assertIsInstance(response, dict)
    
    def test_upload_files_returns_file_name_in_success_response(self):
        """
        Test upload_file
        """
        files = self._create_mock_md_file("test.md")
        response = asyncio.run(upload_files("18a318b688b04fa4", files))
        self.assertIsInstance(response, dict)
        self.assertIn('file_name', response)
        self.assertIsInstance(response['file_name'], str)
        self.assertTrue(response['file_name'])
    
    def test_upload_files_returns_file_path_in_success_response(self):
        """
        Test upload_file
        """
        files = self._create_mock_md_file("test.md")
        response = asyncio.run(upload_files("18a318b688b04fa4", files))
        self.assertIsInstance(response, dict)
        self.assertIn('file_path', response)
        self.assertIsInstance(response['file_path'], str)
        self.assertTrue(response['file_path'])
    
    def test_upload_files_returns_file_id_in_success_response(self):
        """
        Test upload_file
        """

        files = self._create_mock_md_file("test.md")
        response = asyncio.run(upload_files("18a318b688b04fa4", files))
        self.assertIsInstance(response, dict)
        self.assertIn('file_id', response)
        self.assertIsInstance(response['file_id'], int)
        self.assertTrue(response['file_id'])
    

    def test_upload_files_returns_error_response_if_no_file_provided(self):
        """
        Test upload_file without file
        """
        response = asyncio.run(upload_files(account_unique_id="18a318b688b04fa4", files=None))
        self.assertIsInstance(response, dict)
        self.assertEqual(response, {"error": "No files provided"})

    def test_get_files_returns_files_when_found(self):
        """
        Test get_files
        """
        account_unique_id = "18a318b688b04fa4"
        response = self.client.get(f"/api/v1/files/{account_unique_id}")
        files = response.json()
        self.assertIsInstance(files, dict)
        self.assertIn("files", files)
        self.assertIsInstance(files["files"], list)
    
    def test_get_file_by_id_returns_success_response(self):
        """
        Test get_file_by_id
        """
        account_unique_id = "18a318b688b04fa4"
        file_id = 1
        response = self.client.get(f"/api/v1/files/{account_unique_id}/{file_id}")
        file = response.json()
        self.assertIsInstance(file, dict)
        self.assertEqual(file["response"], "success")
    
    def test_get_file_by_id_returns_error_response_if_file_not_found(self):
        """
        Test get_file_by_id with file not found
        """
        account_unique_id = "18a318b688b04fa4"
        file_id = 100
        response = self.client.get(f"/api/v1/files/{account_unique_id}/{file_id}")
        file = response.json()
        self.assertIsInstance(file, dict)
        self.assertEqual(file, {"error": "File not found", "file_id": file_id})
        
    def test_get_file_by_id_returns_file_when_found(self):
        """
        Test get_file_by_id with file found
        """
        account_unique_id = "18a318b688b04fa4"
        file_id = 1
        response = self.client.get(f"/api/v1/files/{account_unique_id}/{file_id}")
        file = response.json()
        self.assertIsInstance(file, dict)
        self.assertIn("file", file)
        self.assertIsInstance(file["file"], dict)
    
    def test_update_file_returns_file_in_success_response(self):
        """
        Test update_file
        """
        included_in_source_data = False
        account_unique_id = "18a318b688b04fa4"
        file_id = 1
        updated_file_body = {
                "included_in_source_data": included_in_source_data,
                "account_unique_id": account_unique_id,
                "id": file_id
                }
        response = self.client.put(f"/api/v1/files/{account_unique_id}/{file_id}", json=updated_file_body)
        file = response.json()
        self.assertIsInstance(file, dict)
        self.assertIn("id", file)
    
    def test_update_file_returns_error_response_if_file_not_found(self):
        """
        Test update_file with file not found
        """
        included_in_source_data = "false"
        account_unique_id = "18a318b688b04fa4"
        file_id = 100
        updated_file_body = {
                "included_in_source_data": included_in_source_data,
                "account_unique_id": account_unique_id,
                "id": file_id
                }
        response = self.client.put(f"/api/v1/files/{account_unique_id}/{file_id}", json=updated_file_body)
        self.assertEqual(response.status_code, 404)
        file = response.json()
        self.assertIsInstance(file, dict)
        self.assertEqual(file, {"detail":{"error": "File not found", "file_id": file_id}})
    
    def test_delete_file_returns_success_response(self):
        """
        Test delete_file
        """
        account_unique_id = '18a318b688b04fa4'
        file_id = 3
        response = self.client.delete(f"/api/v1/files/{account_unique_id}/{file_id}")
        deleted_account = response.json()
        self.assertEqual(deleted_account['response'], "success")
        self.assertTrue(deleted_account['file_id'])
