from typing import List, Optional
from uuid import uuid4

import pytest

from orchestrator.db import ProductTable
from orchestrator.types import State, SubscriptionLifecycle
from orchestrator.utils.state import extract, inject_args

# # from orchestrator.products.product_types.sn8_lp import Sn8LightPathInactive
#
# STATE = {"one": 1, "two": 2, "three": 3, "four": 4}
#
#
# def test_extract():
#     one, two, three, four = extract(("one", "two", "three", "four"), STATE)
#     assert one == 1
#     assert two == 2
#     assert three == 3
#     assert four == 4
#
#     four, three, two, one = extract(("four", "three", "two", "one"), STATE)
#     assert one == 1
#     assert two == 2
#     assert three == 3
#     assert four == 4
#
#     nothing = extract((), STATE)
#     assert len(nothing) == 0
#
#
# def test_extract_key_error():
#     key = "I don't exist"
#     with pytest.raises(KeyError) as excinfo:
#         extract((key,), STATE)
#         assert key in excinfo.value.args
#
#
# def test_state() -> None:
#     @inject_args
#     def step_func_ok(one):
#         assert one == STATE["one"]
#         return {"prefix_id": 42}
#
#     new_state = step_func_ok(STATE)
#     assert "prefix_id" in new_state
#     assert new_state["prefix_id"] == 42
#
#     @inject_args
#     def step_func_fail(i_am_not_in_the_state):
#         return {}
#
#     with pytest.raises(KeyError):
#         step_func_fail(STATE)
#
#     @inject_args
#     def step_func_opt_arg(opt: Optional[str] = None) -> None:
#         assert opt is None
#
#     step_func_opt_arg(STATE)
#
#     @inject_args
#     def step_func_default(default="bla"):
#         assert default == "bla"
#
#     step_func_default(STATE)
#
#
# def test_inject_args() -> None:
#     product_id = ProductTable.query.filter(ProductTable.name == "SN8 LightPath").value(ProductTable.product_id)
#     state = {"product": product_id, "organisation": uuid4()}
#     light_path = Sn8LightPathInactive.from_product_id(
#         product_id=state["product"], customer_id=state["organisation"], status=SubscriptionLifecycle.INITIAL
#     )
#     light_path.save()
#
#     @inject_args
#     def step_existing(light_path: Sn8LightPathInactive) -> State:
#         assert light_path.subscription_id
#         assert light_path.vc.nso_service_id is None
#         light_path.vc.nso_service_id = uuid4()
#         return {"light_path": light_path}
#
#     # Put `light_path` as an UUID in. Entire `light_path` object would have worked as well, but this way we will be
#     # certain that if we end up with an entire `light_path` object in the step function, it will have been retrieved
#     # from the database.
#     state["light_path"] = light_path.subscription_id
#
#     state_amended = step_existing(state)
#     assert "light_path" in state_amended
#
#     # Do we now have an entire object instead of merely a UUID
#     assert isinstance(state_amended["light_path"], Sn8LightPathInactive)
#
#     # And does it have the modifcations from the step functions
#     assert state_amended["light_path"].vc.nso_service_id is not None
#
#     # Test `nso_service_id` has been persisted to the database with the modifications from the step function.`
#     fresh_light_path = Sn8LightPathInactive.from_subscription(state_amended["light_path"].subscription_id)
#     assert fresh_light_path.vc.nso_service_id is not None
#
#
# def test_inject_args_list() -> None:
#     product_id = ProductTable.query.filter(ProductTable.name == "SN8 LightPath").value(ProductTable.product_id)
#     state = {"product": product_id, "organisation": uuid4()}
#     light_path = Sn8LightPathInactive.from_product_id(
#         product_id=state["product"], customer_id=state["organisation"], status=SubscriptionLifecycle.INITIAL
#     )
#     light_path.save()
#
#     @inject_args
#     def step_existing(light_path: List[Sn8LightPathInactive]) -> State:
#         assert len(light_path) == 1
#         assert light_path[0].subscription_id
#         assert light_path[0].vc.nso_service_id is None
#         light_path[0].vc.nso_service_id = uuid4()
#         return {"light_path": light_path}
#
#     # Put `light_path` as an UUID in. Entire `light_path` object would have worked as well, but this way we will be
#     # certain that if we end up with an entire `light_path` object in the step function, it will have been retrieved
#     # from the database.
#     state["light_path"] = [light_path.subscription_id]
#
#     state_amended = step_existing(state)
#     assert "light_path" in state_amended
#     assert len(state_amended["light_path"]) == 1
#
#     # Do we now have an entire object instead of merely a UUID
#     assert isinstance(state_amended["light_path"][0], Sn8LightPathInactive)
#
#     # And does it have the modifcations from the step functions
#     assert state_amended["light_path"][0].vc.nso_service_id is not None
#
#     # Test `nso_service_id` has been persisted to the database with the modifications from the step function.`
#     fresh_light_path = Sn8LightPathInactive.from_subscription(state_amended["light_path"][0].subscription_id)
#     assert fresh_light_path.vc.nso_service_id is not None
#
#
# def test_inject_args_optional() -> None:
#     product_id = ProductTable.query.filter(ProductTable.name == "SN8 LightPath").value(ProductTable.product_id)
#     state = {"product": product_id, "organisation": uuid4()}
#     light_path = Sn8LightPathInactive.from_product_id(
#         product_id=state["product"], customer_id=state["organisation"], status=SubscriptionLifecycle.INITIAL
#     )
#     light_path.save()
#
#     @inject_args
#     def step_existing(light_path: Optional[Sn8LightPathInactive]) -> State:
#         assert light_path is not None, "LP IS NONE"
#         assert light_path.subscription_id
#         assert light_path.vc.nso_service_id is None
#         light_path.vc.nso_service_id = uuid4()
#         return {"light_path": light_path}
#
#     with pytest.raises(AssertionError) as exc_info:
#         step_existing(state)
#
#     assert "LP IS NONE" in str(exc_info.value)
#
#     # Put `light_path` as an UUID in. Entire `light_path` object would have worked as well, but this way we will be
#     # certain that if we end up with an entire `light_path` object in the step function, it will have been retrieved
#     # from the database.
#     state["light_path"] = light_path.subscription_id
#
#     state_amended = step_existing(state)
#     assert "light_path" in state_amended
#
#     # Do we now have an entire object instead of merely a UUID
#     assert isinstance(state_amended["light_path"], Sn8LightPathInactive)
#
#     # And does it have the modifcations from the step functions
#     assert state_amended["light_path"].vc.nso_service_id is not None
#
#     # Test `nso_service_id` has been persisted to the database with the modifications from the step function.`
#     fresh_light_path = Sn8LightPathInactive.from_subscription(state_amended["light_path"].subscription_id)
#     assert fresh_light_path.vc.nso_service_id is not None
