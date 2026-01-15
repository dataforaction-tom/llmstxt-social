import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Download, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import apiClient from '../api/client';
import type { Template, Job } from '../types';
import AssessmentDisplay from '../components/AssessmentDisplay';
import PaymentFlow from '../components/PaymentFlow';
import ProgressIndicator from '../components/ProgressIndicator';

export default function GeneratePage() {
  const [url, setUrl] = useState('');
  const [template, setTemplate] = useState<Template>('charity');
  const [tier, setTier] = useState<'free' | 'paid'>('free');
  const [jobId, setJobId] = useState<string | null>(null);
  const [showPayment, setShowPayment] = useState(false);

  // Mutation for free generation
  const generateMutation = useMutation({
    mutationFn: () => apiClient.generateFree({ url, template }),
    onSuccess: (data) => {
      setJobId(data.job_id);
    },
  });

  // Poll for job status
  const { data: job } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => apiClient.getJob(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data || data.status === 'pending' || data.status === 'processing') {
        return 2000; // Poll every 2 seconds
      }
      return false; // Stop polling when complete or failed
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (tier === 'paid') {
      setShowPayment(true);
    } else {
      generateMutation.mutate();
    }
  };

  const handlePaymentSuccess = (paymentIntentId: string) => {
    apiClient.generatePaid({ url, template, payment_intent_id: paymentIntentId })
      .then((data) => {
        setJobId(data.job_id);
        setShowPayment(false);
      });
  };

  const downloadLlmstxt = () => {
    if (!job?.llmstxt_content) return;

    const blob = new Blob([job.llmstxt_content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'llms.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          Generate llms.txt
        </h1>
        <p className="text-lg text-gray-600 mb-8">
          Create AI-ready documentation for your organization in minutes
        </p>

        {/* Generation Form */}
        {!job && (
          <form onSubmit={handleSubmit} className="card space-y-6">
            {/* URL Input */}
            <div>
              <label htmlFor="url" className="label">
                Website URL
              </label>
              <input
                type="url"
                id="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example-charity.org.uk"
                className="input"
                required
              />
              <p className="text-sm text-gray-500 mt-1">
                Enter your organization's website URL
              </p>
            </div>

            {/* Template Selection */}
            <div>
              <label htmlFor="template" className="label">
                Organization Type
              </label>
              <select
                id="template"
                value={template}
                onChange={(e) => setTemplate(e.target.value as Template)}
                className="input"
              >
                <option value="charity">Charity / VCSE</option>
                <option value="funder">Funder / Foundation</option>
                <option value="public_sector">Public Sector</option>
                <option value="startup">Startup / Social Enterprise</option>
              </select>
            </div>

            {/* Tier Selection */}
            <div>
              <label className="label">Tier</label>
              <div className="grid grid-cols-2 gap-4">
                <button
                  type="button"
                  onClick={() => setTier('free')}
                  className={`p-4 border-2 rounded-lg transition-colors ${
                    tier === 'free'
                      ? 'border-primary-600 bg-primary-50'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <h3 className="font-semibold mb-1">Free</h3>
                  <p className="text-sm text-gray-600">Basic generation</p>
                  <p className="text-xs text-gray-500 mt-2">10/day limit</p>
                </button>

                <button
                  type="button"
                  onClick={() => setTier('paid')}
                  className={`p-4 border-2 rounded-lg transition-colors ${
                    tier === 'paid'
                      ? 'border-primary-600 bg-primary-50'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <h3 className="font-semibold mb-1">Paid - £29</h3>
                  <p className="text-sm text-gray-600">Full assessment</p>
                  <p className="text-xs text-gray-500 mt-2">+ enrichment data</p>
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={generateMutation.isPending || !url}
              className="btn btn-primary w-full"
            >
              {generateMutation.isPending ? (
                <>
                  <Loader2 className="inline-block animate-spin mr-2" />
                  Generating...
                </>
              ) : (
                <>Generate {tier === 'paid' ? '(Proceed to Payment)' : 'Free'}</>
              )}
            </button>
          </form>
        )}

        {/* Payment Modal */}
        {showPayment && (
          <PaymentFlow
            url={url}
            template={template}
            onSuccess={handlePaymentSuccess}
            onCancel={() => setShowPayment(false)}
          />
        )}

        {/* Job Progress */}
        {job && (
          <div className="space-y-6">
            {/* Status Card */}
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-bold">
                  {job.status === 'completed' && 'Generation Complete'}
                  {job.status === 'failed' && 'Generation Failed'}
                  {(job.status === 'pending' || job.status === 'processing') && 'Generating...'}
                </h2>
                <StatusBadge status={job.status} />
              </div>

              <div className="space-y-2 text-sm text-gray-600">
                <p><strong>URL:</strong> {job.url}</p>
                <p><strong>Template:</strong> {job.template}</p>
                <p><strong>Tier:</strong> {job.tier}</p>
              </div>

              {(job.status === 'pending' || job.status === 'processing') && (
                <div className="mt-6">
                  <ProgressIndicator
                    stage={job.progress_stage}
                    detail={job.progress_detail}
                    pagesCrawled={job.pages_crawled}
                    totalPages={job.total_pages}
                    tier={job.tier}
                  />
                </div>
              )}

              {job.status === 'failed' && job.error_message && (
                <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-red-800">
                    <strong>Error:</strong> {job.error_message}
                  </p>
                </div>
              )}

              {job.status === 'completed' && job.llmstxt_content && (
                <div className="mt-4 space-y-4">
                  <button onClick={downloadLlmstxt} className="btn btn-primary">
                    <Download className="inline-block mr-2 w-4 h-4" />
                    Download llms.txt
                  </button>

                  <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
                    <pre className="text-sm text-gray-300 whitespace-pre-wrap">
                      {job.llmstxt_content}
                    </pre>
                  </div>
                </div>
              )}
            </div>

            {/* Assessment Results */}
            {job.status === 'completed' && job.assessment_json && (
              <AssessmentDisplay assessment={job.assessment_json} />
            )}

            {/* Start Over Button */}
            <button
              onClick={() => {
                setJobId(null);
                setUrl('');
              }}
              className="btn btn-secondary w-full"
            >
              Generate Another
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: Job['status'] }) {
  const styles = {
    pending: 'bg-yellow-100 text-yellow-800',
    processing: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  };

  const icons = {
    pending: <Loader2 className="w-4 h-4 animate-spin" />,
    processing: <Loader2 className="w-4 h-4 animate-spin" />,
    completed: <CheckCircle2 className="w-4 h-4" />,
    failed: <XCircle className="w-4 h-4" />,
  };

  return (
    <span className={`px-3 py-1 rounded-full text-sm font-medium flex items-center gap-1.5 ${styles[status]}`}>
      {icons[status]}
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}
