import pytest
from pydantic import ValidationError
from geoai.results import ResultEdit,ResultDelete,result_feature

@pytest.mark.parametrize('field',['source_job','source_metadata','checkpoint_digest','original_geometry','model_name'])
def test_result_edit_rejects_prediction_identity(field):
    with pytest.raises(ValidationError):ResultEdit(expected_revision=1,**{field:'tampered'})

def test_deletion_requires_confirmation_and_revision():
    with pytest.raises(ValidationError):ResultDelete(expected_revision=1,confirmed=False)
    with pytest.raises(ValidationError):ResultDelete(confirmed=True)

def test_export_uses_current_geometry_and_retains_provenance():
    geometry={'type':'Polygon','coordinates':[[[0,0],[1,0],[0,1],[0,0]]]}
    row={'id':'result','job_id':'job','geometry':geometry,'result_name':'Edited','source_metadata':{'model':'test-model','model_version':'1','checkpoint_digest':'abc'}}
    result=result_feature(row)
    assert result['geometry'] is geometry
    assert result['properties']['source_job_id']=='job'
    assert result['properties']['model_name']=='test-model'
    assert result['properties']['checkpoint_digest']=='abc'
    assert result['properties']['result_name']=='Edited'
