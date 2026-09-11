const paths: Record<string,string> = {
 data:'M4 4h16v16H4z M4 9h16 M9 9v11',
 layers:'m12 3 9 5-9 5-9-5 9-5z M3 12l9 5 9-5 M3 16l9 5 9-5',
 aois:'M5 5h14v14H5z M3 3h4v4H3z M17 17h4v4h-4z',
 prompts:'M4 4h16v16H4z M4 16l5-5 4 4 3-3 4 4 M8 8h.01',
 results:'M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z',
 pointer:'m5 3 14 10-7 1-3 7-4-18z',
 pan:'M8 12V6a2 2 0 0 1 4 0v5 M12 10V4a2 2 0 0 1 4 0v7 M16 10V7a2 2 0 0 1 4 0v8c0 4-3 6-6 6h-2c-2 0-3-1-4-3l-4-6a2 2 0 0 1 3-2l1 2',
 prompt:'M4 4h16v16H4z M4 16l5-5 4 4 3-3 4 4 M8 8h.01',
 aoi:'M5 5h14v14H5z M3 3h4v4H3z M17 17h4v4h-4z',
};
export default function WorkspaceIcon({name}:{name:string}){return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]??paths.pointer}/></svg>;}
