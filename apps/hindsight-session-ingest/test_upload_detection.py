import os
import unittest
from unittest.mock import patch

from ingest_safety import inspect_upload


class UploadDetectionTest(unittest.TestCase):
    def test_credential_check_is_off_by_default(self):
        data = b'<script>const password = "fixture-value";</script>'
        with patch.dict(os.environ):
            os.environ.pop("HINDSIGHT_UPLOAD_CREDENTIAL_CHECK", None)
            self.assertEqual(inspect_upload("page.html", data), data)

    def test_explicitly_reenabled_check_still_blocks_credentials(self):
        data = b'password = "fixture-value"'
        with patch.dict(os.environ, {"HINDSIGHT_UPLOAD_CREDENTIAL_CHECK": "1"}):
            with self.assertRaisesRegex(ValueError, "Credentials detected"):
                inspect_upload("page.html", data)

    def test_disabled_detection_preserves_other_bounds(self):
        with patch.dict(os.environ, {"HINDSIGHT_UPLOAD_CREDENTIAL_CHECK": "0"}):
            for filename, data in [("page.exe", b"binary"), ("page.html", b""), ("page.html", b"a\0b")]:
                with self.subTest(filename=filename, data=data), self.assertRaises(ValueError):
                    inspect_upload(filename, data)


if __name__ == "__main__":
    unittest.main()
