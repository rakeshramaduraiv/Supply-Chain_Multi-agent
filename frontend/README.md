# AMASCI Frontend

Enterprise Supply Chain Intelligence Platform - Frontend Application

## Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| React | 18.3 | UI Framework |
| TypeScript | 5.5 | Type Safety |
| Vite | 5.4 | Build Tool |
| React Router | 6.26 | Client Routing |
| Axios | 1.7 | HTTP Client |
| React Query | 5.56 | Server State |
| React Hook Form | 7.53 | Form Management |
| Recharts | 2.12 | Charts |
| React Force Graph | 1.25 | Graph Visualization |
| Lucide React | 0.447 | Icons |
| CSS Modules | - | Scoped Styling |

## Project Structure

```
src/
├── api/            # Axios client, endpoints, interceptors
├── assets/         # Static assets (images, fonts)
├── components/     # Reusable UI components
│   ├── common/     # Button, Card, Table, Modal, Dialog, Drawer, Badge, Chip, Tooltip, Pagination, Tabs, Accordion
│   ├── feedback/   # Spinner, Skeleton, Toast
│   └── navigation/ # Sidebar, TopBar
├── config/         # App configuration
├── constants/      # App constants, navigation items
├── context/        # React Context providers (Auth, Theme, Notification, Toast)
├── hooks/          # Custom hooks (useLocalStorage, useMediaQuery, useDebounce)
├── layouts/        # Page layouts (MainLayout, AuthLayout)
├── pages/          # Route pages (Dashboard, Training, Forecast, etc.)
├── providers/      # App-level provider composition
├── routes/         # Router config, ProtectedRoute, ErrorBoundary
├── services/       # API service layer (auth, dashboard, training, forecast, graph, tpke, graphrag, rca, analytics)
├── store/          # Global state (reserved)
├── styles/         # Global CSS, CSS variables, theme
├── types/          # TypeScript type definitions
└── utils/          # Utility functions (storage, formatters, helpers)
```

## Getting Started

```bash
# Install dependencies
npm install

# Start development server (port 3000)
npm run dev

# Production build
npm run build

# Preview production build
npm run preview
```

## Environment Variables

Create `.env` file (see `.env.example`):

```
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_NAME=AMASCI Platform
VITE_APP_VERSION=1.0.0
```

## Architecture

### Layout System
- **MainLayout**: TopBar + Sidebar + Content + Footer + Toast notifications
- **AuthLayout**: Centered card for login/auth flows

### Authentication
- JWT-based with access/refresh tokens
- Protected routes with role-based access (Admin, Analyst, Viewer)
- Auto-redirect on 401 responses

### API Layer
- Centralized Axios client with request/response interceptors
- Automatic token injection
- Service layer per domain (10 services)

### State Management
- **React Context**: Auth state, theme, notifications, toasts
- **React Query**: Server state caching, background refetching
- **Local Storage**: Token persistence, theme preference

### Theming
- CSS Variables for all design tokens
- Dark theme (default) + Light theme
- Enterprise Oracle-style color palette
- `data-theme` attribute on `<html>` for switching

### Component Library (15 components)
- Button, Card, Table, Modal, Dialog, Drawer
- Badge, Chip, Tooltip, Pagination, Tabs, Accordion
- Spinner (3 variants), Skeleton Loader, Toast Notifications

### Routing (10 routes)
| Path | Page | Access |
|---|---|---|
| /dashboard | Dashboard | All |
| /training | System Training | Admin, Analyst |
| /forecast | Generate Forecast | Admin, Analyst |
| /validation | Validate Actuals | Admin, Analyst |
| /knowledge-graph | Knowledge Graph | All |
| /tpke | TPKE Evolution | All |
| /graphrag | GraphRAG | All |
| /rca | Root Cause Analysis | All |
| /analytics | Analytics | All |
| /settings | Settings | Admin |

## Development Notes

- All components use CSS Modules for scoped styling
- No Tailwind CSS - pure CSS with design tokens
- Responsive sidebar with collapse toggle
- Global error boundary catches route-level errors
- Toast system with auto-dismiss and stacking
- All API services return typed responses
- Pages are shell components ready for full implementation
