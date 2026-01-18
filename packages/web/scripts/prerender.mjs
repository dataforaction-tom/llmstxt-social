import React from 'react';
import path from 'node:path';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createServer } from 'vite';
import { renderToString } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom/server.js';

const routes = ['/', '/pricing', '/login'];
const rootDir = process.cwd();
const distDir = path.join(rootDir, 'dist');
const templatePath = path.join(distDir, 'index.html');

const template = await readFile(templatePath, 'utf8');
const vite = await createServer({
  root: rootDir,
  logLevel: 'error',
  server: { middlewareMode: true },
});

try {
  const { AppRoutes, AppProviders, createQueryClient } = await vite.ssrLoadModule('/src/App.tsx');
  const { default: Layout } = await vite.ssrLoadModule('/src/components/Layout.tsx');

  for (const route of routes) {
    const appHtml = renderToString(
      React.createElement(
        AppProviders,
        { queryClient: createQueryClient() },
        React.createElement(
          StaticRouter,
          { location: route },
          React.createElement(Layout, null, React.createElement(AppRoutes))
        )
      )
    );

    const html = template.replace('<div id="root"></div>', `<div id="root">${appHtml}</div>`);
    const outDir = route === '/' ? distDir : path.join(distDir, route.replace(/^\/+/, ''));

    await mkdir(outDir, { recursive: true });
    await writeFile(path.join(outDir, 'index.html'), html);
  }
} finally {
  await vite.close();
}
