import type { PropsWithChildren, ReactNode } from 'react';

type LayoutProps = PropsWithChildren<{
  header: ReactNode;
  sidebar: ReactNode;
}>;

export default function Layout({ header, sidebar, children }: LayoutProps) {
  return (
    <div className="app-shell">
      {header}
      <div className="workspace-shell">
        <aside className="sidebar-panel">{sidebar}</aside>
        <main className="content-panel">{children}</main>
      </div>
    </div>
  );
}
