import React from 'react';
import ReactDOM from 'react-dom/client';
import { init } from '@plausible-analytics/tracker';
import App from './App.tsx';
import './index.css';

if (typeof window !== 'undefined') {
  init({ domain: 'llmstxt.social' });
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
