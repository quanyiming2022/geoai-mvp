"use client";
import {useEffect,useState} from 'react';
import type {Project} from '../lib/session';
import {loadProjectSettings,type SettingsResult} from '../app/projects/[id]/settings-actions';
import ProjectSettings from './project-settings';
export default function ProjectSettingsPanel({projectId,section='general',hideNavigation=false,onSectionChange,onProjectSaved}:{projectId:string;section?:string;hideNavigation?:boolean;onSectionChange:(value:string)=>void;onProjectSaved?:(project:Project)=>void}){
 const [data,setData]=useState<(SettingsResult&{id:string})|null>(null),[retry,setRetry]=useState(0);
 useEffect(()=>{let active=true;loadProjectSettings(projectId).then(result=>{if(active)setData({...result,id:projectId});}).catch(()=>{if(active)setData({id:projectId,error:'无法加载项目设置，请重试。'});});return()=>{active=false;};},[projectId,retry]);
 if(data?.id!==projectId)return <p role="status">正在加载项目设置…</p>;
 if(data.error||!data.project||!data.members)return <div role="alert"><p>{data.error??'无法加载项目设置。'}</p><button className="secondary" onClick={()=>setRetry(v=>v+1)}>重试</button></div>;
 return <ProjectSettings key={projectId} initial={data.project} initialMembers={data.members} embedded hideNavigation={hideNavigation} initialSection={section} onSectionChange={onSectionChange} onProjectSaved={onProjectSaved}/>;
}
