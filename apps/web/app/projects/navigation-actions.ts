"use server";
import {api,requireUser,type Project} from '../../lib/session';
export async function workspaceProjects(){await requireUser();return api<Project[]>('/projects');}
