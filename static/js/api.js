const API = {
  getToken() { return localStorage.getItem('token'); },
  setToken(t) { localStorage.setItem('token', t); },
  clearToken() { localStorage.removeItem('token'); },

  async request(method, url, body = null, headers = {}) {
    const token = this.getToken();
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json', ...headers },
    };
    if (token) opts.headers['Authorization'] = `Bearer ${token}`;
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(url, opts);
    if (resp.status === 401) { this.clearToken(); window.location = '/login'; return resp; }
    return resp;
  },

  get(url) { return this.request('GET', url); },
  post(url, body) { return this.request('POST', url, body); },
  put(url, body) { return this.request('PUT', url, body); },
  delete(url) { return this.request('DELETE', url); },

  async getJSON(url) {
    const resp = await this.get(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  },

  async postJSON(url, body) {
    const resp = await this.post(url, body);
    const data = await resp.json();
    if (!resp.ok) throw data;
    return data;
  },

  async putJSON(url, body) {
    const resp = await this.put(url, body);
    const data = await resp.json();
    if (!resp.ok) throw data;
    return data;
  },

  isLoggedIn() { return !!this.getToken(); },

  requireAuth() {
    if (!this.isLoggedIn()) {
      window.location = '/login';
      return false;
    }
    return true;
  },
};
