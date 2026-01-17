/**
 * API client for llmstxt backend
 */

import axios from 'axios';
import type {
  GenerateRequest,
  GeneratePaidRequest,
  Job,
  PaymentIntent,
  HealthResponse,
  Subscription,
  SubscriptionCreateRequest,
  CheckoutSession,
  MonitoringHistory,
  User,
  AuthResponse,
  AuthCheckResponse,
  MagicLinkResponse,
  TemplateOptions,
  Template,
  RecalculatedScoreResponse,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

const api = axios.create({
  baseURL: API_BASE_URL || undefined,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Enable cookies for auth
});

export const apiClient = {
  // Health check
  health: async (): Promise<HealthResponse> => {
    const { data } = await api.get('/health');
    return data;
  },

  // Generation endpoints
  generateFree: async (request: GenerateRequest): Promise<Job> => {
    const { data } = await api.post('/api/generate/free', request);
    return data;
  },

  generatePaid: async (request: GeneratePaidRequest): Promise<Job> => {
    const { data } = await api.post('/api/generate/paid', request);
    return data;
  },

  getJob: async (jobId: string): Promise<Job> => {
    const { data } = await api.get(`/api/jobs/${jobId}`);
    return data;
  },

  dismissFindings: async (jobId: string, dismissedIndices: number[]): Promise<RecalculatedScoreResponse> => {
    const { data } = await api.post(`/api/jobs/${jobId}/dismiss-findings`, {
      dismissed_indices: dismissedIndices,
    });
    return data;
  },

  listAssessments: async (): Promise<Job[]> => {
    const { data } = await api.get('/api/assessments');
    return data;
  },

  // Template options (sectors/goals)
  getTemplateOptions: async (template: Template): Promise<TemplateOptions> => {
    const { data } = await api.get(`/api/templates/${template}/options`);
    return data;
  },

  // Payment endpoints
  createPaymentIntent: async (request: GenerateRequest): Promise<PaymentIntent> => {
    const { data } = await api.post('/api/payment/create-intent', request);
    return data;
  },

  // Subscription endpoints
  createSubscription: async (request: SubscriptionCreateRequest): Promise<CheckoutSession> => {
    const { data } = await api.post('/api/subscriptions', request);
    return data;
  },

  listSubscriptions: async (activeOnly: boolean = true): Promise<Subscription[]> => {
    const { data } = await api.get('/api/subscriptions', {
      params: { active_only: activeOnly },
    });
    return data;
  },

  getSubscription: async (subscriptionId: string): Promise<Subscription> => {
    const { data } = await api.get(`/api/subscriptions/${subscriptionId}`);
    return data;
  },

  cancelSubscription: async (subscriptionId: string): Promise<Subscription> => {
    const { data } = await api.post(`/api/subscriptions/${subscriptionId}/cancel`);
    return data;
  },

  getSubscriptionHistory: async (subscriptionId: string, limit: number = 20): Promise<MonitoringHistory[]> => {
    const { data } = await api.get(`/api/subscriptions/${subscriptionId}/history`, {
      params: { limit },
    });
    return data;
  },

  // Auth endpoints
  sendMagicLink: async (email: string): Promise<MagicLinkResponse> => {
    const { data } = await api.post('/api/auth/magic-link', { email });
    return data;
  },

  verifyMagicLink: async (token: string): Promise<AuthResponse> => {
    const { data } = await api.post('/api/auth/verify', { token });
    return data;
  },

  checkAuth: async (): Promise<AuthCheckResponse> => {
    const { data } = await api.get('/api/auth/check');
    return data;
  },

  getMe: async (): Promise<User> => {
    const { data } = await api.get('/api/auth/me');
    return data;
  },

  logout: async (): Promise<void> => {
    await api.post('/api/auth/logout');
  },
};

export default apiClient;
