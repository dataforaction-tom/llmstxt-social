import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Loader2, Globe, Check, AlertCircle } from 'lucide-react';
import apiClient from '../api/client';
import type { Template } from '../types';

export default function SubscribePage() {
  const navigate = useNavigate();
  const [url, setUrl] = useState('');
  const [template, setTemplate] = useState<Template>('charity');
  const [email, setEmail] = useState('');

  const createSubscriptionMutation = useMutation({
    mutationFn: () =>
      apiClient.createSubscription({
        url,
        template,
        email: email || undefined,
        success_url: `${window.location.origin}/dashboard?subscription=success`,
        cancel_url: `${window.location.origin}/subscribe?cancelled=true`,
      }),
    onSuccess: (data) => {
      // Redirect to Stripe Checkout
      window.location.href = data.checkout_url;
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createSubscriptionMutation.mutate();
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="max-w-2xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Subscribe to Monitoring
          </h1>
          <p className="text-gray-600">
            Get automatic llms.txt updates when your website changes
          </p>
        </div>

        <div className="grid md:grid-cols-5 gap-8">
          {/* Form */}
          <div className="md:col-span-3">
            <form onSubmit={handleSubmit} className="card space-y-6">
              <div>
                <label htmlFor="url" className="label">
                  Website URL
                </label>
                <div className="relative">
                  <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    type="url"
                    id="url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://example-charity.org.uk"
                    className="input pl-10"
                    required
                  />
                </div>
              </div>

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

              <div>
                <label htmlFor="email" className="label">
                  Notification Email
                </label>
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="input"
                />
                <p className="text-sm text-gray-500 mt-1">
                  We'll notify you when changes are detected
                </p>
              </div>

              {createSubscriptionMutation.isError && (
                <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
                  <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                  <p className="text-red-800 text-sm">
                    {(createSubscriptionMutation.error as Error)?.message ||
                      'Failed to create subscription. Please try again.'}
                  </p>
                </div>
              )}

              <button
                type="submit"
                disabled={createSubscriptionMutation.isPending || !url}
                className="btn btn-primary w-full"
              >
                {createSubscriptionMutation.isPending ? (
                  <>
                    <Loader2 className="inline-block animate-spin mr-2 w-4 h-4" />
                    Loading...
                  </>
                ) : (
                  'Continue to Payment - £9/month'
                )}
              </button>

              <p className="text-xs text-center text-gray-500">
                You'll be redirected to Stripe to complete payment. Cancel anytime.
              </p>
            </form>
          </div>

          {/* Benefits */}
          <div className="md:col-span-2">
            <div className="bg-gray-50 rounded-xl p-6">
              <h3 className="font-semibold text-gray-900 mb-4">
                What's included
              </h3>
              <ul className="space-y-3">
                {[
                  'Weekly llms.txt regeneration',
                  'Email change notifications',
                  'Full quality assessment',
                  'Enrichment data included',
                  'Change history tracking',
                  'Dashboard access',
                  'Cancel anytime',
                ].map((feature, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm">
                    <Check className="w-4 h-4 text-primary-600 flex-shrink-0 mt-0.5" />
                    <span className="text-gray-700">{feature}</span>
                  </li>
                ))}
              </ul>

              <div className="mt-6 pt-6 border-t border-gray-200">
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-bold text-gray-900">£9</span>
                  <span className="text-gray-600">/month</span>
                </div>
                <p className="text-sm text-gray-500 mt-1">
                  Billed monthly. Cancel anytime.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
