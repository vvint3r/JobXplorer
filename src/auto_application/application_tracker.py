import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import csv
import logging
from datetime import datetime
from pathlib import Path

from paths import APPLICATION_LOGS_DIR, APPLICATIONS_CSV

class ApplicationTracker:
    """Track job applications."""
    
    def __init__(self, log_file=None):
        """
        Initialize the application tracker.
        
        Args:
            log_file: Path to the CSV file for tracking applications
        """
        if log_file is None:
            log_dir = str(APPLICATION_LOGS_DIR)
            os.makedirs(log_dir, exist_ok=True)
            log_file = str(APPLICATIONS_CSV)
        
        self.log_file = log_file
        self.logger = logging.getLogger(__name__)
        
        # Create log file with headers if it doesn't exist
        if not os.path.exists(self.log_file):
            self._create_log_file()
    
    def _create_log_file(self):
        """Create the log file with headers."""
        headers = [
            'timestamp',
            'job_id',
            'job_title',
            'company',
            'job_url',
            'job_board_type',
            'status',
            'submitted',
            'message',
            'error'
        ]
        
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        
        self.logger.info(f"Created application log file: {self.log_file}")
    
    def is_already_applied(self, job_url, job_id=None):
        """
        Check if we've already applied to this job.
        
        Args:
            job_url: URL of the job posting
            job_id: Optional job ID
            
        Returns:
            bool: True if already applied
        """
        if not os.path.exists(self.log_file):
            return False
        
        try:
            with open(self.log_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    status = (row.get('status') or '').strip().lower()
                    submitted = (row.get('submitted') or '').strip().lower()
                    if status not in ['success'] and submitted != 'yes':
                        continue
                    if row.get('job_url') == job_url:
                        return True
                    if job_id and row.get('job_id') == job_id:
                        return True
        except Exception as e:
            self.logger.error(f"Error checking application history: {e}")
        
        return False
    
    def log_application(self, job_data, result, job_board_type):
        """
        Log an application attempt.
        
        Args:
            job_data: Dictionary with job information (job_id, job_title, company, job_url)
            result: Dictionary with application result (success, message, submitted)
            job_board_type: Type of job board (e.g., 'greenhouse', 'workday')
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        status = result.get('status')
        if not status:
            status = 'success' if result.get('success') else 'failed'

        row = {
            'timestamp': timestamp,
            'job_id': job_data.get('job_id', ''),
            'job_title': job_data.get('job_title', ''),
            'company': job_data.get('company', ''),
            'job_url': job_data.get('job_url', ''),
            'job_board_type': job_board_type,
            'status': status,
            'submitted': 'yes' if result.get('submitted') else 'no',
            'message': result.get('message', ''),
            'error': result.get('error', '')
        }
        
        try:
            # Check if headers exist
            file_exists = os.path.exists(self.log_file) and os.path.getsize(self.log_file) > 0
            
            with open(self.log_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=row.keys())
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row)
            
            self.logger.info(f"Logged application: {job_data.get('job_title', 'Unknown')} at {job_data.get('company', 'Unknown')}")
        except Exception as e:
            self.logger.error(f"Error logging application: {e}")
    
    def get_application_stats(self):
        """
        Get statistics about applications.
        
        Returns:
            dict: Statistics including total, successful, failed, submitted
        """
        if not os.path.exists(self.log_file):
            return {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'submitted': 0
            }
        
        try:
            with open(self.log_file, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            total = len(rows)
            successful = sum(1 for row in rows if row.get('status') == 'success')
            failed = sum(1 for row in rows if row.get('status') == 'failed')
            submitted = sum(1 for row in rows if row.get('submitted') == 'yes')
            
            return {
                'total': total,
                'successful': successful,
                'failed': failed,
                'submitted': submitted
            }
        except Exception as e:
            self.logger.error(f"Error getting application stats: {e}")
            return {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'submitted': 0
            }


