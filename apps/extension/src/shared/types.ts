// ── Shared Types ─────────────────────────────────────────────────────────────

export interface PersonalInfo {
  full_name?: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  preferred_name?: string;
  zip_code?: string;
  city?: string;
  linkedin_profile?: string;
  location?: string;
}

export interface DatePart {
  month?: string;
  year?: string;
}

export interface WorkExperience {
  job_title: string;
  company: string;
  location?: string;
  from?: DatePart;
  to?: DatePart;
  currently_work_here: boolean;
  role_description: string;
}

export interface Education {
  school_or_university: string;
  degree: string;
  field_of_study: string;
  from?: DatePart;
  to?: DatePart;
  gpa?: string;
}

export interface ResumeComponents {
  personal_info: PersonalInfo;
  professional_summary: string;
  work_experience: WorkExperience[];
  education: Education[];
  skills: string[];
  accomplishments?: Array<{
    company?: string;
    type?: string;
    description: string;
  }>;
}

export interface UserConfig {
  personal_info: Record<string, string>;
  application_info: Record<string, string>;
  work_authorization: Record<string, unknown>;
  voluntary_disclosures: Record<string, unknown>;
  custom_answers: Record<string, string>;
}

export interface JobMatch {
  id: string;
  job_title: string;
  company_title: string;
  application_url: string | null;
  job_url: string | null;
  alignment_score: number | null;
  alignment_grade: string | null;
  optimized_resume_id: string | null;
  has_optimized_resume: boolean;
  application_status: string | null;
}

export interface ApplicationLogPayload {
  job_id: string;
  board_type: string;
  method: "extension_auto_fill" | "manual";
  status: "filled" | "submitted" | "failed" | "partial";
  fields_filled: number | null;
  fields_total: number | null;
  error_message?: string;
  optimized_resume_id?: string;
}

export interface FillResult {
  fieldsTotal: number;
  fieldsFilled: number;
  errors: string[];
  steps: FillStep[];
}

export interface FillStep {
  name: string;
  status: "pending" | "filling" | "done" | "skipped" | "error";
  fieldsTotal?: number;
  fieldsFilled?: number;
  error?: string;
}

export interface BoardFeatures {
  auto_fill_supported: boolean;
  file_upload_supported: boolean;
  custom_questions: boolean;
  requires_manual_review: boolean;
}

// ── Message Types ────────────────────────────────────────────────────────────

export type MessageType =
  | "AUTH_SET_TOKEN"
  | "AUTH_GET_STATUS"
  | "AUTH_LOGOUT"
  | "API_GET_PROFILE"
  | "API_LOOKUP_JOB_BY_URL"
  | "API_GET_OPTIMIZED_RESUME"
  | "API_DOWNLOAD_RESUME_PDF"
  | "API_OPTIMIZE_RESUME"
  | "API_LOG_APPLICATION"
  | "API_UPDATE_JOB_STATUS"
  | "API_GET_JOBS"
  | "NOTIFICATIONS_GET_COUNT"
  | "NOTIFICATIONS_MARK_READ"
  | "CACHE_INVALIDATE";

export interface ExtensionMessage {
  type: MessageType;
  [key: string]: unknown;
}

export interface AuthSetTokenPayload {
  token: string;
  refreshToken: string;
  expiresAt: number;
}

export interface AuthStatus {
  authenticated: boolean;
  email?: string;
  fullName?: string;
}
