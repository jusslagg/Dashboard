(function () {
  const originalFetch = window.fetch.bind(window);
  const localHosts = ['localhost', '127.0.0.1', '::1'];
  const isLocalFrontend = localHosts.includes(window.location.hostname);
  const configuredBase = (window.API_BASE || '').replace(/\/$/, '');
  const apiBase = configuredBase || (isLocalFrontend && window.location.port !== '5000' ? 'http://127.0.0.1:5000' : '');

  window.apiUrl = function (path) {
    if (typeof path !== 'string') return path;
    if (path.startsWith('/api/')) return apiBase + path;
    try {
      const url = new URL(path, window.location.href);
      if (url.pathname.startsWith('/api/')) return apiBase + url.pathname + url.search;
    } catch (error) {}
    return path;
  };

  window.fetch = function (input, init) {
    if (typeof input === 'string') {
      return originalFetch(window.apiUrl(input), init);
    }

    if (input instanceof Request && input.url.includes('/api/')) {
      const url = new URL(input.url);
      const rewritten = window.apiUrl(url.pathname + url.search);
      return originalFetch(new Request(rewritten, input), init);
    }

    return originalFetch(input, init);
  };
}());
