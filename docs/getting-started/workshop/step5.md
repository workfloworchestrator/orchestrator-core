# Create a workflow
The last step is to create a workflow. The way a workflow works is intricate and can be read about
[here](../../../architecture/application/workflow). Safe to say is that in principe a workflow will execute
a number of steps functions in order and pass state from one step to another through the database. The best
workflow steps execute atomic functions that may fail and can be safely retried without human intervention.

### Exercise - create a workflow and input form
Please do the following:

- Create a workflow file and register it in the workflow engine
- Declare an input form
- Fill out the subscription model and trasition it to the active state.
- Investigate how the client parses the form input to generate a form.

!!! hint
    - You need to create a `LazyWorkflowInstance`
    - An input form generates a Form class.
    - Generating multiple Forms in sequence creates a wizard like flow.
    - Take have a look at the form schema and how it interacts with [Uniforms](https://uniforms.tools)
