// Polyfill localStorage for jsdom >=26 which removed built-in Storage.
class MemoryStorage {
  constructor() { this._data = {}; }
  getItem(key) { return key in this._data ? this._data[key] : null; }
  setItem(key, value) { this._data[key] = String(value); }
  removeItem(key) { delete this._data[key]; }
  clear() { this._data = {}; }
  get length() { return Object.keys(this._data).length; }
  key(i) { return Object.keys(this._data)[i] ?? null; }
}

const storage = new MemoryStorage();
const sessionStore = new MemoryStorage();

for (const g of [globalThis, global, (typeof window !== 'undefined' ? window : null)].filter(Boolean)) {
  if (typeof g.localStorage === 'undefined' || !g.localStorage || typeof g.localStorage.clear !== 'function') {
    Object.defineProperty(g, 'localStorage', { value: storage, writable: true, configurable: true });
  }
  if (typeof g.sessionStorage === 'undefined' || !g.sessionStorage || typeof g.sessionStorage.clear !== 'function') {
    Object.defineProperty(g, 'sessionStorage', { value: sessionStore, writable: true, configurable: true });
  }
}
