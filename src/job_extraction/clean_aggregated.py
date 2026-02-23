import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import logging
import argparse
from datetime import datetime

from paths import master_aggregated_csv, UNIFIED_MASTER_CSV

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def deduplicate_by_company_and_title(df, keep_strategy='latest'):
    """
    Remove duplicates based on company and job title combination.
    
    Args:
        df (pd.DataFrame): DataFrame to deduplicate
        keep_strategy (str): Strategy for keeping duplicates ('latest', 'earliest', 'random')
    
    Returns:
        pd.DataFrame: Deduplicated DataFrame
    """
    try:
        if df.empty:
            return df
            
        original_count = len(df)
        
        # Check if required columns exist
        if 'company_title' not in df.columns or 'job_title' not in df.columns:
            logging.warning("Required columns 'company_title' or 'job_title' not found, skipping company+title deduplication")
            return df
        
        # Create a combination key for company_title + job_title
        df['company_title_key'] = df['company_title'].astype(str) + '|' + df['job_title'].astype(str)
        
        # Remove duplicates based on company_title_key
        if keep_strategy == 'latest':
            # Keep the most recent entry (assuming date_extracted is the first column)
            df_deduped = df.sort_values('date_extracted', ascending=False).drop_duplicates(
                subset=['company_title_key'], keep='first'
            )
        elif keep_strategy == 'earliest':
            # Keep the earliest entry
            df_deduped = df.sort_values('date_extracted', ascending=True).drop_duplicates(
                subset=['company_title_key'], keep='first'
            )
        else:  # random
            # Keep a random entry
            df_deduped = df.drop_duplicates(subset=['company_title_key'], keep='first')
        
        # Remove the temporary key column
        df_deduped = df_deduped.drop('company_title_key', axis=1)
        
        final_count = len(df_deduped)
        duplicates_removed = original_count - final_count
        
        if duplicates_removed > 0:
            logging.info(f"Removed {duplicates_removed} duplicates based on company_title + job_title combination")
        
        return df_deduped
        
    except Exception as e:
        logging.error(f"Error in deduplicate_by_company_and_title: {e}")
        return df


def clean_aggregated_file(job_title, keep_strategy='latest', csv_path=None):
    """Clean an existing aggregated file by removing duplicates.
    
    If *csv_path* is provided it is used directly; otherwise the
    per-title master is resolved from *job_title* (with a fallback
    to the unified master CSV).
    """
    try:
        job_title_clean = job_title.lower().replace(' ', '_')

        if csv_path and os.path.exists(csv_path):
            master_file = csv_path
        else:
            master_file = str(master_aggregated_csv(job_title_clean))
            if not os.path.exists(master_file):
                master_file = str(UNIFIED_MASTER_CSV)
        
        if not os.path.exists(master_file):
            logging.error(f"Master file not found: {master_file}")
            return None
        
        # Load the existing file
        df = pd.read_csv(master_file)
        original_count = len(df)
        
        # Apply deduplication
        df_cleaned = deduplicate_by_company_and_title(df, keep_strategy=keep_strategy)
        final_count = len(df_cleaned)
        
        # Save the cleaned file
        df_cleaned.to_csv(master_file, index=False)
        
        logging.info(f"Cleaned aggregated file: {original_count} -> {final_count} jobs (removed {original_count - final_count} duplicates)")
        
        return master_file
        
    except Exception as e:
        logging.error(f"Error cleaning aggregated file: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description='Clean aggregated job files by removing duplicates')
    parser.add_argument('--job_title', required=True, help='Job title to clean')
    parser.add_argument('--csv_file', default=None,
                        help='Path to input CSV (default: per-title master, falls back to unified master).')
    parser.add_argument('--keep_strategy', default='latest', choices=['latest', 'earliest', 'random'], 
                       help='Strategy for keeping duplicates')
    args = parser.parse_args()
    
    try:
        result_file = clean_aggregated_file(args.job_title, args.keep_strategy, csv_path=args.csv_file)
        if result_file:
            logging.info(f"Successfully cleaned aggregated file: {result_file}")
        else:
            logging.warning("No file was cleaned")
            
    except Exception as e:
        logging.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    main()