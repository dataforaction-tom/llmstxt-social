import { Link } from 'react-router-dom';
import { FileText } from 'lucide-react';

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Navigation */}
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            {/* Logo */}
            <Link to="/" className="flex items-center space-x-2">
              <FileText className="w-8 h-8 text-primary-600" />
              <span className="text-xl font-bold text-gray-900">
                llms.txt Generator
              </span>
            </Link>

            {/* Nav Links */}
            <div className="flex items-center space-x-8">
              <Link
                to="/"
                className="text-gray-700 hover:text-primary-600 transition-colors"
              >
                Home
              </Link>
              <Link
                to="/generate"
                className="text-gray-700 hover:text-primary-600 transition-colors"
              >
                Generate
              </Link>
              <Link
                to="/pricing"
                className="text-gray-700 hover:text-primary-600 transition-colors"
              >
                Pricing
              </Link>
              <Link
                to="/dashboard"
                className="text-gray-700 hover:text-primary-600 transition-colors"
              >
                Dashboard
              </Link>
              <a
                href="https://llmstxt.org"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-700 hover:text-primary-600 transition-colors"
              >
                Spec
              </a>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="flex-1">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-gray-50 border-t border-gray-200 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center text-gray-600 text-sm">
            <p>
              Built for the UK social sector •{' '}
              <a
                href="https://llmstxt.org"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-600 hover:text-primary-700"
              >
                llms.txt specification
              </a>
            </p>
            <p className="mt-2">
              Made with ❤️ for charities, funders, and social enterprises
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
