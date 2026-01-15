/**
 * Magic link verification page
 */

import { useEffect, useState } from 'react';
import { useSearchParams, Navigate, Link } from 'react-router-dom';
import { Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export default function AuthVerifyPage() {
  const [searchParams] = useSearchParams();
  const { verifyToken, isAuthenticated } = useAuth();
  const [status, setStatus] = useState<'verifying' | 'success' | 'error'>('verifying');
  const [errorMessage, setErrorMessage] = useState('');

  const token = searchParams.get('token');

  useEffect(() => {
    const verify = async () => {
      if (!token) {
        setStatus('error');
        setErrorMessage('No verification token provided');
        return;
      }

      const result = await verifyToken(token);
      if (result.success) {
        setStatus('success');
      } else {
        setStatus('error');
        setErrorMessage(result.message);
      }
    };

    verify();
  }, [token, verifyToken]);

  // Redirect to dashboard after successful login
  if (status === 'success' || isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="min-h-[60vh] flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        {status === 'verifying' && (
          <>
            <div className="mx-auto w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mb-6">
              <Loader2 className="w-8 h-8 text-primary-600 animate-spin" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-4">Verifying your link...</h1>
            <p className="text-gray-600">Please wait while we log you in.</p>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="mx-auto w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-6">
              <XCircle className="w-8 h-8 text-red-600" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-4">Link expired or invalid</h1>
            <p className="text-gray-600 mb-6">{errorMessage}</p>
            <Link to="/login" className="btn btn-primary">
              Request a new link
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
