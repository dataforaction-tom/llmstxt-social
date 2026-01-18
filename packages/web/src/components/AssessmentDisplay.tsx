import { useState } from 'react';
import {
  AlertCircle,
  CheckCircle,
  Info,
  AlertTriangle,
  Download,
  ChevronDown,
  ChevronUp,
  Award,
  Target,
  Sparkles,
  FileText,
  Globe,
  TrendingUp,
} from 'lucide-react';
import type { Assessment } from '../types';

interface AssessmentDisplayProps {
  assessment: Assessment;
  websiteUrl?: string;
}

export default function AssessmentDisplay({ assessment, websiteUrl }: AssessmentDisplayProps) {
  const [showAllFindings, setShowAllFindings] = useState(false);
  const [showAllSections, setShowAllSections] = useState(false);

  const visibleFindings = showAllFindings
    ? assessment.findings
    : assessment.findings?.slice(0, 3);

  const visibleSections = showAllSections
    ? assessment.sections
    : assessment.sections?.slice(0, 4);

  const downloadAssessment = () => {
    const content = generateAssessmentMarkdown(assessment, websiteUrl);
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `llmstxt-assessment-${new Date().toISOString().split('T')[0]}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Header Card with Grade */}
      <div className="card overflow-hidden">
        <div className="bg-gradient-to-r from-primary-600 to-primary-700 -m-6 mb-6 p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-white/20 rounded-lg">
                <Award className="w-6 h-6 text-white" aria-hidden="true" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-white">Quality Assessment</h2>
                <p className="text-primary-100 text-sm">AI-powered analysis of your llms.txt</p>
              </div>
            </div>
            <button
              onClick={downloadAssessment}
              className="flex items-center gap-2 px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg text-white transition-colors"
            >
              <Download className="w-4 h-4" aria-hidden="true" />
              <span className="hidden sm:inline">Download Report</span>
            </button>
          </div>
        </div>

        {/* Grade Badge and Scores */}
        <div className="flex flex-col lg:flex-row gap-6 items-center lg:items-start">
          {/* Large Grade Badge */}
          <div className="flex-shrink-0">
            <GradeBadge grade={assessment.grade} score={assessment.overall_score} />
          </div>

          {/* Score Cards */}
          <div className="flex-1 w-full">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <ScoreCard
                icon={Target}
                label="Overall Score"
                score={assessment.overall_score}
                description="Combined assessment score"
              />
              <ScoreCard
                icon={FileText}
                label="Completeness"
                score={assessment.completeness_score}
                description="Required sections present"
              />
              <ScoreCard
                icon={Sparkles}
                label="Quality"
                score={assessment.quality_score}
                description="Content quality & clarity"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Recommendations */}
      {assessment.recommendations && assessment.recommendations.length > 0 && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-primary-600" aria-hidden="true" />
            <h3 className="text-lg font-semibold">Top Recommendations</h3>
          </div>
          <div className="space-y-3">
            {assessment.recommendations.map((rec, idx) => (
              <div
                key={idx}
                className="flex gap-3 p-3 bg-gradient-to-r from-primary-50 to-transparent rounded-lg border-l-4 border-primary-500"
              >
                <span className="flex-shrink-0 w-6 h-6 bg-primary-600 text-white rounded-full flex items-center justify-center text-sm font-medium">
                  {idx + 1}
                </span>
                <p className="text-gray-700">{rec}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Findings */}
      {assessment.findings && assessment.findings.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-amber-600" aria-hidden="true" />
              <h3 className="text-lg font-semibold">Detailed Findings</h3>
              <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-sm rounded-full">
                {assessment.findings.length}
              </span>
            </div>
            {assessment.findings.length > 3 && (
              <button
                onClick={() => setShowAllFindings(!showAllFindings)}
                className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
              >
                {showAllFindings ? (
                  <>
                    Show less <ChevronUp className="w-4 h-4" aria-hidden="true" />
                  </>
                ) : (
                  <>
                    Show all ({assessment.findings.length}) <ChevronDown className="w-4 h-4" aria-hidden="true" />
                  </>
                )}
              </button>
            )}
          </div>
          <div className="space-y-3">
            {visibleFindings?.map((finding, idx) => (
              <FindingCard key={idx} finding={finding} />
            ))}
          </div>
        </div>
      )}

      {/* Section Analysis */}
      {assessment.sections && assessment.sections.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-blue-600" aria-hidden="true" />
              <h3 className="text-lg font-semibold">Section Analysis</h3>
            </div>
            {assessment.sections.length > 4 && (
              <button
                onClick={() => setShowAllSections(!showAllSections)}
                className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
              >
                {showAllSections ? (
                  <>
                    Show less <ChevronUp className="w-4 h-4" aria-hidden="true" />
                  </>
                ) : (
                  <>
                    Show all ({assessment.sections.length}) <ChevronDown className="w-4 h-4" aria-hidden="true" />
                  </>
                )}
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {visibleSections?.map((section, idx) => (
              <SectionCard key={idx} section={section} />
            ))}
          </div>
        </div>
      )}

      {/* Website Gaps */}
      {assessment.website_gaps && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Globe className="w-5 h-5 text-purple-600" aria-hidden="true" />
            <h3 className="text-lg font-semibold">Website Analysis</h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Crawl Stats */}
            <div className="p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-600">Sitemap</span>
                <span
                  className={`px-2 py-1 rounded text-xs font-medium ${
                    assessment.website_gaps.has_sitemap
                      ? 'bg-green-100 text-green-700'
                      : 'bg-red-100 text-red-700'
                  }`}
                >
                  {assessment.website_gaps.has_sitemap ? 'Found' : 'Not Found'}
                </span>
              </div>
              {assessment.website_gaps.crawl_coverage !== undefined && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-gray-600">Crawl Coverage</span>
                    <span className="text-sm font-medium">
                      {Math.round(assessment.website_gaps.crawl_coverage * 100)}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-primary-600 h-2 rounded-full transition-all duration-500"
                      style={{ width: `${assessment.website_gaps.crawl_coverage * 100}%` }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Missing Pages */}
            {assessment.website_gaps.missing_page_types &&
              assessment.website_gaps.missing_page_types.length > 0 && (
                <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                  <p className="text-sm font-medium text-amber-800 mb-2">
                    Missing Page Types
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {assessment.website_gaps.missing_page_types.map((type, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-1 bg-amber-100 text-amber-800 text-xs rounded-full"
                      >
                        {type}
                      </span>
                    ))}
                  </div>
                </div>
              )}
          </div>
        </div>
      )}
    </div>
  );
}

function GradeBadge({ grade, score }: { grade: string; score: number }) {
  const gradeConfig: Record<string, { bg: string; ring: string; text: string; label: string }> = {
    A: { bg: 'bg-green-500', ring: 'ring-green-200', text: 'text-green-500', label: 'Excellent' },
    B: { bg: 'bg-blue-500', ring: 'ring-blue-200', text: 'text-blue-500', label: 'Good' },
    C: { bg: 'bg-yellow-500', ring: 'ring-yellow-200', text: 'text-yellow-500', label: 'Fair' },
    D: { bg: 'bg-orange-500', ring: 'ring-orange-200', text: 'text-orange-500', label: 'Needs Work' },
    F: { bg: 'bg-red-500', ring: 'ring-red-200', text: 'text-red-500', label: 'Poor' },
  };

  const config = gradeConfig[grade] || gradeConfig.C;

  return (
    <div className="flex flex-col items-center">
      <div className={`relative w-28 h-28 ${config.ring} ring-8 rounded-full flex items-center justify-center ${config.bg}`}>
        <span className="text-5xl font-bold text-white">{grade}</span>
      </div>
      <p className={`mt-2 font-semibold ${config.text}`}>{config.label}</p>
      <p className="text-sm text-gray-500">{score}/100 points</p>
    </div>
  );
}

function ScoreCard({
  icon: Icon,
  label,
  score,
  description,
}: {
  icon: typeof Target;
  label: string;
  score: number;
  description: string;
}) {
  const getColor = (score: number) => {
    if (score >= 90) return { bar: 'bg-green-500', text: 'text-green-600' };
    if (score >= 70) return { bar: 'bg-blue-500', text: 'text-blue-600' };
    if (score >= 50) return { bar: 'bg-yellow-500', text: 'text-yellow-600' };
    return { bar: 'bg-red-500', text: 'text-red-600' };
  };

  const colors = getColor(score);

  return (
    <div className="p-4 bg-gray-50 rounded-xl">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4 text-gray-500" aria-hidden="true" />
        <span className="text-sm font-medium text-gray-700">{label}</span>
      </div>
      <div className="flex items-end gap-2 mb-2">
        <span className={`text-3xl font-bold ${colors.text}`}>{score}</span>
        <span className="text-gray-400 text-sm mb-1">/100</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-1.5 mb-2">
        <div
          className={`${colors.bar} h-1.5 rounded-full transition-all duration-500`}
          style={{ width: `${score}%` }}
        />
      </div>
      <p className="text-xs text-gray-500">{description}</p>
    </div>
  );
}

function SectionCard({ section }: { section: NonNullable<Assessment['sections']>[0] }) {
  return (
    <div
      className={`p-4 rounded-lg border ${
        section.present
          ? 'bg-green-50 border-green-200'
          : 'bg-gray-50 border-gray-200'
      }`}
    >
      <div className="flex items-start gap-3">
        <div
          className={`p-1.5 rounded-full ${
            section.present ? 'bg-green-100' : 'bg-gray-200'
          }`}
        >
          {section.present ? (
            <CheckCircle className="w-4 h-4 text-green-600" aria-hidden="true" />
          ) : (
            <AlertCircle className="w-4 h-4 text-gray-500" aria-hidden="true" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-gray-900 truncate">{section.name}</p>
          {section.quality && (
            <p className="text-sm text-gray-600 mt-0.5">{section.quality}</p>
          )}
          {section.issues && section.issues.length > 0 && (
            <ul className="mt-2 space-y-1">
              {section.issues.slice(0, 2).map((issue, i) => (
                <li key={i} className="text-xs text-gray-500 flex items-start gap-1">
                  <span className="text-gray-400">•</span>
                  <span>{issue}</span>
                </li>
              ))}
              {section.issues.length > 2 && (
                <li className="text-xs text-gray-400">
                  +{section.issues.length - 2} more issues
                </li>
              )}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function FindingCard({ finding }: { finding: Assessment['findings'][0] }) {
  const severityStyles: Record<string, { bg: string; border: string; badge: string; icon: typeof AlertCircle; iconColor: string }> = {
    critical: {
      bg: 'bg-red-50',
      border: 'border-red-200',
      badge: 'bg-red-100 text-red-700',
      icon: AlertCircle,
      iconColor: 'text-red-600',
    },
    major: {
      bg: 'bg-orange-50',
      border: 'border-orange-200',
      badge: 'bg-orange-100 text-orange-700',
      icon: AlertTriangle,
      iconColor: 'text-orange-600',
    },
    high: {
      bg: 'bg-orange-50',
      border: 'border-orange-200',
      badge: 'bg-orange-100 text-orange-700',
      icon: AlertTriangle,
      iconColor: 'text-orange-600',
    },
    medium: {
      bg: 'bg-yellow-50',
      border: 'border-yellow-200',
      badge: 'bg-yellow-100 text-yellow-700',
      icon: AlertTriangle,
      iconColor: 'text-yellow-600',
    },
    minor: {
      bg: 'bg-blue-50',
      border: 'border-blue-200',
      badge: 'bg-blue-100 text-blue-700',
      icon: Info,
      iconColor: 'text-blue-600',
    },
    low: {
      bg: 'bg-blue-50',
      border: 'border-blue-200',
      badge: 'bg-blue-100 text-blue-700',
      icon: Info,
      iconColor: 'text-blue-600',
    },
    info: {
      bg: 'bg-gray-50',
      border: 'border-gray-200',
      badge: 'bg-gray-100 text-gray-700',
      icon: Info,
      iconColor: 'text-gray-600',
    },
  };

  const style = severityStyles[finding.severity] || severityStyles.info;
  const Icon = style.icon;

  return (
    <div className={`p-4 rounded-lg border ${style.bg} ${style.border}`}>
      <div className="flex gap-3">
        <div className="flex-shrink-0">
          <Icon className={`w-5 h-5 ${style.iconColor}`} aria-hidden="true" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-1">
            <p className="font-medium text-gray-900">{finding.message}</p>
            <span className={`flex-shrink-0 px-2 py-0.5 rounded text-xs font-medium ${style.badge}`}>
              {finding.severity}
            </span>
          </div>
          {finding.category && (
            <p className="text-xs text-gray-500 mb-2">Category: {finding.category}</p>
          )}
          {finding.suggestion && (
            <div className="mt-2 p-2 bg-white/60 rounded border border-white">
              <p className="text-sm text-gray-700">
                <span className="font-medium">Suggestion:</span> {finding.suggestion}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function generateAssessmentMarkdown(assessment: Assessment, websiteUrl?: string): string {
  const date = new Date().toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  let md = `# llms.txt Quality Assessment Report

**Generated:** ${date}
${websiteUrl ? `**Website:** ${websiteUrl}` : ''}

---

## Overall Grade: ${assessment.grade}

| Metric | Score |
|--------|-------|
| Overall Score | ${assessment.overall_score}/100 |
| Completeness | ${assessment.completeness_score}/100 |
| Quality | ${assessment.quality_score}/100 |

---

`;

  if (assessment.recommendations && assessment.recommendations.length > 0) {
    md += `## Top Recommendations

`;
    assessment.recommendations.forEach((rec, idx) => {
      md += `${idx + 1}. ${rec}\n`;
    });
    md += `\n---\n\n`;
  }

  if (assessment.findings && assessment.findings.length > 0) {
    md += `## Detailed Findings

`;
    const groupedFindings: Record<string, typeof assessment.findings> = {};
    assessment.findings.forEach((f) => {
      const severity = f.severity || 'info';
      if (!groupedFindings[severity]) groupedFindings[severity] = [];
      groupedFindings[severity].push(f);
    });

    // Include all known severity levels plus any dynamic ones found
    const severityOrder = ['critical', 'major', 'high', 'medium', 'minor', 'low', 'info'];
    const allSeverities = new Set([...severityOrder, ...Object.keys(groupedFindings)]);

    // Sort by known order, unknowns go at the end
    const sortedSeverities = Array.from(allSeverities).sort((a, b) => {
      const aIdx = severityOrder.indexOf(a);
      const bIdx = severityOrder.indexOf(b);
      if (aIdx === -1 && bIdx === -1) return 0;
      if (aIdx === -1) return 1;
      if (bIdx === -1) return -1;
      return aIdx - bIdx;
    });

    sortedSeverities.forEach((severity) => {
      const findings = groupedFindings[severity];
      if (findings && findings.length > 0) {
        md += `### ${severity.charAt(0).toUpperCase() + severity.slice(1)} (${findings.length})\n\n`;
        findings.forEach((f) => {
          md += `- **${f.message}**`;
          if (f.category) md += ` _(${f.category})_`;
          md += `\n`;
          if (f.suggestion) md += `  - Suggestion: ${f.suggestion}\n`;
        });
        md += `\n`;
      }
    });
    md += `---\n\n`;
  }

  if (assessment.sections && assessment.sections.length > 0) {
    md += `## Section Analysis

| Section | Status | Quality |
|---------|--------|---------|
`;
    assessment.sections.forEach((s) => {
      const status = s.present ? '✓ Present' : '✗ Missing';
      const quality = s.quality || '-';
      md += `| ${s.name} | ${status} | ${quality} |\n`;
    });
    md += `\n`;

    const sectionsWithIssues = assessment.sections.filter((s) => s.issues && s.issues.length > 0);
    if (sectionsWithIssues.length > 0) {
      md += `### Section Issues\n\n`;
      sectionsWithIssues.forEach((s) => {
        md += `**${s.name}:**\n`;
        s.issues.forEach((issue) => {
          md += `- ${issue}\n`;
        });
        md += `\n`;
      });
    }
    md += `---\n\n`;
  }

  if (assessment.website_gaps) {
    md += `## Website Analysis

- **Sitemap:** ${assessment.website_gaps.has_sitemap ? 'Found' : 'Not Found'}
`;
    if (assessment.website_gaps.crawl_coverage !== undefined) {
      md += `- **Crawl Coverage:** ${Math.round(assessment.website_gaps.crawl_coverage * 100)}%\n`;
    }
    if (assessment.website_gaps.missing_page_types && assessment.website_gaps.missing_page_types.length > 0) {
      md += `\n**Missing Page Types:**\n`;
      assessment.website_gaps.missing_page_types.forEach((type) => {
        md += `- ${type}\n`;
      });
    }
    md += `\n`;
  }

  md += `---

*Report generated by llms.txt Generator*
`;

  return md;
}
