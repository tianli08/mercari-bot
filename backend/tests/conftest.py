"""Shared test environment configuration."""

import os
import sys
from pathlib import Path

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("DISCORD_KEY", "test-discord-key")
os.environ.setdefault("DESTINATION_SECRET_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
os.environ.setdefault("DESIGNER_CHANNEL_ID", "designer")
os.environ.setdefault("SAVED_CHANNEL_ID", "saved")
os.environ["API_ENVIRONMENT"] = "test"
os.environ["CLERK_SECRET_KEY"] = "sk_test_offline"
os.environ["CLERK_PUBLISHABLE_KEY"] = "pk_test_Y2xlcmsuZXhhbXBsZS5jb20k"
os.environ["CLERK_AUTHORIZED_PARTIES"] = '["http://localhost:3000"]'

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clerk_test_helpers import PUBLIC_KEY  # noqa: E402

os.environ["CLERK_JWT_KEY"] = PUBLIC_KEY
