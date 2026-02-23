"""
Configuration file for auto-application system.
Store your personal information here for auto-filling job applications.
"""
import os
import json
import logging

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config', 'user_config.json')

# Default configuration template
DEFAULT_CONFIG = {
    "personal_info": {
        "first_name": "",
        "last_name": "",
        "email": "",
        "phone": "",
        "preferred_name": "",
        "zip_code": "",
        "linkedin_profile": "",
        "location": "",
        "city": ""
    },
    "application_info": {
        "resume_path": "",  # Path to your resume PDF
        "cover_letter_path": "",  # Path to your cover letter (optional)
        "how_did_you_hear": "LinkedIn",  # Default referral source
        "legally_authorized_to_work": "Yes",
        "require_visa_sponsorship": "No",
        "metro_area": ""  # Your current metro area
    },
    "work_authorization": {
        "authorized_to_work": True,
        "requires_sponsorship": False
    },
    "voluntary_disclosures": {
        # Optional - leave empty if you prefer not to disclose
        "gender_identity": "",
        "transgender": "",
        "sexual_orientation": "",
        "race_ethnicity": [],
        "veteran_status": "",
        "disability": "",
        "first_generation_professional": ""
    },
    "custom_answers": {
        # Store answers to common custom questions
        # Key: question pattern (partial match), Value: answer
        "PEO industry experience": "I have [X] years of experience in the PEO industry...",
        "years of experience": "",
        "why interested": ""
    }
}

def load_config():
    """Load user configuration from file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                logging.info(f"Loaded configuration from {CONFIG_FILE}")
                return config
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            return DEFAULT_CONFIG
    else:
        logging.warning(f"Config file not found at {CONFIG_FILE}. Creating default config.")
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

def save_config(config):
    """Save user configuration to file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        logging.info(f"Saved configuration to {CONFIG_FILE}")
    except Exception as e:
        logging.error(f"Error saving config: {e}")

def get_config():
    """Get current configuration, creating default if needed."""
    return load_config()

def validate_config(config=None):
    """Validate that required configuration fields are filled."""
    if config is None:
        config = load_config()
    
    required_fields = [
        "personal_info.first_name",
        "personal_info.last_name",
        "personal_info.email",
        "personal_info.phone",
        "application_info.resume_path"
    ]
    
    missing = []
    for field in required_fields:
        keys = field.split('.')
        value = config
        for key in keys:
            value = value.get(key, {})
        if not value:
            missing.append(field)
    
    if missing:
        logging.warning(f"Missing required configuration fields: {', '.join(missing)}")
        return False
    return True


