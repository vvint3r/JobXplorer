## Task 1
### Sub-Task: A
### Status: In Progress
### Description /
Extract job Description / variables for base resume optimization (located in the directory 'job_search/auto_application/resumes/base_resume'); the variables (as a starting point - this can be expanded where more labeling can be created) are located under 'job_search/auto_application/jd_variables_extraction_glossary.md'. This functionality should extract the variables that are to be used to optimize the resume in a folder where each job's outputs will be stored in a separate .md file with a starting ID of 1 (increment for each new file) alongside the company name and job title in the file name - ending with the date of extraction in the format YYYMMDD.


### Sub-Task: B
### Status: Not Started
### Description /
Update the base resume with the extracted variables for the job defined in Sub-Task A; create a file for the resume with the same file name but extended with _ro (resume optimized). Please utilize the best and most reliable approach for this task as it will be the resume that is utilized for the job application.

### Sub-Task: C
### Status: Not Started
### Description /
Add a CLI helper to batch-run JD variable extraction against a job_details CSV (pick rows by index or filter) and drop markdown outputs into the variables_extracted folder.

### Sub-Task: D
### Status: Not Started
### Description /
Add lightweight tests/fixtures for the extractor (LLM mocked) to keep schemas stable and prevent regressions.

---

## Task 2
### Status: Not Started
### Description /
Make the search pipeline non-interactive by allowing CLI flags/env for salary range, job type, and geography (fall back to prompts).

---
## Task 3
### Status: Not Started
### Description /
Add resilience to LinkedIn auth: detect missing/expired cookies early and prompt/guide manual refresh; optionally support username/password + MFA token for automation.

---
## Task 4
### Status: Not Started
### Description /
Harden apply-link extraction: cap retries, add structured outputs for failure reasons, and unit-test selectors against saved HTML in debug_snapshots.

---
## Task 5
### Status: Not Started
### Description /
Streamline aggregation: consider writing master + salary-filtered JSON/CSV in one place and exposing a latest-artifacts pointer for downstream steps.

---
## Task 6
### Status: Not Started
### Description /
Auto-apply safety: add a dry-run flag that stops before form submission but captures field mappings; expand form fillers for Lever/Workday edge cases.
Add Simplify-assisted manual autofill mode with timeout logging (Timed Out entries re-runnable).

---
## Task 7
### Status: Not Started
### Description /
Observability: centralize logs (per run folders) and add a lightweight status dashboard summarizing counts, failures, and where to resume.

---
## Task 8
### Status: Not Started
### Description /
Create a validation screenshot capture function to take screenshots of the application process as it moves through the process of each job and store it in a folder for checking the status of each step.

---
## Task 9
### Status: Not Started
### Description /
Create a stats summary page to report and visualize various metrics related to the user's relative job field and the users actions over various date ranges (ex. today, this week, last week, this month, last month, last 3 months, YTD).