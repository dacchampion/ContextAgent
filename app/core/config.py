import os
from dotenv import load_dotenv

load_dotenv()  # lee backend/.env

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "")
DB_NAME = os.getenv("DB_NAME", "chartagentstore")
DB_SSL_CA = os.getenv("DB_SSL_CA")  # opcional

# cadena SQLAlchemy (PyMySQL)
def build_db_url() -> str:
    qs = f"?ssl_ca={DB_SSL_CA}" if DB_SSL_CA else ""
    return f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}{qs}"

DATABASE_URL = build_db_url()