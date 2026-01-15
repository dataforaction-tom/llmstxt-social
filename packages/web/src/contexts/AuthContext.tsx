/**
 * Authentication context for managing user state
 */

import { createContext, useContext, useState, ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '../api/client';
import type { User } from '../types';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string) => Promise<{ success: boolean; message: string }>;
  logout: () => Promise<void>;
  verifyToken: (token: string) => Promise<{ success: boolean; user?: User; message: string }>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [verifying, setVerifying] = useState(false);

  // Check auth status on mount
  const { data: authData, isPending, isFetching, refetch } = useQuery({
    queryKey: ['auth'],
    queryFn: apiClient.checkAuth,
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: false,
  });

  // Consider loading if query is pending (no data yet) or actively fetching
  const isLoading = isPending || isFetching || verifying;

  const user = authData?.authenticated ? authData.user : null;

  const login = async (email: string): Promise<{ success: boolean; message: string }> => {
    try {
      const response = await apiClient.sendMagicLink(email);
      return { success: true, message: response.message };
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to send magic link';
      return { success: false, message };
    }
  };

  const verifyToken = async (token: string): Promise<{ success: boolean; user?: User; message: string }> => {
    setVerifying(true);
    try {
      const response = await apiClient.verifyMagicLink(token);
      // Refetch auth status after successful verification
      await refetch();
      return { success: true, user: response.user, message: response.message };
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Invalid or expired link';
      return { success: false, message };
    } finally {
      setVerifying(false);
    }
  };

  const logout = async () => {
    try {
      await apiClient.logout();
    } finally {
      // Clear auth data regardless of API response
      queryClient.setQueryData(['auth'], { authenticated: false, user: null });
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        logout,
        verifyToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
