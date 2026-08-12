"""Genera la documentación técnica HTML a partir del README.

Usa solamente la biblioteca estándar para que la documentación pueda
regenerarse en cualquier instalación del proyecto.
"""

from __future__ import annotations

import html
import re
import unicodedata
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
ORIGEN = RAIZ / "README.md"
DESTINO = RAIZ / "docs" / "documentacion_tecnica.html"


def slug(texto: str, usados: set[str]) -> str:
    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower() or "seccion"
    candidato = base
    numero = 2
    while candidato in usados:
        candidato = f"{base}-{numero}"
        numero += 1
    usados.add(candidato)
    return candidato


def inline(texto: str) -> str:
    texto = html.escape(texto, quote=False)
    texto = re.sub(r"`([^`]+)`", r"<code>\1</code>", texto)
    texto = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', texto)
    return texto


def es_separador_tabla(linea: str) -> bool:
    celdas = [celda.strip() for celda in linea.strip().strip("|").split("|")]
    return bool(celdas) and all(re.fullmatch(r":?-{3,}:?", celda) for celda in celdas)


def render_markdown(texto: str):
    lineas = texto.splitlines()
    usados: set[str] = set()
    indice = []
    salida = []
    i = 0
    lista = None

    def cerrar_lista():
        nonlocal lista
        if lista:
            salida.append(f"</{lista}>")
            lista = None

    while i < len(lineas):
        linea = lineas[i]

        if linea.startswith("```"):
            cerrar_lista()
            lenguaje = linea[3:].strip()
            bloque = []
            i += 1
            while i < len(lineas) and not lineas[i].startswith("```"):
                bloque.append(lineas[i])
                i += 1
            clase = f' class="language-{html.escape(lenguaje)}"' if lenguaje else ""
            salida.append(f"<pre><code{clase}>{html.escape(chr(10).join(bloque))}</code></pre>")
            i += 1
            continue

        titulo = re.match(r"^(#{1,4})\s+(.+)$", linea)
        if titulo:
            cerrar_lista()
            nivel = len(titulo.group(1))
            texto_titulo = titulo.group(2).strip()
            identificador = slug(re.sub(r"[`*]", "", texto_titulo), usados)
            salida.append(
                f'<h{nivel} id="{identificador}">{inline(texto_titulo)}'
                f'<a class="anchor" href="#{identificador}" aria-label="Enlace a esta sección">#</a></h{nivel}>'
            )
            if nivel in (2, 3):
                indice.append((nivel, identificador, re.sub(r"[`*]", "", texto_titulo)))
            i += 1
            continue

        if "|" in linea and i + 1 < len(lineas) and es_separador_tabla(lineas[i + 1]):
            cerrar_lista()
            encabezados = [celda.strip() for celda in linea.strip().strip("|").split("|")]
            filas = []
            i += 2
            while i < len(lineas) and "|" in lineas[i] and lineas[i].strip():
                filas.append([celda.strip() for celda in lineas[i].strip().strip("|").split("|")])
                i += 1
            salida.append('<div class="table-wrap"><table><thead><tr>')
            salida.extend(f"<th>{inline(celda)}</th>" for celda in encabezados)
            salida.append("</tr></thead><tbody>")
            for fila in filas:
                salida.append("<tr>")
                salida.extend(f"<td>{inline(celda)}</td>" for celda in fila)
                salida.append("</tr>")
            salida.append("</tbody></table></div>")
            continue

        elemento = re.match(r"^\s*[-*]\s+(.+)$", linea)
        numerado = re.match(r"^\s*\d+\.\s+(.+)$", linea)
        if elemento or numerado:
            tipo = "ul" if elemento else "ol"
            if lista != tipo:
                cerrar_lista()
                lista = tipo
                salida.append(f"<{tipo}>")
            salida.append(f"<li>{inline((elemento or numerado).group(1))}</li>")
            i += 1
            continue

        if not linea.strip():
            cerrar_lista()
            i += 1
            continue

        cerrar_lista()
        parrafo = [linea.strip()]
        i += 1
        while (
            i < len(lineas)
            and lineas[i].strip()
            and not re.match(r"^(#{1,4})\s+|^```|^\s*[-*]\s+|^\s*\d+\.\s+", lineas[i])
            and not ("|" in lineas[i] and i + 1 < len(lineas) and es_separador_tabla(lineas[i + 1]))
        ):
            parrafo.append(lineas[i].strip())
            i += 1
        contenido = " ".join(parrafo)
        clase = " callout" if contenido.lower().startswith(("importante:", "nota:", "para producción:")) else ""
        salida.append(f'<p class="{clase.strip()}">{inline(contenido)}</p>')

    cerrar_lista()
    return "\n".join(salida), indice


def construir_indice(indice):
    items = []
    for nivel, identificador, titulo in indice:
        clase = "sub" if nivel == 3 else ""
        items.append(f'<li class="{clase}"><a href="#{identificador}">{html.escape(titulo)}</a></li>')
    return "\n".join(items)


def main():
    cuerpo, indice = render_markdown(ORIGEN.read_text(encoding="utf-8"))
    anexos = [
        ("anexo-ddl-sqlite", "Anexo DDL completo - SQLite", RAIZ / "docs" / "esquema_base_datos_sqlite.sql"),
        ("anexo-ddl-postgresql", "Anexo DDL completo - PostgreSQL", RAIZ / "docs" / "esquema_base_datos_postgresql.sql"),
    ]
    bloques_anexos = []
    for identificador, titulo, ruta in anexos:
        if not ruta.exists():
            continue
        indice.append((2, identificador, titulo))
        ddl = html.escape(ruta.read_text(encoding="utf-8"))
        bloques_anexos.append(
            f'<h2 id="{identificador}">{html.escape(titulo)}'
            f'<a class="anchor" href="#{identificador}" aria-label="Enlace a esta sección">#</a></h2>'
            f'<p>Definición física generada desde <code>app/models.py</code>.</p>'
            f'<pre><code class="language-sql">{ddl}</code></pre>'
        )
    if bloques_anexos:
        cuerpo += "\n" + "\n".join(bloques_anexos)
    documento = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Documentación técnica - Dashboard de Facturación</title>
  <style>
    :root{{--navy:#0f2747;--blue:#2563eb;--cyan:#0891b2;--ink:#172033;--muted:#5f6b7a;--line:#dbe4ef;--soft:#f4f7fb;}}
    *{{box-sizing:border-box}} html{{scroll-behavior:smooth}}
    body{{margin:0;color:var(--ink);background:var(--soft);font:15px/1.62 Arial,sans-serif}}
    a{{color:#1859ba}} .top{{position:sticky;top:0;z-index:5;display:flex;gap:12px;align-items:center;justify-content:space-between;padding:12px max(18px,calc((100% - 1180px)/2));color:#fff;background:var(--navy)}}
    .top a{{color:#fff;text-decoration:none}} .buttons{{display:flex;gap:8px;flex-wrap:wrap}}
    .button{{display:inline-block;padding:8px 13px;border:1px solid #7fa1ce;border-radius:7px;background:#173b69;font-weight:bold}}
    .button.primary{{border-color:#67e8f9;background:#0e7490}}
    .page{{max-width:1180px;margin:24px auto 60px;padding:0 18px}}
    .cover,.toc,.content{{margin-bottom:20px;padding:30px;border:1px solid var(--line);border-radius:12px;background:#fff;box-shadow:0 4px 18px rgba(15,39,71,.05)}}
    .cover{{padding:46px;background:linear-gradient(135deg,#0f2747,#155e75);color:#fff}}
    .cover h1{{margin:0 0 10px;color:#fff;font-size:clamp(30px,5vw,48px);line-height:1.15}} .cover p{{max-width:830px;font-size:19px}}
    .toc ol{{columns:2;column-gap:45px;padding-left:24px}} .toc li{{margin:5px 0}} .toc li.sub{{margin-left:18px;font-size:14px}}
    .toc a{{text-decoration:none}} h1,h2,h3,h4{{scroll-margin-top:80px;color:var(--navy)}} h1{{font-size:34px}} h2{{margin-top:44px;padding:12px 15px;border-left:6px solid var(--cyan);background:#eef8fb;font-size:26px}} h3{{margin-top:30px;color:#174b83;font-size:21px}} h4{{font-size:17px}}
    .anchor{{margin-left:8px;color:#9aa9ba;text-decoration:none;font-size:.75em;opacity:0}} h1:hover .anchor,h2:hover .anchor,h3:hover .anchor,h4:hover .anchor{{opacity:1}}
    p{{margin:8px 0 14px}} ul,ol{{padding-left:26px}} li{{margin:5px 0}}
    code{{padding:2px 5px;border-radius:4px;background:#edf1f6;color:#8b1d41;font-family:Consolas,monospace}}
    pre{{overflow:auto;margin:16px 0;padding:17px;border-radius:8px;background:#101b2c;color:#e5edf7;line-height:1.5}} pre code{{padding:0;background:none;color:inherit}}
    .table-wrap{{overflow-x:auto;margin:16px 0}} table{{width:100%;border-collapse:collapse;font-size:14px}} th,td{{padding:10px;border:1px solid var(--line);text-align:left;vertical-align:top}} th{{background:#e9f0f8;color:var(--navy)}}
    .callout{{padding:14px 17px;border-left:5px solid var(--blue);border-radius:6px;background:#eef5ff}}
    .back{{position:fixed;right:20px;bottom:20px;padding:9px 12px;border-radius:8px;background:var(--navy);color:#fff;text-decoration:none}}
    footer{{padding:25px;color:var(--muted);text-align:center}}
    @media(max-width:720px){{.toc ol{{columns:1}}.cover,.toc,.content{{padding:20px}}.top{{align-items:flex-start}}}}
    @media print{{body{{background:#fff;font-size:10pt}}.top,.back,.anchor{{display:none}}.page{{max-width:none;margin:0;padding:0}}.cover,.toc,.content{{box-shadow:none;border:0}}.cover{{break-after:page}}h2{{break-before:page}}pre,.table-wrap{{break-inside:avoid}}.toc a{{color:#1859ba;text-decoration:underline}}}}
  </style>
</head>
<body>
  <div class="top"><strong>Documentación técnica</strong><div class="buttons"><a class="button" href="/">Volver a la aplicación</a><a class="button primary" href="/documentacion-tecnica/esquema/pdf">Esquema BD en PDF</a><a class="button" href="/documentacion-tecnica/esquema/sqlite">SQL SQLite</a><a class="button" href="/documentacion-tecnica/esquema/postgresql">SQL PostgreSQL</a><a class="button" href="/documentacion-tecnica/descargar">Documentación completa PDF</a></div></div>
  <main class="page">
    <header class="cover"><h1>Dashboard de Facturación</h1><p>Documentación técnica para instalación, mantenimiento, soporte, comprensión del modelo de datos y transferencia del sistema.</p><p><strong>Acceso exclusivo para administradores.</strong></p><small>Generada desde README.md · Julio de 2026</small></header>
    <nav class="toc" id="indice"><h2>Índice técnico</h2><ol>{construir_indice(indice)}</ol></nav>
    <article class="content">{cuerpo}</article>
    <footer>Dashboard de Facturación · Documentación técnica</footer>
  </main>
  <a class="back" href="#indice">Índice ↑</a>
</body>
</html>"""
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(documento, encoding="utf-8")
    print(f"Generado: {DESTINO}")


if __name__ == "__main__":
    main()
