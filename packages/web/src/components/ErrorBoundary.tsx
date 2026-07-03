import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
}

/**
 * Last-resort error boundary around the route tree.
 *
 * Without it, any render-time throw (a bad API payload shape, an undefined
 * deref in a page component) blanks the entire SPA to a white screen with no
 * recovery. This catches the throw and shows a usable fallback with a reload.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Surface to the console for diagnosis; a real backend hook can go here.
    console.error('Unhandled UI error:', error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div role="alert" className="mx-auto max-w-lg p-8 text-center">
          <h1 className="font-display text-2xl text-navy">Something went wrong</h1>
          <p className="mt-2 text-grey-blue">
            The page hit an unexpected error. Reloading usually fixes it.
          </p>
          <button
            type="button"
            className="mt-4 rounded bg-primary-700 px-4 py-2 text-white"
            onClick={() => window.location.reload()}
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
