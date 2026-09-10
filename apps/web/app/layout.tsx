import type { Metadata } from 'next';
import 'maplibre-gl/dist/maplibre-gl.css';
import './style.css';
export const metadata: Metadata = { title: 'GeoAI Platform' };
export default function Layout({ children }: { children: React.ReactNode }) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
