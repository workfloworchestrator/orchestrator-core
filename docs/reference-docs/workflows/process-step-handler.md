# Custom Process Step Handler

After each workflow step is completed, the Orchestrator will store the output of this step in the `Process` table in the
subscription database. By default, this will update the `last_status`, and in case the step was a failure, it will set
the `failed_reason` and the `traceback`.

You might want this function to include extra behaviour, custom error mapping, or special cases like setting the
assignee of the process depending on step outcome. In this case, it is possible to override the default process function
in `orchestrator.core.services.processes`. If you override this like the example below, you can include any kind of
custom behaviour fit for your use-case.

```python title="your_orchestrator/__init__.py"
import orchestrator.core.services.processes

def my_custom_handler(p: ProcessTable, process_state: WFProcess) -> ProcessTable:
    """I want to set my custom assignees based on step outcome!"""

    step_state: State = process_state.unwrap()
    if process_state.isfailed():
        error_name = step_state.get("class")

        p.failed_reason = step_state.get("error", default="Blame the intern.")
        p.assignee = "not-me@worfloworchestrator.org"
        p.traceback = f"An '{error_name}' occurred! Help!"

orchestrator.core.services.processes.PROCESS_STEP_HANDLER = my_custom_handler
```
