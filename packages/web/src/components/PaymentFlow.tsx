import { useState } from 'react';
import { useStripe, useElements, PaymentElement } from '@stripe/react-stripe-js';
import { useMutation } from '@tanstack/react-query';
import { X, Loader2 } from 'lucide-react';
import apiClient from '../api/client';
import type { Template } from '../types';

interface PaymentFlowProps {
  url: string;
  template: Template;
  onSuccess: (paymentIntentId: string) => void;
  onCancel: () => void;
}

export default function PaymentFlow({ url, template, onSuccess, onCancel }: PaymentFlowProps) {
  const stripe = useStripe();
  const elements = useElements();
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);

  // Create payment intent
  const paymentMutation = useMutation({
    mutationFn: () => apiClient.createPaymentIntent({ url, template }),
    onSuccess: (data) => {
      setClientSecret(data.client_secret);
    },
  });

  // Load payment form on mount
  useState(() => {
    paymentMutation.mutate();
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!stripe || !elements || !clientSecret) {
      return;
    }

    setProcessing(true);

    try {
      const { error, paymentIntent } = await stripe.confirmPayment({
        elements,
        confirmParams: {
          return_url: window.location.href,
        },
        redirect: 'if_required',
      });

      if (error) {
        alert(error.message);
      } else if (paymentIntent && paymentIntent.status === 'succeeded') {
        onSuccess(paymentIntent.id);
      }
    } catch (err) {
      console.error('Payment error:', err);
      alert('Payment failed. Please try again.');
    } finally {
      setProcessing(false);
    }
  };

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
            One-time payment • Valid for 30 days
          </p>
        </div>

        {paymentMutation.isPending && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="animate-spin w-8 h-8 text-primary-600" />
          </div>
        )}

        {clientSecret && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <PaymentElement />

            <button
              type="submit"
              disabled={!stripe || processing}
              className="btn btn-primary w-full"
            >
              {processing ? (
                <>
                  <Loader2 className="inline-block animate-spin mr-2" />
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
        )}
      </div>
    </div>
  );
}
