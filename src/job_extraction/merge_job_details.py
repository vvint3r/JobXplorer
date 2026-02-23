import os
import pandas as pd
import logging
import glob
import argparse
from datetime import datetime
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from paths import (
    aggregated_for, job_details_for, search_results_for, master_aggregated_csv,
    AGGREGATED_DIR, UNIFIED_MASTER_CSV,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def filter_out_engineering_jobs(df):
    """
    Filter out jobs with 'engineer' or 'engineering' in the job title.
    
    Args:
        df (pd.DataFrame): DataFrame to filter
    
    Returns:
        pd.DataFrame: Filtered DataFrame
    """
    try:
        if df.empty:
            return df
        
        # Check if job_title column exists
        if 'job_title' not in df.columns:
            logging.warning("job_title column not found, returning original DataFrame")
            return df
        
        # Create a copy to avoid modifying original
        filtered_df = df.copy()
        
        # Filter out jobs with 'engineer' or 'engineering' in the job title (case-insensitive)
        mask = ~filtered_df['job_title'].astype(str).str.lower().str.contains('engineer', na=False)
        
        original_count = len(filtered_df)
        filtered_df = filtered_df[mask]
        final_count = len(filtered_df)
        
        removed_count = original_count - final_count
        
        if removed_count > 0:
            logging.info(f"Filtered out {removed_count} engineering jobs from {original_count} total jobs")
        else:
            logging.info("No engineering jobs found to filter out")
        
        return filtered_df
        
    except Exception as e:
        logging.error(f"Error filtering out engineering jobs: {e}")
        return df


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


def create_salary_filtered_aggregate(job_title, min_salary=175000):
    """
    Create a salary-filtered version of the aggregated file.
    Now also excludes engineering jobs.
    
    Args:
        job_title (str): The job title to process
        min_salary (int): Minimum salary threshold in thousands (default 175 for $175K)
    
    Returns:
        str: Path to the salary-filtered file
    """
    try:
        job_title_clean = job_title.lower().replace(' ', '_')
        
        # Path to the master aggregated file
        master_file = str(master_aggregated_csv(job_title_clean))
        
        if not os.path.exists(master_file):
            logging.error(f"Master file not found: {master_file}")
            return None
        
        # Load the master aggregated file
        df = pd.read_csv(master_file)
        
        if df.empty:
            logging.warning("Master aggregated file is empty")
            return None
        
        # Filter by salary first
        salary_filtered_df = filter_by_salary(df, min_salary)
        
        if salary_filtered_df.empty:
            logging.info(f"No jobs found with salary >= ${min_salary}K")
            return None
        
        # Then filter out engineering jobs
        salary_filtered_df = filter_out_engineering_jobs(salary_filtered_df)
        
        if salary_filtered_df.empty:
            logging.info(f"No jobs remaining after filtering out engineering jobs")
            return None
        
        # Create output filename with _salary suffix
        salary_file = master_file.replace('_master_aggregated.csv', f'_aggregated_salary_{min_salary}k.csv')
        
        # Save the salary-filtered file
        salary_filtered_df.to_csv(salary_file, index=False)
        
        # Create JSON version
        json_file = salary_file.replace('.csv', '.json')
        df_json = salary_filtered_df.copy()
        df_json = df_json.where(pd.notnull(df_json), None)
        
        # Convert datetime columns to strings
        for col in df_json.select_dtypes(include=['datetime64[ns]']).columns:
            df_json[col] = df_json[col].astype(str)
        
        output_data = {
            "metadata": {
                "job_title": job_title_clean,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_jobs": len(salary_filtered_df),
                "min_salary_threshold": f"${min_salary}K",
                "filter_type": "salary_range + exclude_engineering",
                "filters_applied": [
                    f"salary >= ${min_salary}K",
                    "exclude jobs with 'engineer' or 'engineering' in job title"
                ]
            },
            "jobs": df_json.to_dict('records')
        }
        
        with open(json_file, 'w', encoding='utf-8') as f:
            import json
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logging.info(f"Created salary-filtered aggregated file with {len(salary_filtered_df)} jobs (excluding engineering): {salary_file}")
        
        return salary_file
        
    except Exception as e:
        logging.error(f"Error creating salary-filtered aggregate: {e}")
        raise


def build_master_salary_aggregate(job_title, min_salary=175):
    """Aggregate all salary-filtered CSVs into a single master file."""
    try:
        job_title_clean = job_title.lower().replace(' ', '_')
        aggregated_path = str(aggregated_for(job_title_clean))
        pattern = os.path.join(aggregated_path, f"{job_title_clean}_aggregated_salary_{min_salary}k.csv")
        csv_files = glob.glob(pattern)

        if not csv_files:
            logging.warning(f"No salary-filtered files found for {job_title_clean}")
            return None

        frames = []
        for file in csv_files:
            try:
                frames.append(pd.read_csv(file))
            except Exception as e:
                logging.warning(f"Error reading salary file {file}: {e}")

        if not frames:
            return None

        master_df = pd.concat(frames, ignore_index=True)
        if 'job_url' in master_df.columns:
            master_df = master_df.drop_duplicates(subset=['job_url'], keep='last')

        output_file = os.path.join(aggregated_path, f"{job_title_clean}_master_aggregated_{min_salary}k.csv")
        master_df.to_csv(output_file, index=False)
        logging.info(f"Saved master salary aggregate to: {output_file}")

        return output_file
    except Exception as e:
        logging.error(f"Error building master salary aggregate: {e}")
        return None


def filter_by_salary(df, min_salary=175):
    """
    Filter DataFrame by salary range.
    
    Args:
        df (pd.DataFrame): DataFrame to filter
        min_salary (int): Minimum salary threshold in thousands
    
    Returns:
        pd.DataFrame: Filtered DataFrame
    """
    try:
        if df.empty:
            return df
        
        # Check if salary_range column exists
        if 'salary_range' not in df.columns:
            logging.warning("salary_range column not found, returning original DataFrame")
            return df
        
        # Create a copy to avoid modifying original
        filtered_df = df.copy()
        
        # Extract salary numbers from salary_range column
        filtered_df['salary_extracted'] = filtered_df['salary_range'].astype(str).apply(extract_salary_numbers)
        
        # Filter based on minimum salary
        # Include rows where any extracted salary is >= min_salary
        mask = filtered_df['salary_extracted'].apply(
            lambda salaries: any(salary >= min_salary for salary in salaries) if salaries else False
        )
        
        filtered_df = filtered_df[mask]
        
        # Remove the temporary salary_extracted column
        filtered_df = filtered_df.drop('salary_extracted', axis=1)
        
        logging.info(f"Filtered {len(df)} jobs to {len(filtered_df)} jobs with salary >= ${min_salary}K")
        
        return filtered_df
        
    except Exception as e:
        logging.error(f"Error filtering by salary: {e}")
        return df

def extract_salary_numbers(salary_text):
    """
    Extract salary numbers from salary text.
    
    Args:
        salary_text (str): Salary text like "$70/hr - $75/hr", "$100K/yr - $140K/yr", etc.
    
    Returns:
        list: List of salary numbers in thousands
    """
    try:
        if pd.isna(salary_text) or salary_text == '-':
            return []
        
        import re
        
        # Convert to string and clean
        salary_str = str(salary_text).replace(',', '').replace('$', '').replace(' ', '')
        
        # Extract numbers followed by K (thousands)
        k_matches = re.findall(r'(\d+(?:\.\d+)?)k', salary_str.lower())
        k_numbers = [float(match) for match in k_matches]
        
        # Extract numbers followed by /yr or /hr
        yr_hr_matches = re.findall(r'(\d+(?:\.\d+)?)(?:/yr|/hr)', salary_str.lower())
        yr_hr_numbers = [float(match) for match in yr_hr_matches]
        
        # For hourly rates, convert to annual (assuming 2000 hours/year)
        annual_from_hourly = [num * 2 for num in yr_hr_numbers if 'hr' in salary_str.lower()]
        
        # Combine all numbers
        all_numbers = k_numbers + yr_hr_numbers + annual_from_hourly
        
        # Remove duplicates and sort
        unique_numbers = list(set(all_numbers))
        
        return unique_numbers
        
    except Exception as e:
        logging.error(f"Error extracting salary numbers from '{salary_text}': {e}")
        return []

def aggregate_jobs_with_deduplication(job_title, new_jobs_df=None):
    """
    Aggregate jobs by job title, dedupe them, and only add new jobs.
    Creates a master aggregated file with date_extracted column.
    Now includes deduplication by company + job title combination.
    Also creates salary-filtered versions (excluding engineering jobs).
    
    Args:
        job_title (str): The job title to aggregate
        new_jobs_df (pd.DataFrame, optional): New jobs to add from current run
    
    Returns:
        str: Path to the aggregated file
    """
    try:
        # Clean job title
        job_title_clean = job_title.lower().replace(' ', '_')
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Define paths
        aggregated_path = str(aggregated_for(job_title_clean))
        os.makedirs(aggregated_path, exist_ok=True)
        
        # Path to master aggregated file
        master_file = os.path.join(aggregated_path, f"{job_title_clean}_master_aggregated.csv")
        
        # Initialize master dataframe
        master_df = pd.DataFrame()
        
        # Load existing master file if it exists
        if os.path.exists(master_file):
            master_df = pd.read_csv(master_file)
            logging.info(f"Loaded existing master file with {len(master_df)} records")
        else:
            logging.info("No existing master file found, creating new one")
        
        def enrich_from_job_details(df_in):
            """Merge description, days_since_posted, and application_url from job_details by job_url."""
            try:
                job_details_path = str(job_details_for(job_title_clean))
                patterns = [
                    os.path.join(job_details_path, f"{job_title_clean}_details_*.csv"),
                    os.path.join(job_details_path, f"{job_title_clean}_job_details_*.csv"),
                ]
                detail_files = []
                for pattern in patterns:
                    detail_files.extend(glob.glob(pattern))

                if not detail_files or df_in.empty:
                    return df_in

                detail_frames = []
                for file in detail_files:
                    try:
                        detail_df = pd.read_csv(file)
                        if 'job_url' in detail_df.columns:
                            detail_frames.append(
                                detail_df[['job_url', 'description', 'days_since_posted', 'application_url']]
                                .dropna(subset=['job_url'])
                            )
                    except Exception as e:
                        logging.warning(f"Error reading job details file {file}: {e}")

                if not detail_frames:
                    return df_in

                details_df = pd.concat(detail_frames, ignore_index=True)
                details_df['job_url'] = details_df['job_url'].astype(str)
                details_df = details_df.drop_duplicates(subset=['job_url'], keep='last')

                df_out = df_in.copy()
                df_out['job_url'] = df_out['job_url'].astype(str)

                merged = df_out.merge(details_df, on='job_url', how='left', suffixes=('', '_detail'))

                for col in ['description', 'application_url', 'days_since_posted']:
                    detail_col = f"{col}_detail"
                    if detail_col in merged.columns:
                        merged[col] = merged[col].where(
                            merged[col].notna() & (merged[col].astype(str).str.strip() != ''),
                            merged[detail_col]
                        )
                        merged = merged.drop(columns=[detail_col])

                return merged

            except Exception as e:
                logging.warning(f"Error enriching from job_details: {e}")
                return df_in

        # If new jobs are provided, process them
        new_jobs_added = 0
        if new_jobs_df is not None and not new_jobs_df.empty:
            # Add date_extracted column to new jobs if it doesn't exist
            new_jobs_df = new_jobs_df.copy()
            
            # Check if date_extracted column already exists
            if 'date_extracted' not in new_jobs_df.columns:
                new_jobs_df.insert(0, 'date_extracted', current_date)
            else:
                # Update existing date_extracted column with current date for new jobs
                new_jobs_df['date_extracted'] = current_date
            
            # Convert job_url to string for comparison
            new_jobs_df['job_url'] = new_jobs_df['job_url'].astype(str)

            # Enrich new jobs from job_details files if available
            new_jobs_df = enrich_from_job_details(new_jobs_df)
            
            if not master_df.empty:
                master_df['job_url'] = master_df['job_url'].astype(str)
                
                # Find new jobs (not in master file)
                existing_urls = set(master_df['job_url'].tolist())
                new_jobs_filtered = new_jobs_df[~new_jobs_df['job_url'].isin(existing_urls)]
                
                # Update existing jobs with new application_url and days_since_posted values
                update_columns = ['application_url', 'days_since_posted']
                jobs_updated = 0
                for col in update_columns:
                    if col in new_jobs_df.columns:
                        # Create a mapping from job_url to the new column value
                        url_to_value = dict(zip(new_jobs_df['job_url'], new_jobs_df[col]))
                        
                        # Ensure the column exists in master_df
                        if col not in master_df.columns:
                            master_df[col] = None
                        
                        # Update rows where we have new data and old data is missing/empty
                        for url, new_value in url_to_value.items():
                            if new_value and str(new_value).strip() and str(new_value) != 'nan':
                                mask = (master_df['job_url'] == url) & (
                                    master_df[col].isna() | 
                                    (master_df[col].astype(str).str.strip() == '') |
                                    (master_df[col].astype(str) == 'nan')
                                )
                                if mask.any():
                                    master_df.loc[mask, col] = new_value
                                    jobs_updated += 1
                
                if jobs_updated > 0:
                    logging.info(f"Updated {jobs_updated} existing jobs with new application_url/days_since_posted data")
                
                if not new_jobs_filtered.empty:
                    # Append new jobs to master
                    master_df = pd.concat([master_df, new_jobs_filtered], ignore_index=True)
                    new_jobs_added = len(new_jobs_filtered)
                    logging.info(f"Added {new_jobs_added} new unique jobs to master file")
                else:
                    logging.info("No new unique jobs to add")
            else:
                # First time creating master file
                master_df = new_jobs_df
                new_jobs_added = len(new_jobs_df)
                logging.info(f"Created new master file with {new_jobs_added} jobs")
        
        # Also process all existing CSV files in job_details directory to ensure completeness
        job_details_path = str(job_details_for(job_title_clean))
        if os.path.exists(job_details_path):
            patterns = [
                os.path.join(job_details_path, f"{job_title_clean}_details_*.csv"),
                os.path.join(job_details_path, f"{job_title_clean}_job_details_*.csv"),
            ]
            csv_files = []
            for pattern in patterns:
                csv_files.extend(glob.glob(pattern))
            
            for file in csv_files:
                try:
                    df = pd.read_csv(file)
                    df['job_url'] = df['job_url'].astype(str)
                    
                    # Add date_extracted if not present
                    if 'date_extracted' not in df.columns:
                        # Try to extract date from filename
                        import re
                        filename = os.path.basename(file)
                        date_match = re.search(r'(\d{8})', filename)
                        if date_match:
                            file_date = datetime.strptime(date_match.group(1), '%Y%m%d').strftime('%Y-%m-%d %H:%M:%S')
                            df.insert(0, 'date_extracted', file_date)
                        else:
                            df.insert(0, 'date_extracted', current_date)
                    
                    # Find jobs not in master
                    if not master_df.empty:
                        existing_urls = set(master_df['job_url'].tolist())
                        new_from_file = df[~df['job_url'].isin(existing_urls)]
                        
                        # Update existing jobs with new application_url and days_since_posted values
                        update_columns = ['application_url', 'days_since_posted']
                        for col in update_columns:
                            if col in df.columns:
                                url_to_value = dict(zip(df['job_url'], df[col]))
                                if col not in master_df.columns:
                                    master_df[col] = None
                                for url, new_value in url_to_value.items():
                                    if new_value and str(new_value).strip() and str(new_value) != 'nan':
                                        mask = (master_df['job_url'] == url) & (
                                            master_df[col].isna() | 
                                            (master_df[col].astype(str).str.strip() == '') |
                                            (master_df[col].astype(str) == 'nan')
                                        )
                                        if mask.any():
                                            master_df.loc[mask, col] = new_value
                        
                        if not new_from_file.empty:
                            master_df = pd.concat([master_df, new_from_file], ignore_index=True)
                            logging.info(f"Added {len(new_from_file)} jobs from {os.path.basename(file)}")
                    else:
                        master_df = df
                        logging.info(f"Initialized master file from {os.path.basename(file)}")
                        
                except Exception as e:
                    logging.error(f"Error processing file {file}: {e}")
                    continue
        
        # Final deduplication based on job_url
        if not master_df.empty:
            original_count = len(master_df)
            master_df = master_df.drop_duplicates(subset=['job_url'], keep='last')
            url_deduped_count = len(master_df)
            
            if original_count != url_deduped_count:
                logging.info(f"Removed {original_count - url_deduped_count} duplicate entries based on job_url")
            
            # NEW: Additional deduplication based on company + job title
            master_df = deduplicate_by_company_and_title(master_df, keep_strategy='latest')
            
            # Ensure required columns exist (add if missing)
            required_columns = ['application_url', 'days_since_posted']
            for col in required_columns:
                if col not in master_df.columns:
                    master_df[col] = None
                    logging.info(f"Added missing column '{col}' to aggregated file")
            
            # Enrich master with job_details data before saving
            master_df = enrich_from_job_details(master_df)

            # Sort by date_extracted (most recent first)
            master_df = master_df.sort_values('date_extracted', ascending=False)
            
            # Save master aggregated file
            master_df.to_csv(master_file, index=False)
            logging.info(f"Saved master aggregated file with {len(master_df)} unique jobs to: {master_file}")
            
            # Also save a copy with current date for this run
            run_file = os.path.join(aggregated_path, f"{job_title_clean}_aggregated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            master_df.to_csv(run_file, index=False)
            
            # NEW: Create salary-filtered version (excluding engineering jobs)
            try:
                salary_file = create_salary_filtered_aggregate(job_title, min_salary=175)
                if salary_file:
                    logging.info(f"Created salary-filtered aggregated file: {salary_file}")
                master_salary_file = build_master_salary_aggregate(job_title, min_salary=175)
                if master_salary_file:
                    logging.info(f"Created master salary aggregate file: {master_salary_file}")
            except Exception as e:
                logging.error(f"Error creating salary-filtered aggregate: {e}")
            
            # Create JSON version with metadata
            json_file = master_file.replace('.csv', '.json')
            df_json = master_df.copy()
            df_json = df_json.where(pd.notnull(df_json), None)
            
            # Convert datetime columns to strings
            for col in df_json.select_dtypes(include=['datetime64[ns]']).columns:
                df_json[col] = df_json[col].astype(str)
            
            output_data = {
                "metadata": {
                    "job_title": job_title_clean,
                    "timestamp": current_date,
                    "total_unique_jobs": len(master_df),
                    "new_jobs_added_this_run": new_jobs_added,
                    "last_updated": current_date,
                    "deduplication_strategy": "job_url + company_title_combination"
                },
                "jobs": df_json.to_dict('records')
            }
            
            with open(json_file, 'w', encoding='utf-8') as f:
                import json
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            logging.info(f"Saved JSON version to: {json_file}")
            
            # Rebuild the cross-title unified master CSV
            rebuild_unified_master()
            
            return master_file
        
        return None
        
    except Exception as e:
        logging.error(f"Error in aggregate_jobs_with_deduplication: {e}")
        raise


def rebuild_unified_master():
    """
    Rebuild the unified master CSV by concatenating every per-title
    master_aggregated CSV.  Adds a ``search_title`` column so rows
    remain traceable back to the search that produced them.

    Deduplicates on ``job_url`` (keeps latest) so the same posting
    found under multiple searches appears only once.

    Returns the path to the unified CSV, or *None* if no data exists.
    """
    try:
        agg_root = str(AGGREGATED_DIR)
        if not os.path.isdir(agg_root):
            logging.info("rebuild_unified_master: aggregated dir does not exist yet.")
            return None

        frames = []
        for title_dir in sorted(os.listdir(agg_root)):
            title_path = os.path.join(agg_root, title_dir)
            if not os.path.isdir(title_path):
                continue
            master_file = os.path.join(title_path, f"{title_dir}_master_aggregated.csv")
            if not os.path.isfile(master_file):
                continue
            try:
                df = pd.read_csv(master_file)
                if df.empty:
                    continue
                df["search_title"] = title_dir
                frames.append(df)
                logging.info("rebuild_unified_master: added %d rows from '%s'", len(df), title_dir)
            except Exception as e:
                logging.warning("rebuild_unified_master: error reading %s: %s", master_file, e)

        if not frames:
            logging.info("rebuild_unified_master: no per-title masters found.")
            return None

        unified = pd.concat(frames, ignore_index=True)

        # Deduplicate – same job_url across titles keeps the most-recent row
        if "job_url" in unified.columns:
            unified = unified.drop_duplicates(subset=["job_url"], keep="last")

        # Sort newest first
        if "date_extracted" in unified.columns:
            unified = unified.sort_values("date_extracted", ascending=False)

        os.makedirs(str(AGGREGATED_DIR), exist_ok=True)
        out_path = str(UNIFIED_MASTER_CSV)
        unified.to_csv(out_path, index=False)
        logging.info(
            "rebuild_unified_master: saved %d unique jobs → %s",
            len(unified), out_path,
        )
        return out_path

    except Exception as e:
        logging.error("rebuild_unified_master failed: %s", e)
        return None


def process_job_search_results(job_title):
    """
    Process all job search results for a given job title and create aggregated file.
    This function processes both the initial search results and detailed job information.
    """
    try:
        job_title_clean = job_title.lower().replace(' ', '_')
        
        # Process initial search results
        search_results_path = str(search_results_for(job_title_clean))
        if os.path.exists(search_results_path):
            # Find the most recent search results file
            pattern = os.path.join(search_results_path, f"{job_title_clean}__*.csv")
            csv_files = glob.glob(pattern)
            
            if csv_files:
                latest_file = max(csv_files, key=os.path.getctime)
                logging.info(f"Processing latest search results: {os.path.basename(latest_file)}")
                
                search_df = pd.read_csv(latest_file)
                
                # Add date_extracted column if it doesn't exist
                if 'date_extracted' not in search_df.columns:
                    search_df.insert(0, 'date_extracted', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                
                # Aggregate these results
                result_file = aggregate_jobs_with_deduplication(job_title, search_df)
                
                if result_file:
                    logging.info(f"Successfully processed search results for {job_title}")
                    return result_file
        
        # Also process detailed job information if available
        detailed_results_path = str(job_details_for(job_title_clean))
        if os.path.exists(detailed_results_path):
            patterns = [
                os.path.join(detailed_results_path, f"{job_title_clean}_details_*.csv"),
                os.path.join(detailed_results_path, f"{job_title_clean}_job_details_*.csv"),
            ]
            csv_files = []
            for pattern in patterns:
                csv_files.extend(glob.glob(pattern))
            
            if csv_files:
                # Get the most recent detailed results
                latest_file = max(csv_files, key=os.path.getctime)
                logging.info(f"Processing latest detailed results: {os.path.basename(latest_file)}")
                
                detailed_df = pd.read_csv(latest_file)
                
                # Add date_extracted column if it doesn't exist
                if 'date_extracted' not in detailed_df.columns:
                    detailed_df.insert(0, 'date_extracted', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                
                # Aggregate these results
                result_file = aggregate_jobs_with_deduplication(job_title, detailed_df)
                
                if result_file:
                    logging.info(f"Successfully processed detailed results for {job_title}")
                    return result_file
        
        # If no specific new data, just update the master file
        result_file = aggregate_jobs_with_deduplication(job_title)
        
        return result_file
        
    except Exception as e:
        logging.error(f"Error processing job search results: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description='Aggregate and deduplicate job search results')
    parser.add_argument('--job_title', help='Job title to process')
    parser.add_argument('--input_file', help='Specific CSV file to process (optional)')
    parser.add_argument('--rebuild_unified', action='store_true',
                        help='Only rebuild the unified master CSV (no per-title merge)')
    args = parser.parse_args()
    
    try:
        if args.rebuild_unified:
            unified = rebuild_unified_master()
            if unified:
                logging.info(f"Unified master rebuilt: {unified}")
            else:
                logging.warning("No per-title data to unify.")
            return

        if not args.job_title:
            parser.error("--job_title is required unless --rebuild_unified is set")

        if args.input_file:
            # Process specific input file
            if os.path.exists(args.input_file):
                df = pd.read_csv(args.input_file)
                result_file = aggregate_jobs_with_deduplication(args.job_title, df)
            else:
                logging.error(f"Input file not found: {args.input_file}")
                return
        else:
            # Process all results for the job title
            result_file = process_job_search_results(args.job_title)
        
        if result_file:
            logging.info(f"Job aggregation completed successfully. Output: {result_file}")
        else:
            logging.warning("No aggregation was performed")
            
    except Exception as e:
        logging.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    main()