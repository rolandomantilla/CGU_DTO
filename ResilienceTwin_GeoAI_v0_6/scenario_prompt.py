"""Translate scenario prompts into validated optimizer settings."""
import json
import re
from urllib.request import Request, urlopen

from optimizer_v06 import POLICIES

SCENARIOS = {
    'Normal conditions': 'SCN-NORMAL', 'Highway slowdown': 'SCN-SLOW',
    'Road closure': 'SCN-CLOSE', 'Delayed pickup': 'SCN-PICKUP',
    'Wildfire-related slowdown': 'SCN-FIRE', 'Flood-related slowdown': 'SCN-FLOOD',
}
DEFAULT = dict(scenario='Highway slowdown', severity=75, policy='Balanced',
               turnaround=25, max_trips=4, attempts=6, closure_segment=None, closure_location=None, basemap="streets")
LIMITS = {'severity': (0, 240), 'turnaround': (0, 90), 'max_trips': (1, 8), 'attempts': (1, 12)}


def closure_target(prompt):
    """Resolve supported named closures to explicit simulation corridors."""
    if re.search(r'\b(reopen|clear the closure|normal conditions)\b', prompt, re.I):
        return None
    segment = re.search(r'\bS-00[1-9]\b|\bS-01[0-3]\b', prompt, re.I)
    highway = re.search(r'\b(?:highway|freeway|state route|route|SR|I)\s*-?\s*(\d+)\b', prompt, re.I)
    if segment:
        return segment[0].upper()
    if highway:
        match = {'60': 'S-005', '57': 'S-004', '10': 'S-004', '710': 'S-003', '605': 'S-013'}.get(highway[1])
        if match is None:
            raise ValueError(f'Highway {highway[1]} has no mapped simulation corridor. Use a modeled segment ID.')
        return match
    return None


BASEMAPS = ("streets", "satellite", "topographic", "gray")


def openai_updates(prompt, current, api_key, model, history):
    fields = {
        "scenario": {"enum": [*SCENARIOS, None]},
        "policy": {"enum": [*POLICIES, None]},
        "basemap": {"enum": [*BASEMAPS, None]},
        **{field: {"type": ["integer", "null"]} for field in LIMITS},
    }
    request = Request(
        "https://api.openai.com/v1/responses",
        json.dumps({
            "model": model, "store": False,
            "instructions": (
                "Extract only requested changes for a synthetic logistics simulator. "
                "Use null for settings the user wants to retain. Preserve context for follow-ups. "
                "Severity is the disruption delay in minutes; turnaround is receiving time in minutes. "
                f"Integer bounds: {LIMITS}. Use gray for light gray. "
                "The simulator validates named roads separately. For an unsupported request "
                "return all nulls; never invent routes, traffic or geographic data."
            ),
            "input": json.dumps({"request": prompt, "active_settings": current,
                                 "recent_requests": history[-5:]}),
            "text": {"format": {"type": "json_schema", "name": "scenario_updates", "strict": True,
                                "schema": {"type": "object", "properties": fields,
                                           "required": list(fields), "additionalProperties": False}}},
        }).encode(),
        {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    with urlopen(request, timeout=45) as response:
        data = json.load(response)
    if data.get("status") != "completed":
        raise ValueError("OpenAI did not complete the request.")
    parts = [part["text"] for item in data.get("output", []) if item["type"] == "message"
             for part in item["content"] if part["type"] == "output_text"]
    if not parts:
        raise ValueError("OpenAI returned no scenario settings.")
    updates = json.loads("".join(parts))
    if not isinstance(updates, dict):
        raise ValueError("Invalid scenario settings.")
    return {key: value for key, value in updates.items() if value is not None}


def interpret(prompt, current, model='', *, api_key='', openai_model='gpt-4o-mini', history=()):
    if not prompt.strip():
        raise ValueError("Describe the scenario or map change first.")
    current = {**DEFAULT, **current}
    target = closure_target(prompt)
    reopening = bool(re.search(r'\b(reopen|clear the closure)\b', prompt, re.I))
    if api_key:
        updates = openai_updates(prompt, current, api_key, openai_model, history)
    elif model:
        request = Request('http://127.0.0.1:11434/api/chat', json.dumps({
            'model': model, 'stream': False, 'format': 'json',
            'messages': [
                {'role': 'system', 'content': (
                    'Return a JSON object containing only explicitly requested setting changes. '
                    'Return {} for unsupported requests; never invent new scenarios. Do not return closure_segment or closure_location. '
                    'Distinguish turnaround minutes from disruption severity. '
                    f'Allowed scenarios: {list(SCENARIOS)}. Policies: {POLICIES}. '
                    f'Integer fields and bounds: {LIMITS}.'
                )},
                {'role': 'user', 'content': json.dumps({'current': current, 'request': prompt})},
            ],
        }).encode(), {'Content-Type': 'application/json'})
        with urlopen(request, timeout=60) as response:
            updates = json.loads(json.load(response)['message']['content'])
    else:
        updates = {}
        text = prompt.lower()
        terms = {
            'Normal conditions': r'\b(normal|baseline)\b',
            'Road closure': r'\b(closure|closed)\b',
            'Delayed pickup': r'\bpickup\b',
            'Wildfire-related slowdown': r'\bwildfire\b',
            'Flood-related slowdown': r'\bflood\w*\b',
            'Highway slowdown': r'\b(slowdown|traffic delay)\b',
        }
        for scenario, pattern in terms.items():
            if re.search(pattern, text):
                updates['scenario'] = scenario
                break
        for label, value in (("satellite", "satellite"), ("topographic", "topographic"),
                             ("light gray", "gray"), ("street map", "streets"), ("streets", "streets")):
            if label in text:
                updates["basemap"] = value
                break
        for policy in POLICIES:
            if policy.lower() in text.replace('co₂', 'co2'):
                updates['policy'] = policy
        for field, pattern in {
            'turnaround': r'(\d+)\s*[- ]?\s*min(?:utes?)?\s+(?:receiving\s+)?turnaround\b',
            'max_trips': r'(\d+)\s+trips?\s+per\s+truck',
            'attempts': r'(\d+)\s+(?:attempts|orderings)\b',
            'severity': r'(\d+)\s*[- ]?\s*min(?:utes?)?\s*(?:delay|highway slowdown|slowdown)\b|\bdelay\s+(?:of\s+|to\s+)?(\d+)\s*min',
        }.items():
            match = re.search(pattern, text)
            if match:
                updates[field] = int(next(value for value in match.groups() if value))
    if not isinstance(updates, dict) or set(updates) - (set(DEFAULT) - {'closure_segment', 'closure_location'}):
        raise ValueError('Invalid scenario settings.')
    if reopening:
        updates.update(scenario='Normal conditions')
    elif target:
        updates.update(scenario='Road closure')
    if not updates:
        raise ValueError('No supported scenario settings found.')
    settings = {**current, **updates}
    if settings['scenario'] not in SCENARIOS or settings['policy'] not in POLICIES:
        raise ValueError('Unknown scenario or policy.')
    if settings['basemap'] not in BASEMAPS:
        raise ValueError('Unknown basemap.')
    for field, (low, high) in LIMITS.items():
        value = settings[field]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f'{field} must be an integer from {low} to {high}.')
    if settings['scenario'] == 'Normal conditions':
        settings['severity'] = 0
    elif 'scenario' in updates and settings['scenario'] != current['scenario'] and 'severity' not in updates:
        settings['severity'] = 75 if settings['scenario'] == 'Highway slowdown' else 90
    settings['closure_segment'] = (
        target or (current.get('closure_segment') if current['scenario'] == 'Road closure' else None)
    ) if settings['scenario'] == 'Road closure' else None
    highway = re.search(r'\b(?:highway|freeway|state route|route|SR|I)\s*-?\s*(\d+)\b', prompt, re.I)
    if target and highway:
        place = ' · East LA' if re.search(r'\beast (?:la|los angeles)\b', prompt, re.I) else ''
        settings['closure_location'] = f'Highway {highway[1]}{place}'
    elif target or settings['scenario'] != 'Road closure':
        settings['closure_location'] = None
    return settings
