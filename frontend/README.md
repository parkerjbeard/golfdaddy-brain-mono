# GolfDaddy Brain Frontend

This is the frontend application for GolfDaddy Brain, an AI-powered software engineering assistant that helps teams track work, manage tasks, and improve productivity through intelligent analysis of code commits and daily reports.

## Tech Stack

- React 18 with TypeScript
- Vite for build tooling
- TailwindCSS for styling
- Shadcn/ui component library
- Zustand for state management
- React Query for server state
- Supabase for authentication

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Backend API running at `http://localhost:8000`

### Installation

```bash
# Install dependencies
npm install
```

### Development

```bash
# Start development server
npm run dev

# The app will be available at http://localhost:8080
```

### Build

```bash
# Production build
npm run build

# Preview production build
npm run preview
```

### Testing

```bash
# Run tests
npm test

# Run tests with UI
npm run test:ui

# Run tests with coverage
npm run test:coverage
```

### Linting

```bash
npm run lint
```

## Environment Variables

Create a `.env` file in the frontend directory:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
```

## Project Structure

```
frontend/
├── src/
│   ├── components/     # Reusable UI components
│   ├── pages/          # Page components
│   ├── services/       # API clients and services
│   ├── stores/         # Zustand stores
│   ├── hooks/          # Custom React hooks
│   ├── lib/            # Utility functions
│   └── types/          # TypeScript type definitions
├── public/             # Static assets
└── index.html          # Entry HTML file
```

## Features

- User authentication with Supabase
- Role-based access control (Employee, Manager, Admin)
- Daily report submissions
- Commit analysis and insights
- KPI tracking and visualization
- RACI matrix management
- Documentation generation
- Semantic search across codebase

## API Integration

The frontend proxies the following paths to the backend:
- `/api` - API endpoints
- `/auth` - Authentication endpoints
- `/dev` - Development tools
- `/test` - Test endpoints

## Deployment

The frontend can be deployed to any static hosting service that supports SPAs (Single Page Applications). The build output is in the `dist` directory after running `npm run build`.

For custom domain deployment, we recommend using services like Netlify, Vercel, or Cloudflare Pages.