import type { Metadata } from 'next';
import './style.css';
export const metadata: Metadata = { title: 'GeoAI Platform · P0' };
export default function Layout({ children }: { children: React.ReactNode }) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
