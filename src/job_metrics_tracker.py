import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging
import uuid

from paths import METRICS_DIR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def generate_unique_id() -> str:
    """Generate a unique ID using UUID4."""
    return str(uuid.uuid4())

class JobMetricsTracker:
    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir) if base_dir else METRICS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def save_run_metrics(self, 
                        job_title: str,
                        total_jobs: int,
                        salary_range: str,
                        job_type: str,
                        search_type: str,
                        geography: str) -> str:
        """Save metrics for a single job collection run."""
        try:
            # Create metrics data with unique ID
            metrics_data = {
                'run_id': generate_unique_id(),
                'date_of_run': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'job_title_input': job_title,
                'total_jobs_collected': total_jobs,
                'job_title': job_title,
                'salary_range': salary_range,
                'job_type_setting': job_type,
                'search_type': search_type,
                'geography': geography
            }
            
            # Create or update metrics file
            metrics_file = self.base_dir / f"{job_title.lower().replace(' ', '_')}_job_run_metrics.csv"
            
            if metrics_file.exists():
                existing_df = pd.read_csv(metrics_file)
                updated_df = pd.concat([existing_df, pd.DataFrame([metrics_data])], ignore_index=True)
            else:
                updated_df = pd.DataFrame([metrics_data])
            
            # Save metrics
            updated_df.to_csv(metrics_file, index=False)
            logging.info(f"Saved run metrics to {metrics_file}")
            
            return str(metrics_file)
            
        except Exception as e:
            logging.error(f"Error saving run metrics: {e}")
            raise
    
    def update_jobs_aggregation(self,
                              job_title: str,
                              new_jobs: List[Dict]) -> str:
        """Update the aggregated jobs file with new job records."""
        try:
            # Prepare new jobs data with unique IDs
            new_jobs_data = []
            collection_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            for job in new_jobs:
                job_data = {
                    'job_id': generate_unique_id(),
                    'job_title_input': job_title,
                    'job_title_collected': job.get('job_title', ''),
                    'company_name': job.get('company_name', ''),
                    'date_of_collection': collection_date,
                    'job_url': job.get('job_url', ''),
                    'location': job.get('location', ''),
                    'salary_range': job.get('salary_range', ''),
                    'job_type': job.get('job_type', '')
                }
                new_jobs_data.append(job_data)
            
            # Create or update aggregation file
            agg_file = self.base_dir / f"{job_title.lower().replace(' ', '_')}_individual_jobs_agg.csv"
            
            if agg_file.exists():
                existing_df = pd.read_csv(agg_file)
                # Remove duplicates based on job_url if it exists
                if 'job_url' in existing_df.columns:
                    new_jobs_df = pd.DataFrame(new_jobs_data)
                    # Only add jobs that don't exist (based on URL)
                    existing_urls = set(existing_df['job_url'].dropna())
                    new_jobs_df = new_jobs_df[~new_jobs_df['job_url'].isin(existing_urls)]
                    updated_df = pd.concat([existing_df, new_jobs_df], ignore_index=True)
                else:
                    updated_df = pd.concat([existing_df, pd.DataFrame(new_jobs_data)], ignore_index=True)
            else:
                updated_df = pd.DataFrame(new_jobs_data)
            
            # Save aggregated data
            updated_df.to_csv(agg_file, index=False)
            logging.info(f"Updated jobs aggregation in {agg_file}")
            
            return str(agg_file)
            
        except Exception as e:
            logging.error(f"Error updating jobs aggregation: {e}")
            raise 