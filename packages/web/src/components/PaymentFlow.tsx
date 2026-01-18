import { useState, useEffect, useCallback } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, useStripe, useElements, PaymentElement } from '@stripe/react-stripe-js';
import { useMutation } from '@tanstack/react-query';
import { X, Loader2, AlertCircle } from 'lucide-react';
import FocusTrap from 'focus-trap-react';
import apiClient from '../api/client';
import type { Template } from '../types';

// Initialize Stripe outside component to avoid recreating on each render
const stripePromise = loadStripe(
  import.meta.env.VITE_STRIPE_PUBLIC_KEY || 'pk_test_dummy'
);

interface PaymentFlowProps {
  url: string;
  template: Template;
  sector?: string;
  goal?: string;
  userEmail?: string;
  onSuccess: (paymentIntentId: string) => void;
  onCancel: () => void;
}

export default function PaymentFlow({ url, template, sector, goal, userEmail, onSuccess, onCancel }: PaymentFlowProps) {
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState(userEmail || '');

  // Handle Escape key to close modal
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      onCancel();
    }
  }, [onCancel]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Create payment intent on mount
  const paymentMutation = useMutation({
    mutationFn: () => apiClient.createPaymentIntent({
      url,
      template,
      sector,
      goal,
      customer_email: (userEmail || email) || undefined,
    }),
    onSuccess: (data) => {
      setClientSecret(data.client_secret);
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to initialize payment');
    },
  });

  useEffect(() => {
    if (userEmail || email) {
      paymentMutation.mutate();
    }
  }, [userEmail, email]);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <FocusTrap>
        <div
          className="bg-white rounded-xl max-w-md w-full p-6 relative"
          role="dialog"
          aria-modal="true"
          aria-labelledby="payment-dialog-title"
        >
          <button
            onClick={onCancel}
            className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            aria-label="Close dialog"
          >
            <X className="w-6 h-6" aria-hidden="true" />
          </button>

          <h2 id="payment-dialog-title" className="text-2xl font-bold mb-4">Payment</h2>
        <p className="text-gray-600 mb-6">
          Complete your payment to generate llms.txt with full assessment and enrichment data.
        </p>

        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="flex justify-between mb-2">
            <span className="text-gray-700">Full Generation + Assessment</span>
            <span className="font-semibold">£9.00</span>
          </div>
          <p className="text-sm text-gray-600">
            One-time payment - Valid for 30 days
          </p>
        </div>

        {!userEmail && (
          <div className="mb-6">
            <label htmlFor="email" className="label">
              Email for receipt and dashboard access <span aria-hidden="true" className="text-red-500">*</span>
            </label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="input"
              required
              aria-required="true"
            />
          </div>
        )}

        {paymentMutation.isPending && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="animate-spin w-8 h-8 text-primary-600" />
            <span className="ml-2 text-gray-600">Loading payment form...</span>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 p-4 bg-red-50 border border-red-200 rounded-lg mb-4">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-red-800 font-medium">Payment Error</p>
              <p className="text-red-700 text-sm">{error}</p>
            </div>
          </div>
        )}

        {clientSecret && (
          <Elements
            stripe={stripePromise}
            options={{
              clientSecret,
              appearance: {
                theme: 'stripe',
                variables: {
                  colorPrimary: '#6366f1',
                },
              },
            }}
          >
            <PaymentForm onSuccess={onSuccess} onCancel={onCancel} />
          </Elements>
        )}
        </div>
      </FocusTrap>
    </div>
  );
}

interface PaymentFormProps {
  onSuccess: (paymentIntentId: string) => void;
  onCancel: () => void;
}

function PaymentForm({ onSuccess, onCancel }: PaymentFormProps) {
  const stripe = useStripe();
  const elements = useElements();
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!stripe || !elements) {
      return;
    }

    setProcessing(true);
    setError(null);

    try {
      const { error: submitError, paymentIntent } = await stripe.confirmPayment({
        elements,
        confirmParams: {
          return_url: window.location.href,
        },
        redirect: 'if_required',
      });

      if (submitError) {
        setError(submitError.message || 'Payment failed');
      } else if (paymentIntent && paymentIntent.status === 'succeeded') {
        onSuccess(paymentIntent.id);
      }
    } catch (err) {
      console.error('Payment error:', err);
      setError('Payment failed. Please try again.');
    } finally {
      setProcessing(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <PaymentElement />

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800 text-sm">{error}</p>
        </div>
      )}

      <button
        type="submit"
        disabled={!stripe || processing}
        className="btn btn-primary w-full"
      >
        {processing ? (
          <>
            <Loader2 className="inline-block animate-spin mr-2 w-4 h-4" />
            Processing...
          </>
        ) : (
          'Pay £9.00'
        )}
      </button>

      <button
        type="button"
        onClick={onCancel}
        className="btn btn-secondary w-full"
      >
        Cancel
      </button>
    </form>
  );
}
