"use client";
export default function ErrorPage({ reset }: { reset: () => void }) { return <section className="card"><h2>暂时无法加载项目</h2><p>请检查本地服务状态后重试。</p><button onClick={reset}>重试</button></section>; }
