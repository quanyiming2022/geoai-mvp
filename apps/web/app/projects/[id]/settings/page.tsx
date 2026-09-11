import ProjectSettingsPage from '../../../../components/project-settings-page';
export default function Page({params}:{params:Promise<{id:string}>}){return <ProjectSettingsPage params={params} section="general"/>;}
