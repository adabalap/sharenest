import unittest
import os
import json
from unittest.mock import patch, MagicMock

# Set env vars before importing app
os.environ['FLASK_ENV'] = 'testing'
os.environ['SQLITE_DB'] = ':memory:'
os.environ['OCI_TENANCY_OCID'] = 'mock-tenancy'
os.environ['OCI_USER_OCID'] = 'mock-user'
os.environ['OCI_FINGERPRINT'] = 'mock-fingerprint'
os.environ['OCI_PRIVATE_KEY_PATH'] = '/dev/null'
os.environ['OCI_REGION'] = 'mock-region'
os.environ['OCI_NAMESPACE'] = 'mock-namespace'
os.environ['OCI_BUCKET_NAME'] = 'mock-bucket'

from app import app, get_db, init_db

class ShareNestAPITests(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        with app.app_context():
            init_db()

    def tearDown(self):
        with app.app_context():
            db = get_db()
            # You might need to add more tables to drop if your schema grows
            db.execute("DROP TABLE IF EXISTS files")
            db.execute("DROP TABLE IF EXISTS share_links")
            db.commit()

    @patch('app.oci_generate_write_par')
    def test_initiate_upload_direct(self, mock_gen_par):
        """Test initiating a direct upload for a small file."""
        mock_gen_par.return_value = "https://mock.oci/par-write/some-object"
        
        response = self.app.post('/api/initiate-upload',
                                 data=json.dumps({
                                     "filename": "test.txt",
                                     "file_size_bytes": 10 * 1024 * 1024  # 10MB
                                 }),
                                 content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['upload_type'], 'direct')
        self.assertIn('par_url', data)
        self.assertIn('object_name', data)
        mock_gen_par.assert_called_once()

    @patch('app.oci_create_multipart_upload')
    def test_initiate_upload_multipart(self, mock_create_multi):
        """Test initiating a multipart upload for a large file."""
        mock_create_multi.return_value = "mock-upload-id-123"
        
        response = self.app.post('/api/initiate-upload',
                                 data=json.dumps({
                                     "filename": "large_video.mp4",
                                     "file_size_bytes": 200 * 1024 * 1024  # 200MB
                                 }),
                                 content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['upload_type'], 'multipart')
        self.assertEqual(data['upload_id'], 'mock-upload-id-123')
        self.assertIn('object_name', data)
        self.assertIn('part_size_bytes', data)
        mock_create_multi.assert_called_once()

    @patch('app.oci_generate_part_par')
    def test_request_part_url(self, mock_gen_part_par):
        """Test requesting a pre-signed URL for a multipart chunk."""
        mock_gen_part_par.return_value = "https://mock.oci/par-part/some-object?part=1"
        
        response = self.app.post('/api/request-part-url',
                                 data=json.dumps({
                                     "object_name": "large_video.mp4",
                                     "upload_id": "mock-upload-id-123",
                                     "part_num": 1
                                 }),
                                 content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('par_url', data)
        mock_gen_part_par.assert_called_once_with("large_video.mp4", "mock-upload-id-123", 1)

    @patch('app.oci_commit_multipart_upload')
    def test_finalize_upload_multipart(self, mock_commit):
        """Test finalizing a multipart upload."""
        mock_commit.return_value = True
        
        finalize_data = {
            "pin": "1234",
            "original_filename": "large_video.mp4",
            "object_name": "some_object_name",
            "size_bytes": 200 * 1024 * 1024,
            "upload_id": "mock-upload-id-123",
            "parts": [{"partNum": 1, "etag": "etag1"}, {"partNum": 2, "etag": "etag2"}]
        }
        
        response = self.app.post('/api/finalize-upload',
                                 data=json.dumps(finalize_data),
                                 content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('share_url', data)
        mock_commit.assert_called_once_with("some_object_name", "mock-upload-id-123", finalize_data["parts"])

        # Verify DB entry
        with app.app_context():
            db = get_db()
            row = db.execute("SELECT * FROM files WHERE object_name = ?", ("some_object_name",)).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row['original_filename'], "large_video.mp4")

    def test_finalize_upload_direct(self):
        """Test finalizing a direct upload (no commit call)."""
        finalize_data = {
            "pin": "5678",
            "original_filename": "test.txt",
            "object_name": "another_object_name",
            "size_bytes": 1024
        }
        
        response = self.app.post('/api/finalize-upload',
                                 data=json.dumps(finalize_data),
                                 content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('share_url', data)

        # Verify DB entry
        with app.app_context():
            db = get_db()
            row = db.execute("SELECT * FROM files WHERE object_name = ?", ("another_object_name",)).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row['original_filename'], "test.txt")

    @patch('app.oci_abort_multipart_upload')
    def test_abort_upload(self, mock_abort):
        """Test aborting a multipart upload."""
        mock_abort.return_value = True
        
        response = self.app.post('/api/abort-upload',
                                 data=json.dumps({
                                     "object_name": "stale_object",
                                     "upload_id": "stale_upload_id"
                                 }),
                                 content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'aborted')
        mock_abort.assert_called_once_with("stale_object", "stale_upload_id")

if __name__ == "__main__":
    unittest.main()