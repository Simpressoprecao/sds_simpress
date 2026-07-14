import sys, os

sys.path.insert(0, os.path.dirname(__file__))

os.environ["APP_ENV"] = "production"

from app import app as application
