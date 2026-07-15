# TODO - Scheduler/Reminder Removal

## Steps
- [x] Remove FastAPI lifespan scheduler startup from `main.py`.

- [x] Remove scheduler/reminder configuration fields and derived properties from `config.py`.


- [x] Delete scheduler/reminder modules: `scheduler.py`, `services/scheduler_service.py`, `services/scheduler.py`.

- [ ] Delete any remaining reminder-related code/constants if present.
- [ ] Ensure no lingering imports/references to removed scheduler modules.
- [ ] Run `python -m py_compile` across the project.

- [ ] Summarize modified files and exact changes.

