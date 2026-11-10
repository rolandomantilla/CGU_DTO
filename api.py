"""Synthetic simulation API; employee edits are scoped to each scenario request."""
from pathlib import Path
from typing import Annotated, Literal
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator

from engine import load_model, simulate
from human_factors import employee_profiles

app = FastAPI(title='ResilienceTwin Simulation API', version='0.2.0')
BASE = Path(__file__).parent
DATA = load_model()
app.mount('/static', StaticFiles(directory=BASE / 'web'), name='static')

NonnegativeNumber = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
Proficiency = Annotated[float, Field(strict=True, ge=1, le=5, allow_inf_nan=False)]


class InputModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ExperienceUpdate(InputModel):
    workflow_id: str
    years_in_role: NonnegativeNumber | None = None
    similar_tasks_completed: Annotated[int, Field(strict=True, ge=0)] | None = None

    @model_validator(mode='after')
    def one_measure(self):
        if (self.years_in_role is None) == (self.similar_tasks_completed is None):
            raise ValueError('Choose years in role or similar tasks completed, not both')
        return self


class RelationshipUpdate(InputModel):
    workflow_id: str
    target_employee_id: str
    collaboration_events: Annotated[int, Field(strict=True, ge=0)]
    handoff_events: Annotated[int, Field(strict=True, ge=1)]
    mean_handoff_hours: NonnegativeNumber


class EmployeeUpdate(InputModel):
    employee_id: str
    skills: dict[str, Proficiency] | None = None
    experience: list[ExperienceUpdate] | None = None
    relationships: list[RelationshipUpdate] | None = None


class Scenario(InputModel):
    type: str
    model_variant: Literal['process_only', 'skills_only', 'experience_only',
                           'relationships_only', 'human_centered'] = 'human_centered'
    facility_id: str | None = None
    personnel_unavailable_pct: Annotated[float, Field(strict=True, ge=0, le=100, allow_inf_nan=False)] | None = None
    employee_id: str | None = None
    system_id: str | None = None
    role: str | None = None
    duration_hours: Annotated[float, Field(strict=True, gt=0, le=2160, allow_inf_nan=False)] = 24
    employee_updates: list[EmployeeUpdate] = Field(default_factory=list, max_length=100)


@app.get('/')
def root():
    return FileResponse(BASE / 'web' / 'index.html', headers={'Cache-Control': 'no-cache'})


@app.get('/api/health')
def health():
    return {'status': 'ok', 'version': '0.2.0', 'data': 'synthetic',
            'features': ['editable_employee_human_variables']}


@app.get('/api/model')
def model():
    return {
        'facilities': DATA['facilities'], 'systems': DATA['systems'],
        'roles': sorted({e['role'] for e in DATA['employees']}),
        'employees': employee_profiles(DATA),
        'workflows': DATA['workflows'],
        'skill_ids': sorted({r['skill_id'] for r in DATA['employee_skills']}
                            | {r['skill_id'] for r in DATA['workflow_skill_requirements']}),
        'human_parameters': DATA['human_factors']['parameters'],
        'scenarios': json.loads((BASE / 'data' / 'scenarios.json').read_text()),
    }


@app.post('/api/simulate')
def run(s: Scenario):
    try:
        return simulate(s.model_dump(exclude_none=True), DATA)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
