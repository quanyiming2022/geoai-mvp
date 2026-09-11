import { notFound } from 'next/navigation';
import { api, ApiError, type Project } from '../lib/session';
import ProjectSettings from './project-settings';
import type { SettingsMember } from '../app/projects/[id]/settings-actions';
export default async function ProjectSettingsPage({params,section="general"}:{params:Promise<{id:string}>;section?:string}){
 const {id}=await params;if(!/^[0-9a-f-]{36}$/i.test(id))notFound();
 let project:Project;let members:SettingsMember[];
 try {project=await api<Project>(`/projects/${id}`);members=await api<SettingsMember[]>(`/projects/${id}/member-identities`);}catch(error){if(error instanceof ApiError&&error.status===404)notFound();throw error;}
 return <ProjectSettings initial={project} initialMembers={members} initialSection={section}/>;
}
