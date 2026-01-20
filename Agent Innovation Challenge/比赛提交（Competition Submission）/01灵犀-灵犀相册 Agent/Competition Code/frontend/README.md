# Smart Album Frontend (Refactored)

Based on Ant Design + React + TypeScript + Vite.

## Features

### 1. Modern UI/UX
- **Design System**: Built with Ant Design 5.0, featuring a clean, enterprise-grade interface.
- **Responsive Layout**: Sidebar navigation (`MainLayout`) adapting to different screen sizes.
- **Theming**: Consistent color palette and typography.

### 2. Intelligent Chat (`/chat`)
- **Interface**: Chat-like interface similar to modern AI assistants.
- **Features**:
  - Message bubbles for User and Agent.
  - Image result visualization with preview.
  - Suggestion chips for quick actions.
  - Auto-scroll and loading states.

### 3. Smart Gallery (`/gallery`)
- **Views**: Toggle between Grid and List views.
- **Performance**: Pagination and optimized image rendering.
- **Search**: Real-time filtering and semantic search integration.
- **Preview**: Integrated Lightbox for full-screen image viewing.

### 4. Upload Center (`/upload`)
- **Methods**: 
  - Drag & Drop for local files.
  - URL import for network images.
- **Management**:
  - Upload progress tracking.
  - Batch tagging and description.
  - Recent upload history with delete capability.

## Project Structure

```
frontend/src/
├── api/            # API clients (Axios + Interceptors)
├── components/     
│   └── layout/     # Global Layouts (MainLayout)
├── pages/          # Page Components
│   ├── HomePage.tsx
│   ├── ChatPage.tsx
│   ├── GalleryPage.tsx
│   └── UploadPage.tsx
├── store/          # State Management (Zustand)
└── main.tsx        # Entry point with ConfigProvider
```

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start development server:
   ```bash
   npm run dev
   ```

3. Build for production:
   ```bash
   npm run build
   ```
