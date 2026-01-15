/**
 * Type definitions for the llmstxt web app
 */

export type Template = 'charity' | 'funder' | 'public_sector' | 'startup';

export type Tier = 'free' | 'paid' | 'subscription';

export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface GenerateRequest {
  url: string;
  template: Template;
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
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
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
