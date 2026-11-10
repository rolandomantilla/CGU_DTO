/* Scenario-scoped employee edits. The API owns validation and the source dataset. */
const humanEditor = (() => {
  let model, runSimulation, current, draft, latestResult;
  const edits = new Map();
  const el = id => document.getElementById(id);
  const safe = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const clone = value => structuredClone(value);
  const workflowName = id => model.workflows.find(w => w.workflow_id === id)?.workflow_name || id;
  const employeeName = id => model.employees.find(e => e.employee_id === id)?.display_name || id;
  const number = input => input.value.trim() === '' ? NaN : Number(input.value);
  const options = (items, value) => items.map(([id, name]) => `<option value="${safe(id)}"${id === value ? ' selected' : ''}>${safe(name)}</option>`).join('');
  const validNumber = (v, min, max = Infinity, integer = false) => typeof v === 'number' && Number.isFinite(v) && v >= min && v <= max && (!integer || Number.isInteger(v));

  function original(employee) {
    return {
      employee_id: employee.employee_id,
      skills: Object.fromEntries(employee.skills.map(s => [s.skill_id, s.proficiency_1_to_5])),
      experience: clone(employee.experience),
      relationships: employee.organizational_relationships.work_interactions
        .filter(r => r.direction === 'outgoing')
        .map(r => ({workflow_id: r.workflow_id, target_employee_id: r.peer_employee_id,
          collaboration_events: r.collaboration_events, handoff_events: r.handoff_events,
          mean_handoff_hours: r.mean_handoff_hours})),
    };
  }

  function markEdited() {
    edits.set(current.employee_id, draft);
    latestResult = null;
    el('humanEditStatus').className = 'editor-status';
    el('humanEditStatus').textContent = `${edits.size} employee(s) changed. Run the simulation to update results.`;
  }

  function renderSkills() {
    const skills = Object.entries(draft.skills);
    el('employeeSkills').innerHTML = '<table class="editor-table"><thead><tr><th>Skill</th><th>Proficiency</th></tr></thead><tbody>' +
      skills.map(([id, value], i) => `<tr><td>${safe(id.replaceAll('_', ' '))}</td><td><input aria-label="${safe(id)} proficiency" type="number" min="1" max="5" step="0.1" value="${safe(value)}" data-skill="${i}"></td></tr>`).join('') + '</tbody></table>' +
      '<label for="newHumanSkill">Add a competency</label><div style="display:flex;gap:8px"><select id="newHumanSkill">' +
      options(model.skill_ids.filter(id => !(id in draft.skills)).map(id => [id, id.replaceAll('_', ' ')]), '') +
      '</select><button type="button" class="secondary" id="addHumanSkill">Add skill</button></div>';
    el('employeeSkills').querySelectorAll('[data-skill]').forEach(input => input.addEventListener('input', () => {
      draft.skills[skills[Number(input.dataset.skill)][0]] = number(input); markEdited();
    }));
    el('addHumanSkill').disabled = !el('newHumanSkill').options.length;
    el('addHumanSkill').onclick = () => {
      const id = el('newHumanSkill').value;
      if (id) { draft.skills[id] = 1; markEdited(); renderSkills(); }
    };
  }

  function renderExperience() {
    el('employeeExperience').innerHTML = '<table class="editor-table"><thead><tr><th>Workflow</th><th>Measure</th><th>Value</th></tr></thead><tbody>' + draft.experience.map((r, i) => {
      const measure = 'years_in_role' in r ? 'years_in_role' : 'similar_tasks_completed';
      return `<tr><td>${safe(workflowName(r.workflow_id))}</td><td><select aria-label="Experience measure ${safe(r.workflow_id)}" data-experience-measure="${i}">${options([['years_in_role','Years in role'],['similar_tasks_completed','Similar tasks completed']],measure)}</select></td><td><input aria-label="Experience value ${safe(r.workflow_id)}" type="number" min="0" step="${measure === 'years_in_role' ? '0.1' : '1'}" value="${safe(r[measure])}" data-experience="${i}"></td></tr>`;
    }).join('') + '</tbody></table>';
    el('employeeExperience').querySelectorAll('[data-experience-measure]').forEach(input => input.onchange = () => {
      const r = draft.experience[Number(input.dataset.experienceMeasure)];
      const previous = 'years_in_role' in r ? 'years_in_role' : 'similar_tasks_completed';
      delete r[previous];
      // A different unit requires a new value, not an implicit conversion.
      r[input.value] = 0;
      if (input.value === 'years_in_role') {
        r.years_in_role = draft.experience.find(x => x !== r && 'years_in_role' in x)?.years_in_role ?? 0;
      }
      markEdited(); renderExperience();
    });
    el('employeeExperience').querySelectorAll('[data-experience]').forEach(input => input.oninput = () => {
      const r = draft.experience[Number(input.dataset.experience)];
      const measure = 'years_in_role' in r ? 'years_in_role' : 'similar_tasks_completed';
      r[measure] = number(input);
      if (measure === 'years_in_role') {
        // Role years describe the same employee across every task assignment.
        draft.experience.forEach((other, i) => {
          if ('years_in_role' in other) {
            other.years_in_role = r.years_in_role;
            el('employeeExperience').querySelector(`[data-experience="${i}"]`).value = input.value;
          }
        });
      }
      markEdited();
    });
  }

  function peers(wid) {
    return model.employees.filter(e => e.employee_id !== current.employee_id && e.experience.some(x => x.workflow_id === wid))
      .map(e => [e.employee_id, `${e.display_name} (${e.employee_id})`]);
  }

  function renderRelationships() {
    const workflows = draft.experience.map(r => [r.workflow_id, workflowName(r.workflow_id)]);
    el('employeeRelationships').innerHTML = '<table class="editor-table"><thead><tr><th>Workflow</th><th>Handoff to</th><th>Collaborations / window</th><th>Handoffs / window</th><th>Mean delay (hours)</th><th>Remove</th></tr></thead><tbody>' +
      draft.relationships.map((r, i) => `<tr data-edge="${i}"><td><select aria-label="Relationship workflow ${i+1}" data-field="workflow_id">${options(workflows,r.workflow_id)}</select></td><td><select aria-label="Relationship colleague ${i+1}" data-field="target_employee_id">${options(peers(r.workflow_id),r.target_employee_id)}</select></td><td><input aria-label="Collaboration events ${i+1}" type="number" min="0" step="1" data-field="collaboration_events" value="${safe(r.collaboration_events)}"></td><td><input aria-label="Handoff events ${i+1}" type="number" min="1" step="1" data-field="handoff_events" value="${safe(r.handoff_events)}"></td><td><input aria-label="Mean handoff hours ${i+1}" type="number" min="0" max="${model.human_parameters.disconnected_handoff_hours}" step="0.01" data-field="mean_handoff_hours" value="${safe(r.mean_handoff_hours)}"></td><td><button class="secondary" type="button" aria-label="Remove relationship ${i+1}" data-remove="${i}">Remove</button></td></tr>`).join('') +
      '</tbody></table>' + (draft.relationships.length ? '' : '<p class="small">No outgoing handoffs recorded. Add one to model coordination with a colleague.</p>');
    el('employeeRelationships').querySelectorAll('[data-edge]').forEach(row => {
      const r = draft.relationships[Number(row.dataset.edge)];
      row.querySelectorAll('[data-field]').forEach(input => {
        const field = input.dataset.field;
        const update = () => {
          r[field] = input.tagName === 'SELECT' ? input.value : number(input);
          if (field === 'workflow_id') {
            r.target_employee_id = peers(r.workflow_id)[0]?.[0] || '';
            markEdited(); renderRelationships();
          } else { markEdited(); }
        };
        input.addEventListener(input.tagName === 'SELECT' ? 'change' : 'input', update);
      });
    });
    el('employeeRelationships').querySelectorAll('[data-remove]').forEach(button => button.onclick = () => {
      draft.relationships.splice(Number(button.dataset.remove),1); markEdited(); renderRelationships();
    });
  }

  function renderNetwork() {
    const profile = latestResult?.employees?.find(e => e.employee_id === current.employee_id) || current;
    const network = profile.organizational_relationships;
    const incoming = network.work_interactions.filter(r => r.direction === 'incoming');
    el('incomingRelationships').textContent = `Starting collaborators: ${current.organizational_relationships.collaborator_count}. ` +
      (latestResult ? `Current available collaborators: ${network.available_collaborator_count}; degree centrality: ${network.degree_centrality}. ` : 'Run the simulation to calculate the edited network. ') +
      'Incoming handoffs: ' + (incoming.map(r => `${employeeName(r.peer_employee_id)} (${r.workflow_id}), ${r.handoff_events} handoffs${r.disrupted ? ', disrupted' : ''}`).join('; ') || 'none') +
      '. To edit an incoming handoff, select the colleague who sends it.';
  }

  function render() {
    current = model.employees.find(e => e.employee_id === el('humanEmployee').value);
    draft = edits.get(current.employee_id) || original(current);
    el('humanEmployeeInfo').textContent = `${current.employee_id} · ${current.role} · ${current.facility_id}`;
    el('relationshipHint').textContent = `Edit directed outgoing handoffs to colleagues assigned to the same workflow. Counts cover ${current.organizational_relationships.observation_window_days} days. Mean delay can be 0–${model.human_parameters.disconnected_handoff_hours} hours. Centrality is recalculated after simulation.`;
    renderSkills(); renderExperience(); renderRelationships(); renderNetwork();
  }

  function getUpdates() {
    for (const [eid, update] of edits) {
      for (const [id, value] of Object.entries(update.skills)) {
        if (!validNumber(value, 1, 5)) throw Error(`${eid}: ${id} proficiency must be between 1 and 5.`);
      }
      for (const r of update.experience) {
        const years = 'years_in_role' in r;
        if (!validNumber(r[years ? 'years_in_role' : 'similar_tasks_completed'], 0, Infinity, !years)) {
          throw Error(`${eid}: enter valid nonnegative ${years ? 'years in role' : 'whole similar-task counts'}.`);
        }
      }
      const seen = new Set();
      for (const r of update.relationships) {
        const key = `${r.workflow_id}:${r.target_employee_id}`;
        if (seen.has(key)) throw Error(`${eid}: duplicate relationship for ${key}. Edit the existing row instead.`);
        seen.add(key);
        if (!r.target_employee_id || !validNumber(r.collaboration_events,0,Infinity,true) ||
            !validNumber(r.handoff_events,1,Infinity,true) ||
            !validNumber(r.mean_handoff_hours,0,model.human_parameters.disconnected_handoff_hours)) {
          throw Error(`${eid}: check the colleague, whole event counts, and handoff delay.`);
        }
      }
    }
    return clone([...edits.values()]);
  }

  function showError(message) {
    el('humanEditStatus').className = 'editor-status error';
    el('humanEditStatus').textContent = message;
  }

  function showResult(result) {
    latestResult = result;
    el('humanEditStatus').className = 'editor-status';
    el('humanEditStatus').textContent = edits.size ? `Results include changes to ${edits.size} employee(s). Starting data is unchanged.` : 'Results use starting employee values. Select an employee to explore changes.';
    renderNetwork();
  }

  function init(data, run) {
    model = data; runSimulation = run;
    el('humanEmployee').innerHTML = options(model.employees.map(e => [e.employee_id, `${e.display_name} · ${e.employee_id} · ${e.role}`]), model.employees[0].employee_id);
    el('humanEmployee').onchange = render;
    el('applyHumanEdits').onclick = runSimulation;
    el('resetHumanEmployee').onclick = () => {
      edits.delete(current.employee_id); latestResult = null; render(); runSimulation();
    };
    el('resetHumanAll').onclick = () => { edits.clear(); latestResult = null; render(); runSimulation(); };
    el('addRelationship').onclick = () => {
      for (const r of draft.experience) {
        const peer = peers(r.workflow_id).find(([id]) => !draft.relationships.some(edge => edge.workflow_id === r.workflow_id && edge.target_employee_id === id));
        if (peer) {
          draft.relationships.push({workflow_id:r.workflow_id,target_employee_id:peer[0],collaboration_events:0,handoff_events:1,mean_handoff_hours:Math.min(1,model.human_parameters.disconnected_handoff_hours)});
          markEdited(); renderRelationships(); return;
        }
      }
      showError('All colleagues in this employee’s assigned workflows already have an outgoing relationship.');
    };
    render();
  }
  return {init, getUpdates, showError, showResult};
})();
