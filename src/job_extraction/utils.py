import json
import logging
import os
from pathlib import Path

# Default cookie path is config/linkedin_cookies.txt
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_COOKIE_PATH = _PROJECT_ROOT / "config" / "linkedin_cookies.txt"

def load_cookie_data(cookie_file=None):
    """Load cookie data from external file."""
    try:
        if cookie_file is None:
            cookie_path = str(_DEFAULT_COOKIE_PATH)
        elif os.path.isabs(cookie_file):
            cookie_path = cookie_file
        else:
            # Legacy: relative to this file's directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            cookie_path = os.path.join(current_dir, cookie_file)
        
        with open(cookie_path, 'r') as file:
            content = file.read().strip()
            logging.info("Cookie file read successfully")
            
            # Clean up the content without logging it
            cookie_json = content.replace('\n', '').replace('    ', '')
            
            # Parse the JSON
            cookies = json.loads(cookie_json)
            logging.info(f"Successfully parsed {len(cookies)} cookies")
            return cookies
            
    except FileNotFoundError:
        logging.error(f"Cookie file not found: {cookie_path}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing cookies JSON: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error loading cookies: {e}")
        raise