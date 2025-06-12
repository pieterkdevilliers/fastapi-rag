import unittest
import asyncio
import query_data.query_source_data as query_source_data
from main import read_root, query_data


class TestRoot(unittest.TestCase):
    """
    Initial Test as principle of TDD"""

    def test_read_root_returns_success_response_as_dictionary(self):
        """
        Test read_root
        """
        response = asyncio.run(read_root())
        self.assertIsInstance(response, dict)


class TestQueryData(unittest.TestCase):
    """
    Tests for the Query Data"""

    def test_query_data_returns_success_response_if_query_provided(self):
        """
        Test query_data with query
        """
        query = "test"
        response = asyncio.run(query_data(query))
        self.assertIsInstance(response, dict)

    def test_query_data_returns_error_response_if_no_query_provided(self):
        """
        Test query_data without query
        """
        response = asyncio.run(query_data(query=None))
        self.assertIsInstance(response, dict)
        self.assertEqual(response, {"error": "No query provided"})
    
    def test_query_source_data_returns_response_including_query(self):
        """
        Test query_data with query
        """
        query = "test"
        response = query_source_data.query_source_data(query)
        print(response['query'])
        self.assertEqual(response['query'], query)
        self.assertIsInstance(response, dict)

    def test_db_prepared_successfully_returns_db_response(self):
        """
        Test preparing the DB
        """
        response = query_source_data.prepare_db()
        self.assertIsNotNone(response)
    
    def test_search_db_returns_response_when_no_result_found(self):
        """
        Test searching the DB
        """
        query = "test"
        db = query_source_data.prepare_db()
        response = query_source_data.search_db(db, query)
        self.assertEqual(response, f"Unable to find matching results for: {query}")

    def test_search_db_returns_response_when_result_found(self):
        """
        Test searching the DB
        """
        query = "Who was romeo?"
        db = query_source_data.prepare_db()
        response = query_source_data.search_db(db, query)
        self.assertIsInstance(response, dict)
        self.assertNotEqual(response, f"Unable to find matching results for: {query}")