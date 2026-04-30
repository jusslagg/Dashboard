from pathlib import Path

from app import create_app


PAGES = {
    "/": "index.html",
    "/cargar": "cargar.html",
    "/catalogos": "catalogos.html",
    "/comparativo": "comparativo.html",
    "/matriz": "matriz.html",
    "/control": "control.html",
}


def rewrite_links(html):
    replacements = {
        'href="/"': 'href="./index.html"',
        'href="/cargar"': 'href="./cargar.html"',
        'href="/catalogos"': 'href="./catalogos.html"',
        'href="/comparativo"': 'href="./comparativo.html"',
        'href="/matriz"': 'href="./matriz.html"',
        'href="/control"': 'href="./control.html"',
        'href="/api/template_carga"': 'href="#" onclick="window.location.href = window.apiUrl(\'/api/template_carga\'); return false;"',
        "window.location.href = '/api/exportar_excel' + buildQuery();": "window.location.href = window.apiUrl('/api/exportar_excel' + buildQuery());",
        "window.location.href = '/api/exportar_excel' + (query ? `?${query}` : '');": "window.location.href = window.apiUrl('/api/exportar_excel' + (query ? `?${query}` : ''));",
    }
    for old, new in replacements.items():
        html = html.replace(old, new)
    return html


def render_page(app, route, filename, output_dir):
    endpoint = "main.index" if route == "/" else f"main.{route.strip('/')}"
    with app.test_request_context(route):
        html = app.view_functions[endpoint]()
    html = rewrite_links(html)
    html = html.replace(
        "    <script>\n        async function cargarSeed()",
        '    <script src="./assets/config.js"></script>\n'
        '    <script src="./assets/api-client.js"></script>\n'
        "    <script>\n        async function cargarSeed()",
        1,
    )
    (output_dir / filename).write_text(html, encoding="utf-8")


def main():
    output_dir = Path("docs")
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    (assets_dir / "config.js").write_text(
        "// URL publica del backend Flask en Render para GitHub Pages.\n"
        "// Ejemplo: window.API_BASE = 'https://tu-dashboard.onrender.com';\n"
        "// En Live Server se usa automaticamente http://127.0.0.1:5000.\n"
        "window.API_BASE = window.API_BASE || '';\n",
        encoding="utf-8",
    )
    (assets_dir / "api-client.js").write_text(
        "(function () {\n"
        "  const originalFetch = window.fetch.bind(window);\n"
        "  const localHosts = ['localhost', '127.0.0.1', '::1'];\n"
        "  const isLocalFrontend = localHosts.includes(window.location.hostname);\n"
        "  const configuredBase = (window.API_BASE || '').replace(/\\/$/, '');\n"
        "  const apiBase = configuredBase || (isLocalFrontend && window.location.port !== '5000' ? 'http://127.0.0.1:5000' : '');\n"
        "\n"
        "  window.apiUrl = function (path) {\n"
        "    if (typeof path !== 'string') return path;\n"
        "    if (path.startsWith('/api/')) return apiBase + path;\n"
        "    try {\n"
        "      const url = new URL(path, window.location.href);\n"
        "      if (url.pathname.startsWith('/api/')) return apiBase + url.pathname + url.search;\n"
        "    } catch (error) {}\n"
        "    return path;\n"
        "  };\n"
        "\n"
        "  window.fetch = function (input, init) {\n"
        "    if (typeof input === 'string') {\n"
        "      return originalFetch(window.apiUrl(input), init);\n"
        "    }\n"
        "\n"
        "    if (input instanceof Request && input.url.includes('/api/')) {\n"
        "      const url = new URL(input.url);\n"
        "      const rewritten = window.apiUrl(url.pathname + url.search);\n"
        "      return originalFetch(new Request(rewritten, input), init);\n"
        "    }\n"
        "\n"
        "    return originalFetch(input, init);\n"
        "  };\n"
        "}());\n",
        encoding="utf-8",
    )

    app = create_app()
    for route, filename in PAGES.items():
        render_page(app, route, filename, output_dir)


if __name__ == "__main__":
    main()
