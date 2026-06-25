import React from 'react';
import ReactDOM from 'react-dom/client';
// Self-hosted editorial type system for Open Org pages. Variable axes for
// Fraunces (opsz, wght) and DM Sans (wght) keep the request budget low.
// Static 400/500 for JetBrains Mono — mono doesn't need variation.
import '@fontsource-variable/fraunces';
import '@fontsource-variable/dm-sans';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';
import App from './App.tsx';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);