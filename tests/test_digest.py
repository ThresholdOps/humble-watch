import unittest
from unittest.mock import patch

from scripts import discord_digest as digest


class DigestTests(unittest.TestCase):
    def test_interest_terms_require_word_boundaries_and_match_phrases(self):
        matches = digest.matched_keywords("Airmail detail assets for world   building", ["ai", "asset", "assets", "world building"])
        self.assertEqual(matches, ["assets", "world building"])

    def test_rolling_expiry_sections_have_accurate_labels(self):
        with patch.object(digest, "load_json", return_value={"items": []}), patch.object(digest, "load_seen", return_value={"items": [], "initialized": False}), patch.object(digest, "write_seen"):
            message = digest.build_message()
        self.assertIn("Ending within 24h", message)
        self.assertIn("Ending 24–48h", message)
        self.assertNotIn("Ending today", message)


if __name__ == "__main__":
    unittest.main()
