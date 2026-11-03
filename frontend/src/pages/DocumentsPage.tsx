import { DocumentQueueTable } from '../components/queue/DocumentQueueTable';

export function DocumentsPage() {
  return (
    <div className="space-y-4 pt-6">
      <h1 className="text-[16px] font-medium">Meus documentos</h1>
      <DocumentQueueTable />
    </div>
  );
}
