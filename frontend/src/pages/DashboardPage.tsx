/** Dashboard / Converter: upload → configuração → acompanhamento → fila. */

import { OcrConfigurationPanel } from '../components/ocr/OcrConfigurationPanel';
import { ProcessingMonitor } from '../components/ocr/ProcessingMonitor';
import { DocumentQueueTable } from '../components/queue/DocumentQueueTable';
import { ReviewPendingSummary } from '../components/review/ReviewPendingSummary';
import { UploadDropzone } from '../components/upload/UploadDropzone';
import { useOcrStore } from '../store/useOcrStore';

export function DashboardPage() {
  const ready = useOcrStore((s) => s.ready);
  const documents = useOcrStore((s) => s.documents);

  if (!ready) {
    return (
      <div className="space-y-4 pt-6" aria-label="Carregando">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-36 animate-pulse rounded-lg bg-surface" />
        ))}
      </div>
    );
  }

  const hasActive = documents.some((d) => d.status === 'ocr' || d.status === 'preprocessing');

  return (
    <div className="space-y-4 pt-6">
      <UploadDropzone compact={hasActive} />
      <OcrConfigurationPanel />
      <ProcessingMonitor />
      <DocumentQueueTable />
      <ReviewPendingSummary />
    </div>
  );
}
