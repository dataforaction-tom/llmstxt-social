import { AlertCircle, CheckCircle, Info, AlertTriangle } from 'lucide-react';
import type { Assessment } from '../types';

interface AssessmentDisplayProps {
  assessment: Assessment;
}

export default function AssessmentDisplay({ assessment }: AssessmentDisplayProps) {
  return (
    <div className="card space-y-6">
      <h2 className="text-2xl font-bold">Quality Assessment</h2>

      {/* Scores */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <ScoreCard
          label="Overall Score"
          score={assessment.overall_score}
          grade={assessment.grade}
        />
        <ScoreCard
          label="Completeness"
          score={assessment.completeness_score}
        />
        <ScoreCard
          label="Quality"
          score={assessment.quality_score}
        />
      </div>

      {/* Top Recommendations */}
      {assessment.recommendations && assessment.recommendations.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-3">Top Recommendations</h3>
          <ul className="space-y-2">
            {assessment.recommendations.map((rec, idx) => (
              <li key={idx} className="flex gap-2 text-gray-700">
                <AlertCircle className="w-5 h-5 text-primary-600 flex-shrink-0 mt-0.5" />
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Findings */}
      {assessment.findings && assessment.findings.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-3">Findings</h3>
          <div className="space-y-2">
            {assessment.findings.map((finding, idx) => (
              <FindingCard key={idx} finding={finding} />
            ))}
          </div>
        </div>
      )}

      {/* Section Assessment */}
      {assessment.sections && assessment.sections.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-3">Section Analysis</h3>
          <div className="space-y-2">
            {assessment.sections.map((section, idx) => (
              <div
                key={idx}
                className="flex items-start justify-between p-3 bg-gray-50 rounded-lg"
              >
                <div className="flex items-start gap-2">
                  {section.present ? (
                    <CheckCircle className="w-5 h-5 text-green-600 mt-0.5" />
                  ) : (
                    <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
                  )}
                  <div>
                    <p className="font-medium">{section.name}</p>
                    {section.quality && (
                      <p className="text-sm text-gray-600">{section.quality}</p>
                    )}
                    {section.issues && section.issues.length > 0 && (
                      <ul className="text-sm text-gray-600 mt-1 space-y-1">
                        {section.issues.map((issue, i) => (
                          <li key={i}>• {issue}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Website Gaps */}
      {assessment.website_gaps && (
        <div>
          <h3 className="text-lg font-semibold mb-3">Website Analysis</h3>
          <div className="space-y-2 text-sm text-gray-700">
            {assessment.website_gaps.missing_page_types &&
              assessment.website_gaps.missing_page_types.length > 0 && (
                <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <p className="font-medium text-yellow-900 mb-2">
                    Missing Page Types
                  </p>
                  <ul className="space-y-1">
                    {assessment.website_gaps.missing_page_types.map((type, idx) => (
                      <li key={idx}>• {type}</li>
                    ))}
                  </ul>
                </div>
              )}
            <div className="flex items-center gap-2">
              <span className="font-medium">Has Sitemap:</span>
              <span>{assessment.website_gaps.has_sitemap ? 'Yes' : 'No'}</span>
            </div>
            {assessment.website_gaps.crawl_coverage !== undefined && (
              <div className="flex items-center gap-2">
                <span className="font-medium">Crawl Coverage:</span>
                <span>{Math.round(assessment.website_gaps.crawl_coverage * 100)}%</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ScoreCard({ label, score, grade }: { label: string; score: number; grade?: string }) {
  const getColor = (score: number) => {
    if (score >= 90) return 'text-green-600';
    if (score >= 70) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <p className="text-sm text-gray-600 mb-1">{label}</p>
      <div className="flex items-end gap-2">
        <span className={`text-3xl font-bold ${getColor(score)}`}>{score}</span>
        {grade && <span className="text-2xl font-bold text-gray-400 mb-1">({grade})</span>}
      </div>
    </div>
  );
}

function FindingCard({ finding }: { finding: Assessment['findings'][0] }) {
  const severityStyles = {
    critical: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-900', icon: AlertCircle },
    high: { bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-900', icon: AlertTriangle },
    medium: { bg: 'bg-yellow-50', border: 'border-yellow-200', text: 'text-yellow-900', icon: AlertTriangle },
    low: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-900', icon: Info },
    info: { bg: 'bg-gray-50', border: 'border-gray-200', text: 'text-gray-900', icon: Info },
  };

  const style = severityStyles[finding.severity] || severityStyles.info;
  const Icon = style.icon;

  return (
    <div className={`p-4 rounded-lg border ${style.bg} ${style.border}`}>
      <div className="flex gap-3">
        <Icon className={`w-5 h-5 ${style.text} flex-shrink-0 mt-0.5`} />
        <div className="flex-1">
          <div className="flex items-start justify-between mb-1">
            <p className={`font-medium ${style.text}`}>{finding.message}</p>
            <span className="text-xs px-2 py-1 rounded bg-white/50">
              {finding.severity}
            </span>
          </div>
          {finding.suggestion && (
            <p className="text-sm text-gray-600 mt-2">
              <strong>Suggestion:</strong> {finding.suggestion}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
