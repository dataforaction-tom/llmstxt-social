import React from 'react';
import path from 'node:path';
import { readFile, writeFile, mkdir, access, constants } from 'node:fs/promises';
import { createServer } from 'vite';
import { renderToString } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom/server.js';
import pkg from 'react-helmet-async';
const { HelmetProvider } = pkg;

const routes = ['/', '/pricing', '/login', '/generate', '/subscribe'];
const rootDir = process.cwd();
const distDir = path.join(rootDir, 'dist');
const templatePath = path.join(distDir, 'index.html');

console.log('Starting prerender...');
console.log('Root directory:', rootDir);
console.log('Dist directory:', distDir);

// Verify dist directory exists
try {
  await access(distDir, constants.R_OK);
  console.log('Dist directory exists');
} catch {
  console.error('ERROR: Dist directory does not exist. Run build first.');
  process.exit(1);
}

// Verify template exists
let template;
try {
  template = await readFile(templatePath, 'utf8');
  console.log('Template loaded successfully');
} catch (err) {
  console.error('ERROR: Could not read template:', err.message);
  process.exit(1);
}

// Create Vite server
let vite;
try {
  vite = await createServer({
    root: rootDir,
    logLevel: 'error',
    server: { middlewareMode: true },
  });
  console.log('Vite server created');
} catch (err) {
  console.error('ERROR: Could not create Vite server:', err.message);
  process.exit(1);
}

try {
  // Load app modules
  console.log('Loading app modules...');
  const { AppRoutes, AppProviders, createQueryClient } = await vite.ssrLoadModule('/src/App.tsx');
  const { default: Layout } = await vite.ssrLoadModule('/src/components/Layout.tsx');
  console.log('App modules loaded successfully');

  // Prerender each route
  for (const route of routes) {
    console.log(`Prerendering ${route}...`);

    try {
      const helmetContext = {};

      const appHtml = renderToString(
        React.createElement(
          HelmetProvider,
          { context: helmetContext },
          React.createElement(
            AppProviders,
            { queryClient: createQueryClient() },
            React.createElement(
              StaticRouter,
              { location: route },
              React.createElement(Layout, null, React.createElement(AppRoutes))
            )
          )
        )
      );

      // Inject helmet data into template
      const { helmet } = helmetContext;
      let html = template.replace('<div id="root"></div>', `<div id="root">${appHtml}</div>`);

      // Inject helmet tags if available
      if (helmet) {
        const headTags = [
          helmet.title?.toString() || '',
          helmet.meta?.toString() || '',
          helmet.link?.toString() || '',
        ].filter(Boolean).join('\n');

        if (headTags) {
          html = html.replace('</head>', `${headTags}\n</head>`);
        }
      }

      const outDir = route === '/' ? distDir : path.join(distDir, route.replace(/^\/+/, ''));

      // Ensure output directory exists
      await mkdir(outDir, { recursive: true });

      // Write prerendered HTML
      const outPath = path.join(outDir, 'index.html');
      await writeFile(outPath, html);
      console.log(`  Written: ${outPath}`);
    } catch (routeErr) {
      console.error(`  ERROR prerendering ${route}:`, routeErr.message);
      // Continue with other routes
    }
  }

  console.log('Prerender complete!');
} catch (err) {
  console.error('ERROR during prerender:', err.message);
  console.error(err.stack);
  process.exit(1);
} finally {
  await vite.close();
  console.log('Vite server closed');
}
