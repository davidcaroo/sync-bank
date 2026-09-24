import os

# Ensure required env vars exist before importing config/settings.
REQUIRED_ENV = {
    "APP_ENV": "test",
    "IMAP_USER": "test",
    "IMAP_PASS": "test",
    "ALEGRA_EMAIL": "test",
    "ALEGRA_TOKEN": "test",
    "ADMIN_API_KEY": "test",
    "COMPANY_NIT": "900741732",
    "DATABASE_URL": "postgresql://syncbank:syncbank@localhost:55432/syncbank",
}

for key, value in REQUIRED_ENV.items():
    os.environ.setdefault(key, value)
