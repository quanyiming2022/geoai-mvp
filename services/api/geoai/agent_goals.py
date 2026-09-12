"""Bounded goals, deterministic identity resolution and capability policy."""
import re
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field

CAPABILITIES={'visual_prompt_segmentation':True,'single_tile':True,'single_tile_full_aoi':True,'multi_tile_full_aoi':False,'multi_shot':False,'text_to_mask':False,'language_conditioned_segmentation':False}
ERRORS={'endpoint_unreachable':'当前 GPU 服务无法连接。','request_timeout':'模型测试超时，未产生可用结果。','timeout':'模型测试超时，未产生可用结果。','cuda_oom':'GPU 显存不足，任务没有产生有效结果。','inference_failed':'模型推理未完成，请检查计算节点后重试。','invalid_response':'模型响应未通过有效性检查，不能作为 GIS 成果。','cancelled':'任务已取消。'}
class AgentGoal(BaseModel):
    model_config=ConfigDict(extra='forbid')
    goal_type:Literal['extract_similar','test_model_here','inspect_result','check_job_status','show_resource','explain_failure','cancel_job','switch_project','unsupported']
    target:Literal['visual_prompt','class','result','none']='none'
    scope:Literal['current_aoi','current_map_extent','selected_location','explicit_aoi']='current_aoi'
    requested_execution_scope:Literal['single_tile','full_aoi','none']='none'
    output_intent:Literal['preview','gis_result','status','explanation']='explanation'
    prompt_name:str|None=Field(default=None,max_length=120)
    aoi_name:str|None=Field(default=None,max_length=120)
    raster_name:str|None=Field(default=None,max_length=255)
    resource_kind:Literal['aoi','prompt','raster','result','none']='none'
    ui_action:Literal['zoom_to_object','select_result','toggle_layer','set_layer_visibility','none']='none'
    visible:bool|None=None

class ResolutionError(Exception):
    def __init__(self,field,message,candidates=()):
        self.field=field;self.message=message;self.candidates=list(candidates)


def resolve_resource(items,hint,current_id,field,required=True):
    if hint:
        exact=[x for x in items if str(x.get('name',x.get('filename',''))).casefold()==hint.casefold()]
        candidates=exact or [x for x in items if hint.casefold() in str(x.get('name',x.get('filename',''))).casefold()]
        if not candidates:raise ResolutionError(field,f'没有找到“{hint}”，请检查名称。',items)
    elif current_id:
        candidates=[x for x in items if str(x['id'])==str(current_id)]
        if not candidates:raise ResolutionError(field,'当前选择已失效，请重新选择。',items)
    else:candidates=items
    if len(candidates)>1 and current_id:
        selected=next((x for x in candidates if str(x['id'])==str(current_id)),None)
        if selected:return selected
    if len(candidates)==1:return candidates[0]
    if not required and not candidates:return None
    if not candidates:raise ResolutionError(field,'当前项目尚无可用'+{'raster_id':'影像','prompt_id':'视觉样例','aoi_id':'AOI','endpoint_id':'模型节点'}.get(field,'对象')+'。')
    label={'aoi_id':'AOI','prompt_id':'视觉样例','raster_id':'影像','endpoint_id':'模型节点'}.get(field,'对象')
    raise ResolutionError(field,f'有 {len(candidates)} 个可用{label}，要使用哪一个？',candidates)


def select_endpoint(endpoints,selected=None):
    # The upstream catalog includes enabled/authorized endpoints only. Synthetic
    # infrastructure is never automatically advertised as a real model.
    compatible=[e for e in endpoints if e.get('usage_policy') in ('research_only','commercial') and e.get('health_status')=='healthy']
    if selected:
        found=next((e for e in endpoints if str(e['id'])==str(selected)),None)
        if not found or found.get('health_status')!='healthy':raise ResolutionError('endpoint_id','当前真实模型节点不可用。')
        if found.get('usage_policy') not in ('research_only','commercial'):raise ResolutionError('endpoint_id','此节点仅用于合成流程测试。')
        return found
    if not compatible:raise ResolutionError('endpoint_id','当前真实模型节点不可用。')
    return resolve_resource(compatible,None,None,'endpoint_id')


def enforce_goal_scope(goal,text):
    # Never silently convert an extraction of a geographic range into a tile.
    whole=bool(re.search(r'所有|整个|全部|全范围|全图|full[ _-]?aoi|whole|entire',text,re.I))
    if goal.goal_type in ('extract_similar','test_model_here'):
        if whole or goal.requested_execution_scope=='full_aoi':return goal.model_copy(update={'goal_type':'extract_similar','requested_execution_scope':'full_aoi'})
        if re.search(r'测试|试试|再测|在这里跑一下|single[ _-]?tile|test',text,re.I):return goal.model_copy(update={'goal_type':'test_model_here','scope':'selected_location','requested_execution_scope':'single_tile'})
        return goal.model_copy(update={'requested_execution_scope':'full_aoi'})
    return goal


def capability_check(goal,coverage=None):
    return goal.requested_execution_scope!='full_aoi' or bool(coverage and coverage.get('available'))


def job_message(job):
    state=job['status'];status={'queued':'正在排队','running':'正在运行','succeeded':'已完成','failed':'失败','cancelled':'已取消'}.get(state,'状态未知')
    message=f'最近任务{status}。'
    if state=='running':message=f"最近任务正在运行，进度 {job.get('progress',0)}%。"
    if state=='failed':message+=ERRORS.get(job.get('error_code'),'任务未产生可用结果，请查看任务详情。')
    if state=='succeeded':
        result=job.get('result') or {};runtime=result.get('runtime_ms')
        if runtime is not None:message+=f'模型推理用时 {runtime/1000:.2f} 秒。'
        count=result.get('result_count')
        if count is not None:message+=f'产生 {count} 个候选图斑，仍需人工审核。'
    return message
