# Copyright 2019-2020 SURF, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import copy
import os
from collections.abc import Iterable
from http import HTTPStatus
from time import sleep
from typing import Any, TypedDict, Union
from uuid import UUID

import jsonref
import requests
import structlog
from more_itertools import first, first_true

from nwastdlib.url import URL
from pydantic_forms.types import InputForm as LegacyInputForm
from pydantic_forms.types import State


class JSONSubSchema(TypedDict, total=False):
    title: str
    type: str
    format: str
    pattern: str
    const: Any
    default: Any
    uniforms: dict
    enum: list
    allOf: list
    anyOf: list


class JSONSchema(JSONSubSchema, total=False):
    properties: JSONSubSchema
    items: JSONSubSchema


InputForm = Union[LegacyInputForm, JSONSchema]

try:
    # dotenv is not available during acceptance tests
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

logger = structlog.get_logger(__name__)


UUIDstr = str
ALLOWED_VLAN_RANGE = 4095


BASE_API_URL = URL(os.getenv("BASE_API_URL", "http://localhost:8080/api"))
TOKEN = os.getenv("TOKEN")
CWI = "2f47f65a-0911-e511-80d0-005056956c1a"


def resolve_all_of(input_field: JSONSchema) -> None:
    """Resolve allof in input field.

    Example:
        >>> field = {"allOf": [{"type": "string"}]}
        >>> resolve_all_of(field)
        >>> field
        {'allOf': [{'type': 'string'}], 'type': 'string'}
    """
    for object in input_field.get("allOf", []):
        input_field.update(object)


def get_input_field_types(input_field: JSONSchema) -> Iterable[str]:
    """Yield all possible types for the given input field.

    Example:
        >>> list(get_input_field_types({"type": "foo"}))
        ['foo']
        >>> list(get_input_field_types({'anyOf': [], "type": "foo"}))
        ['foo']
        >>> list(get_input_field_types({'anyOf': [{"type": "foo"}, {}, {"type": "bar"}]}))
        ['foo', 'bar']
        >>> list(get_input_field_types({'anyOf': [{"type": "foo"}], "type": "bar"}))
        ['foo', 'bar']
    """

    def yield_type(v: dict | JSONSchema) -> Iterable[str]:
        if "type" in v:
            yield v["type"]

    for item in input_field.get("anyOf", []):
        yield from yield_type(item)

    yield from yield_type(input_field)


def first_not_none_key(d: dict[str, Any], keys: list[str]) -> Any:
    """Get the dict value for the first existing key that is not None.

    Examples:
        >>> first_not_none_key({}, [])
        >>> first_not_none_key({}, ["foo"])
        >>> first_not_none_key({"foo": "bar"}, [])
        >>> first_not_none_key({"foo": "bar"}, ["bar"])
        >>> first_not_none_key({"foo": "bar"}, ["foo"])
        'bar'
        >>> first_not_none_key({"foo": None}, ["foo"])
        >>> first_not_none_key({"foo": None, "oof": "rab"}, ["foo", "oof"])
        'rab'
    """
    return first(filter(None, (d.get(k) for k in keys)), None)


class Populator:
    """Base class for populating stuff, it will contain functionality to provide default input for all types."""

    def __init__(self, product_name: str) -> None:
        self.started = False
        self.done = False
        self.waiting_for_input = False
        self.last_state: dict = {}
        self.process_id = None
        self._product_name = product_name

        customer_id = os.getenv("POPULATOR_CUSTOMER_ID") or CWI
        contact_name = os.getenv("POPULATOR_CONTACT_NAME") or os.getenv("USER") or "unknown"
        contact_email = os.getenv("POPULATOR_CONTACT_EMAIL") or "a@b.nl"
        contact_phone = os.getenv("POPULATOR_CONTACT_PHONE") or ""

        # When a input_type is not found the populator will try to call a function self."resolve_"input_type()
        self.default_input_values = {
            "customer_id": customer_id,
            "guid": "6769d05f-3b11-e511-80d0-005056956c1a",
            "contact_persons": [{"email": contact_email, "name": contact_name, "phone": contact_phone}],
            "accept": "ACCEPTED",
            "ticket_id": "",
            "label": "",
        }
        self.custom_input_values: dict = {}
        self.add_default_values()
        self.session = requests.Session()
        if TOKEN:
            self.update_headers({"Authorization": "bearer " + TOKEN})

        self._product = self._get_product_by_name(self._product_name)
        self.create_workflow = first_true(
            self._product.get("workflows", []), {"name": "no_create_wf"}, lambda wf: wf["target"] == "CREATE"
        )["name"]
        if not hasattr(self, "log"):
            self.log = logger.bind()  # Silence type errors
            raise AssertionError("self.log must be set first")
        self.log = self.log.bind(product_name=self._product_name)
        self.log.info("Populator info", BASE_API_URL=BASE_API_URL)

        try:
            self.terminate_workflow = first_true(
                self._product.get("workflows", []), {"name": "no_terminate_wf"}, lambda wf: wf["target"] == "TERMINATE"
            )["name"]
        except TypeError:
            #  Terminate not yet implemented: Fall back to unbound logger to avoid logging problems
            logger.warning("Terminate workflow not implemented")
            self.terminate_workflow = None

        self.modify_workflows = list(  # noqa: C417
            map(lambda wf: wf["name"], filter(lambda wf: wf["target"] == "MODIFY", self._product.get("workflows", [])))
        )

    def update_headers(self, headers: dict) -> None:
        self.session.headers.update(headers)

    def add_default_values(self) -> None:
        """Add extra default value from classes that inherit me.

        This method can be overridden to add custom default
        values. Please ensure that you call super().add_default_values() in that case.
        """

    def _get_product_by_name(self, product_name: str) -> dict:
        """Fetch all active products.

        Returns: product dict

        """
        response = self.session.get(BASE_API_URL / "products/")
        if response.status_code == HTTPStatus.OK:
            for product in response.json():
                if product["name"] == product_name:
                    self.log.info("Resolved product.", product_id=product["product_id"])
                    return product
        self.log.error("Error product not found.", product=product_name, status_code=response.status_code)
        return {}

    def get_form_data(self, form: JSONSchema) -> dict:  # noqa: C901
        """Compiles a dict that can be used as the payload in api request that need human input.

        Note: if you want to populate a boolean field: you have to provide 'False' instead of 'None', as the
        latter is used to determine if one of the ways to populate the input_filed value was already successful.

        Args:
            form: a json schema form definition.

        Returns: a dict that can be used as payload.

        """

        self.log.info("Get form data for input fields.", form=form)
        data = {}

        # Resolve refs
        form = jsonref.JsonRef.replace_refs(form)

        field_name: str
        input_field: JSONSchema
        for field_name, input_field in form["properties"].items():  # type: ignore
            log = self.log.bind(field_name=field_name, input_field=input_field)

            if all_of := input_field.get("allOf"):
                resolve_all_of(input_field)
                # Warning for now because I'm wondering why/where we need this
                log.warning("Combined allOf for input field", all_of=all_of)

            input_field_types = list(get_input_field_types(input_field))

            # Read only always has a value that should be returned as is
            if "const" in input_field:
                value = input_field.get("const")
            else:
                value = None

            if value is None:
                value = self.custom_input_values.get(field_name)

            if value is None:
                value = self.custom_input_values.get(input_field.get("format"))

            if value is None:
                value = first_not_none_key(self.custom_input_values, input_field_types)

            # Before resolving we check if we cannot use the default/current
            if value is None:
                value = input_field.get("default")

            if value is None and field_name:
                value = self.default_input_values.get(field_name)

            if value is None:
                value = self.default_input_values.get(input_field.get("format", ""))

            if value is None:
                value = first_not_none_key(self.default_input_values, input_field_types)

            if value is None:
                # try to call a function based on the field_name
                log.info("Trying to resolve input field with custom function based on name.")
                try:
                    func_name = "resolve_" + field_name.replace(".", "_")
                    log = log.bind(func_name=func_name)
                    log.info("Calling custom function.")
                    value = getattr(self, func_name)(input_field)
                except AttributeError:
                    log.warning("Unable to resolve custom function based on name.")
                    value = None

            if value is None:
                # try to call a function based on the input_field["format"]
                log.info("Trying to resolve input field with custom function based on format.")
                try:
                    func_name = f"resolve_{input_field.get('format')}"
                    log = log.bind(func_name=func_name)
                    log.info("Calling custom function.")
                    value = getattr(self, func_name)(input_field)
                except AttributeError:
                    log.warning("Unable to resolve custom function based on format.")
                    value = None

            if value is None:
                # try to call a function based on the input_field["type"]
                log.info("Trying to resolve input field with custom function based on type.")
                for input_field_type in input_field_types:
                    try:
                        func_name = f"resolve_{input_field_type}"
                        log = log.bind(func_name=func_name)
                        log.info("Calling custom function.")
                        value = getattr(self, func_name)(input_field)
                    except AttributeError:
                        log.warning("Unable to resolve custom function based on type.", type_=input_field_type)
                        value = None

            # If enum just pick the first or leave empty if there are no options to select
            if value is None and "enum" in input_field and input_field["enum"]:
                value = input_field["enum"][0]

            if value is None and input_field.get("format") == "divider":
                # Ignore divider elements
                value = ""

            if value is None and input_field.get("format") == "summary":
                # Ignore migration elements
                continue

            log.debug("Resolved input_field.", value=value)
            data[field_name] = value
        return data

    def _start_workflow(self, workflow_name: str, **kwargs: Any) -> UUIDstr:
        """Start a workflow.

        Args:
            workflow_name: workflow name
            kwargs: The kwargs

        Returns: the process_id of the workflow process

        """
        self.log = self.log.bind(process_id=None, workflow=workflow_name)
        self.log.info("Starting workflow")

        self.custom_input_values.update(kwargs)

        response = self.provide_user_input("POST", BASE_API_URL / "processes" / workflow_name)

        response_json = response.json()
        if "id" not in response_json:
            raise Exception(f"Starting workflow {workflow_name} failed: {response_json}")

        self.process_id = process_id = response_json["id"]
        self.log = self.log.bind(process_id=self.process_id)
        self.started = True
        return process_id

    def start_create_workflow(self, **kwargs: Any) -> UUIDstr:
        """Start a create workflow.

        Args:
            kwargs: values to be used as form input

        Returns: the process_id of the workflow process

        """
        self.log = self.log.bind(subscription_id=None)
        self.log.info("Started create workflow")
        product_id = self._product.get("product_id")
        return self._start_workflow(self.create_workflow, product=product_id, **kwargs)

    def start_modify_workflow(self, workflow_name: str, subscription_id: UUIDstr | UUID, **kwargs: Any) -> UUIDstr:
        """Start a modify workflow for the provided name and subscription_id.

        Args:
            workflow_name: workflow name
            subscription_id: uuid of the subscription you want to modify
            kwargs: values to be used as form input

        Returns: the process_id of the workflow process

        """
        subscription_id = str(subscription_id)
        self.log = self.log.bind(subscription_id=subscription_id)
        self.log.info("Started modify workflow")
        return self._start_workflow(workflow_name, subscription_id=subscription_id, **kwargs)

    def start_verify_workflow(self, workflow_name: str, subscription_id: UUIDstr | UUID) -> UUIDstr:
        subscription_id = str(subscription_id)
        self.log = self.log.bind(subscription_id=subscription_id)
        self.log.info("Started verify workflow")
        return self._start_workflow(workflow_name, subscription_id=subscription_id)

    def start_terminate_workflow(self, subscription_id: UUIDstr | UUID, **kwargs: Any) -> UUIDstr:
        """Start a terminate workflow for the provided subscription_id.

        Args:
            subscription_id: uuid of the subscription you want to terminate
            kwargs: values to be used as form input

        Returns: the process_id of the workflow process

        """
        subscription_id = str(subscription_id)
        self.log = self.log.bind(process_id=None, subscription_id=subscription_id)
        self.log.info("Starting terminate workflow")
        return self._start_workflow(self.terminate_workflow, subscription_id=subscription_id, **kwargs)

    def human_input_needed(self) -> bool:
        """Check whether the workflow process needs human input.

        Returns: True or False

        """
        response = self.session.get(BASE_API_URL / "processes" / self.process_id)
        if response.status_code == HTTPStatus.OK:
            self.last_state = response.json()
        else:
            self.log.error("Cowardly quitting due to response code.", status_code=response.status_code)
            raise Exception("Request failed")
        status = self.last_state["status"] if "status" in self.last_state else self.last_state["last_status"]
        if status == "completed":
            self.log.info("Process is complete.")
            self.done = True
            return False

        if status == "suspended":
            return True

        if status in ("created", "running", "resumed"):
            return False

        if status in ("failed", "waiting"):
            if self.retries < 1:
                self.retries += 1
                return True

            self.log.error("Cowardly quitting due to failed step.", reason=self.last_state["failed_reason"])
            raise Exception(f"Step failed: {self.last_state['failed_reason']}")
        self.log.error("Cowardly quitting due to unknown status", status=self.last_state["status"])
        raise Exception(f"Unknown status: {status}")

    def get_current_form(self) -> JSONSchema | None:
        self.log.info("Current form.", form=self.last_state.get("form"))
        return copy.deepcopy(self.last_state.get("form"))

    def provide_user_input(self, method: str, url: URL, form: JSONSchema | None = None) -> requests.Response:
        """Provide input for steps that normally require a user."""
        self.log.info("Providing user input.")

        user_inputs: list[State] = [self.get_form_data(form)] if form else []
        # Keep submitting the form until it has been successfully submitted
        while True:
            self.log.info("Submitting user input", data=user_inputs)
            response = self.session.request(method, url, json=user_inputs)
            self.log.debug("Response", response=response.content)

            # Return the response if the form has been successfully submitted
            if response.status_code != HTTPStatus.NOT_EXTENDED:
                return response

            response_json = response.json()
            meta = response_json.get("meta", {}) or {}
            no_next = meta.get("hasNext") is False
            is_summary_form = response_json.get("form", {}).get("title", "").endswith("Summary")

            # If there are no next pages and a summary form is expected then append an empty form/dict
            if no_next and is_summary_form:
                self.log.info("Append empty form", response=response_json)
                user_inputs.append({})
            # Otherwise resolve the values for the input fields on the form
            else:
                input_fields = response_json["form"]
                user_inputs.append(self.get_form_data(input_fields))

    def reset(self) -> None:
        """Reset internal state."""
        self.log = self.log.bind(subscription_id=None, process_id=None).unbind("subscription_id", "process_id")
        self.started = False
        self.done = False
        self.waiting_for_input = False
        self.last_state = {}
        self.process_id = None

        # ensure dynamic stuff is also reset
        self.add_default_values()

    def run(self, **kwargs: Any) -> UUIDstr:
        """Responsible for auto-completing the workflow after the process has been started.

        Returns: subscription_id of the created subscription

        """
        self.custom_input_values.update(kwargs)
        self.retries = 0

        while self.started and not self.done:
            self.log.info("Sleeping.")
            sleep(1.0)
            if self.human_input_needed():
                form = self.get_current_form()

                response = self.provide_user_input("PUT", BASE_API_URL / "processes" / self.process_id / "resume", form)
                if response.status_code == HTTPStatus.NO_CONTENT:
                    self.log.info("Resumed process.")
                else:
                    self.log.error("Resume process failed.", status_code=response.status_code)
                    raise Exception("Resume process failed")

        subscription_id = self.last_state["current_state"]["subscription_id"]
        self.log.info("Finished workflow", subscription_id=subscription_id)

        self.reset()

        return subscription_id


class TerminatePopulator(Populator):
    def __init__(self) -> None:
        self.log = logger.bind()
        super().__init__("IP_PREFIX")  # Dummy product name because we don't care for terminates
