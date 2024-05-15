# Workflow Orchestrator UI

The default workflow orchestrator ui app should offer sufficient functionality to start working and experiencing the workflow orchestrator without any customisation. For this an [example-orchestrator-ui](https://github.com/workfloworchestrator/example-orchestrator-ui) is available to start working with a running workflow orchestrator backend. 

At the same time the UI is developed with the concept in mind that any user of the workflow orchestrator can customize the ui to meet their own requirements. There are two possible ways to accomplish this:

- Overriding components
- Using components from the npm ui library


## Overriding components
The first solution is based on using the orchestrator-ui library in its full extend and just add/tweak components. Examples of this approach would be: 
- render certain resource type differently then the npm normally does
- add menu items to the naviation
- add summary cards to the dashboard page

An example of a custom orchestrator-ui is shown below, which shows custom summary card and additional meu items compared to the standard orchestrator-ui as available from the demo-orchestrator-ui.

## Using components from the npm ui library
The second solution will probaby require more work, but could be interesting to extend an existing application with orchestrator components


Both customization solutions rely on the npm package of the components libray published in [npm](https://www.npmjs.com/package/@orchestrator-ui/orchestrator-ui-components). This package contains the pages and components that are meant to be used in an app that serves the frontend to a workflow orchestrator backend. 

To have a development setup where both the source code of the app and the source code of this package are available have a look at the [Orchestrator UI library repository](https://github.com/workfloworchestrator/orchestrator-ui-library) at the location packages/orchestrator-ui.


## Example screenshots of orchestrator-ui
### Standard orchestrator-ui
![Screenshot](/docs/img/Standard-orchestrator-ui.png)

### Custom orchestrator-ui
- showing additional summary card component (in-maintence corelink)
- additional menu items
![Screenshot](/docs/img/Custom-orchestrator-ui-using-override.png)
