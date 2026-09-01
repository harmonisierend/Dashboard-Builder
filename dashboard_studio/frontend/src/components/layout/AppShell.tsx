import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ConnectionStatus } from "../status/ConnectionStatus";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex min-h-screen flex-col bg-gray-50 text-gray-900">
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-3">
        <div className="flex items-center gap-6">
          <h1 className="text-lg font-semibold">HA Dashboard Studio</h1>
          <nav className="flex gap-4 text-sm">
            <Link to="/" className="text-gray-600 hover:text-gray-900">
              Entitäten
            </Link>
            <Link to="/design" className="text-gray-600 hover:text-gray-900">
              Design
            </Link>
          </nav>
        </div>
        <ConnectionStatus />
      </header>
      <main className="flex-1 p-4">{children}</main>
    </div>
  );
}
