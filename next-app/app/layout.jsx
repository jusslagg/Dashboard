import './globals.css';
import Link from 'next/link';
import { BarChart3, Database, LayoutDashboard, Table2 } from 'lucide-react';

export const metadata = {
  title: 'Facturacion 2026',
  description: 'Control ejecutivo de facturacion migrado a Next.js',
};

const links = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/control', label: 'Control', icon: Table2 },
];

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <body>
        <div className="app-shell">
          <aside className="sidebar">
            <div className="brand">
              <h1><BarChart3 size={20} /> Facturacion</h1>
              <p>Next local + Flask API</p>
            </div>
            <nav>
              {links.map((link) => {
                const Icon = link.icon;
                return (
                  <Link key={link.href} href={link.href} className="nav-link">
                    <Icon size={18} />
                    <span>{link.label}</span>
                  </Link>
                );
              })}
              <a className="nav-link" href="http://127.0.0.1:8009/cargar">
                <Database size={18} />
                <span>Cargar Datos</span>
              </a>
              <a className="nav-link" href="http://127.0.0.1:8009/catalogos">
                <Database size={18} />
                <span>Datos Maestros</span>
              </a>
            </nav>
          </aside>
          <main className="content">{children}</main>
        </div>
      </body>
    </html>
  );
}
