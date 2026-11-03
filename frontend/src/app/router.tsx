import { createBrowserRouter } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell';
import { CollectionDetailPage } from '../pages/CollectionDetailPage';
import { CollectionsPage } from '../pages/CollectionsPage';
import { DashboardPage } from '../pages/DashboardPage';
import { DocumentReviewPage } from '../pages/DocumentReviewPage';
import { DocumentsPage } from '../pages/DocumentsPage';
import { SettingsPage } from '../pages/SettingsPage';

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: '/', element: <DashboardPage /> },
      { path: '/colecoes', element: <CollectionsPage /> },
      { path: '/colecoes/:collectionId', element: <CollectionDetailPage /> },
      { path: '/documentos', element: <DocumentsPage /> },
      { path: '/documentos/:documentId', element: <DocumentReviewPage /> },
      { path: '/configuracoes', element: <SettingsPage /> },
    ],
  },
]);
