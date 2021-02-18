from http import HTTPStatus
from urllib import parse

from orchestrator.utils.json import json_dumps, json_loads
from test.unit_tests.mock.helpers import read_file


class NsoMocks:
    def __init__(self, responses):
        self.responses = responses

    def get_nso_info(self):
        self.responses.add(
            "GET",
            "/restconf/data/tailf-ncs:devices/device=ledn002a-jnx-01-vtb",
            content_type="application/yang-data+json",
            status=HTTPStatus.OK,
            body=read_file("nso/node/ledn002a-jnx-01-vtb.json"),
        )

    def get_nso_info_404(self):
        self.responses.add(
            "GET",
            "/restconf/data/tailf-ncs:devices/device=ledn002a-jnx-01-vtb",
            content_type="application/yang-data+json",
            status=HTTPStatus.NOT_FOUND,
            body="Error code 404: Message not json. Response data: Not Found",
        )

    def post_service(self):
        self.responses.add(
            "POST",
            "/restconf/data/tailf-ncs:services",
            content_type="application/json",
            status=HTTPStatus.CREATED,
            body=json_dumps({}),
        )

    def put_service(self, service_type, service_name):
        encoded_service_name = parse.quote_plus(f'"{service_name}"')

        self.responses.add(
            "PUT",
            f"/restconf/data/tailf-ncs:services/{service_type}={encoded_service_name}",
            content_type="application/json",
            status=HTTPStatus.CREATED,
            body=json_dumps({}),
        )

    def re_deploy_service(self, service_type, service_name):
        encoded_service_name = parse.quote_plus(f'"{service_name}"')

        self.responses.add(
            "POST",
            f"/restconf/data/tailf-ncs:services/{service_type}={encoded_service_name}/re-deploy",
            content_type="application/json",
            status=HTTPStatus.OK,
            body=json_dumps({"tailf-ncs:output": {}}),
        )

    def get_service_specific(
        self, service_type, service_name, subscription_id=None, esi_ids=None, instance_ids=None, **kwargs
    ):
        # a relatively innocent seeming hack for NSO URLs containing quotes and /
        if instance_ids is None:
            instance_ids = {}
        service_name_file_name = service_name.replace('"', "").replace("/", "")
        if "no_parent" in kwargs:
            service_name_file_name = service_name_file_name + "_no_parent"
            del kwargs["no_parent"]
        data = json_loads(read_file(f"nso/service/{service_type}_{service_name_file_name}.json"))
        if subscription_id:
            data[service_type][0]["subscription_id"] = subscription_id

        # Try to find the instance ID in endpoint by key and replaces it with value
        if instance_ids and data[service_type][0].get("endpoint"):  # SP
            data[service_type][0]["endpoint"]["instance_id"] = instance_ids["1"]
        elif instance_ids and "l2vpn" in service_type and data[service_type][0].get("endpoints"):  # L2VPN
            for i, esi_id in enumerate(esi_ids):
                data[service_type][0]["endpoints"][i]["name"] = esi_id

            for port, key in zip(
                (p for e in data[service_type][0]["endpoints"] for p in e["ports"]), instance_ids.keys()
            ):
                port["instance_id"] = instance_ids[key]
        elif instance_ids and data[service_type][0].get("endpoints"):  # IP
            data[service_type][0]["endpoints"][0]["instance_id"] = instance_ids["1"]
            data[service_type][0]["endpoints"][1]["instance_id"] = instance_ids["2"]
        elif instance_ids and data[service_type][0].get("endpoints_a"):  # LP
            data[service_type][0]["endpoints_a"][0]["instance_id"] = str(instance_ids["a"])
            data[service_type][0]["endpoints_z"][0]["instance_id"] = str(instance_ids["z"])

        data[service_type] = [{**data[service_type][0], **kwargs}]

        encoded_service_name = parse.quote_plus(f'"{service_name}"')

        self.responses.add(
            "GET",
            f"/restconf/data/tailf-ncs:services/{service_type}={encoded_service_name}",
            content_type="application/yang-data+json",
            status=HTTPStatus.OK,
            body=json_dumps(data),
        )

    def delete_service(self, service_type, service_name):
        encoded_service_name = parse.quote_plus(f'"{service_name}"')

        self.responses.add(
            "DELETE",
            f"/restconf/data/tailf-ncs:services/{service_type}={encoded_service_name}",
            content_type="application/json",
            status=HTTPStatus.CREATED,
        )

    def get_sr_segment_ids(self):
        self.responses.add(
            "GET",
            "/restconf/data/tailf-ncs:services/node_create:node_create?fields=sr_segment_node_id&content=config",
            content_type="application/yang-data+json",
            status=HTTPStatus.OK,
            body=read_file("nso/node_create_sr_segment_node_ids.json"),
            match_querystring=True,
        )

    def set_node_unlocked(self, name):
        self.responses.add(
            "PUT",
            f"/restconf/data/tailf-ncs:devices/device={name}/state/admin-state",
            content_type="application/yang-data+json",
            status=HTTPStatus.NO_CONTENT,
            match_querystring=True,
        )

    def node_in_sync(self, name):
        self.responses.add(
            "POST",
            f"/restconf/data/tailf-ncs:devices/device={name}/check-sync",
            content_type="application/yang-data+json",
            status=HTTPStatus.OK,
            body='{"tailf-ncs:output": {"result": "in-sync"}}',
            match_querystring=True,
        )
