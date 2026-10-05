import os
# Select the disposable integration engine before any test imports models.
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")
os.environ["JWT_SECRET"] = "tests-only-not-for-deployment-" + "x" * 40
