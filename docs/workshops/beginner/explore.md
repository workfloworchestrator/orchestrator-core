# Explore the GUI and API

## Start from scratch (if necessary) 

If the orchestrator setup including the products that were created as 
part of this 
workshop do not work for 
some reason or the other, it is possible to quickly get up and running by 
following these steps in an empty folder (on Debian add `sudo` where needed):

```shell
# only drop database when you are really sure!
echo 'drop database "orchestrator-core";' | psql postgres
createdb orchestrator-core -O nwa
# the next command assumes you have checked out the orchestrator-core
cp -av ../orchestrator-core/docs/workshops/beginner/sources/. .
git init
git add .
git commit -m 'initial commit'
PYTHONPATH=. python main.py db init
cp -ipv example_migrations/* migrations/versions/schema
PYTHONPATH=. python main.py db upgrade heads
ENABLE_WEBSOCKETS=True uvicorn --host 127.0.0.1 --port 8080 main:app
```

## Explore

It is now time to explore the GUI and API. With the set of products created 
during this workshop 
users and groups can be created, modified and deleted. The easiest way is by 
using the GUI at:

```shell
http://localhost:3000/
```

Also check out the API at:

```shell
http://127.0.0.1:8080/api/docs
```

And look at the products:

```shell
curll http://127.0.0.1:8080/api/products/ | jq
```

Or get a list of subscriptions:

```shell
curl http://127.0.0.1:8080/api/subscriptions/all | jq
```

Or inspect the instantiated domain model for a subscription ID:

```shell
curl http://127.0.0.1:8080/api/subscriptions/domain-model/<subscription_id> | jq
```

And for the adventurers, create a subscription from the command line:

```shell
curl -X POST \
     -H "Content-Type: application/json" \
     http://127.0.0.1:8080/api/processes/create_user_group \
    --data '[
  {
    "product": "a03eb19a-8a83-4964-85ea-98371f1d87f8"
  },
  {
    "group_name": "Test Group"
  }
]'
```
