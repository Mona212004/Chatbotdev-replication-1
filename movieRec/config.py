from configparser import ConfigParser
import os
from dotenv import load_dotenv

# config.py is at movieRec/config.py
# .env is at movieRec/movieRecommendation2/.env
_current_dir = os.path.dirname(os.path.abspath(__file__))  # movieRec/
_env_path = os.path.join(_current_dir, "movieRecommendation2", ".env")
load_dotenv(dotenv_path=_env_path)


def load_config(filename="db_params.ini", section="postgresql"):
    """
    Loads database configuration. Returns a connection string (URL) if
    the Neon cloud environment variable is present, otherwise falls back
    to a dictionary built from your local db_params.ini.
    """
    # 1. Primary Check: If the standard Cloud Connection string is set, use it
    # This is what you and your frontend dev will use for local/production cloud runs
    neon_url = os.getenv("DATABASE_URL")
    if neon_url:
        return neon_url

    # 2. Fallback Check: Individual Neon variables (keeping your current logic working)
    neon_host = os.getenv("DB_HOST")
    neon_db = os.getenv("DB_NAME")
    neon_user = os.getenv("DB_USER")
    neon_password = os.getenv("DB_PASSWORD")
    neon_sslmode = os.getenv("DB_SSLMODE", "require")

    if neon_host and neon_db and neon_user and neon_password:
        return {
            "host": neon_host,
            "dbname": neon_db,
            "user": neon_user,
            "password": neon_password,
            "sslmode": neon_sslmode,
        }

    # 3. Ultimate Fallback: Local offline db_params.ini
    parser = ConfigParser()
    parser.read(os.path.join(_current_dir, filename))

    config = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            config[param[0]] = param[1]
    else:
        raise Exception(
            "Section {0} not found in the {1} file".format(section, filename)
        )

    return config


if __name__ == "__main__":
    config = load_config()
    print("Loaded Config Type:", type(config))
    print("Loaded Config Content:", config)
