/**
 * Generates sitemap.xml during build
 */

import { writeFile, stat } from 'node:fs/promises';
import path from 'node:path';

const BASE_URL = 'https://llmstxt.social';

// Define site routes with their priorities and change frequencies
const routes = [
  { path: '/', priority: 1.0, changefreq: 'weekly' },
  { path: '/generate', priority: 0.9, changefreq: 'monthly' },
  { path: '/pricing', priority: 0.8, changefreq: 'monthly' },
  { path: '/login', priority: 0.5, changefreq: 'yearly' },
  { path: '/subscribe', priority: 0.7, changefreq: 'monthly' },
];

// Get the lastmod date (use current date for dynamic content)
function getLastMod() {
  return new Date().toISOString().split('T')[0];
}

// Generate XML for a single URL
function generateUrlEntry(route) {
  const lastmod = getLastMod();

  return `  <url>
    <loc>${BASE_URL}${route.path}</loc>
    <lastmod>${lastmod}</lastmod>
    <changefreq>${route.changefreq}</changefreq>
    <priority>${route.priority.toFixed(1)}</priority>
  </url>`;
}

// Generate the full sitemap XML
function generateSitemap() {
  const urlEntries = routes.map(generateUrlEntry).join('\n');

  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urlEntries}
</urlset>
`;
}

// Main execution
const rootDir = process.cwd();
const publicDir = path.join(rootDir, 'public');
const distDir = path.join(rootDir, 'dist');

const sitemap = generateSitemap();

// Write to public folder (for dev)
try {
  await writeFile(path.join(publicDir, 'sitemap.xml'), sitemap);
  console.log('Sitemap written to public/sitemap.xml');
} catch (err) {
  console.error('Could not write to public:', err.message);
}

// Write to dist folder if it exists (for build)
try {
  await stat(distDir);
  await writeFile(path.join(distDir, 'sitemap.xml'), sitemap);
  console.log('Sitemap written to dist/sitemap.xml');
} catch {
  // dist folder doesn't exist yet, that's OK during dev
}

console.log(`Generated sitemap with ${routes.length} URLs`);
