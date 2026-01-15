import { useState, useEffect } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, useStripe, useElements, PaymentElement } from '@stripe/react-stripe-js';
import { useMutation } from '@tanstack/react-query';
import { X, Loader2, AlertCircle } from 'lucide-react';
import apiClient from '../api/client';
import type { Template } from '../types';

// Initialize Stripe outside component to avoid recreating on each render
const stripePromise = loadStripe(
  import.meta.env.VITE_STRIPE_PUBLIC_KEY || 'pk_test_dummy'
);

interface PaymentFlowProps {
  url: string;
  template: Template;
  onSuccess: (paymentIntentId: string) => void;
  onCancel: () => void;
}

export default function PaymentFlow({ url, template, onSuccess, onCancel }: PaymentFlowProps) {
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Create payment intent on mount
  const paymentMutation = useMutation({
    mutationFn: () => apiClient.createPaymentIntent({ url, template }),
    onSuccess: (data) => {
      setClientSecret(data.client_secret);
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to initialize payment');
    },
  });

  useEffect(() => {
    paymentMutation.mutate();
  }, []);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl max-w-md w-full p-6 relative">
        <button
          onClick={onCancel}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
        >
          <X className="w-6 h-6" />
        </button>

        <h2 className="text-2xl font-bold mb-4">Payment</h2>
        <p className="text-gray-600 mb-6">
          Complete your payment to generate llms.txt with full assessment and enrichment data.
        </p>

        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="flex justify-between mb-2">
            <span className="text-gray-700">Full Generation + Assessment</span>
            <span className="font-semibold">£29.00</span>
          </div>
          <p className="text-sm text-gray-600">
            One-time payment - Valid for 30 days
          </p>
        </div>

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
          'Pay £29.00'
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
