import os
import tempfile

os.environ.setdefault("NIGHTSHIFT_DB", os.path.join(tempfile.mkdtemp(), "test.db"))
os.environ.setdefault("NIGHTSHIFT_REPORTS", tempfile.mkdtemp())
os.environ.setdefault("VULTR_INFERENCE_API_KEY", "test-key-not-real")
