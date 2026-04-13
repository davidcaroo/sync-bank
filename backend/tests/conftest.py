import os

# Ensure required env vars exist before importing config/settings.
REQUIRED_ENV = {
    "IMAP_USER": "test",
    "IMAP_PASS": "test",
    "ALEGRA_EMAIL": "test",
    "ALEGRA_TOKEN": "test",
    "SUPABASE_URL": "http://localhost",
    "SUPABASE_KEY": "test",
    "ADMIN_API_KEY": "test",
}

for key, value in REQUIRED_ENV.items():
    os.environ.setdefault(key, value)
