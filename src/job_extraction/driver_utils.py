import os
import time
import random
import shutil
import logging
import subprocess
import signal
import atexit
import undetected_chromedriver as uc
import re
from selenium.webdriver.chrome.options import Options

# Module-level tracking for Xvfb process
_xvfb_process = None
_xvfb_display = None


def _is_display_in_use(display_num):
    """Check if an X display number is already in use (lock file or running process)."""
    lock_file = f"/tmp/.X{display_num}-lock"
    if os.path.exists(lock_file):
        return True
    # Also check for a running Xvfb on this display
    try:
        result = subprocess.run(
            ["pgrep", "-f", f"Xvfb :{display_num}\\b"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0 and result.stdout.strip():
            return True
    except Exception:
        pass
    return False


def _ensure_display():
    """Ensure a display is available. Start Xvfb if needed (headless SSH servers)."""
    global _xvfb_process, _xvfb_display

    # If DISPLAY is already set (local desktop, X11 forwarding, or previous Xvfb), nothing to do
    if os.environ.get("DISPLAY"):
        logging.info(f"Using existing DISPLAY={os.environ['DISPLAY']}")
        return

    # Check if Xvfb is available
    xvfb_path = shutil.which("Xvfb")
    if not xvfb_path:
        logging.warning(
            "No DISPLAY set and Xvfb not found. Chrome may fail to launch. "
            "Install Xvfb: sudo apt-get install -y xvfb"
        )
        return

    # Pick a display number that's not in use (check both lock files and running processes)
    display_num = None
    for candidate in range(99, 200):
        if not _is_display_in_use(candidate):
            display_num = candidate
            break

    if display_num is None:
        logging.error("Could not find a free display number for Xvfb (tried :99-:199)")
        return

    display = f":{display_num}"
    logging.info(f"No DISPLAY detected (headless server). Starting Xvfb on {display}")

    try:
        _xvfb_process = subprocess.Popen(
            ["Xvfb", display, "-screen", "0", "1920x1080x24", "-ac", "+extension", "GLX"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid,
        )
        time.sleep(1.5)  # give Xvfb a moment to start

        if _xvfb_process.poll() is not None:
            stderr = _xvfb_process.stderr.read().decode(errors="replace").strip()
            logging.error(f"Xvfb failed to start: {stderr}")
            _xvfb_process = None
            return

        os.environ["DISPLAY"] = display
        _xvfb_display = display
        atexit.register(cleanup_xvfb)
        logging.info(f"Xvfb started successfully (PID {_xvfb_process.pid}, DISPLAY={display})")
    except Exception as e:
        logging.error(f"Failed to start Xvfb: {e}")


def cleanup_xvfb():
    """Stop the Xvfb process if we started one."""
    global _xvfb_process, _xvfb_display
    if _xvfb_process:
        try:
            os.killpg(os.getpgid(_xvfb_process.pid), signal.SIGTERM)
            _xvfb_process.wait(timeout=5)
            logging.info("Xvfb stopped")
        except Exception as e:
            logging.warning(f"Error stopping Xvfb: {e}")
        finally:
            _xvfb_process = None
            if _xvfb_display and os.environ.get("DISPLAY") == _xvfb_display:
                del os.environ["DISPLAY"]
            _xvfb_display = None

def get_chrome_version():
    """Get the version of Chrome installed on the system."""
    try:
        # Try different commands to get Chrome version
        commands = [
            ['google-chrome', '--version'],
            ['google-chrome-stable', '--version'],
            ['chromium-browser', '--version'],
            ['chromium', '--version']
        ]
        
        for cmd in commands:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    version_text = result.stdout.strip()
                    # Extract version number (e.g., "Google Chrome 141.0.7390.76" -> "141")
                    version_match = re.search(r'(\d+)\.', version_text)
                    if version_match:
                        return int(version_match.group(1))
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        # Fallback: try to detect from Chrome binary
        chrome_paths = [
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable',
            '/usr/bin/chromium-browser',
            '/usr/bin/chromium'
        ]
        
        for chrome_path in chrome_paths:
            if os.path.exists(chrome_path):
                try:
                    result = subprocess.run([chrome_path, '--version'], capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        version_text = result.stdout.strip()
                        version_match = re.search(r'(\d+)\.', version_text)
                        if version_match:
                            return int(version_match.group(1))
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                    continue
        
        logging.warning("Could not detect Chrome version, using default version 141")
        return 141  # Default fallback
        
    except Exception as e:
        logging.warning(f"Error detecting Chrome version: {e}, using default version 141")
        return 141  # Default fallback

def create_driver(port=None, profile_name=None, headless=True, user_data_dir=None, keep_user_data_dir=False):
    """
    Create a Chrome driver with unique debugging port and profile.
    
    Args:
        port (int, optional): Specific port to use. If None, generates random port.
        profile_name (str, optional): Name for the profile directory. If None, uses timestamp.
        headless (bool): Whether to run in headless mode. Defaults to True.
    """
    try:
        # Ensure we have a display (starts Xvfb on headless servers)
        _ensure_display()

        # Generate random port if none provided
        if not port:
            port = random.randint(9222, 9999)
        
        # Create profile directory for this instance
        if user_data_dir:
            temp_dir = user_data_dir
            keep_user_data_dir = True
        else:
            profile_id = profile_name or f"chrome_profile_{int(time.time())}"
            temp_dir = f"/tmp/{profile_id}_{port}"

        os.makedirs(temp_dir, exist_ok=True)
        
        options = uc.ChromeOptions()
        
        # Basic required options
        options.add_argument('--no-sandbox')
        if headless:
            options.add_argument('--headless')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument(f'--remote-debugging-port={port}')
        options.add_argument(f'--user-data-dir={temp_dir}')
        
        # Enhanced anti-detection measures
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-browser-side-navigation')
        options.add_argument('--disable-site-isolation-trials')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--start-maximized')
        
        # Random window size
        width = random.randint(1050, 1200)
        height = random.randint(800, 1000)
        options.add_argument(f'--window-size={width},{height}')
        
        # Randomized user agent
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        options.add_argument(f'user-agent={random.choice(user_agents)}')
        
        # Get the actual Chrome version installed
        chrome_version = get_chrome_version()
        logging.info(f"Detected Chrome version: {chrome_version}")
        
        chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
        if chromedriver_path and not os.path.exists(chromedriver_path):
            logging.warning(f"CHROMEDRIVER_PATH not found: {chromedriver_path}")
            chromedriver_path = None

        driver = uc.Chrome(
            options=options,
            version_main=chrome_version,  # Use detected version
            use_subprocess=True,
            headless=headless,
            driver_executable_path=chromedriver_path
        )
        
        # Store temp_dir as attribute for cleanup
        driver.temp_dir = temp_dir
        driver.keep_user_data_dir = keep_user_data_dir
        
        # Additional JavaScript patches to avoid detection
        driver.execute_script("""
            // Overwrite the navigator properties
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Add language and plugins to appear more human-like
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Modify the permissions behavior
            Object.defineProperty(navigator, 'permissions', {
                get: () => ({
                    query: Promise.resolve({ state: 'granted' })
                })
            });
        """)
        
        # Add random delay before returning driver
        time.sleep(random.uniform(1, 3))
        
        logging.info(f"Created Chrome driver on port {port} with profile dir {temp_dir}")
        return driver
        
    except Exception as e:
        logging.error(f"Failed to create driver on port {port}: {e}")
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise

def cleanup_driver(driver, temp_dir=None):
    """
    Safely cleanup driver and its temporary directory.
    
    Args:
        driver: The Chrome driver instance
        temp_dir (str, optional): Path to the temporary directory to clean up
    """
    try:
        if driver:
            driver.quit()
            logging.info("Driver closed successfully")
    except Exception as e:
        logging.error(f"Error closing driver: {e}")
    
    try:
        # Use temp_dir from driver attribute if not provided
        cleanup_dir = temp_dir or (getattr(driver, 'temp_dir', None) if driver else None)
        keep_dir = getattr(driver, 'keep_user_data_dir', False) if driver else False
        if cleanup_dir and os.path.exists(cleanup_dir) and not keep_dir:
            shutil.rmtree(cleanup_dir, ignore_errors=True)
            logging.info(f"Cleaned up temporary directory: {cleanup_dir}")
    except Exception as e:
        logging.error(f"Error cleaning up temporary directory: {e}")