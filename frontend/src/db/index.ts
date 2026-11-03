/** Persistência local (IndexedDB via Dexie): coleções, perfis, revisões. */

import Dexie, { type Table } from 'dexie';
import type { OcrCollection, OcrProfile, RevisionEvent } from '../types/ocr';

class OcrStudioDb extends Dexie {
  collections!: Table<OcrCollection, string>;
  profiles!: Table<OcrProfile, string>;
  revisions!: Table<RevisionEvent, string>;

  constructor() {
    super('ocr-studio-v2');
    this.version(1).stores({
      collections: 'id, updatedAt',
      profiles: 'id',
      revisions: 'id, documentId, createdAt',
    });
  }
}

export const db = new OcrStudioDb();
