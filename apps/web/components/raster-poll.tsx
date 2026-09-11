"use client";
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
export default function RasterPoll({ pending }: { pending: boolean }) {
 const router=useRouter();
 useEffect(()=>{if(!pending)return;const timer=setInterval(()=>router.refresh(),3000);return ()=>clearInterval(timer);},[pending,router]);
 return null;
}
