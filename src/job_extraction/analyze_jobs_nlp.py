import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import json
import logging
from collections import Counter
from datetime import datetime
import re
import argparse
from pathlib import Path

from paths import JOB_DETAILS_DIR, ANALYSIS_DIR

# NLP libraries
import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tag import pos_tag



# python3 ./job_search/job_extraction/analyze_jobs_nlp.py

# Download required NLTK data (only needed once)
try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab', quiet=True)

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

try:
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('wordnet', quiet=True)

try:
    nltk.data.find('taggers/averaged_perceptron_tagger_eng')
except LookupError:
    nltk.download('averaged_perceptron_tagger_eng', quiet=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class JobAnalyzer:
    def __init__(self):
        self.stop_words = set(stopwords.words('english'))
        self.lemmatizer = WordNetLemmatizer()
        # Add custom stop words relevant to job postings
        self.custom_stop_words = {
            'job', 'position', 'role', 'work', 'team', 'company', 'business',
            'include', 'including', 'additionally', 'also', 'able', 'ability',
            'experience', 'experiences', 'required', 'require', 'requirements',
            'skills', 'skill', 'knowledge', 'preferred', 'prefer'
        }
        self.stop_words.update(self.custom_stop_words)
        
        # Define stop phrases (low-value phrases to filter out)
        self.stop_phrases = {
            'color religion', 'please note', 'tools like', 'high quality',
            'united states', 'equal opportunity', 'note please', 'like tools',
            'opportunity employer', 'employer equal', 'religion color',
            'race color', 'disability veteran', 'veteran status', 'status age',
            'age national', 'national origin', 'origin sex', 'sex sexual',
            'sexual orientation', 'orientation gender', 'gender identity',
            'identity protected', 'protected veteran', 'veteran equal',
            'tools include', 'include tools', 'etc tools', 'tools etc',
            'variety tools', 'different tools', 'available tools',
            'may include', 'include working', 'working variety', 'variety tools',
            'internal tools', 'external tools', 'proprietary tools'
        }
        
        # Define category keywords for phrase classification
        self.category_keywords = {
            'technical_skill': {
                'python', 'sql', 'r', 'excel', 'tableau', 'power bi', 'looker',
                'javascript', 'java', 'scala', 'spark', 'hadoop', 'cloud',
                'aws', 'azure', 'gcp', 'snowflake', 'databricks', 'dbt',
                'api', 'rest', 'machine learning', 'ml', 'deep learning',
                'statistics', 'statistical', 'predictive', 'modeling',
                'etl', 'data pipeline', 'data warehouse', 'database',
                'github', 'git', 'docker', 'kubernetes', 'linux'
            },
            'analytics_function': {
                'data analysis', 'data analytics', 'business intelligence',
                'reporting', 'dashboard', 'kpi', 'metrics', 'tracking',
                'forecasting', 'trend analysis', 'ad hoc', 'ad hoc analysis',
                'data visualization', 'visualization', 'insights', 'insight',
                'a/b testing', 'experimentation', 'analytical', 'analysis',
                'exploratory analysis', 'statistical analysis', 'data mining'
            },
            'soft_skill': {
                'communication', 'collaboration', 'teamwork', 'leadership',
                'problem solving', 'critical thinking', 'time management',
                'self motivated', 'proactive', 'curious', 'creative',
                'attention detail', 'detail oriented', 'analytical thinking',
                'interpersonal', 'presentation', 'storytelling', 'influence',
                'stakeholder management'
            },
            'data_management': {
                'data quality', 'data governance', 'data cleaning',
                'data integrity', 'data validation', 'data modeling',
                'data architecture', 'master data', 'reference data',
                'data catalog', 'metadata', 'data privacy', 'gdpr'
            },
            'domain_expertise': {
                'marketing', 'sales', 'finance', 'revenue', 'customer',
                'product', 'operations', 'supply chain', 'logistics',
                'healthcare', 'pharma', 'retail', 'ecommerce',
                'digital marketing', 'advertising', 'campaign',
                'customer acquisition', 'retention', 'lifetime value',
                'crm', 'seo', 'sem', 'ppc', 'social media'
            },
            'methodology_approach': {
                'agile', 'scrum', 'waterfall', 'sdlc', 'ci/cd',
                'lean', 'six sigma', 'design thinking', 'user research',
                'experimentation', 'hypothesis testing', 'scientific method'
            }
        }
        
    def preprocess_text(self, text):
        """Clean and preprocess text."""
        if pd.isna(text) or text == '-':
            return ''
        
        # Convert to string and lowercase
        text = str(text).lower()
        
        # Remove special characters but keep spaces and hyphens
        text = re.sub(r'[^\w\s\-]', ' ', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text
    
    def extract_skills_and_phrases(self, text):
        """Extract meaningful phrases and terms from text."""
        if not text:
            return []
        
        processed_text = self.preprocess_text(text)
        if not processed_text:
            return []
        
        # Tokenize
        tokens = word_tokenize(processed_text)
        
        # Remove stop words
        tokens = [token for token in tokens if token not in self.stop_words and len(token) > 2]
        
        # POS tagging
        pos_tags = pos_tag(tokens)
        
        # Extract important phrases and terms
        important_terms = []
        
        # Extract noun phrases (NN, NNS, NNPS, NNP)
        nouns = [word for word, pos in pos_tags if pos.startswith('N')]
        important_terms.extend(nouns)
        
        # Extract adjective-noun combinations
        for i in range(len(pos_tags) - 1):
            word1, pos1 = pos_tags[i]
            word2, pos2 = pos_tags[i + 1]
            if pos1.startswith('J') and pos2.startswith('N'):
                important_terms.append(f"{word1} {word2}")
        
        # Extract consecutive nouns (multi-word skills)
        consecutive_nouns = []
        temp_phrase = []
        for word, pos in pos_tags:
            if pos.startswith('N'):
                temp_phrase.append(word)
            else:
                if len(temp_phrase) >= 2:
                    consecutive_nouns.append(' '.join(temp_phrase))
                temp_phrase = []
        if len(temp_phrase) >= 2:
            consecutive_nouns.append(' '.join(temp_phrase))
        
        important_terms.extend(consecutive_nouns)
        
        # Lemmatize terms
        lemmatized_terms = []
        for term in important_terms:
            words = term.split()
            if len(words) == 1:
                lemmatized = self.lemmatizer.lemmatize(term)
                if len(lemmatized) > 2:
                    lemmatized_terms.append(lemmatized)
            else:
                lemmatized_terms.append(term)
        
        return lemmatized_terms
    
    def extract_key_phrases(self, text, min_length=3, max_length=4):
        """Extract key phrases of specific length."""
        if not text:
            return []
        
        processed_text = self.preprocess_text(text)
        if not processed_text:
            return []
        
        tokens = word_tokenize(processed_text)
        tokens = [token for token in tokens if token not in self.stop_words and len(token) > 2]
        
        # Generate n-grams
        phrases = []
        for n in range(min_length, max_length + 1):
            for i in range(len(tokens) - n + 1):
                phrase = ' '.join(tokens[i:i+n])
                phrases.append(phrase)
        
        return phrases
    
    def is_valuable_phrase(self, phrase):
        """Check if a phrase is valuable (not in stop phrases list)."""
        if not phrase:
            return False
        
        phrase_lower = phrase.lower().strip()
        
        # Check against stop phrases
        if phrase_lower in self.stop_phrases:
            return False
        
        # Check if phrase starts with stop phrases
        for stop_phrase in self.stop_phrases:
            if phrase_lower.startswith(stop_phrase) or stop_phrase in phrase_lower:
                return False
        
        # Filter out very short phrases
        if len(phrase_lower) < 4:
            return False
        
        # Filter out phrases with too many common words
        words = phrase_lower.split()
        if len(words) > 5:
            return False
        
        # Must contain at least one meaningful word
        meaningful_words = [w for w in words if len(w) > 3 and w not in self.stop_words]
        if len(meaningful_words) == 0:
            return False
        
        return True
    
    def classify_phrase(self, phrase):
        """Classify a phrase into a category."""
        if not phrase:
            return 'uncategorized'
        
        phrase_lower = phrase.lower().strip()
        
        # Check each category
        for category, keywords in self.category_keywords.items():
            for keyword in keywords:
                # Check if keyword appears in the phrase
                if keyword in phrase_lower or phrase_lower in keyword:
                    return category
        
        return 'uncategorized'
    
    def filter_and_classify_phrases(self, phrases):
        """Filter out low-value phrases and classify the rest."""
        classified = {
            'technical_skill': Counter(),
            'analytics_function': Counter(),
            'soft_skill': Counter(),
            'data_management': Counter(),
            'domain_expertise': Counter(),
            'methodology_approach': Counter(),
            'uncategorized': Counter()
        }
        
        filtered_out = 0
        
        for phrase, count in phrases.items():
            if self.is_valuable_phrase(phrase):
                category = self.classify_phrase(phrase)
                classified[category][phrase] = count
            else:
                filtered_out += count
        
        logging.info(f"Filtered out {filtered_out} low-value phrase occurrences")
        
        return classified
    
    def analyze_job_postings(self, df):
        """Analyze a DataFrame of job postings."""
        results = {
            'job_titles': Counter(),
            'job_descriptions': Counter(),
            'companies': Counter(),
            'locations': Counter(),
            'skills': Counter(),
            'phrases': Counter(),
            'bigrams': Counter(),
            'trigrams': Counter(),
            'total_jobs': len(df)
        }
        
        logging.info(f"Analyzing {len(df)} job postings...")
        
        for idx, row in df.iterrows():
            # Analyze job title
            if 'job_title' in row and pd.notna(row['job_title']):
                title_terms = self.extract_skills_and_phrases(row['job_title'])
                results['job_titles'].update(title_terms)
            
            # Analyze job description
            if 'description' in row and pd.notna(row['description']):
                desc_terms = self.extract_skills_and_phrases(row['description'])
                results['job_descriptions'].update(desc_terms)
                
                # Extract key phrases
                phrases = self.extract_key_phrases(row['description'], min_length=2, max_length=3)
                results['phrases'].update(phrases)
            
            # Count companies
            if 'company' in row and pd.notna(row['company']):
                company = str(row['company']).strip()
                if company and company != '-':
                    results['companies'][company] += 1
            elif 'company_title' in row and pd.notna(row['company_title']):
                company = str(row['company_title']).strip()
                if company and company != '-':
                    results['companies'][company] += 1
            
            # Count locations
            if 'location' in row and pd.notna(row['location']):
                location = str(row['location']).strip()
                if location and location != '-':
                    results['locations'][location] += 1
        
        return results
    
    def merge_results(self, all_results):
        """Merge results from multiple files."""
        merged = {
            'job_titles': Counter(),
            'job_descriptions': Counter(),
            'companies': Counter(),
            'locations': Counter(),
            'skills': Counter(),
            'phrases': Counter(),
            'bigrams': Counter(),
            'trigrams': Counter(),
            'total_jobs': 0
        }
        
        for result in all_results:
            for key in merged:
                if key == 'total_jobs':
                    merged[key] += result.get(key, 0)
                else:
                    merged[key] += result.get(key, Counter())
        
        # Filter and classify phrases
        logging.info("Filtering and classifying phrases...")
        classified_phrases = self.filter_and_classify_phrases(merged['phrases'])
        
        # Add classified phrases to merged results
        for category, counter in classified_phrases.items():
            merged[f'phrases_{category}'] = counter
        
        return merged
    
    def save_results(self, results, output_dir, job_title, processed_files_current_run=None):
        """Save analysis results to JSON and CSV."""
        job_title_clean = job_title.lower().replace(' ', '_')
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Convert counters to dictionaries for JSON serialization
        results_dict = {}
        for key, value in results.items():
            if isinstance(value, Counter):
                results_dict[key] = dict(value.most_common())
            else:
                results_dict[key] = value
        
        # Save JSON with full results (timestamped)
        json_file = os.path.join(output_dir, f"{job_title_clean}_analysis_{timestamp}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results_dict, f, indent=2, ensure_ascii=False)
        
        logging.info(f"Saved detailed analysis to: {json_file}")
        
        # Load and merge with cumulative master file
        master_json_file = os.path.join(output_dir, f"{job_title_clean}_cumulative_analysis.json")
        cumulative_results = None
        processed_files_tracker = os.path.join(output_dir, f"{job_title_clean}_processed_files.json")
        
        if os.path.exists(master_json_file):
            try:
                with open(master_json_file, 'r', encoding='utf-8') as f:
                    cumulative_results = json.load(f)
                logging.info(f"Loaded existing cumulative analysis from: {master_json_file}")
            except Exception as e:
                logging.error(f"Error loading cumulative analysis: {e}")
                cumulative_results = None
        
        # Load list of previously processed files
        previously_processed = set()
        if os.path.exists(processed_files_tracker):
            try:
                with open(processed_files_tracker, 'r', encoding='utf-8') as f:
                    previously_processed = set(json.load(f))
                logging.info(f"Loaded {len(previously_processed)} previously processed files")
            except Exception as e:
                logging.warning(f"Error loading processed files tracker: {e}")
        
        # Filter out already processed files from current run
        skip_cumulative_update = False
        if processed_files_current_run:
            new_files = [f for f in processed_files_current_run if f not in previously_processed]
            if new_files:
                logging.info(f"Processing {len(new_files)} new files out of {len(processed_files_current_run)} total")
                previously_processed.update(new_files)
            else:
                logging.info("No new files to process, skipping cumulative update to avoid double-counting")
                skip_cumulative_update = True
        
        # Merge with cumulative results only if we have new files
        if skip_cumulative_update:
            # Don't update cumulative if no new files
            cumulative_results = json.load(open(master_json_file, 'r')) if os.path.exists(master_json_file) else results_dict.copy()
            logging.info("Skipping cumulative update - no new files")
        elif cumulative_results:
            # Merge the results only if we have new files
            for key in results_dict:
                if key == 'total_jobs':
                    # Sum total jobs
                    cumulative_results[key] = cumulative_results.get(key, 0) + results_dict[key]
                else:
                    # Merge counters (handles both regular and categorized phrases)
                    cumulative_counter = Counter(cumulative_results.get(key, {}))
                    current_counter = Counter(results_dict[key])
                    merged_counter = cumulative_counter + current_counter
                    cumulative_results[key] = dict(merged_counter.most_common())
            
            logging.info(f"Merging with cumulative analysis (total jobs: {cumulative_results['total_jobs']})")
        else:
            # First time, so cumulative is same as current
            cumulative_results = results_dict.copy()
            logging.info("Creating new cumulative analysis")
        
        # Save cumulative results
        cumulative_results['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cumulative_results['analysis_count'] = cumulative_results.get('analysis_count', 0) + 1
        
        with open(master_json_file, 'w', encoding='utf-8') as f:
            json.dump(cumulative_results, f, indent=2, ensure_ascii=False)
        
        logging.info(f"Saved cumulative analysis to: {master_json_file}")
        
        # Save CSV files for top terms
        csv_dir = os.path.join(output_dir, "analysis_reports")
        os.makedirs(csv_dir, exist_ok=True)
        
        csv_files = {}
        
        # Top terms from job titles
        top_titles = results['job_titles'].most_common(100)
        if top_titles:
            df_titles = pd.DataFrame(top_titles, columns=['Term', 'Count'])
            csv_file = os.path.join(csv_dir, f"{job_title_clean}_top_title_terms.csv")
            df_titles.to_csv(csv_file, index=False)
            csv_files['title_terms'] = csv_file
        
        # Top terms from descriptions
        top_descriptions = results['job_descriptions'].most_common(200)
        if top_descriptions:
            df_descriptions = pd.DataFrame(top_descriptions, columns=['Term', 'Count'])
            csv_file = os.path.join(csv_dir, f"{job_title_clean}_top_description_terms.csv")
            df_descriptions.to_csv(csv_file, index=False)
            csv_files['description_terms'] = csv_file
        
        # Top phrases
        top_phrases = results['phrases'].most_common(200)
        if top_phrases:
            df_phrases = pd.DataFrame(top_phrases, columns=['Phrase', 'Count'])
            csv_file = os.path.join(csv_dir, f"{job_title_clean}_top_phrases.csv")
            df_phrases.to_csv(csv_file, index=False)
            csv_files['phrases'] = csv_file
        
        # Top companies
        top_companies = results['companies'].most_common(50)
        if top_companies:
            df_companies = pd.DataFrame(top_companies, columns=['Company', 'Count'])
            csv_file = os.path.join(csv_dir, f"{job_title_clean}_top_companies.csv")
            df_companies.to_csv(csv_file, index=False)
            csv_files['companies'] = csv_file
        
        # Top locations
        top_locations = results['locations'].most_common(50)
        if top_locations:
            df_locations = pd.DataFrame(top_locations, columns=['Location', 'Count'])
            csv_file = os.path.join(csv_dir, f"{job_title_clean}_top_locations.csv")
            df_locations.to_csv(csv_file, index=False)
            csv_files['locations'] = csv_file
        
        logging.info(f"Saved CSV reports to: {csv_dir}")
        
        # Also save cumulative CSV reports
        cumulative_csv_files = {}
        
        # Convert cumulative results back to counters for CSV generation
        cumulative_titles = Counter(cumulative_results.get('job_titles', {}))
        cumulative_descriptions = Counter(cumulative_results.get('job_descriptions', {}))
        cumulative_phrases = Counter(cumulative_results.get('phrases', {}))
        cumulative_companies = Counter(cumulative_results.get('companies', {}))
        cumulative_locations = Counter(cumulative_results.get('locations', {}))
        
        # Save cumulative top title terms
        top_titles_cum = cumulative_titles.most_common(100)
        if top_titles_cum:
            df_titles = pd.DataFrame(top_titles_cum, columns=['Term', 'Count'])
            csv_file = os.path.join(csv_dir, f"{job_title_clean}_cumulative_top_title_terms.csv")
            df_titles.to_csv(csv_file, index=False)
            cumulative_csv_files['cumulative_title_terms'] = csv_file
        
        # Save cumulative top description terms
        top_descriptions_cum = cumulative_descriptions.most_common(200)
        if top_descriptions_cum:
            df_descriptions = pd.DataFrame(top_descriptions_cum, columns=['Term', 'Count'])
            csv_file = os.path.join(csv_dir, f"{job_title_clean}_cumulative_top_description_terms.csv")
            df_descriptions.to_csv(csv_file, index=False)
            cumulative_csv_files['cumulative_description_terms'] = csv_file
        
        # Save cumulative top phrases
        top_phrases_cum = cumulative_phrases.most_common(200)
        if top_phrases_cum:
            df_phrases = pd.DataFrame(top_phrases_cum, columns=['Phrase', 'Count'])
            csv_file = os.path.join(csv_dir, f"{job_title_clean}_cumulative_top_phrases.csv")
            df_phrases.to_csv(csv_file, index=False)
            cumulative_csv_files['cumulative_phrases'] = csv_file
        
        # Save cumulative top companies
        top_companies_cum = cumulative_companies.most_common(50)
        if top_companies_cum:
            df_companies = pd.DataFrame(top_companies_cum, columns=['Company', 'Count'])
            csv_file = os.path.join(csv_dir, f"{job_title_clean}_cumulative_top_companies.csv")
            df_companies.to_csv(csv_file, index=False)
            cumulative_csv_files['cumulative_companies'] = csv_file
        
        # Save cumulative top locations
        top_locations_cum = cumulative_locations.most_common(50)
        if top_locations_cum:
            df_locations = pd.DataFrame(top_locations_cum, columns=['Location', 'Count'])
            csv_file = os.path.join(csv_dir, f"{job_title_clean}_cumulative_top_locations.csv")
            df_locations.to_csv(csv_file, index=False)
            cumulative_csv_files['cumulative_locations'] = csv_file
        
        logging.info(f"Saved cumulative CSV reports to: {csv_dir}")
        
        # Save categorized phrase CSV files (for current run)
        categorized_csv_files = {}
        for category in ['technical_skill', 'analytics_function', 'soft_skill', 
                        'data_management', 'domain_expertise', 'methodology_approach', 'uncategorized']:
            key = f'phrases_{category}'
            if key in results:
                top_cat = results[key].most_common(100)
                if top_cat:
                    df_cat = pd.DataFrame(top_cat, columns=['Phrase', 'Count'])
                    csv_file = os.path.join(csv_dir, f"{job_title_clean}_phrases_{category}.csv")
                    df_cat.to_csv(csv_file, index=False)
                    categorized_csv_files[f'phrases_{category}'] = csv_file
        
        # Save cumulative categorized phrase CSV files
        cumulative_categorized_csv_files = {}
        for category in ['technical_skill', 'analytics_function', 'soft_skill',
                        'data_management', 'domain_expertise', 'methodology_approach', 'uncategorized']:
            key = f'phrases_{category}'
            if key in cumulative_results:
                cumulative_cat = Counter(cumulative_results[key])
                top_cat_cum = cumulative_cat.most_common(100)
                if top_cat_cum:
                    df_cat = pd.DataFrame(top_cat_cum, columns=['Phrase', 'Count'])
                    csv_file = os.path.join(csv_dir, f"{job_title_clean}_cumulative_phrases_{category}.csv")
                    df_cat.to_csv(csv_file, index=False)
                    cumulative_categorized_csv_files[f'cumulative_phrases_{category}'] = csv_file
        
        logging.info(f"Saved categorized phrase reports to: {csv_dir}")
        
        # Save the updated processed files tracker
        if processed_files_current_run:
            with open(processed_files_tracker, 'w', encoding='utf-8') as f:
                json.dump(sorted(list(previously_processed)), f, indent=2)
            logging.info(f"Updated processed files tracker with {len(previously_processed)} files")
        
        return json_file, csv_files, cumulative_csv_files, categorized_csv_files, cumulative_categorized_csv_files

def analyze_job_post_details(job_title=None):
    """
    Analyze all job postings in the job_post_details folder.
    
    Args:
        job_title (str, optional): Specific job title to analyze. If None, analyzes all.
    
    Returns:
        dict: Analysis results
    """
    try:
        analyzer = JobAnalyzer()
        
        base_path = str(JOB_DETAILS_DIR)
        
        if not os.path.exists(base_path):
            logging.error(f"Job post details directory not found: {base_path}")
            return None
        
        all_results = []
        processed_files = []
        
        # Process each job title directory
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            
            # Skip if not a directory
            if not os.path.isdir(item_path):
                continue
            
            # Skip aggregated directories
            if item.startswith('.'):
                continue
            
            # If specific job title provided, only process that one
            if job_title:
                job_title_clean = job_title.lower().replace(' ', '_')
                if item != job_title_clean:
                    continue
            
            job_details_dir = item_path  # In new structure, each subdir IS the job_details dir
            
            if not os.path.exists(job_details_dir):
                logging.warning(f"No job_details directory found for: {item}")
                continue
            
            # Process all CSV files in job_details directory
            for file in os.listdir(job_details_dir):
                if file.endswith('.csv'):
                    file_path = os.path.join(job_details_dir, file)
                    
                    try:
                        df = pd.read_csv(file_path)
                        logging.info(f"Processing file: {file_path}")
                        
                        results = analyzer.analyze_job_postings(df)
                        all_results.append(results)
                        processed_files.append(file_path)
                        
                    except Exception as e:
                        logging.error(f"Error processing file {file_path}: {e}")
                        continue
        
        if not all_results:
            logging.warning("No job postings found to analyze")
            return None
        
        # Merge all results
        logging.info("Merging results from all files...")
        merged_results = analyzer.merge_results(all_results)
        
        # Determine output job title
        output_job_title = job_title if job_title else "all_jobs"
        
        # Save results
        output_dir = str(ANALYSIS_DIR)
        json_file, csv_files, cumulative_csv_files, categorized_csv_files, cumulative_categorized_csv_files = analyzer.save_results(merged_results, output_dir, output_job_title, processed_files)
        
        logging.info(f"Analysis complete! Processed {len(processed_files)} files")
        logging.info(f"Total jobs analyzed: {merged_results['total_jobs']}")
        
        return {
            'results': merged_results,
            'json_file': json_file,
            'csv_files': csv_files,
            'cumulative_csv_files': cumulative_csv_files,
            'categorized_csv_files': categorized_csv_files,
            'cumulative_categorized_csv_files': cumulative_categorized_csv_files,
            'processed_files': processed_files
        }
        
    except Exception as e:
        logging.error(f"Error analyzing job post details: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description='Analyze job postings using NLP')
    parser.add_argument('--job_title', help='Specific job title to analyze (optional)')
    args = parser.parse_args()
    
    try:
        results = analyze_job_post_details(args.job_title)
        
        if results:
            logging.info("Analysis completed successfully!")
            logging.info(f"JSON file: {results['json_file']}")
            logging.info(f"Current CSV files: {results['csv_files']}")
            logging.info(f"Cumulative CSV files: {results['cumulative_csv_files']}")
            logging.info(f"Categorized phrase files: {results['categorized_csv_files']}")
            logging.info(f"Cumulative categorized phrase files: {results['cumulative_categorized_csv_files']}")
        else:
            logging.warning("No results generated")
            
    except Exception as e:
        logging.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    main()