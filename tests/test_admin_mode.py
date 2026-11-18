import hashlib
import json
import os
import tempfile
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException, Response

from src import app as application


class AdminModeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.users_file = Path(self.temp_dir.name) / "admins.json"
        salt = "test-salt"
        digest = hashlib.pbkdf2_hmac(
            "sha256", b"teacher-password", salt.encode("ascii"), 100_000
        ).hex()
        self.users_file.write_text(
            json.dumps([{
                "username": "teacher",
                "password_hash": f"pbkdf2_sha256$100000${salt}${digest}",
            }]),
            encoding="utf-8",
        )
        self.environment = patch.dict(os.environ, {
            "ADMIN_USERS_FILE": str(self.users_file),
            "ADMIN_SESSION_SECRET": "test-secret-with-at-least-32-bytes",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_password_hash_verifies_only_matching_password(self):
        stored_hash = application.load_admin_users()["teacher"]

        self.assertTrue(application.verify_password("teacher-password", stored_hash))
        self.assertFalse(application.verify_password("wrong-password", stored_hash))

    def test_signup_and_unregister_require_teacher_session(self):
        request = SimpleNamespace(cookies={})

        with self.assertRaises(HTTPException) as signup_error:
            application.signup_for_activity("Chess Club", "new@mergington.edu", request)
        self.assertEqual(signup_error.exception.status_code, 401)

        with self.assertRaises(HTTPException) as unregister_error:
            application.unregister_from_activity(
                "Chess Club", "michael@mergington.edu", request
            )
        self.assertEqual(unregister_error.exception.status_code, 401)

    def test_teacher_session_can_manage_activity_registrations(self):
        token = application.create_admin_session(
            "teacher", application.get_session_secret()
        )
        request = SimpleNamespace(cookies={application.ADMIN_COOKIE_NAME: token})
        participants = application.activities["Chess Club"]["participants"]
        original_participants = participants.copy()
        self.addCleanup(participants.__setitem__, slice(None), original_participants)

        application.signup_for_activity("Chess Club", "new@mergington.edu", request)
        self.assertIn("new@mergington.edu", participants)

        application.unregister_from_activity("Chess Club", "new@mergington.edu", request)
        self.assertNotIn("new@mergington.edu", participants)

    def test_login_sets_http_only_signed_session_cookie(self):
        request = SimpleNamespace(
            cookies={},
            url=SimpleNamespace(scheme="https"),
        )
        response = Response()

        application.admin_login(
            application.AdminLogin(
                username="teacher",
                password="teacher-password",
            ),
            request,
            response,
        )

        cookies = SimpleCookie()
        cookies.load(response.headers["set-cookie"])
        session_cookie = cookies[application.ADMIN_COOKIE_NAME]
        self.assertTrue(session_cookie["httponly"])
        self.assertTrue(session_cookie["secure"])
        self.assertEqual(
            application.get_session_username(
                session_cookie.value, application.get_session_secret()
            ),
            "teacher",
        )


if __name__ == "__main__":
    unittest.main()
