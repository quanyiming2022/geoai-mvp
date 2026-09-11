import {api,requireUser,type Project} from '../../../lib/session';
import ProjectHub from '../../../components/project-hub';
export default async function Projects(){const user=await requireUser();const projects=await api<Project[]>('/projects');return <ProjectHub projects={projects} userId={user.id}/>;}
