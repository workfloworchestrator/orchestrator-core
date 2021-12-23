# Writing unit tests

Notes and lessons learned about writing unit tests for workflows.

Point the first, there are `test` and `test_esnet` file hierarchies. The latter is a clone of the former with all of the SN specific stuff torn out. Any of our stuff should go in `test_esnet` but in some cases will still reference code in the `test` hierarchy. This is covered later.

## Domain model tests

There is a test for the circuit transition domain models here:

```shell
orchestrator/test_esnet/unit_tests/domain/product_types/test_cts.py
```

These are relatively straightforward. There are basic imports which include the domain models being tested:

```python
from server.db import Product, db
from server.domain.product_blocks.cts import CircuitTransitionBlockInactive
from server.domain.product_types.cts import CircuitTransition, CircuitTransitionInactive
from server.types import SubscriptionLifecycle
```

It pulls in the inactive version of the product block, plus the default and inactive product type models. Then just write functions. They seemed to have defined two kinds of test (you can put them in the same module).

### New

This test just creates a new model in the function. Super easy, instantiate the inactive version of the model and test that the default fields are properly defined.

### Save and load

This is commented and a bit more complex. In the `conftest.py` file at the root of the test directory a `pytest` fixture is defined that creates the model and saves it in the db.

Then the test function loads the version from the db, checks the contents, makes some changes, save it, and load it up again.

Also pretty simple but you mostly need to know where the fixtures get defined.

## Workflow tests

There is a unit test for the ESnet circuit transition workflow here:

```shell
orchestrator/test_esnet/unit_tests/workflows/cts/test_create_cts.py
```

It's mostly complete and is liberally commented.

### Fundamental imports

It uses the `pytest` framework, and some custom orchestrator code. So we need to pull in some imports for the framework and functions to run the workflow in the test. Finally, the function gets a decorator:

```python
import uuid
import pytest

from server.db import Product, Subscription
from test.unit_tests.workflows import (
    assert_complete,
    assert_failed,
    extract_error,
    extract_state,
    run_workflow,
    assert_suspended,
    resume_workflow,
)


@pytest.mark.workflow
def test_create_cts(responses):
    pass
```

### General flow

To start it off, just define the initial input content in a data structure and feed it to a function that starts the workflow:

```python
initial_state = [
    {"product": str(product.product_id)},
    {
        "organisation": ESNET_ORG_UUID,
        "esnet5_circuit_id": "2",
        "esnet6_circuit_id": "2",
        "snow_ticket_assignee": "mgoode",
        "noc_due_date": "2020-07-02 07:00:00",
    },
]

result, process, step_log = run_workflow("create_circuit_transition", initial_state)
assert_suspended(result)
state = extract_state(result)
```

In this example it's a workflow suspends several times so the `assert_suspended` function is called. If the workflow doesn't have anything like that (ie: it's just one step) you can just let it go and call `assert_complete`. In the above example, you can pause, and examine the state object to make sure the contents are what is expected.

To resume a multi-step/suspended workflow, you do this:

```python
confirm_complete_prework = {
    "outbound_shipper": "fedex",
    "return_shipper": "fedex",
    "generate_shipping_details": "ACCEPTED",
    "provider_receiving_ticket": "23432",
    "provider_remote_hands_ticket": "345345",
    "confirm_colo_and_ports": "ACCEPTED",
    "complete_mops_info": "ACCEPTED",
    "create_pmc_notification": "pmc notify",
    "reserve_traffic_generator": "ACCEPTED",
}

result, step_log = resume_workflow(process, step_log, confirm_complete_prework)
```

One doesn't need to update the main state object, just create a fresh data structure of the new data and call `resume_workflow` - the new data will be added to the state object. Lather, rinse and repeat until the workflow is complete.

### HTTP mocking

One non-obvious facet of the test framework is that it forces one to mock any HTTP calls going to an external service. This is defined by a fixture in the `conftest.py` file - this is compatible with the http lib we are using.

Consider a test function prototype:

```python
@pytest.mark.workflow
def test_create_cts(responses):
    product = Product.query.filter(Product.name == "Circuit Transition Service").one()
```

That responses arg being passed in is the aforementioned fixture. This is then passed into your mock classes:

```python
esdb = EsdbMocks(responses)
oauth = OAuthMocks(responses)
snow = SnowMocks(responses)
```

`Product.name` needs to match the first argument of the `@create_workflow` decorator and needs to be defined as a product in the database or that call will fail.

#### Defining a mock

Here is the constructor and a single method from a mock file:

```python
class OAuthMocks:
    def __init__(self, responses):
        self.responses = responses

    def post_token(self):

        response = r"""{
  "access_token":"MTQ0NjJkZmQ5OTM2NDE1ZTZjNGZmZjI3",
  "token_type":"bearer",
  "expires_in":3600,
  "refresh_token":"IwOGYzYTlmM2YxOTQ5MGE3YmNmMDFkNTVk",
  "scope":"create"
}"""
        response = json.loads(response)

        self.responses.add(
            "POST",
            f"/oauth_token.do",
            body=json.dumps(response),
            content_type="application/json",
        )
```

Pretty basic - define what the return payload looks like. One defines an HTTP verb, URI and the like.

Also, if you're mocking a call that contains a query string make sure to include the

```python
match_querystring = (True,)
```

flag to `responses.add()` or you'll go insane trying to figure out why it didn't register properly.

Not going to lie, this part can get kind of tedious depending on the amount of calls you need to mock.

#### Registering with the fixture (the non-obvious bit)

The way this works is that rather than mimicking the name of the method being mocked, it does a look up using a two-tuple of the verb and the uri. And it needs to be registered with the fixture or else the lookup won't work. So back in the test function, one needs to do this before initiating the workflow:

```python
oauth = OAuthMocks(responses)
...
token = oauth.post_token()
```

Even though you haven't run the workflow yet, and you won't use the return value, doing that registers the verb/uri pair with the fixture. Then going forward when the code executes and there is an HTTP call to that verb/uri pair, the contents of that method will be returned (payload, headers, etc).

And if you try to cheat, the fixture will stop you. Any un-mocked HTTP call will raise an exception.

## Running the tests

The tests need to be run inside the container. First, to enable "live" updating, add this to the `volumes` stanza of the docker compose file:

```yaml
      - ../test:/usr/src/app/test
```

Then shell into the container:

```shell
    docker exec -it backend /bin/bash
```

And run the test:

```shell
root@d30f71ee1afe:/usr/src/app# pytest -s test_esnet/unit_tests/workflows/cts/test_create_cts.py
```

The `-s` flag to `pytest` is needed if you want to see your print statements. Otherwise `pytest` will cheerfully eat them.

### Gotchas and etc

#### Executing multiple tasks

The `test_esnet` tree is a clone of the SN `test` tree with all of the SN specific stuff removed. Some tests may still reference code in the `test` tree - utility testing code for example:

```python
from test.unit_tests.workflows import (
    assert_complete,
    assert_failed,
    extract_error,
    extract_state,
    run_workflow,
    assert_suspended,
    resume_workflow,
)
```

That's by design - those things are core orchestrator code so it stays put.

At some point we might want to crib off of SN code or modify it (like some of the mocking code for example) - if so, go ahead and move it into our tree. The goal of this is to have the `test_esnet` tree be pretty lean and just have our stuff in it. That way we can also just run the entire tree w/out worrying about their stuff.

#### Test DB

See `.env.example` on how to set the URI for the database the testing framework uses. The original default was to use your "production" local db which had the super helpful side effect of trashing your orchestrator state.

#### Initial state

The initial state for the form input is defined in a pretty straightforward way - at least for create workflows:

```python
initial_state = [
    {"product": str(product.product_id)},
    {
        "organisation": ESNET_ORG_UUID,
        "esnet5_circuit_id": "2",
        "esnet6_circuit_id": "2",
        "snow_ticket_assignee": "mgoode",
        "noc_due_date": "2020-07-02 07:00:00",
    },
]

result, process, step_log = run_workflow("create_circuit_transition", initial_state)
```

But there seems to be a gotcha when defining initial state for a terminate / etc workflow that modifies existing subscriptions:

```python
# Yes, the initial state is a list of two identical dicts.
# Why? I don't know. But I do know if you don't do this an
# maddening form incomplete validation error will happen. -mmg
initial_state = [
    {"subscription_id": nes_subscription2},
    {
        "subscription_id": nes_subscription2,
    },
]

result, process, step_log = run_workflow("terminate_node_enrollment", initial_state)
```

So if one gets a vague form validation error when doing this, it might be something alone these lines.

#### insync = True

When defining a fixture in `conftest.py` to make an entry in the testing DB for a subscription that a unit test might consume, make sure to mark the subscription object `.insync = True`. Otherwise the unit test will fail thinking that it is attached to an active process.
