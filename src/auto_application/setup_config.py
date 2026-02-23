"""
Helper script to set up user configuration interactively.
"""
import sys
import os
import json

# Add src/ directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_application.config import DEFAULT_CONFIG, save_config, CONFIG_FILE

def setup_config_interactive():
    """Interactively set up user configuration."""
    print("=" * 60)
    print("Job Application Auto-Fill Configuration Setup")
    print("=" * 60)
    print()
    
    config = DEFAULT_CONFIG.copy()
    
    # Personal Information
    print("PERSONAL INFORMATION")
    print("-" * 60)
    config['personal_info']['first_name'] = input("First Name: ").strip()
    config['personal_info']['last_name'] = input("Last Name: ").strip()
    config['personal_info']['email'] = input("Email: ").strip()
    config['personal_info']['phone'] = input("Phone: ").strip()
    config['personal_info']['preferred_name'] = input("Preferred Name (optional): ").strip()
    config['personal_info']['zip_code'] = input("Zip Code: ").strip()
    config['personal_info']['linkedin_profile'] = input("LinkedIn Profile URL (optional): ").strip()
    config['personal_info']['location'] = input("Location (City, State): ").strip()
    config['personal_info']['city'] = input("City: ").strip()
    print()
    
    # Application Information
    print("APPLICATION INFORMATION")
    print("-" * 60)
    resume_path = input("Resume PDF Path (absolute path): ").strip()
    if os.path.exists(resume_path):
        config['application_info']['resume_path'] = os.path.abspath(resume_path)
    else:
        print(f"Warning: Resume file not found at {resume_path}")
        config['application_info']['resume_path'] = resume_path
    
    cover_letter_path = input("Cover Letter PDF Path (optional, press Enter to skip): ").strip()
    if cover_letter_path and os.path.exists(cover_letter_path):
        config['application_info']['cover_letter_path'] = os.path.abspath(cover_letter_path)
    elif cover_letter_path:
        print(f"Warning: Cover letter file not found at {cover_letter_path}")
        config['application_info']['cover_letter_path'] = cover_letter_path
    
    config['application_info']['how_did_you_hear'] = input("How did you hear about opportunities? (default: LinkedIn): ").strip() or "LinkedIn"
    config['application_info']['legally_authorized_to_work'] = input("Legally authorized to work? (Yes/No, default: Yes): ").strip() or "Yes"
    config['application_info']['require_visa_sponsorship'] = input("Require visa sponsorship? (Yes/No, default: No): ").strip() or "No"
    config['application_info']['metro_area'] = input("Metro Area (optional): ").strip()
    print()
    
    # Work Authorization
    print("WORK AUTHORIZATION")
    print("-" * 60)
    authorized = input("Authorized to work? (yes/no, default: yes): ").strip().lower() or "yes"
    config['work_authorization']['authorized_to_work'] = authorized == "yes"
    
    requires_sponsorship = input("Requires sponsorship? (yes/no, default: no): ").strip().lower() or "no"
    config['work_authorization']['requires_sponsorship'] = requires_sponsorship == "yes"
    print()
    
    # Custom Answers (optional)
    print("CUSTOM ANSWERS (Optional - press Enter to skip)")
    print("-" * 60)
    print("You can add answers to common custom questions.")
    print("For example, if applications ask about PEO experience:")
    peo_answer = input("PEO industry experience answer (optional): ").strip()
    if peo_answer:
        config['custom_answers']['PEO industry experience'] = peo_answer
    
    years_exp = input("Years of experience answer (optional): ").strip()
    if years_exp:
        config['custom_answers']['years of experience'] = years_exp
    
    why_interested = input("Why interested answer (optional): ").strip()
    if why_interested:
        config['custom_answers']['why interested'] = why_interested
    print()
    
    # Save configuration
    save_config(config)
    print()
    print("=" * 60)
    print(f"Configuration saved to: {CONFIG_FILE}")
    print("=" * 60)
    print()
    print("You can edit this file directly to update your information.")
    print("To use the auto-application system, run:")
    print("  python3 src/auto_application/main_apply.py --csv_file path/to/jobs.csv")

if __name__ == "__main__":
    setup_config_interactive()


