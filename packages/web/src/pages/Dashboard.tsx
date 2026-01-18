import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams, Navigate } from 'react-router-dom';
import {
  CheckCircle2,
  XCircle,
  Calendar,
  Globe,
  Loader2,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  TrendingUp,
  Bell,
  Clock,
  ExternalLink,
  Download,
  Activity,
  Award,
  Timer,
} from 'lucide-react';
import apiClient from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import SEOHead from '../components/SEOHead';
import type { Subscription, MonitoringHistory, Job } from '../types';

export default function DashboardPage() {
  const [searchParams] = useSearchParams();
  const subscriptionSuccess = searchParams.get('subscription') === 'success';
  const paymentSuccess = searchParams.get('payment') === 'success';
  const { isAuthenticated, isLoading: authLoading, user } = useAuth();

  const { data: subscriptions, isLoading: subscriptionsLoading } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: () => apiClient.listSubscriptions(false),
    enabled: isAuthenticated,
  });

  const { data: assessments, isLoading: assessmentsLoading } = useQuery({
    queryKey: ['assessments'],
    queryFn: () => apiClient.listAssessments(),
    enabled: isAuthenticated,
  });

  const isLoading = subscriptionsLoading || assessmentsLoading;

  if (authLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const activeCount = subscriptions?.filter(s => s.active).length || 0;
  const totalChecks = subscriptions?.reduce((acc, s) => acc + (s.last_check ? 1 : 0), 0) || 0;
  const changesDetected = subscriptions?.filter(s => s.last_change_detected).length || 0;
  const assessmentCount = assessments?.length || 0;

  return (
    <>
      <SEOHead
        title="Dashboard"
        canonicalPath="/dashboard"
        description="View your llms.txt assessments and manage monitoring subscriptions."
        noIndex={true}
      />
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <div className="bg-gradient-to-r from-primary-600 to-primary-700">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between">
              <div>
                <h1 className="text-3xl font-bold text-white">Dashboard</h1>
              <p className="text-primary-100 mt-1">
                Welcome back{user?.email ? `, ${user.email.split('@')[0]}` : ''}
              </p>
            </div>
            <Link
              to="/subscribe"
              className="mt-4 md:mt-0 inline-flex items-center gap-2 bg-white text-primary-600 px-5 py-2.5 rounded-lg font-medium hover:bg-primary-50 transition-colors shadow-sm"
            >
              <Globe className="w-4 h-4" aria-hidden="true" />
              New Subscription
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Success Messages */}
        {subscriptionSuccess && (
          <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-xl flex items-start gap-3 shadow-sm">
            <div className="p-1 bg-green-100 rounded-full">
              <CheckCircle2 className="w-5 h-5 text-green-600" aria-hidden="true" />
            </div>
            <div>
              <p className="font-semibold text-green-800">Subscription activated!</p>
              <p className="text-green-700 text-sm">
                Your monitoring subscription is now active. We'll check your site regularly and notify you of changes.
              </p>
            </div>
          </div>
        )}
        {paymentSuccess && (
          <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-xl flex items-start gap-3 shadow-sm">
            <div className="p-1 bg-green-100 rounded-full">
              <CheckCircle2 className="w-5 h-5 text-green-600" aria-hidden="true" />
            </div>
            <div>
              <p className="font-semibold text-green-800">Assessment purchased!</p>
              <p className="text-green-700 text-sm">
                Your llms.txt assessment has been saved to your dashboard. It will be available for 30 days.
              </p>
            </div>
          </div>
        )}

        {/* Stats Cards */}
        {(subscriptions?.length || assessments?.length) ? (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <StatsCard
              icon={<Award className="w-5 h-5" aria-hidden="true" />}
              label="Assessments"
              value={assessmentCount}
              color="purple"
            />
            <StatsCard
              icon={<Activity className="w-5 h-5" aria-hidden="true" />}
              label="Active Subscriptions"
              value={activeCount}
              color="primary"
            />
            <StatsCard
              icon={<Clock className="w-5 h-5" aria-hidden="true" />}
              label="Monitoring Checks"
              value={totalChecks}
              color="blue"
            />
            <StatsCard
              icon={<Bell className="w-5 h-5" aria-hidden="true" />}
              label="Changes Detected"
              value={changesDetected}
              color="orange"
            />
          </div>
        ) : null}

        {/* Loading State */}
        {isLoading && (
          <div className="flex items-center justify-center py-16" role="status" aria-live="polite">
            <div className="text-center">
              <Loader2 className="w-10 h-10 animate-spin text-primary-600 mx-auto mb-4" aria-hidden="true" />
              <p className="text-gray-500">Loading your subscriptions...</p>
            </div>
          </div>
        )}

        {/* Empty State */}
        {(!subscriptions?.length && !assessments?.length) && !isLoading && (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-12 text-center">
            <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <Globe className="w-8 h-8 text-primary-600" aria-hidden="true" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-3">Welcome to your dashboard</h2>
            <p className="text-gray-600 mb-8 max-w-md mx-auto">
              Purchase an llms.txt assessment or set up monitoring to see your results here.
              Assessments are stored for 30 days.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                to="/generate"
                className="inline-flex items-center justify-center gap-2 btn btn-primary text-lg px-6 py-3"
              >
                <Award className="w-5 h-5" aria-hidden="true" />
                Generate Assessment
              </Link>
              <Link
                to="/subscribe"
                className="inline-flex items-center justify-center gap-2 btn btn-outline text-lg px-6 py-3"
              >
                <Globe className="w-5 h-5" aria-hidden="true" />
                Start Monitoring
              </Link>
            </div>
          </div>
        )}

        {/* Assessments List */}
        {assessments && assessments.length > 0 && (
          <div className="space-y-4 mb-8">
            <h2 className="text-lg font-semibold text-gray-900">Your Assessments</h2>
            <p className="text-sm text-gray-500">One-time assessments are stored for 30 days from purchase.</p>
            {assessments.map((assessment) => (
              <AssessmentCard key={assessment.job_id} assessment={assessment} />
            ))}
          </div>
        )}

        {/* Subscription List */}
        {subscriptions && subscriptions.length > 0 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">Your Subscriptions</h2>
            {subscriptions.map((subscription) => (
              <SubscriptionCard key={subscription.id} subscription={subscription} />
            ))}
          </div>
        )}
        </div>
      </div>
    </>
  );
}

function StatsCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  color: 'primary' | 'blue' | 'orange' | 'purple';
}) {
  const colorClasses = {
    primary: 'bg-primary-50 text-primary-600',
    blue: 'bg-blue-50 text-blue-600',
    orange: 'bg-orange-50 text-orange-600',
    purple: 'bg-purple-50 text-purple-600',
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
      <div className="flex items-center gap-4">
        <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
          {icon}
        </div>
        <div>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          <p className="text-sm text-gray-500">{label}</p>
        </div>
      </div>
    </div>
  );
}

function AssessmentCard({ assessment }: { assessment: Job }) {
  const [showContent, setShowContent] = useState(false);
  const [activeTab, setActiveTab] = useState<'assessment' | 'llmstxt'>('assessment');
  const [dismissedIndices, setDismissedIndices] = useState<Set<number>>(new Set());
  const [localScores, setLocalScores] = useState<{
    overall_score: number;
    quality_score: number;
    grade: string;
  } | null>(null);
  const queryClient = useQueryClient();

  const dismissMutation = useMutation({
    mutationFn: (indices: number[]) => apiClient.dismissFindings(assessment.job_id, indices),
    onSuccess: (data) => {
      setLocalScores({
        overall_score: data.overall_score,
        quality_score: data.quality_score,
        grade: data.grade,
      });
      queryClient.invalidateQueries({ queryKey: ['assessments'] });
    },
  });

  const handleDismiss = (index: number) => {
    const newDismissed = new Set(dismissedIndices);
    newDismissed.add(index);
    setDismissedIndices(newDismissed);
    dismissMutation.mutate(Array.from(newDismissed));
  };

  const formatUrl = (url: string) => {
    try {
      return new URL(url).hostname;
    } catch {
      return url;
    }
  };

  const downloadLlmstxt = () => {
    if (!assessment.llmstxt_content) return;
    const blob = new Blob([assessment.llmstxt_content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `llms-${formatUrl(assessment.url)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const daysRemaining = assessment.expires_at
    ? Math.max(0, Math.ceil((new Date(assessment.expires_at).getTime() - Date.now()) / (1000 * 60 * 60 * 24)))
    : 0;

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-100 text-red-700 border-red-200';
      case 'major': case 'high': return 'bg-orange-100 text-orange-700 border-orange-200';
      case 'minor': case 'medium': return 'bg-yellow-100 text-yellow-700 border-yellow-200';
      default: return 'bg-blue-100 text-blue-700 border-blue-200';
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden transition-shadow hover:shadow-md">
      <div className="p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-4 min-w-0">
            <div className="p-3 rounded-xl flex-shrink-0 bg-gradient-to-br from-purple-400 to-purple-500">
              <Award className="w-6 h-6 text-white" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-semibold text-gray-900 truncate">{formatUrl(assessment.url)}</h3>
                <a
                  href={assessment.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-gray-400 hover:text-primary-600 transition-colors"
                  aria-label={`Open ${assessment.url} in new tab`}
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
              <div className="flex items-center gap-3 mt-1 text-sm text-gray-500 flex-wrap">
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 rounded-full text-xs font-medium">
                  {assessment.template}
                </span>
                {assessment.sector && assessment.sector !== 'general' && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-primary-100 text-primary-700 rounded-full text-xs font-medium">
                    {assessment.sector.replace(/_/g, ' ')}
                  </span>
                )}
                {assessment.goal && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full text-xs font-medium">
                    {assessment.goal.replace(/_/g, ' ')}
                  </span>
                )}
                {assessment.assessment_json && (
                  <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-bold ${
                    (localScores?.grade ?? assessment.assessment_json.grade) === 'A' ? 'bg-green-100 text-green-700' :
                    (localScores?.grade ?? assessment.assessment_json.grade) === 'B' ? 'bg-blue-100 text-blue-700' :
                    (localScores?.grade ?? assessment.assessment_json.grade) === 'C' ? 'bg-yellow-100 text-yellow-700' :
                    'bg-red-100 text-red-700'
                  }`}>
                    Grade: {localScores?.grade ?? assessment.assessment_json.grade}
                  </span>
                )}
                {assessment.assessment_json && (
                  <span className="text-xs text-gray-500">
                    Score: {localScores?.overall_score ?? assessment.assessment_json.overall_score}/100
                  </span>
                )}
              </div>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium bg-purple-100 text-purple-700">
            <Timer className="w-4 h-4" aria-hidden="true" />
            {daysRemaining} days left
          </span>
        </div>

        {/* Metadata Row */}
        <div className="mt-5 pt-5 border-t border-gray-100 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
          <div className="flex items-center gap-2 text-gray-500">
            <Calendar className="w-4 h-4" aria-hidden="true" />
            <span>Created {new Date(assessment.created_at).toLocaleDateString()}</span>
          </div>
          {assessment.expires_at && (
            <div className="flex items-center gap-2 text-gray-500">
              <Clock className="w-4 h-4" aria-hidden="true" />
              <span>Expires {new Date(assessment.expires_at).toLocaleDateString()}</span>
            </div>
          )}
        </div>

        {/* Actions Row */}
        <div className="mt-4 flex items-center gap-4">
          <button
            onClick={() => setShowContent(!showContent)}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-primary-600 hover:text-primary-700 transition-colors"
          >
            {showContent ? (
              <>
                <ChevronUp className="w-4 h-4" aria-hidden="true" />
                Hide Details
              </>
            ) : (
              <>
                <ChevronDown className="w-4 h-4" aria-hidden="true" />
                View Details
              </>
            )}
          </button>
          {assessment.llmstxt_content && (
            <button
              onClick={downloadLlmstxt}
              className="inline-flex items-center gap-1.5 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
            >
              <Download className="w-4 h-4" aria-hidden="true" />
              Download llms.txt
            </button>
          )}
        </div>
      </div>

      {/* Expanded Content Section */}
      {showContent && (
        <div className="border-t border-gray-100">
          {/* Tabs */}
          <div className="flex border-b border-gray-200 bg-gray-50">
            <button
              onClick={() => setActiveTab('assessment')}
              className={`px-6 py-3 text-sm font-medium transition-colors ${
                activeTab === 'assessment'
                  ? 'text-primary-600 border-b-2 border-primary-600 bg-white'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Assessment Report
            </button>
            <button
              onClick={() => setActiveTab('llmstxt')}
              className={`px-6 py-3 text-sm font-medium transition-colors ${
                activeTab === 'llmstxt'
                  ? 'text-primary-600 border-b-2 border-primary-600 bg-white'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              llms.txt Content
            </button>
          </div>

          {/* Assessment Tab */}
          {activeTab === 'assessment' && assessment.assessment_json && (
            <div className="p-6 space-y-6">
              {/* Score Breakdown */}
              <div>
                <h4 className="text-sm font-semibold text-gray-900 mb-3">Score Breakdown</h4>
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-gray-50 rounded-lg p-4 text-center">
                    <div className={`text-2xl font-bold ${getScoreColor(localScores?.overall_score ?? assessment.assessment_json.overall_score)}`}>
                      {localScores?.overall_score ?? assessment.assessment_json.overall_score}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">Overall</div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-4 text-center">
                    <div className={`text-2xl font-bold ${getScoreColor(assessment.assessment_json.completeness_score)}`}>
                      {assessment.assessment_json.completeness_score}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">Completeness</div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-4 text-center">
                    <div className={`text-2xl font-bold ${getScoreColor(localScores?.quality_score ?? assessment.assessment_json.quality_score)}`}>
                      {localScores?.quality_score ?? assessment.assessment_json.quality_score}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">Quality</div>
                  </div>
                </div>
              </div>

              {/* Recommendations */}
              {assessment.assessment_json.recommendations && assessment.assessment_json.recommendations.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-gray-900 mb-3">Recommendations</h4>
                  <ul className="space-y-2">
                    {assessment.assessment_json.recommendations.map((rec, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                        <TrendingUp className="w-4 h-4 text-primary-500 mt-0.5 flex-shrink-0" aria-hidden="true" />
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Findings */}
              {assessment.assessment_json.findings && assessment.assessment_json.findings.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-semibold text-gray-900">
                      Findings ({assessment.assessment_json.findings.filter((_, i) => !dismissedIndices.has(i)).length})
                    </h4>
                    {dismissedIndices.size > 0 && (
                      <span className="text-xs text-gray-500">
                        {dismissedIndices.size} dismissed
                      </span>
                    )}
                  </div>
                  <div className="space-y-3">
                    {assessment.assessment_json.findings.map((finding, i) => {
                      const isDismissed = dismissedIndices.has(i);
                      if (isDismissed) return null;

                      return (
                        <div key={i} className={`rounded-lg border p-4 ${getSeverityColor(finding.severity)}`}>
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs font-semibold uppercase">{finding.severity}</span>
                                <span className="text-xs opacity-75">({finding.category})</span>
                              </div>
                              <p className="text-sm font-medium">{finding.message}</p>
                              {finding.suggestion && (
                                <p className="text-sm mt-2 opacity-90">
                                  <strong>Suggestion:</strong> {finding.suggestion}
                                </p>
                              )}
                            </div>
                            <button
                              onClick={() => handleDismiss(i)}
                              disabled={dismissMutation.isPending}
                              className="flex-shrink-0 text-xs px-2 py-1 rounded bg-white/50 hover:bg-white/80 transition-colors border border-current/20"
                              title="Mark as not relevant to your organisation"
                            >
                              {dismissMutation.isPending ? '...' : 'Not relevant'}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  {dismissMutation.isError && (
                    <p className="text-sm text-red-600 mt-2">Failed to update. Please try again.</p>
                  )}
                </div>
              )}

              {/* Section Assessments */}
              {assessment.assessment_json.sections && assessment.assessment_json.sections.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-gray-900 mb-3">Section Analysis</h4>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {assessment.assessment_json.sections.map((section, i) => (
                      <div key={i} className={`rounded-lg border p-3 ${section.present ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'}`}>
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-gray-900">{section.name}</span>
                          {section.present ? (
                            <CheckCircle2 className="w-4 h-4 text-green-600" aria-hidden="true" />
                          ) : (
                            <XCircle className="w-4 h-4 text-gray-400" aria-hidden="true" />
                          )}
                        </div>
                        {section.present && section.quality && (
                          <div className="text-xs text-gray-500 mt-1">Quality: {section.quality}</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Website Gaps */}
              {assessment.assessment_json.website_gaps && (
                <div>
                  <h4 className="text-sm font-semibold text-gray-900 mb-3">Website Analysis</h4>
                  <div className="bg-gray-50 rounded-lg p-4 text-sm">
                    <div className="flex items-center gap-2 mb-2">
                      {assessment.assessment_json.website_gaps.has_sitemap ? (
                        <CheckCircle2 className="w-4 h-4 text-green-600" aria-hidden="true" />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-500" aria-hidden="true" />
                      )}
                      <span>Sitemap {assessment.assessment_json.website_gaps.has_sitemap ? 'detected' : 'not found'}</span>
                    </div>
                    {assessment.assessment_json.website_gaps.missing_page_types &&
                     assessment.assessment_json.website_gaps.missing_page_types.length > 0 && (
                      <div className="mt-2">
                        <span className="text-gray-600">Missing page types: </span>
                        <span className="text-gray-900">{assessment.assessment_json.website_gaps.missing_page_types.join(', ')}</span>
                      </div>
                    )}
                    {assessment.assessment_json.website_gaps.suggested_pages &&
                     assessment.assessment_json.website_gaps.suggested_pages.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-200">
                        <span className="text-gray-600 font-medium">Suggestions:</span>
                        <ul className="mt-2 space-y-1">
                          {assessment.assessment_json.website_gaps.suggested_pages.map((suggestion, i) => (
                            <li key={i} className="text-gray-700 flex items-start gap-2">
                              <span className="text-primary-500">•</span>
                              {suggestion}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* llms.txt Tab */}
          {activeTab === 'llmstxt' && assessment.llmstxt_content && (
            <div className="p-6">
              <div className="bg-gray-900 rounded-lg overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
                  <span className="text-sm text-gray-400 font-mono">llms.txt</span>
                </div>
                <pre className="p-4 text-sm text-gray-300 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed max-h-96">
                  {assessment.llmstxt_content}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SubscriptionCard({ subscription }: { subscription: Subscription }) {
  const [expanded, setExpanded] = useState(false);
  const queryClient = useQueryClient();

  const cancelMutation = useMutation({
    mutationFn: () => apiClient.cancelSubscription(subscription.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
    },
  });

  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ['subscription-history', subscription.id],
    queryFn: () => apiClient.getSubscriptionHistory(subscription.id),
    enabled: expanded,
  });

  const handleCancel = () => {
    if (window.confirm('Are you sure you want to cancel this subscription? You can resubscribe at any time.')) {
      cancelMutation.mutate();
    }
  };

  const formatUrl = (url: string) => {
    try {
      return new URL(url).hostname;
    } catch {
      return url;
    }
  };

  return (
    <div className={`bg-white rounded-xl shadow-sm border overflow-hidden transition-shadow hover:shadow-md ${
      subscription.active ? 'border-gray-200' : 'border-gray-200 opacity-75'
    }`}>
      <div className="p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-4 min-w-0">
            <div className={`p-3 rounded-xl flex-shrink-0 ${
              subscription.active
                ? 'bg-gradient-to-br from-green-400 to-green-500'
                : 'bg-gray-200'
            }`}>
              <Globe className="w-6 h-6 text-white" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-semibold text-gray-900 truncate">{formatUrl(subscription.url)}</h3>
                <a
                  href={subscription.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-gray-400 hover:text-primary-600 transition-colors"
                  aria-label={`Open ${subscription.url} in new tab`}
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
              <div className="flex items-center gap-3 mt-1 text-sm text-gray-500 flex-wrap">
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 rounded-full text-xs font-medium">
                  {subscription.template}
                </span>
                {subscription.sector && subscription.sector !== 'general' && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-primary-100 text-primary-700 rounded-full text-xs font-medium">
                    {subscription.sector.replace(/_/g, ' ')}
                  </span>
                )}
                {subscription.goal && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full text-xs font-medium">
                    {subscription.goal.replace(/_/g, ' ')}
                  </span>
                )}
                <span className="capitalize">{subscription.frequency}</span>
              </div>
            </div>
          </div>
          <StatusBadge active={subscription.active} />
        </div>

        {/* Metadata Row */}
        <div className="mt-5 pt-5 border-t border-gray-100 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
          <div className="flex items-center gap-2 text-gray-500">
            <Calendar className="w-4 h-4" aria-hidden="true" />
            <span>Created {new Date(subscription.created_at).toLocaleDateString()}</span>
          </div>
          {subscription.last_check && (
            <div className="flex items-center gap-2 text-gray-500">
              <Clock className="w-4 h-4" aria-hidden="true" />
              <span>Checked {new Date(subscription.last_check).toLocaleDateString()}</span>
            </div>
          )}
          {subscription.last_change_detected && (
            <div className="flex items-center gap-2 text-orange-600 font-medium">
              <TrendingUp className="w-4 h-4" aria-hidden="true" />
              <span>Changed {new Date(subscription.last_change_detected).toLocaleDateString()}</span>
            </div>
          )}
        </div>

        {/* Actions Row */}
        <div className="mt-4 flex items-center justify-between">
          <button
            onClick={() => setExpanded(!expanded)}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-primary-600 hover:text-primary-700 transition-colors"
            aria-expanded={expanded}
            aria-controls={`history-${subscription.id}`}
          >
            {expanded ? (
              <>
                <ChevronUp className="w-4 h-4" aria-hidden="true" />
                Hide History
              </>
            ) : (
              <>
                <ChevronDown className="w-4 h-4" aria-hidden="true" />
                View History
              </>
            )}
          </button>

          {subscription.active && (
            <button
              onClick={handleCancel}
              disabled={cancelMutation.isPending}
              className="text-sm text-gray-500 hover:text-red-600 transition-colors"
            >
              {cancelMutation.isPending ? 'Cancelling...' : 'Cancel Subscription'}
            </button>
          )}
        </div>
      </div>

      {/* History Section */}
      {expanded && (
        <div
          id={`history-${subscription.id}`}
          className="border-t border-gray-100 bg-gray-50 p-6"
        >
          <h4 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-gray-400" aria-hidden="true" />
            Monitoring History
          </h4>

          {historyLoading && (
            <div className="flex items-center justify-center py-8" role="status" aria-live="polite">
              <Loader2 className="w-6 h-6 animate-spin text-primary-600" aria-hidden="true" />
              <span className="sr-only">Loading history...</span>
            </div>
          )}

          {history && history.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              <Clock className="w-8 h-8 mx-auto mb-2 text-gray-300" aria-hidden="true" />
              <p>No monitoring checks yet</p>
              <p className="text-sm">First check will run soon</p>
            </div>
          )}

          {history && history.length > 0 && (
            <div className="space-y-3">
              {history.map((entry, index) => (
                <HistoryEntry key={entry.id} entry={entry} isLatest={index === 0} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function HistoryEntry({ entry, isLatest }: { entry: MonitoringHistory; isLatest: boolean }) {
  const [showContent, setShowContent] = useState(false);
  const [activeTab, setActiveTab] = useState<'assessment' | 'llmstxt'>('assessment');

  const downloadContent = () => {
    const blob = new Blob([entry.llmstxt_content || ''], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `llms-${new Date(entry.checked_at).toISOString().split('T')[0]}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-100 text-red-700 border-red-200';
      case 'major': case 'high': return 'bg-orange-100 text-orange-700 border-orange-200';
      case 'minor': case 'medium': return 'bg-yellow-100 text-yellow-700 border-yellow-200';
      default: return 'bg-blue-100 text-blue-700 border-blue-200';
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className={`bg-white rounded-lg border transition-all ${
      entry.changed
        ? 'border-orange-200 shadow-sm'
        : 'border-gray-200'
    }`}>
      <div className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            {entry.changed ? (
              <div className="p-2 rounded-full bg-orange-100 flex-shrink-0">
                <AlertCircle className="w-4 h-4 text-orange-600" aria-hidden="true" />
              </div>
            ) : (
              <div className="p-2 rounded-full bg-green-100 flex-shrink-0">
                <CheckCircle2 className="w-4 h-4 text-green-600" aria-hidden="true" />
              </div>
            )}
            <div>
              <div className="flex items-center gap-2">
                <p className="font-medium text-gray-900">
                  {new Date(entry.checked_at).toLocaleDateString('en-GB', {
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </p>
                {isLatest && (
                  <span className="px-2 py-0.5 bg-primary-100 text-primary-700 text-xs font-medium rounded-full">
                    Latest
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-500 mt-0.5">
                {entry.changed ? (
                  <span className="text-orange-600 font-medium">Changes detected</span>
                ) : (
                  'No changes'
                )}
                {entry.notification_sent && (
                  <span className="ml-2 inline-flex items-center gap-1">
                    <Bell className="w-3 h-3" aria-hidden="true" />
                    Notified
                  </span>
                )}
              </p>
              {entry.assessment_json && (
                <div className="mt-2 flex items-center gap-3">
                  <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-bold ${
                    entry.assessment_json.grade === 'A' ? 'bg-green-100 text-green-700' :
                    entry.assessment_json.grade === 'B' ? 'bg-blue-100 text-blue-700' :
                    entry.assessment_json.grade === 'C' ? 'bg-yellow-100 text-yellow-700' :
                    'bg-red-100 text-red-700'
                  }`}>
                    Grade: {entry.assessment_json.grade}
                  </span>
                  <span className="text-xs text-gray-500">
                    Score: {entry.assessment_json.overall_score}/100
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {entry.llmstxt_content && (
              <button
                onClick={downloadContent}
                className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                title="Download llms.txt"
                aria-label="Download llms.txt file"
              >
                <Download className="w-4 h-4" aria-hidden="true" />
              </button>
            )}
            {(entry.llmstxt_content || entry.assessment_json) && (
              <button
                onClick={() => setShowContent(!showContent)}
                className="inline-flex items-center gap-1.5 text-sm font-medium text-primary-600 hover:text-primary-700 transition-colors"
                aria-expanded={showContent}
              >
                {showContent ? (
                  <>
                    <ChevronUp className="w-4 h-4" aria-hidden="true" />
                    Hide Details
                  </>
                ) : (
                  <>
                    <ChevronDown className="w-4 h-4" aria-hidden="true" />
                    View Details
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Expanded Content Section */}
      {showContent && (entry.llmstxt_content || entry.assessment_json) && (
        <div className="border-t border-gray-100">
          {/* Tabs */}
          <div className="flex border-b border-gray-200 bg-gray-50">
            <button
              onClick={() => setActiveTab('assessment')}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === 'assessment'
                  ? 'text-primary-600 border-b-2 border-primary-600 bg-white'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Assessment Report
            </button>
            <button
              onClick={() => setActiveTab('llmstxt')}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === 'llmstxt'
                  ? 'text-primary-600 border-b-2 border-primary-600 bg-white'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              llms.txt Content
            </button>
          </div>

          {/* Assessment Tab */}
          {activeTab === 'assessment' && entry.assessment_json && (
            <div className="p-4 space-y-4">
              {/* Score Breakdown */}
              <div>
                <h4 className="text-sm font-semibold text-gray-900 mb-2">Score Breakdown</h4>
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <div className={`text-xl font-bold ${getScoreColor(entry.assessment_json.overall_score)}`}>
                      {entry.assessment_json.overall_score}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">Overall</div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <div className={`text-xl font-bold ${getScoreColor(entry.assessment_json.completeness_score)}`}>
                      {entry.assessment_json.completeness_score}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">Completeness</div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3 text-center">
                    <div className={`text-xl font-bold ${getScoreColor(entry.assessment_json.quality_score)}`}>
                      {entry.assessment_json.quality_score}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">Quality</div>
                  </div>
                </div>
              </div>

              {/* Recommendations */}
              {entry.assessment_json.recommendations && entry.assessment_json.recommendations.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-gray-900 mb-2">Recommendations</h4>
                  <ul className="space-y-1">
                    {entry.assessment_json.recommendations.map((rec, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                        <TrendingUp className="w-4 h-4 text-primary-500 mt-0.5 flex-shrink-0" aria-hidden="true" />
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Findings */}
              {entry.assessment_json.findings && entry.assessment_json.findings.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-gray-900 mb-2">
                    Findings ({entry.assessment_json.findings.length})
                  </h4>
                  <div className="space-y-2">
                    {entry.assessment_json.findings.map((finding, i) => (
                      <div key={i} className={`rounded-lg border p-3 ${getSeverityColor(finding.severity)}`}>
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-xs font-semibold uppercase">{finding.severity}</span>
                              <span className="text-xs opacity-75">({finding.category})</span>
                            </div>
                            <p className="text-sm font-medium">{finding.message}</p>
                            {finding.suggestion && (
                              <p className="text-sm mt-1 opacity-90">
                                <strong>Suggestion:</strong> {finding.suggestion}
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Section Assessments */}
              {entry.assessment_json.sections && entry.assessment_json.sections.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-gray-900 mb-2">Section Analysis</h4>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    {entry.assessment_json.sections.map((section, i) => (
                      <div key={i} className={`rounded-lg border p-2 ${section.present ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'}`}>
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-medium text-gray-900">{section.name}</span>
                          {section.present ? (
                            <CheckCircle2 className="w-3 h-3 text-green-600" aria-hidden="true" />
                          ) : (
                            <XCircle className="w-3 h-3 text-gray-400" aria-hidden="true" />
                          )}
                        </div>
                        {section.present && section.quality && (
                          <div className="text-xs text-gray-500 mt-1">Quality: {section.quality}</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Website Gaps */}
              {entry.assessment_json.website_gaps && (
                <div>
                  <h4 className="text-sm font-semibold text-gray-900 mb-2">Website Analysis</h4>
                  <div className="bg-gray-50 rounded-lg p-3 text-sm">
                    <div className="flex items-center gap-2 mb-2">
                      {entry.assessment_json.website_gaps.has_sitemap ? (
                        <CheckCircle2 className="w-4 h-4 text-green-600" aria-hidden="true" />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-500" aria-hidden="true" />
                      )}
                      <span>Sitemap {entry.assessment_json.website_gaps.has_sitemap ? 'detected' : 'not found'}</span>
                    </div>
                    {entry.assessment_json.website_gaps.missing_page_types &&
                     entry.assessment_json.website_gaps.missing_page_types.length > 0 && (
                      <div className="mt-2">
                        <span className="text-gray-600">Missing page types: </span>
                        <span className="text-gray-900">{entry.assessment_json.website_gaps.missing_page_types.join(', ')}</span>
                      </div>
                    )}
                    {entry.assessment_json.website_gaps.suggested_pages &&
                     entry.assessment_json.website_gaps.suggested_pages.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-gray-200">
                        <span className="text-gray-600 font-medium">Suggestions:</span>
                        <ul className="mt-1 space-y-1">
                          {entry.assessment_json.website_gaps.suggested_pages.map((suggestion, i) => (
                            <li key={i} className="text-gray-700 flex items-start gap-2">
                              <span className="text-primary-500">•</span>
                              {suggestion}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* llms.txt Tab */}
          {activeTab === 'llmstxt' && entry.llmstxt_content && (
            <div className="p-4">
              <div className="bg-gray-900 rounded-lg overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
                  <span className="text-sm text-gray-400 font-mono">llms.txt</span>
                </div>
                <pre className="p-4 text-sm text-gray-300 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed max-h-96">
                  {entry.llmstxt_content}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ active }: { active: boolean }) {
  if (active) {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium bg-green-100 text-green-700">
        <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" aria-hidden="true" />
        Active
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium bg-gray-100 text-gray-600">
      <XCircle className="w-4 h-4" aria-hidden="true" />
      Cancelled
    </span>
  );
}
