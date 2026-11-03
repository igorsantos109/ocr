import { FolderOpen, Plus } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState } from '../components/common/EmptyState';
import { useOcrStore } from '../store/useOcrStore';

export function CollectionsPage() {
  const collections = useOcrStore((s) => s.collections);
  const documents = useOcrStore((s) => s.documents);
  const toast = useOcrStore((s) => s.toast);
  const [name, setName] = useState('');

  function createCollection(e: React.FormEvent) {
    e.preventDefault();
    if (name.trim().length < 2) {
      toast('Nome com ao menos 2 caracteres', 'error');
      return;
    }
    useOcrStore.setState((s) => ({
      collections: [...s.collections, { id: `col-${Date.now()}`, name: name.trim(), description: '', createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }],
    }));
    setName('');
    toast('Coleção criada', 'success');
  }

  const createForm = (
    <form className="flex gap-1.5" onSubmit={createCollection}>
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nova coleção…" aria-label="Nome da nova coleção" className="rounded-lg border border-border px-3 py-1.5 text-[13px]" />
      <button type="submit" className="inline-flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-[13px] font-medium text-[#202124] hover:bg-primary-hover">
        <Plus size={14} aria-hidden /> Criar
      </button>
    </form>
  );

  if (!collections.length) {
    return (
      <div className="space-y-4 pt-6">
        <div className="flex items-center justify-between">
          <h1 className="text-[16px] font-medium">Coleções</h1>
          {createForm}
        </div>
        <EmptyState title="Sem coleções" hint="Crie a primeira coleção acima para organizar documentos." action={null} />
      </div>
    );
  }

  return (
    <div className="space-y-4 pt-6">
      <div className="flex items-center justify-between">
        <h1 className="text-[16px] font-medium">Coleções ({collections.length})</h1>
        {createForm}
      </div>
      <ul className="grid gap-3 md:grid-cols-2">
        {collections.map((c) => {
          const n = documents.filter((d) => d.collectionId === c.id).length;
          return (
            <li key={c.id} className="rounded-lg border border-border p-4 hover:border-muted">
              <Link to={`/colecoes/${c.id}`} className="flex items-center gap-2 font-medium">
                <FolderOpen size={16} aria-hidden className="text-warn" /> {c.name}
              </Link>
              <p className="mt-1 text-[13px] text-muted">{c.description || 'Sem descrição'} · {n} documento(s)</p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
