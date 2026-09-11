-- pg_policies verified: UPDATE USING/WITH CHECK require project_role owner/editor.
-- Authenticated is a database role, not a permission to edit every project.
ALTER TABLE public.aois ADD COLUMN description text NOT NULL DEFAULT '' CHECK (char_length(description)<=2000);
GRANT INSERT(description) ON public.aois TO authenticated;
GRANT UPDATE(description) ON public.aois, public.visual_prompts TO authenticated;
NOTIFY pgrst,'reload schema';
