"use client";
import { useFormStatus } from 'react-dom';
export default function PendingSubmit({children,pendingLabel='处理中…',disabled=false,className='secondary compact'}:{children:React.ReactNode;pendingLabel?:string;disabled?:boolean;className?:string}) { const {pending}=useFormStatus(); return <button className={className} disabled={disabled||pending} aria-busy={pending}>{pending?pendingLabel:children}</button>; }
