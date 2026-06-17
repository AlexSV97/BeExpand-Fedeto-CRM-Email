# Proposal: OTRS Healthcheck & Connectivity

## Intent
Add real healthcheck capabilities so operators can verify OTRS/Znuny connectivity, database status, and AI model availability through a single endpoint — no more guessing why the SOC is in "demo" mode.

## Scope

### In Scope
1. Add health_check() method to OtrsZnunyClient — probes OTRS API with a lightweight call
2. Expand /api/v1/health to check DB (real connection), OTRS (real probe), AI model (Ollama/OpenRouter ping)
3. Expose OTRS settings (configured status, base URL) in /soc/config 
4. Add OTRS connectivity status to Command Center surface (badge or indicator)
5. Add otrs_configured + otrs_reachable fields to health response

### Out of Scope
- Full observability dashboard (separate epic)
- OTRS metrics collection (latency, error rates)
- Auto-recovery from OTRS failure

## Capabilities

### Modified Capabilities
- health-api: Add real service-level checks (DB, OTRS, AI)
- soc-router: Add OTRS settings to config endpoint
- soc-surfaces: Add OTRS connectivity indicator to Command Center

## Approach
1. Add health_check() -> bool to OtrsZnunyClient that hits a lightweight endpoint (list queues or tickets with limit=1)
2. Add check_database() -> bool that does a real SQLAlchemy SELECT 1
3. Add check_ai() -> bool that pings Ollama or OpenRouter status
4. Update /api/v1/health to return {status, services: {database, otrs, ai}}
5. Add otrs_configured and otrs_base_url to /soc/config
6. Add OTRS status badge to Command Center (below operating mode)

## Risks
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Healthcheck timeout blocks startup | Low | Timeout per check (5s), parallel execution |
| OTRS credentials exposed in config | Low | Mask base_url in response |

## Success Criteria
- [ ] /api/v1/health returns database, otrs, i service status
- [ ] OTRS health reflects real connectivity (not just env config)
- [ ] Command Center shows OTRS connectivity badge
