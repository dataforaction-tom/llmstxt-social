import { Link } from 'react-router-dom';
import { FileText, User, LogOut, ExternalLink } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const { user, isAuthenticated, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Skip Link for Keyboard Navigation */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-primary-600 focus:text-white focus:rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400"
      >
        Skip to main content
      </a>

      {/* Navigation */}
      <nav className="bg-white border-b border-gray-200" aria-label="Main navigation">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            {/* Logo */}
            <Link to="/" className="flex items-center space-x-2" aria-label="llms.txt Generator - Home">
              <FileText className="w-8 h-8 text-primary-600" aria-hidden="true" />
              <span className="text-xl font-bold text-gray-900">
                llms.txt Generator
              </span>
            </Link>

            {/* Nav Links */}
            <div className="flex items-center space-x-8" role="navigation">
              <Link
                to="/"
                className="text-gray-700 hover:text-primary-600 transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 rounded-md px-1"
              >
                Home
              </Link>
              <Link
                to="/generate"
                className="text-gray-700 hover:text-primary-600 transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 rounded-md px-1"
              >
                Generate
              </Link>
              <Link
                to="/pricing"
                className="text-gray-700 hover:text-primary-600 transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 rounded-md px-1"
              >
                Pricing
              </Link>
              {isAuthenticated && (
                <Link
                  to="/dashboard"
                  className="text-gray-700 hover:text-primary-600 transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 rounded-md px-1"
                >
                  Dashboard
                </Link>
              )}
              <a
                href="https://llmstxt.org"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-700 hover:text-primary-600 transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 rounded-md px-1 inline-flex items-center gap-1"
              >
                Spec
                <ExternalLink className="w-3 h-3" aria-hidden="true" />
                <span className="sr-only">(opens in new tab)</span>
              </a>

              {/* Auth section */}
              {isAuthenticated ? (
                <div className="flex items-center gap-4 ml-4 pl-4 border-l border-gray-200">
                  <span className="text-sm text-gray-600 flex items-center gap-2">
                    <User className="w-4 h-4" aria-hidden="true" />
                    <span className="sr-only">Logged in as </span>
                    {user?.email}
                  </span>
                  <button
                    onClick={handleLogout}
                    className="text-gray-500 hover:text-red-600 transition-colors focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 rounded-md p-1"
                    aria-label="Log out"
                  >
                    <LogOut className="w-5 h-5" aria-hidden="true" />
                  </button>
                </div>
              ) : (
                <Link
                  to="/login"
                  className="ml-4 btn btn-primary text-sm focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
                >
                  Log in
                </Link>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main id="main-content" className="flex-1" role="main">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-gray-50 border-t border-gray-200 mt-auto" role="contentinfo">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-gray-600 text-sm">
            <p>
              Built for the UK social sector •{' '}
              <a
                href="https://llmstxt.org"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-600 hover:text-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 rounded"
              >
                llms.txt specification
                <span className="sr-only">(opens in new tab)</span>
              </a>
            </p>
            <p className="mt-2">
              Made with <span aria-label="love">❤️</span> for charities, funders, and social enterprises
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
