import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Loader2, X, AlertCircle } from 'lucide-react';
import apiClient from '../api/client';
import type { Template } from '../types';

interface SubscriptionFlowProps {
  url: string;
  template: Template;
  onCancel: () => void;
  userEmail?: string;
}

export default function SubscriptionFlow({
  url,
  template,
  onCancel,
  userEmail,
}: SubscriptionFlowProps) {
  const [email, setEmail] = useState(userEmail || '');

  const createSubscriptionMutation = useMutation({
    mutationFn: () =>
      apiClient.createSubscription({
        url,
        template,
        email: email || undefined,
        success_url: `${window.location.origin}/dashboard?subscription=success`,
        cancel_url: `${window.location.origin}/pricing?subscription=cancelled`,
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
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
        <div className="flex justify-between items-start mb-6">
          <div>
            <h2 className="text-xl font-bold text-gray-900">
              Subscribe to Monitoring
            </h2>
            <p className="text-gray-600 mt-1">
              £9/month - Cancel anytime
            </p>
          </div>
          <button
            onClick={onCancel}
            className="p-1 hover:bg-gray-100 rounded-full transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="label">URL to Monitor</label>
            <p className="text-gray-900 font-medium">{url}</p>
          </div>

          <div>
            <label htmlFor="email" className="label">
              Email (optional)
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
              We'll send change notifications to this email
            </p>
          </div>

          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="font-semibold text-gray-900 mb-2">What you'll get:</h3>
            <ul className="text-sm text-gray-600 space-y-1">
              <li>- Weekly or monthly llms.txt regeneration</li>
              <li>- Email notifications when changes detected</li>
              <li>- Full quality assessment with each check</li>
              <li>- Change history and comparison</li>
            </ul>
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

          <div className="flex gap-3">
            <button
              type="button"
              onClick={onCancel}
              className="btn btn-secondary flex-1"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createSubscriptionMutation.isPending}
              className="btn btn-primary flex-1"
            >
              {createSubscriptionMutation.isPending ? (
                <>
                  <Loader2 className="inline-block animate-spin mr-2 w-4 h-4" />
                  Loading...
                </>
              ) : (
                'Continue to Payment'
              )}
            </button>
          </div>

          <p className="text-xs text-center text-gray-500">
            You'll be redirected to Stripe to complete payment
          </p>
        </form>
      </div>
    </div>
  );
}
