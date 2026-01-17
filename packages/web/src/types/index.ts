/**
 * Type definitions for the llmstxt web app
 */

export type Template = 'charity' | 'funder' | 'public_sector' | 'startup';

export type Tier = 'free' | 'paid' | 'subscription';

export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed';

// Sector and Goal types
export interface SectorOption {
  id: string;
  label: string;
  description: string;
}

export interface GoalOption {
  id: string;
  label: string;
}

export interface TemplateOptions {
  template: Template;
  sectors: SectorOption[];
  goals: GoalOption[];
  default_sector: string;
  default_goal: string;
}

export interface GenerateRequest {
  url: string;
  template: Template;
  sector?: string;
  goal?: string;
  customer_email?: string;
}

export interface GeneratePaidRequest extends GenerateRequest {
  payment_intent_id: string;
}

export type ProgressStage = 'crawling' | 'extracting' | 'enriching' | 'analyzing' | 'generating' | 'assessing' | 'completed' | 'failed';

export interface Job {
  job_id: string;
  status: JobStatus;
  url: string;
  template: Template;
  sector?: string;
  goal?: string;
  tier: Tier;
  created_at: string;
  completed_at?: string;
  expires_at?: string;
  // Progress tracking
  progress_stage?: ProgressStage;
  progress_detail?: string;
  pages_crawled?: number;
  total_pages?: number;
  // Results
  llmstxt_content?: string;
  assessment_json?: Assessment;
  error_message?: string;
}

export interface Assessment {
  overall_score: number;
  completeness_score: number;
  quality_score: number;
  grade: string;
  findings: AssessmentFinding[];
  recommendations: string[];
  sections?: SectionAssessment[];
  website_gaps?: WebsiteGaps;
}

export interface AssessmentFinding {
  category: string;
  severity: 'critical' | 'major' | 'high' | 'medium' | 'minor' | 'low' | 'info';
  message: string;
  suggestion?: string;
}

export interface SectionAssessment {
  name: string;
  present: boolean;
  quality?: string;
  issues: string[];
}

export interface WebsiteGaps {
  missing_page_types: string[];
  has_sitemap: boolean;
  suggested_pages?: string[];
  crawl_coverage?: number;
}

export interface PaymentIntent {
  client_secret: string;
  amount: number;
  currency: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
}

// Subscription types
export interface Subscription {
  id: string;
  url: string;
  template: Template;
  sector?: string;
  goal?: string;
  frequency: 'weekly' | 'monthly';
  active: boolean;
  last_check?: string;
  last_change_detected?: string;
  created_at: string;
  cancelled_at?: string;
}

export interface SubscriptionCreateRequest {
  url: string;
  template: Template;
  sector?: string;
  goal?: string;
  email?: string;
  success_url: string;
  cancel_url: string;
}

export interface CheckoutSession {
  session_id: string;
  checkout_url: string;
}

export interface MonitoringHistory {
  id: string;
  subscription_id: string;
  checked_at: string;
  changed: boolean;
  llmstxt_content?: string;
  assessment_json?: Assessment;
  notification_sent: boolean;
}

// Auth types
export interface User {
  id: string;
  email: string;
  created_at: string;
  stripe_customer_id?: string;
}

export interface AuthResponse {
  user: User;
  message: string;
}

export interface AuthCheckResponse {
  authenticated: boolean;
  user: User | null;
}

export interface MagicLinkResponse {
  message: string;
  email: string;
}

// Dismiss findings types
export interface DismissFindingsRequest {
  dismissed_indices: number[];
}

export interface RecalculatedScoreResponse {
  overall_score: number;
  completeness_score: number;
  quality_score: number;
  grade: string;
  dismissed_count: number;
  remaining_findings: AssessmentFinding[];
}
