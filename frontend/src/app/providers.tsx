import * as Tooltip from '@radix-ui/react-tooltip';
import { useEffect, type ReactNode } from 'react';
import { useOcrStore } from '../store/useOcrStore';

export function Providers({ children }: { children: ReactNode }) {
  const boot = useOcrStore((s) => s.boot);
  useEffect(() => {
    void boot();
  }, [boot]);
  return <Tooltip.Provider delayDuration={300}>{children}</Tooltip.Provider>;
}
