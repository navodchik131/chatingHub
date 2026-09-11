/**
 * Обёртка IndexedDB для Unibox.
 */

const DB_NAME = 'modelmate_unibox_v1'
const DB_VERSION = 1

export type StoreName = 'meta' | 'conversations' | 'threads' | 'blobs'

let dbPromise: Promise<IDBDatabase> | null = null

function openDb(): Promise<IDBDatabase> {
  if (dbPromise) return dbPromise
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onerror = () => reject(req.error ?? new Error('idb open failed'))
    req.onupgradeneeded = () => {
      const db = req.result
      for (const name of ['meta', 'conversations', 'threads', 'blobs'] as const) {
        if (!db.objectStoreNames.contains(name)) db.createObjectStore(name)
      }
    }
    req.onsuccess = () => resolve(req.result)
  })
  return dbPromise
}

function txStore<T>(
  store: StoreName,
  mode: IDBTransactionMode,
  fn: (os: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  return openDb().then(
    (db) =>
      new Promise((resolve, reject) => {
        const tx = db.transaction(store, mode)
        const req = fn(tx.objectStore(store))
        req.onsuccess = () => resolve(req.result as T)
        req.onerror = () => reject(req.error ?? new Error('idb failed'))
      }),
  )
}

export async function idbGet<T>(store: StoreName, key: string): Promise<T | null> {
  try {
    const result = await txStore(store, 'readonly', (os) => os.get(key))
    return (result as T | undefined) ?? null
  } catch {
    return null
  }
}

export async function idbSet(store: StoreName, key: string, value: unknown): Promise<void> {
  try {
    await txStore(store, 'readwrite', (os) => os.put(value, key))
  } catch {
    /* private mode / quota */
  }
}

export async function idbDelete(store: StoreName, key: string): Promise<void> {
  try {
    await txStore(store, 'readwrite', (os) => os.delete(key))
  } catch {
    /* ignore */
  }
}

export async function idbGetAllKeys(store: StoreName): Promise<string[]> {
  try {
    const keys = await txStore(store, 'readonly', (os) => os.getAllKeys())
    return (keys as IDBValidKey[]).map(String)
  } catch {
    return []
  }
}
