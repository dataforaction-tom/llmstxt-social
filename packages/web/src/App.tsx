import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import helmetAsync from 'react-helmet-async';
const { HelmetProvider } = helmetAsync;
import HomePage from './pages/Home';
import GeneratePage from './pages/Generate';
import PricingPage from './pages/Pricing';
import DashboardPage from './pages/Dashboard';
import SubscribePage from './pages/Subscribe';
import LoginPage from './pages/Login';
import AuthVerifyPage from './pages/AuthVerify';
import Layout from './components/Layout';
import { AuthProvider, useAuth } from './contexts/AuthContext';

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  });
}

const defaultQueryClient = createQueryClient();

// Protected route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/generate" element={<GeneratePage />} />
      <Route path="/pricing" element={<PricingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/verify" element={<AuthVerifyPage />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route path="/subscribe" element={<SubscribePage />} />
    </Routes>
  );
}

export function AppProviders({
  children,
  queryClient = defaultQueryClient,
}: {
  children: React.ReactNode;
  queryClient?: QueryClient;
}) {
  return (
    <HelmetProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>{children}</AuthProvider>
      </QueryClientProvider>
    </HelmetProvider>
  );
}

function App() {
  return (
    <AppProviders>
      <BrowserRouter>
        <Layout>
          <AppRoutes />
        </Layout>
      </BrowserRouter>
    </AppProviders>
  );
}

export default App;
