/**
 * Main application component — assembles the platform layout.
 *
 * Layout:
 * ┌──────────────────────────────────────────────────┐
 * │ Header                                           │
 * ├──────────┬────────────────────────────────────────┤
 * │          │                                        │
 * │  Chat /  │         Center Panel                   │
 * │  Tasks   │    (Sandbox + Agent State)              │
 * │          │                                        │
 * ├──────────┴────────────────────────────────────────┤
 * │ Bottom Panel (Timeline / Terminal / Tools / etc)  │
 * └──────────────────────────────────────────────────┘
 */
import { useEffect } from 'react';
import { useStore } from './stores/appStore';
import { Header } from './components/layout/Header';
import { ChatPanel } from './components/chat/ChatPanel';
import { CenterPanel } from './components/sandbox/CenterPanel';
import { BottomPanel } from './components/panels/BottomPanel';

export default function App() {
  const { init, backendConnected } = useStore();

  useEffect(() => {
    init();
  }, []);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      background: 'var(--bg-primary)',
      color: 'var(--text-primary)',
    }}>
      <Header />

      {/* Main content area */}
      <div style={{
        flex: 1,
        display: 'flex',
        overflow: 'hidden',
        minHeight: 0,
      }}>
        <ChatPanel />
        <CenterPanel />
      </div>

      <BottomPanel />
    </div>
  );
}
