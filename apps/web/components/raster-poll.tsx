"use client";
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
export default function RasterPoll({ pending, monitorEndpoints=false }: { pending: boolean; monitorEndpoints?:boolean }) {
 const router=useRouter();
 useEffect(()=>{if(!pending&&!monitorEndpoints)return;const timer=setInterval(()=>router.refresh(),pending?3000:10000);return ()=>clearInterval(timer);},[pending,monitorEndpoints,router]);
 return null;
}
