import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams, Navigate } from 'react-router-dom';
import {
  CheckCircle2,
  XCircle,
  Calendar,
  Globe,
  FileText,
  Loader2,
  ChevronDown,
  ChevronUp,
  AlertCircle,
} from 'lucide-react';
import apiClient from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import type { Subscription, MonitoringHistory } from '../types';

export default function DashboardPage() {
  const [searchParams] = useSearchParams();
  const subscriptionSuccess = searchParams.get('subscription') === 'success';
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const { data: subscriptions, isLoading } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: () => apiClient.listSubscriptions(false), // Get all including cancelled
    enabled: isAuthenticated, // Only fetch when authenticated
  });

  // Show loading while checking auth
  if (authLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-600 mt-1">Manage your subscriptions and monitoring</p>
        </div>
        <Link to="/pricing" className="btn btn-primary">
          New Subscription
        </Link>
      </div>

      {subscriptionSuccess && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg flex items-start gap-3">
          <CheckCircle2 className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-green-800">Subscription activated!</p>
            <p className="text-green-700 text-sm">
              Your monitoring subscription is now active. We'll check your site regularly and notify you of changes.
            </p>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
        </div>
      )}

      {subscriptions && subscriptions.length === 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
          <Globe className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">No subscriptions yet</h2>
          <p className="text-gray-600 mb-6">
            Start monitoring your website's llms.txt to get notified when content changes.
          </p>
          <Link to="/pricing" className="btn btn-primary">
            Get Started
          </Link>
        </div>
      )}

      {subscriptions && subscriptions.length > 0 && (
        <div className="space-y-6">
          {subscriptions.map((subscription) => (
            <SubscriptionCard key={subscription.id} subscription={subscription} />
          ))}
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

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <div className="p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className={`p-3 rounded-lg ${subscription.active ? 'bg-green-100' : 'bg-gray-100'}`}>
              <Globe className={`w-6 h-6 ${subscription.active ? 'text-green-600' : 'text-gray-500'}`} />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">{subscription.url}</h3>
              <p className="text-sm text-gray-500">
                Template: {subscription.template} | Frequency: {subscription.frequency}
              </p>
            </div>
          </div>
          <StatusBadge active={subscription.active} />
        </div>

        <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
          <div className="flex items-center gap-2 text-gray-600">
            <Calendar className="w-4 h-4" />
            <span>Created: {new Date(subscription.created_at).toLocaleDateString()}</span>
          </div>
          {subscription.last_check && (
            <div className="flex items-center gap-2 text-gray-600">
              <CheckCircle2 className="w-4 h-4" />
              <span>Last check: {new Date(subscription.last_check).toLocaleDateString()}</span>
            </div>
          )}
          {subscription.last_change_detected && (
            <div className="flex items-center gap-2 text-orange-600">
              <AlertCircle className="w-4 h-4" />
              <span>Change: {new Date(subscription.last_change_detected).toLocaleDateString()}</span>
            </div>
          )}
        </div>

        <div className="mt-4 flex items-center justify-between">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
          >
            {expanded ? (
              <>
                <ChevronUp className="w-4 h-4" />
                Hide History
              </>
            ) : (
              <>
                <ChevronDown className="w-4 h-4" />
                View History
              </>
            )}
          </button>

          {subscription.active && (
            <button
              onClick={handleCancel}
              disabled={cancelMutation.isPending}
              className="text-sm text-red-600 hover:text-red-700"
            >
              {cancelMutation.isPending ? 'Cancelling...' : 'Cancel Subscription'}
            </button>
          )}
        </div>
      </div>

      {expanded && (
        <div className="border-t border-gray-200 bg-gray-50 p-6">
          <h4 className="font-semibold text-gray-900 mb-4">Monitoring History</h4>

          {historyLoading && (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="w-5 h-5 animate-spin text-primary-600" />
            </div>
          )}

          {history && history.length === 0 && (
            <p className="text-gray-500 text-sm">No monitoring checks yet.</p>
          )}

          {history && history.length > 0 && (
            <div className="space-y-3">
              {history.map((entry) => (
                <HistoryEntry key={entry.id} entry={entry} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function HistoryEntry({ entry }: { entry: MonitoringHistory }) {
  const [showContent, setShowContent] = useState(false);

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {entry.changed ? (
            <div className="p-1.5 rounded-full bg-orange-100">
              <AlertCircle className="w-4 h-4 text-orange-600" />
            </div>
          ) : (
            <div className="p-1.5 rounded-full bg-green-100">
              <CheckCircle2 className="w-4 h-4 text-green-600" />
            </div>
          )}
          <div>
            <p className="font-medium text-gray-900">
              {new Date(entry.checked_at).toLocaleString()}
            </p>
            <p className="text-sm text-gray-500">
              {entry.changed ? 'Changes detected' : 'No changes'}
              {entry.notification_sent && ' - Notification sent'}
            </p>
          </div>
        </div>

        {entry.llmstxt_content && (
          <button
            onClick={() => setShowContent(!showContent)}
            className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
          >
            <FileText className="w-4 h-4" />
            {showContent ? 'Hide' : 'View'} Content
          </button>
        )}
      </div>

      {showContent && entry.llmstxt_content && (
        <div className="mt-4 bg-gray-900 rounded-lg p-4 overflow-x-auto">
          <pre className="text-sm text-gray-300 whitespace-pre-wrap">
            {entry.llmstxt_content}
          </pre>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ active }: { active: boolean }) {
  if (active) {
    return (
      <span className="px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800 flex items-center gap-1.5">
        <CheckCircle2 className="w-4 h-4" />
        Active
      </span>
    );
  }
  return (
    <span className="px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-600 flex items-center gap-1.5">
      <XCircle className="w-4 h-4" />
      Cancelled
    </span>
  );
}
