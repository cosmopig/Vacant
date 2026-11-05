from vacant_network.reqloop.requirements import RequirementSet
from vacant_network.reqloop.checks import run_requirement_checks
from pathlib import Path

dir = Path('ops/reqloop/g1/tasks/inventory_alerts')
reqs = RequirementSet.load(dir / 'requirements.json')
res = run_requirement_checks(dir, reqs, dir / 'good')
for r in res:
    print(f'ID: {r.claim_id}, Status: {r.status}, Detail: {r.detail}')
