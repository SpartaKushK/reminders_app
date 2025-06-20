import os
from datetime import date

from dotenv import load_dotenv

# Force load .env from the directory of this config.py
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError(
        "GOOGLE_API_KEY environment variable not set. Please set it in your environment or create a .env file.")

TODAY = date.today().strftime("%m/%d/%Y")

# logging.basicConfig(level=logging.INFO,
#                     format="%(asctime)s - %(levelname)s - %(message)s")
