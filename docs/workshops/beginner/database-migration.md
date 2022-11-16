# Database migration

## Introduction

The orchestrator uses SQLAlchemy, the Python SQL toolkit and Object Relational
Mapper, as interface to the database. For the creation, management, and
invocation of change management scripts Alembic is being used.  Alembic is part
of SQLAlchemy.

Now that the product and product block domain models have been created it is
time to create an Alembic database migration to insert this information into
the database. All the SQL statements needed for this migration can be written
by hand, or created by making use of the helper functions from
`orchestrator/migrations/helpers.py`, or use the orchestrators ability to
detect differences between the database and the registered product domain
models and create all needed SQL statements for you. Below we will make use of
the ability of the orchestrator to create database migrations for us.

## Exercise 1: add products to registry

In order to use the products that were defined earlier, the orchestrator needs
to know about there existence. This is done by adding the products with a
description to the `SUBSCRIPTION_MODEL_REGISTRY`.

The products can be added to the registry in `main.py`, but for this exercise
the registry will be updated by the `products` module, this keeps the
registration code close to the definition of the products and nicely separated
from the rest of the code.

Create the file `products/__init__.py` and add the following code:

```python
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY

from products.product_types.user import User
from products.product_types.user_group import UserGroup

SUBSCRIPTION_MODEL_REGISTRY.update(
    {
        "User Group": UserGroup,
        "User internal": User,
        "User external": User,
    }
)
```

To make Python execute this code, add the following import statement to
`main.py`:

```python
import products
```

## Exercise 2: create database migration

The orchestrator command line interface offers the `db migrate-domain-models`
command to create a database migration based on the differences between the
database and the registered products. In most cases this command will be able
to detect all changes, but in more complex situations it will ask the user for
additional input to create the correct migration. For new products it will also
ask for user friendly descriptions for the products, product blocks, resource
types and fixed inputs, as well as information that is not defined in the
domain models like product and product block types and tags, and values for the
fixed inputs to differentiate the products of the same product type.

Create the migration with the following command, have a look at the overview
below when in doubt of the correct answer to the questions, and make sure that
the product type entered exactly matches the product types defined in the
domain models, including upper/lowercase: 

```shell
PYTHONPATH=. python main.py db migrate-domain-models "Add User and UserGroup products"
```

When finished have a look at the migration created in the folder
`migrations/versions/schema`.

> --- PRODUCT ['User Group'] INPUTS ---
<br>
Product description: **user group administration**
<br>
Product type: **UserGroup**
<br>
Product tag: **GROUP**
<br>
--- PRODUCT ['User internal'] INPUTS ---
<br>
Product description: **user administration - internal**
<br>
Product type: **User**
<br>
Product tag: **USER_INT**
<br>
--- PRODUCT ['User external'] INPUTS ---
<br>
Product description: **user administration - external**
<br>
Product type: **User**
<br>
Product tag: **USER_EXT**
<br>
--- PRODUCT ['User internal'] FIXED INPUT ['affiliation'] ---
<br>
Fixed input value: **internal**
<br>
--- PRODUCT ['User external'] FIXED INPUT ['affiliation'] ---
<br>
Fixed input value: **external**
<br>
--- PRODUCT BLOCK ['UserGroupBlock'] INPUTS ---
<br>
Product block description: **user group block**
<br>
Product block tag: **UGB**
<br>
--- PRODUCT BLOCK ['UserBlock'] INPUTS ---
<br>
Product block description: **user block**
<br>
Product block tag: **UB**
<br>
--- RESOURCE TYPE ['group_name'] ---
<br>
Resource type description: **name of the user group**
<br>
--- RESOURCE TYPE ['group_id'] ---
<br>
Resource type description: **id of the user group**
<br>
--- RESOURCE TYPE ['username'] ---
<br>
Resource type description: **name of the user**
<br>
--- RESOURCE TYPE ['age'] ---
<br>
Resource type description: **age of the user**
<br>
--- RESOURCE TYPE ['user_id'] ---
<br>
Resource type description: **id of the user**

## Exercise 3: perform database migration

To create a representation of the products in the database that matches the 
domain models, the database migration created above is executed. One way to do 
this is to explicitly upgrade the database with `db upgrade <revision>` to 
the revision that was just created. Another way is to upgrade to the latest
heads again, as was done during the initialisation of the database.

```shell
PYTHONPATH=. python main.py db upgrade heads
```

Look at what the migration added to the database by either querying the
database directly:

```shell
psql orchestrator-core
```

or by using the orchestrator API:

```shell
curl http://127.0.0.1:8080/api/products/ | jq
```

or by browsing through the orchestrator meta data through the GUI at:

```shell
http://localhost:3000/metadata/products
```

or all of the above.

