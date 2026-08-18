"""Shared test environment configuration."""

import os

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("DISCORD_KEY", "test-discord-key")
os.environ.setdefault("DESTINATION_SECRET_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
os.environ.setdefault("DESIGNER_CHANNEL_ID", "designer")
os.environ.setdefault("SAVED_CHANNEL_ID", "saved")
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-with-at-least-32-characters")
os.environ.setdefault("API_ENVIRONMENT", "test")
os.environ.setdefault("AUTH_COOKIE_SECURE", "false")
