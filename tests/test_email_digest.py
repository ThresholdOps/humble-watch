import os
import unittest
from unittest.mock import patch

from scripts import discord_digest as digest, email_digest


class EmailDigestTests(unittest.TestCase):
    def test_discord_workflow_also_sends_private_email_over_tls(self):
        sent = []

        class FakeSMTP:
            def __init__(self, host, port, timeout):
                self.secure = False

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def starttls(self, context):
                self.secure = True

            def login(self, username, password):
                if not self.secure:
                    raise AssertionError("SMTP login attempted before TLS")

            def send_message(self, message):
                if not self.secure:
                    raise AssertionError("SMTP delivery attempted before TLS")
                sent.append(message)

        settings = {
            "DIGEST_EMAIL_FROM": "watch@example.org", "DIGEST_EMAIL_TO": "one@example.org",
            "DIGEST_SMTP_HOST": "smtp.example.org", "DIGEST_SMTP_USERNAME": "watch@example.org",
            "DIGEST_SMTP_PASSWORD": "test-password", "DIGEST_SMTP_PORT": "",
        }
        with patch.dict(os.environ, settings, clear=True), patch.object(digest, "build_message", return_value="New bundles: Python Bundle"), patch.object(digest, "load_json", return_value={"generated_at": "2026-11-14T18:00:00Z"}), patch.object(digest, "send_discord"), patch.object(email_digest.smtplib, "SMTP", FakeSMTP):
            digest.main()
        self.assertEqual(len(sent), 1)
        self.assertIn("Python Bundle", sent[0].get_content())

    def test_message_contains_sections_link_and_fixed_recipients(self):
        content = "📡 **Humble Watch Daily Digest**\nDashboard: <https://example.org/>\n🆕 **New bundles**\n• Python Bundle"
        message = email_digest.build_email_message(
            content, "watch@example.org", ["one@example.org", "two@example.org"], "2026-11-14T18:00:00Z"
        )
        self.assertEqual(message["From"], "watch@example.org")
        self.assertEqual(message["To"], "one@example.org, two@example.org")
        self.assertIn("2026-11-14", message["Subject"])
        self.assertIn("https://example.org/", message.get_content())
        self.assertIn("New bundles", message.get_content())
        self.assertIn("Python Bundle", message.get_content())

    def test_unconfigured_email_is_skipped(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(email_digest.send_email_digest("digest", "2026-11-14T18:00:00Z"))

    def test_partial_configuration_fails_clearly(self):
        with patch.dict(os.environ, {"DIGEST_SMTP_HOST": "smtp.example.org"}, clear=True):
            with self.assertRaisesRegex(ValueError, "DIGEST_EMAIL_FROM"):
                email_digest.send_email_digest("digest", "2026-11-14T18:00:00Z")

    def test_email_failure_does_not_block_feed_publication(self):
        with patch.object(digest, "build_message", return_value="digest"), patch.object(digest, "load_json", return_value={}), patch.object(digest, "send_discord"), patch.object(digest, "send_email_digest", side_effect=OSError("SMTP unavailable")):
            self.assertEqual(digest.main(), 0)


if __name__ == "__main__":
    unittest.main()
