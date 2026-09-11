"use client";
import {useRef,useState,useId} from 'react';
import {useRouter} from 'next/navigation';
import {renameSpatialObject,deleteSpatialObject} from '../app/actions';

export default function SpatialObjectActions({projectId,id,kind,name,description,editable,onLocate,onEdit,onDeleted,revision}:{projectId:string;id:string;kind:'aois'|'prompts';name:string;description:string;editable:boolean;onLocate:()=>void;onEdit:()=>void;onDeleted:()=>void;revision:number}) {
  const router=useRouter();
  const menuId=useId();
  const menu=useRef<HTMLDivElement>(null),dialog=useRef<HTMLDialogElement>(null);
  const [value,setValue]=useState(name),[pending,setPending]=useState(false),[message,setMessage]=useState('');
  const [descriptionValue,setDescriptionValue]=useState(description);
  const removeDialog=useRef<HTMLDialogElement>(null);
  const [editing,setEditing]=useState<'name'|'description'>('name');
  const openEditor=(field:'name'|'description')=>{menu.current?.hidePopover();setValue(name);setDescriptionValue(description);setMessage('');setEditing(field);dialog.current?.showModal();requestAnimationFrame(()=>dialog.current?.querySelector<HTMLElement>(field==='name'?'input':'textarea')?.focus());};
  const close=()=>{if(!pending)dialog.current?.close();};
  return <>
    <button className="secondary object-more" aria-label={`${name} 的操作`} title="更多操作" aria-haspopup="true" popoverTarget={menuId} onClick={event=>{const rect=event.currentTarget.getBoundingClientRect();if(menu.current){menu.current.style.left=`${Math.max(8,rect.right-144)}px`;menu.current.style.top=`${Math.min(rect.bottom+4,window.innerHeight-150)}px`;}event.stopPropagation();}}>⋯</button>
    <div id={menuId} ref={menu} popover="auto" className="object-action-menu" aria-label={`${name} 的操作菜单`}>
      <button onClick={()=>{menu.current?.hidePopover();onLocate();}}>定位到地图</button>
      {editable&&<><button onClick={()=>openEditor('name')}>重命名</button><button onClick={()=>{menu.current?.hidePopover();onEdit();}}>编辑</button><button onClick={()=>{menu.current?.hidePopover();setMessage('');removeDialog.current?.showModal();}}>删除</button></>}
      {kind==='prompts'&&<><a href={`/api/prompts/${id}/image/download`}>下载样例影像</a><a href={`/api/prompts/${id}/mask/download`}>下载样例掩膜</a></>}
    </div>
    <dialog ref={removeDialog} className="object-rename-dialog" aria-label="确认删除" onCancel={e=>{if(pending)e.preventDefault();}} onKeyDown={e=>e.stopPropagation()}><h3>删除“{name}”？</h3><p>该对象将不再出现在当前项目资源中，不能用于新任务。历史任务及其结果、审核和导出将保留。</p>{message&&<p role="alert">{message}</p>}<div className="object-dialog-actions"><button className="secondary" disabled={pending} onClick={()=>removeDialog.current?.close()}>取消</button><button className="danger" disabled={pending} onClick={async()=>{setPending(true);try{const result=await deleteSpatialObject(projectId,kind,id,revision);if(result.error)setMessage(result.error);else{removeDialog.current?.close();onDeleted();router.refresh();}}catch{setMessage('删除失败，请重试。');}finally{setPending(false);}}}>{pending?'正在删除…':kind==='aois'?'删除 AOI':'删除样例'}</button></div></dialog>
    <dialog ref={dialog} className="object-rename-dialog" aria-label={editing==='name'?'重命名':'编辑描述'} onCancel={event=>{if(pending)event.preventDefault();}} onKeyDown={event=>event.stopPropagation()}>
      <h3>{editing==='name'?'重命名':'编辑描述'} · {kind==='aois'?'AOI':'视觉样例'}</h3>
      <form onSubmit={async event=>{
        event.preventDefault();setPending(true);setMessage('');
        try {const result=await renameSpatialObject(projectId,kind,id,value.trim(),name,descriptionValue.trim(),description);
          if(result.error)setMessage(result.error);
          else {dialog.current?.close();router.refresh();}
        } catch {setMessage('保存失败，请重试。');}
        finally {setPending(false);}
      }}>
        <label>名称<input name="object_name" value={value} onChange={event=>setValue(event.target.value)} maxLength={120} required disabled={pending}/></label>
        <label>描述<textarea name="object_description" value={descriptionValue} onChange={event=>setDescriptionValue(event.target.value)} maxLength={2000} rows={4} disabled={pending} placeholder="记录用途或目标说明"/></label>
        <small>描述用于记录信息，不会直接改变模型推理结果。</small>
        {message&&<p role="alert">{message}</p>}
        <div className="object-dialog-actions"><button type="button" className="secondary" disabled={pending} onClick={close}>取消</button><button className="secondary" disabled={pending||!value.trim()||(value.trim()===name&&descriptionValue.trim()===description)}>{pending?'正在保存…':'保存'}</button></div>
      </form>
    </dialog>
  </>;
}
