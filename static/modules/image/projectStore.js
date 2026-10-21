/* Kho dự án ảnh: lưu trong IndexedDB của trình duyệt (ảnh không rời máy khách).
   Nếu trình duyệt chặn IndexedDB (chế độ riêng tư…) thì giữ tạm trong bộ nhớ và báo isPersistent() = false. */

const DB_NAME = 'pm-image-studio';
const STORE = 'projects';
const memory = new Map();
let dbPromise = null;
let persistent = true;

function openDb() {
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      if (!window.indexedDB) {
        reject(new Error('IndexedDB không khả dụng'));
        return;
      }
      const request = indexedDB.open(DB_NAME, 1);
      request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: 'id' });
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
      request.onblocked = () => reject(new Error('IndexedDB bị chặn'));
    }).catch(() => {
      persistent = false;
      return null;
    });
  }
  return dbPromise;
}

function wrap(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function store(mode) {
  const db = await openDb();
  return db ? db.transaction(STORE, mode).objectStore(STORE) : null;
}

export function isPersistent() {
  return persistent;
}

export async function listProjects() {
  const os = await store('readonly');
  const all = os ? await wrap(os.getAll()) : [...memory.values()];
  return all.sort((a, b) => b.updatedAt - a.updatedAt);
}

export async function getProject(id) {
  const os = await store('readonly');
  return os ? wrap(os.get(id)) : memory.get(id);
}

export async function saveProject(project) {
  const os = await store('readwrite');
  if (os) {
    try {
      await wrap(os.put(project));
      return;
    } catch (error) {
      persistent = false;
      throw error;
    }
  }
  memory.set(project.id, project);
}

export async function deleteProject(id) {
  const os = await store('readwrite');
  if (os) await wrap(os.delete(id));
  else memory.delete(id);
}
