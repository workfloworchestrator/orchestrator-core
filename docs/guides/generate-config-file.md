# Generating a Config File

This guide describes the YAML product configuration file format used by the
`python main.py generate` commands (`generate product-blocks`, `generate products`,
`generate workflows`, `generate migration`, and `generate unit-tests`).

See the [CLI reference](../reference-docs/cli.md#generate) for the full list of
`generate` sub-commands and their options.

An example of a simple product configuration:

```yaml
config:
  summary_forms: true
name: node
type: Node
tag: NODE
description: "Network node"
fixed_inputs:
  - name: node_rack_mountable
    type: bool
    description: "is node rack mountable"
  - name: node_vendor
    type: enum
    description: "vendor of node"
    enum_type: str
    values:
      - "Cisco"
      - "Nokia"
product_blocks:
  - name: node
    type: Node
    tag: NODE
    description: "node product block"
    fields:
      - name: node_name
        description: "Unique name of the node"
        type: str
        required: provisioning
        modifiable:
      - name: node_description
        description: "Description of the node"
        type: str
        modifiable:
      - name: ims_id
        description: "ID of the node in the inventory management system"
        type: int
        required: active
      - name: under_maintenance
        description: "node is under maintenance"
        type: bool
        required: initial
        default: False

workflows:
  - name: terminate
    validations:
      - id: can_only_terminate_when_under_maintenance
        description: "Can only terminate when the node is placed under maintenance"
  - name: validate
    enabled: false
    validations:
      - id: validate_ims_administration
        description: "Validate that the node is correctly administered in IMS"
```

Next we will describe the different sections in more detail:

## Global `config` section

This section sets some global configuration, applicable for most workflows.

```yaml
config:
  summary_forms: true
```

- `summary_forms` indicates if a summary form will be generated in the
  create and modify workflows, default is `false`.

## Product type definition

```yaml
name: node
type: Node
tag: NODE
description: "Network node"
```

Every product type is described using the following fields:
- `name`: the name of type product type, used in descriptions, as variable name, and to generate
          filenames
- `type`: used to indicate the type of the product in Python code, types in
          Python usually starts with an uppercase character
- `tag`: used to register the product tag in the database, can for example be used to filter
         products, will typically be all uppercase
- `description`: descriptive text for the product type

## `fixed_inputs` section

In this section we define a list of fixed inputs for a product.

```yaml
fixed_inputs:
  - name: node_vendor
    type: enum
    description: "vendor of node"
    enum_type: str
    values:
      - "Cisco"
      - "Nokia"
  - name: node_ports
    type: enum
    description: "number of ports in chassis"
    values:
      - 10
      - 20
      - 40
```

A fixed input has a `name`, `type` and `description` field. If the type is a primitive type
(for example: str, bool, int), then this is sufficient. In case of
`node_vendor` an `enum` type is used, and two additional fields to describe the
enumeration `type` and its possible `values`. Both `str` and `int` enums are supported.

When one or more enum types are specified, the necessary migration and product registry code
will be generated for all possible combinations of the enums. In this example six products of type
Node will
be generated: "Cisco 10", "Cisco 20", "Cisco 40", "Nokia 10", "Nokia 20" and "Nokia 40".

## `product_blocks` section

```yaml
product_blocks:
  - name: port
    type: Port
    tag: PORT
    description: "port product block"
    fields:
      -
      -
```

In this section we define the product block(s) that are part of this product.

**A product configuration should contain exactly 1 root product block.** This means there should be 1 product block that is not used by any other product blocks within this product.
If the configuration does contain multiple root blocks, or none at all due to a cyclic dependency, then the generator will raise a helpful error.

The use of `name`, `type`, `tag` and `description` in the product block definition is equivalent
to the product definition above. The `fields` describe the product block resource types.

## Product block fields

```yaml
  - name: port_mode
    description: 'port mode'
    required: provisioning
    modifiable:
    type: enum
    enum_type: str
    values:
      - "untagged"
      - "tagged"
      - "link_member"
    default: "tagged"
    validations:
      - id: must_be_unused_to_change_mode
        description: "Mode can only be changed when there are no services attached to it"
```

Resource types are described by the following:

- `name`: name of the resource type, usually in snake case
- `decription`: resource type description
- `required`: if the resource type is required starting from lifecycle state `inital`, `provisioning`
              or `active`, when omitted the resource type will always be optional
- `modifiable`: indicate if the resource type can be altered by a modify workflow, when omitted
                no code will be generated to modify the resource type, currently only supported for simple types
- `default`: specify the default for this resource type, this is mandatory when `required` is set to
             `intitial`, will be `None` if not specified
- `validations`: specify the validation `id` and `description`, generates a skeleton
                 validation function used in a new annotated type
- `type`: see explanation below

## Resource type types

The following types are supported when specifying resource types:

- primitive types like `int`, `str`, and `bool`
  ```yaml
  - name: circuit_id
    type: int
  ```
- types with a period in there name will generate code to import that type, e.q. `ipaddress.IPv4Address`
  ```yaml
  - name: ipv4_loopback
    type: ipaddress.IPv4Address
  ```
- existing product block types like `UserGroup`, possible types will be read from `products/product_blocks`
  ```yaml
  - name: group
    type: UserGroup
  ```
- the type `list`, used together with `min_items` and `max_items` to specify the constraints, and
  `list_type` to specify the type of the list items
  ```yaml
  - name: link_members
    type: list
    list_type: Link
    min_items: 2
    max_items: 2
  ```
- validation code for constrained a `int` is generated when `min_value` and `max_value` are specified
  ```yaml
    - name: ims_id
      type: int
      min_value: 1
      max_value: 32_767
  ```

## Workflows

```yaml
  - name: create
    validations:
      - id: endpoints_cannot_be_on_same_node
        description: "Service endpoints must land on different nodes"
  - name: validate
    enabled: false
    validations:
      - id: validate_ims_administration
        description: "Validate that the node is correctly administered in IMS"
```

The following optional workflow configuration is supported:

- `name`: can be either `create`, `modify`, `terminate` or `validate`
- `enabled`: to enable or disable the generation of code for that type of workflow, is `true` when omitted
- `validations`: list of validations used to generate skeleton code as `model_validator` in input forms,
  and validation steps in the validate workflow
