from orchestrator.workflows import LazyWorkflowInstance

LazyWorkflowInstance("workflows.user_group.create_user_group", "create_user_group")
LazyWorkflowInstance("workflows.user_group.modify_user_group", "modify_user_group")
LazyWorkflowInstance("workflows.user_group.terminate_user_group", "terminate_user_group")
LazyWorkflowInstance("workflows.user.create_user", "create_user")
LazyWorkflowInstance("workflows.user.modify_user", "modify_user")
LazyWorkflowInstance("workflows.user.terminate_user", "terminate_user")
