# Explore the GUI and API

## Is the example orchestrator working?

If the orchestrator setup including the products that were created as part of
this workshop do not work for some reason or the other, it is possible to
quickly setup a working example orchestrator by  following the steps below (on
Debian add `sudo` where needed):

```shell
git clone https://github.com/workfloworchestrator/example-orchestrator-beginner.git
cd example-orchestrator-beginner
# only drop database when you are really sure!
echo 'drop database "orchestrator-core";' | psql postgres
createdb orchestrator-core -O nwa
source virtualenvwrapper.sh
workon example-orchestrator || mkvirtualenv --python python3.11 example-orchestrator
pip install orchestrator-core
PYTHONPATH=. python main.py db init
cp -av examples/*add_user_and_usergroup* migrations/versions/schema
PYTHONPATH=. python main.py db upgrade heads
ENABLE_WEBSOCKETS=True uvicorn --host 127.0.0.1 --port 8080 main:app
```

## Explore

It is now time to explore the GUI and API. With the set of products created
during this workshop users and groups can be created, modified and deleted. The
easiest way is by using the GUI at:

```shell
http://localhost:3000/
```

But also check out the API at:

```shell
http://127.0.0.1:8080/api/docs
```

And look at the products:

```shell
curl http://127.0.0.1:8080/api/products/ | jq
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
