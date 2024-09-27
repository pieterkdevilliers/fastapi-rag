import unittest
import asyncio
from fastapi.testclient import TestClient
from main import app


class TestAccounts(unittest.TestCase):
    """
    A class for testing Account endpoints
    """
    @classmethod
    def setup_class(cls):
        """
        Setup Test Class
        """
        cls.client = TestClient(app)
    
    def test_get_accounts_returns_success_response(self):
        """
        Test get_all_accounts
        """
        response = self.client.get("/api/v1/accounts")
        self.assertEqual(response.status_code, 200)
        
    def test_get_accounts_returns_accounts_in_success_response(self):
        """
        Test get_all_accounts
        """
        response = self.client.get("/api/v1/accounts")
        returned_accounts = response.json()
        self.assertIsInstance(returned_accounts, dict)
        self.assertIn('accounts', returned_accounts)
        self.assertIsInstance(returned_accounts['accounts'], list)
        
    def test_get_account_by_id_returns_success_response(self):
        """
        Test get_account_by_id
        """
        account_id = 12345263574687
        response = self.client.get(f"/api/v1/accounts/{account_id}")
        self.assertEqual(response.status_code, 200)
    
    def test_post_accounts_returns_success_response(self):
        """
        Test post_account
        """
        account_organisation = "Test Organisation"
        response = self.client.post(f"/api/v1/accounts/{account_organisation}")
        returned_account = response.json()
        self.assertTrue(returned_account['response'], "success")
        
    def test_post_accounts_returns_account_in_success_response(self):
        """
        Test post_account
        """
        account_organisation = "Test Organisation"
        response = self.client.post(f"/api/v1/accounts/{account_organisation}")
        returned_account = response.json()
        self.assertTrue(returned_account['account_unique_id'])
        self.assertIn('response', returned_account)
        self.assertEqual(returned_account['response'], "success")
    
    def test_put_accounts_returns_success_response(self):
        """
        Test post_account
        """
        account_unique_id = 12345263574687
        account_organisation = "Test Organisation"
        response = self.client.put(f"/api/v1/accounts/{account_organisation}/{account_unique_id}")
        returned_account = response.json()
        self.assertTrue(returned_account['response'], "success")
        
    def test_put_accounts_returns_account_in_success_response(self):
        """
        Test post_account
        """
        account_unique_id = 12345263574687
        account_organisation = "Test Organisation"
        response = self.client.put(f"/api/v1/accounts/{account_organisation}/{account_unique_id}")
        returned_account = response.json()
        self.assertTrue(returned_account['account_unique_id'])
        self.assertIn('response', returned_account)
        self.assertEqual(returned_account['response'], "success")
    
