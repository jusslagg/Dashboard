(function () {
  const originalFetch = window.fetch.bind(window);
  const apiBase = (window.API_BASE || '').replace(/\/$/, '');

  window.apiUrl = function (path) {
    return path.startsWith('/api/') ? apiBase + path : path;
  };

  window.fetch = function (input, init) {
    if (typeof input === 'string' && input.startsWith('/api/')) {
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
