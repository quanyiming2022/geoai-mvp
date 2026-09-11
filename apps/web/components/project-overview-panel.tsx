"use client";
import {useEffect,useState} from 'react';
import {loadProjectOverview} from '../app/projects/[id]/settings-actions';
import type {Project} from '../lib/session';
export default function ProjectOverviewPanel({project}:{project:Project}){
 const [data,setData]=useState<{id:string;counts?:number[];error?:string}|null>(null);
 useEffect(()=>{let active=true;loadProjectOverview(project.id).then(result=>{if(active)setData({...result,id:project.id});}).catch(()=>{if(active)setData({id:project.id,error:'统计暂不可用'});});return()=>{active=false;};},[project.id]);
 return <div className="project-overview"><h2>项目概览</h2><p>{project.description||'尚未填写项目描述。可在设置中说明项目目标。'}</p>{data?.id!==project.id?<p role="status">正在读取项目数据…</p>:data.error?<p role="status">{data.error}</p>:<><div className="overview-metrics">{['影像','AOI','视觉样例','结果','进行中任务'].map((label,i)=><div key={label}><strong>{data.counts?.[i]}</strong><span>{label}</span></div>)}</div><small className="muted">统计当前接口返回的可见记录；任务统计范围为最近 50 条。</small></>}<dl><dt>创建时间</dt><dd>{new Date(project.created_at).toLocaleDateString('zh-CN')}</dd><dt>最近活动</dt><dd>暂未提供完整活动记录</dd></dl><p className="muted">进入工作区管理影像、AOI、视觉样例与提取结果。</p></div>;
}
