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
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
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

  // Payment endpoints
  createPaymentIntent: async (request: GenerateRequest): Promise<PaymentIntent> => {
    const { data } = await api.post('/api/payment/create-intent', request);
    return data;
  },
};

export default apiClient;
