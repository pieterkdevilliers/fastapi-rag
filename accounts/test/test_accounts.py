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
        account_unique_id = 12345263574687
        response = self.client.get(f"/api/v1/accounts/{account_unique_id}")
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
        account_unique_id = 'a6f3de5a43d26e9e'
        response = self.client.put(f"/api/v1/accounts/{account_unique_id}")
        returned_account = response.json()
        self.assertIsInstance(returned_account, dict)
        
    def test_put_accounts_returns_account_in_success_response(self):
        """
        Test post_account
        """
        account_unique_id = 'a6f3de5a43d26e9e'
        account_id = 1
        account_organisation = "Test Organisation Amended Test"
        updated_account = Account(account_organisation=account_organisation, account_unique_id=account_unique_id, id=account_id)
        response = self.client.put(f"/api/v1/accounts/{account_unique_id}", json=updated_account.model_dump())
        returned_account = response.json()
        self.assertIn('response', returned_account)
    
    def test_delete_accounts_returns_success_response(self):
        """
        Test delete_account
        """
        account_unique_id = '9d26846e4be226d1'
        response = self.client.delete(f"/api/v1/accounts/{account_unique_id}")
        deleted_account = response.json()
        self.assertEqual(deleted_account['response'], "success")
        self.assertTrue(deleted_account['account_unique_id'])
    


class TestUsers(unittest.TestCase):
    """
    A class for testing User endpoints
    """
    @classmethod
    def setup_class(cls):
        """
        Setup Test Class
        """
        cls.client = TestClient(app)
    
    def test_get_users_returns_success_response(self):
        """
        Test get_users
        """
        response = self.client.get("/api/v1/users")
        self.assertEqual(response.status_code, 200)
        
    def test_get_users_returns_users_in_success_response(self):
        """
        Test get_users
        """
        response = self.client.get("/api/v1/users")
        returned_users = response.json()
        self.assertIsInstance(returned_users, dict)
        self.assertIn('users', returned_users)
        self.assertIsInstance(returned_users['users'], list)
        
    def test_get_user_by_id_returns_success_response(self):
        """
        Test get_account_by_id
        """
        account_unique_id = '461d83b0371706b4'
        user_id = 1
        response = self.client.get(f"/api/v1/users/{account_unique_id}/{user_id}")
        returned_user = response.json()
        self.assertTrue(returned_user['response'], "success")
    
    def test_post_user_returns_success_response(self):
        """
        Test create_user
        """
        account_unique_id = '461d83b0371706b4'
        user_email = "anotheruser@test.com"
        user_password = "password"
        response = self.client.post(f"/api/v1/users/{account_unique_id}/{user_email}/{user_password}")
        response = response.json()
        self.assertTrue(response['response'], "success")
        
    def test_post_user_returns_user_in_success_response(self):
        """
        Test create_user
        """
        account_unique_id = '461d83b0371706b4'
        user_email = "anotheruser2@test.com"
        user_password = "password2"
        response = self.client.post(f"/api/v1/users/{account_unique_id}/{user_email}/{user_password}")
        returned_user = response.json()
        self.assertTrue(returned_user['user_email'])
        self.assertIn('response', returned_user)
        self.assertEqual(returned_user['response'], "success")

    
    def test_put_users_returns_success_response(self):
        """
        Test post_account
        """
        account_unique_id = '461d83b0371706b4'
        user_email = "anotheruser@test.com"
        user_password = "password2PasswordChange"
        user_id = 4
        response = self.client.put(f"/api/v1/users/{account_unique_id}/{user_id}/{user_email}/{user_password}")
        returned_user = response.json()
        self.assertTrue(returned_user['response'], "success")
        
    def test_put_accounts_returns_account_in_success_response(self):
        """
        Test post_account
        """
        account_unique_id = '461d83b0371706b4'
        user_email = "anotheruser@test.com"
        user_password = "password2PasswordChange"
        user_id = 4
        response = self.client.put(f"/api/v1/users/{account_unique_id}/{user_id}/{user_email}/{user_password}")
        returned_account = response.json()
        self.assertTrue(returned_account['user_email'])
        self.assertIn('response', returned_account)
        self.assertEqual(returned_account['response'], "success")
    
    def test_delete_user_returns_success_response(self):
        """
        Test delete_account
        """
        account_unique_id = '461d83b0371706b4'
        user_id = 6
        response = self.client.delete(f"/api/v1/users/{account_unique_id}/{user_id}")
        deleted_user = response.json()
        self.assertEqual(deleted_user['response'], "success")
        self.assertTrue(deleted_user['user_id'])