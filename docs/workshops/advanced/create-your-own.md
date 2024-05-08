# Create your own workflow and product

To cap off this workshop we will create a new product and workflows by using the built in tools that the Workflow
Orchestrator provides the user. In this scenario you will create a product that is very similar to the provided
L2VPN product, but constrained to two interfaces. In other words a L2 Point-to-Point circuit.

## L2 Point-to-Point model
{{ external_markdown('https://raw.githubusercontent.com/workfloworchestrator/orchestrator-core/main/docs/architecture/product_modelling/l2_point_to_point.md',
'') }}

## Product and Workflow Generator
To create a new product configuration and wire up the python, database and workflows correctly you need to create a
lot of boilerplate configuration and code. To speed up this process and make the experience as user friendly as
possible, initial configuration of what a product looks like can be created with a yaml file.
