## Overview

Products can be described in a configuration file which makes it easy to generate
a skeleton of a working product.

An example of a simple product configuration:

```yaml
config:
  create_summary_forms: false
  send_email: false
name: User
type: User
fixed_inputs:
  - name: affiliation
    type: enum
    enum_type: str
    values:
      - "internal"
      - "external"
product_blocks:
  - name: user
    type: User
    block_name: "UserBlock"
    fields:
      - name: group
        type: UserGroup
      - name: username
        type: str
        required: provisioning
      - name: age
        type: int
      - name: user_id
        type: int
        required: active
```

Next we will describe the different sections in more detail:

### The `config` section

This section sets some global configuration, applicable for most workflows.

```yaml
config:
  create_summary_forms: false
  send_email: false
```

- `create_summary_forms` indicates if a summary form will be generated in the create and
modify workflows.

- `send_email` indicates if code will be generated for steps that send emails.


### The `fixed_inputs` section

In this section we define a list of fixed inputs for a product.

```yaml
fixed_inputs:
  - name: affiliation
    type: enum
    enum_type: str
    values:
      - "internal"
      - "external"
```

A fixed input has a `name` and a `type` field. If the type is a primitive type 
(for example: str, bool, int, UUID), then this is sufficient. In this example we use
an enum type, so we add additional fields to describe the enumeration type and its possible 
values.

### The `product_blccks` section

In this section we define the product blocks that are part of this product. They can be
either new or refer to previously defined product blocks.

```yaml
product_blocks:
  - name: user
    type: User
    block_name: "UserBlock"
    fields:
      - name: group
        type: UserGroup
      - name: username
        type: str
        required: provisioning
      - name: age
        type: int
      - name: user_id
        type: int
        required: active
```

In this example we define a product block with name 'user' and type `User`.
'fields' is a list of field with a type and name. The 'required' field defines in which
lifecycle state the field is required. In previous life cycle states the field will
be optional.