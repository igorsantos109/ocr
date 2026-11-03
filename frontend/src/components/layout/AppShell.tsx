import { Outlet } from 'react-router-dom';
import { Toasts } from '../common/Toasts';
import { TopBar } from './TopBar';

export function AppShell() {
  return (
    <div className="min-h-screen bg-white text-ink">
      <TopBar />
      <main className="mx-auto max-w-[1200px] px-6 pb-10">
        <Outlet />
      </main>
      <footer className="border-t border-border bg-surface">
        <div className="mx-auto flex max-w-[1200px] flex-wrap justify-between gap-3 px-6 py-4 text-xs text-muted">
          <span>OCR Studio V2 · ocr-historico-br — painel 100% local, sem nuvem</span>
          <span className="mono">API {import.meta.env.VITE_API_MODE ?? 'mock'} · {import.meta.env.VITE_API_BASE ?? 'mock local'}</span>
        </div>
      </footer>
      <Toasts />
    </div>
  );
}
