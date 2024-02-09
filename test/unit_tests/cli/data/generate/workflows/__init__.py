from orchestrator.workflows import LazyWorkflowInstance

LazyWorkflowInstance("workflows.example2.create_example2", "create_example2")
LazyWorkflowInstance("workflows.example2.modify_example2", "modify_example2")
LazyWorkflowInstance("workflows.example2.terminate_example2", "terminate_example2")
LazyWorkflowInstance("workflows.example2.validate_example2", "validate_example2")
LazyWorkflowInstance("workflows.example1.create_example1", "create_example1")
LazyWorkflowInstance("workflows.example1.modify_example1", "modify_example1")
LazyWorkflowInstance("workflows.example1.terminate_example1", "terminate_example1")
LazyWorkflowInstance("workflows.example1.validate_example1", "validate_example1")
