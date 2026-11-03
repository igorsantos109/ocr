import { Link, useParams } from 'react-router-dom';
import { DocumentQueueTable } from '../components/queue/DocumentQueueTable';
import { UploadDropzone } from '../components/upload/UploadDropzone';
import { useOcrStore } from '../store/useOcrStore';

export function CollectionDetailPage() {
  const { collectionId = '' } = useParams();
  const collections = useOcrStore((s) => s.collections);
  const col = collections.find((c) => c.id === collectionId);

  return (
    <div className="space-y-4 pt-6">
      <nav aria-label="Trilha" className="text-[13px] text-muted">
        <Link to="/colecoes" className="underline">Coleções</Link> / <span>{col?.name ?? collectionId}</span>
      </nav>
      <h1 className="text-[16px] font-medium">{col?.name ?? 'Coleção'}</h1>
      {col?.description ? <p className="text-[13px] text-muted">{col.description}</p> : null}
      <UploadDropzone compact />
      <DocumentQueueTable collectionId={collectionId} />
    </div>
  );
}
