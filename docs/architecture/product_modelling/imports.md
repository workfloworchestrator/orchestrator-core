# Importing Existing Subscriptions
When adding new products to Workflow Orchestrator, these products can rely on existing estate in the network that first
needs to be added to the service database. This page describes a procedure that can be used to have a separate creation
and import workflow for one product.

As a requirement, each product type must have exactly one workflow where `target=Target.CREATE`. It is therefore not
possible to have for example two workflows `create_node` and `import_node`. It is possible however, to have a separate
product type, that relies on the same product block.

## Using Separate Product Types
In the code example below, an example is given for a `Node` product type that needs to be imported into Orchestrator.

```python
class Node(NodeProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    """A node that is currently active."""
    node: NodeBlock

class ImportedNode(ImportedNodeInactive, lifecycle=[SubscriptionLifecycle.ACTIVE]):
    """An imported node that is currently active."""
    node: NodeBlock
```

In this example, both types contain the same product block, which is required for this approach to import existing
products. The creation workflow for a `Node` will remain `create_node`, which is most likely a workflow that takes user
input from a form page, and then interacts with external systems to provision a new node.

For the `ImportedNode`, the creation workflow is `create_imported_node`. This workflow can be designed to still take
user input from a form page, but could also be provided programmatically by either a CLI command or API endpoint that is
called. Data sources can include external API resources, CSV- or YAML files, etc. If desired, interaction with all
external provisioning systems can be skipped, resulting in a creation workflow that could be as simple as follows.

```python
from orchestrator.workflow import StepList, begin
from orchestrator.workflows.steps import store_process_subscription
from orchestrator.workflows.utils import create_workflow

@create_workflow("Create imported Node")
def create_imported_node() -> StepList:
    """Workflow to import a Node without provisioning it."""
    return (
        begin
        >> create_subscription
        >> store_process_subscription(Target.CREATE)
        >> initialize_subscription
    )
```

## Importing Products
With the `ImportedNode` part of the service database, we need a modification workflow to take the imported product to a
`Node` subscription. This is done using a modification workflow `import_node` that is added to the `ImportedNode`
product.

This workflow is another place where external provisioning could take place, but it could also be a
straightforward workflow alike the example given earlier. For the modification of importing the `Node` product, the
following serves as an example.

```python
from orchestrator.workflow import StepList, begin, step
from orchestrator.workflows.utils import modify_workflow

@step("Create new Node subscription")
def import_node_subscription(subscription_id: UUIDstr) -> State:
    """Take an ImportedNode subscription, and turn it into a Node subscription."""
    imported_node = ImportedNode.from_subscription(subscription_id)
    new_product_id = get_product_id_by_name(ProductName.NODE)
    new_subscription = Node.from_other_product(imported_node, new_product_id)

    return {"subscription": new_subscription}


@modify_workflow("Import Node", target=Target.MODIFY)
def import_node() -> StepList:
    """Modify into a Node subscription to complete the import."""
    return begin >> import_node_subscription
```

In this workflow, the existing `ImportedNode` subscription is modified into a `Node` subscription, and is stored in the
service database. Now, the import has been completed, and the imported variety of the product has been replaced with a
"regular" `Node` subscription.

In short, the procedure is visualized in the following flowchart.

``` mermaid
graph LR
  A[CSV file with existing nodes] -->|create_imported_node| B[ImportedNode];
  B -->|import_node| C[Node];
```

With `create_imported_node` as the creation workflow, and `import_node` as a modification workflow of the `ImportedNode`
product.
