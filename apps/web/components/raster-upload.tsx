"use client";
import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
export default function RasterUpload({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false); const [message, setMessage] = useState('');
  const [progress, setProgress] = useState(0); const active = useRef<XMLHttpRequest | null>(null);
  useEffect(() => () => { if (active.current) { active.current.onload = null; active.current.onerror = null; active.current.abort(); } }, []);
  function upload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget;
    const file = new FormData(form).get('raster');
    if (!(file instanceof File) || !file.size) { setMessage('请选择 GeoTIFF 文件。'); return; }
    const xhr = new XMLHttpRequest(); active.current = xhr; setBusy(true); setMessage('正在上传…'); setProgress(0);
    xhr.open('POST', `/api/projects/${projectId}/rasters`);
    xhr.setRequestHeader('Content-Type', 'image/tiff'); xhr.setRequestHeader('x-filename', encodeURIComponent(file.name));
    xhr.upload.onprogress = event => { if (event.lengthComputable) { setProgress(Math.round(event.loaded / event.total * 100)); if (event.loaded === event.total) setMessage('文件已发送，正在校验与保存…'); } };
    xhr.onload = () => {
      setBusy(false); active.current = null;
      if (xhr.status === 201) { setMessage('影像上传成功。'); form.reset(); router.refresh(); }
      else setMessage(xhr.status === 413 ? '文件超过服务器配置的大小限制。' : xhr.status === 422 ? '请选择有效且包含 CRS 的 GeoTIFF。' : xhr.status === 403 ? '你没有上传权限。' : xhr.status === 401 ? '请重新登录后重试。' : '上传失败，请检查服务后重试。');
    };
    xhr.onerror = () => { setBusy(false); active.current = null; setMessage('网络中断，请重试。'); };
    xhr.send(file);
  }
  return <form onSubmit={upload} className="upload-form"><label>上传 GeoTIFF<input name="raster" type="file" accept=".tif,.tiff,image/tiff" required disabled={busy}/></label><button disabled={busy}>{busy ? '上传处理中…' : '上传影像'}</button>{busy && <progress max={100} value={progress} aria-label="上传进度"/>}{message && <p role="status">{message}</p>}</form>;
}
