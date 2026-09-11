"use client";
import type {Project} from '../lib/session';
import {useEffect,useRef,useState} from 'react';
import ProjectOverviewPanel from './project-overview-panel';
import {loadProjectSettings} from '../app/projects/[id]/settings-actions';
import {useSearchParams} from 'next/navigation';
import ProjectSettingsPanel from './project-settings-panel';
export default function WorkspaceSettingsSheet({projectId,onProjectSaved}:{projectId:string;onProjectSaved?:(project:Project)=>void}){
 const params=useSearchParams(),dialog=useRef<HTMLDialogElement>(null),dirty=useRef(false);useEffect(()=>{const changed=(e:Event)=>{dirty.current=(e as CustomEvent<boolean>).detail;};window.addEventListener('workspace-settings-dirty',changed);return()=>window.removeEventListener('workspace-settings-dirty',changed);},[]);const open=['settings','overview','members'].includes(params.get('panel')??'');const overview=params.get('panel')==='overview';const [project,setProject]=useState<Project|null>(null);useEffect(()=>{if(overview)loadProjectSettings(projectId).then(data=>{if(data.project)setProject(data.project);});},[overview,projectId]);const section=params.get('panel')==='members'?'members':['general','members','danger'].includes(params.get('section')??'')?params.get('section')!:'general';
 function navigate(next:string|null){if(dirty.current&&!window.confirm('当前设置有未保存更改，是否放弃并关闭或切换？'))return;const url=new URL(location.href);if(next){url.searchParams.set('panel','settings');url.searchParams.set('section',next);}else{url.searchParams.delete('panel');url.searchParams.delete('section');}history.pushState(null,'',url);}
 useEffect(()=>{if(open&&!dialog.current?.open)dialog.current?.showModal();else if(!open&&dialog.current?.open)dialog.current.close();},[open]);
 return <><dialog ref={dialog} className="workspace-settings-sheet" aria-label="项目设置" onKeyDown={event=>event.stopPropagation()} onCancel={event=>{event.preventDefault();navigate(null);}}><header><strong>{overview?'项目概览':section==='members'?'成员与权限':'项目设置'}</strong><button className="secondary" aria-label="关闭项目设置" onClick={()=>navigate(null)}>关闭</button></header>{open&&overview?(project?<ProjectOverviewPanel project={project}/>:<p>正在加载项目概览…</p>):open&&<ProjectSettingsPanel projectId={projectId} section={section} onProjectSaved={onProjectSaved} onSectionChange={navigate}/>}</dialog></>;
}
