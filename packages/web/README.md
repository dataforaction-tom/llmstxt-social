# llmstxt-web

React frontend for the llmstxt SaaS platform.

## Features

- **Modern Stack**: React 18 + TypeScript + Vite
- **Styling**: Tailwind CSS with custom design system
- **Data Fetching**: TanStack Query for server state
- **Payments**: Stripe Elements integration
- **Routing**: React Router for navigation

## Development

### Installation

```bash
cd packages/web
npm install
```

### Environment Setup

Create a `.env` file:

```bash
VITE_API_URL=http://localhost:8000
VITE_STRIPE_PUBLIC_KEY=pk_test_your-key-here
```

### Start Development Server

```bash
npm run dev
```

Open http://localhost:3000

### Build for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

### Preview Production Build

```bash
npm run preview
```

## Pages

- **Home (`/`)**: Landing page with features and CTA
- **Generate (`/generate`)**: Generation form with progress tracking
- **Pricing (`/pricing`)**: Pricing tiers and FAQs

## Components

- `Layout`: Navigation and footer wrapper
- `AssessmentDisplay`: Quality assessment results
- `PaymentFlow`: Stripe payment modal

## API Integration

The app communicates with the FastAPI backend via the `apiClient`:

```typescript
import apiClient from './api/client';

// Generate free
const job = await apiClient.generateFree({ url, template });

// Get job status
const status = await apiClient.getJob(jobId);

// Create payment
const payment = await apiClient.createPaymentIntent({ url, template });
```

## Deployment

### Docker

```bash
# Build image
docker build -t llmstxt-web .

# Run container
docker run -p 80:80 llmstxt-web
```

### Vercel/Netlify

The app is configured for static hosting platforms:

1. Build command: `npm run build`
2. Output directory: `dist`
3. Set environment variables in platform settings

### DigitalOcean App Platform

See deployment guide in `infrastructure/digitalocean/`

## Environment Variables

- `VITE_API_URL`: Backend API URL (default: http://localhost:8000)
- `VITE_STRIPE_PUBLIC_KEY`: Stripe publishable key

## Tech Stack

- **React 18**: UI library
- **TypeScript**: Type safety
- **Vite**: Build tool and dev server
- **Tailwind CSS**: Utility-first CSS
- **TanStack Query**: Server state management
- **React Router**: Client-side routing
- **Stripe Elements**: Payment UI
- **Lucide React**: Icons
- **Axios**: HTTP client

## License

MIT
