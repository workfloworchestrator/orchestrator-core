import json
from http import HTTPStatus
from typing import Any, Dict, List, Optional, cast

from orchestrator.utils.json import json_dumps, json_loads
from test.unit_tests.mock.helpers import read_file, render

DEFAULT_MODIFY_SERVICE_BODY = read_file("ims/service_by_ims_service_id_24990.json")


class ImsMocks:
    def __init__(self, responses):
        self.responses = responses

    def create_service(self, service_ids):
        def respond(request):
            service = json_loads(request.body)
            return HTTPStatus.CREATED, {}, json_dumps({**service, "id": service_ids.pop(0), "order_id": "SNNP-1337"})

        self.responses.add_callback("POST", "/ims/services", callback=respond, content_type="application/json")

    def get_object_relate_by_service_id(self, service_id: int, body: Optional[List[Dict[str, Any]]] = None) -> None:
        if body is None:
            body = []
        if service_id in [24990, 24991, 101, 65317, 25688, 25689, 25690]:
            body = cast(
                List[Dict[str, Any]], json_loads(read_file(f"ims/object_relates_for_service_id_{service_id}.json"))
            )

        self.responses.add(
            "GET",
            f"/ims/object_relates/:service_id/{service_id}",
            content_type="application/json",
            status=HTTPStatus.OK,
            body=json_dumps(body),
        )

    def create_object_relate(self) -> None:
        def respond(request):
            payload = {"id": 243579, "object_name": "KLM", "relate_id": 24990, "relate_type": "CUST_TO_CIRCUIT"}
            return HTTPStatus.CREATED, {}, json_dumps(payload)

        self.responses.add_callback("POST", "/ims/object_relates", callback=respond, content_type="application/json")

    def update_service_status(self, service_id, status):
        self.responses.add(
            "PUT",
            f"/ims/services/{service_id}/{status}",
            content_type="application/json",
            status=HTTPStatus.OK,
            body=json_dumps({}),
        )

    def modify_service(self, ims_service_id, status=HTTPStatus.OK, body=DEFAULT_MODIFY_SERVICE_BODY):
        self.responses.add(
            "PUT",
            f"/ims/services/{ims_service_id}",
            content_type="application/json",
            status=status,
            body=render(body, id=ims_service_id),
        )

    def delete_service(self, service_id):
        self.responses.add("DELETE", f"/ims/services/{service_id}")

    def get_service_by_ims_port_id(self, ims_port_id, **kwargs):
        if ims_port_id == 671564:
            body = render(read_file("ims/service_by_ims_port_id_67154.json"))
        else:
            body = render(read_file("ims/service_by_ims_port_id.json"))
        self.responses.add(
            "GET",
            f"/ims/services/:ims_port_id/{ims_port_id}",
            status=HTTPStatus.OK,
            content_type="application/json",
            body=body,
            **kwargs,
        )

    def get_service_by_ims_service_id(
        self,
        ims_service_id: int,
        subscription_id: Optional[str] = None,
        http_status: HTTPStatus = HTTPStatus.OK,
        **kwargs: Any,
    ) -> None:
        if http_status != HTTPStatus.OK:
            self.responses.add(
                "GET",
                f"/ims/services/:ims_service_id/{ims_service_id}",
                status=http_status,
                content_type="application/json",
                body=json_dumps({"reason": "Rejected for testing purposes"}),
            )
            return

        body = render(read_file(f"ims/service_by_ims_service_id_{ims_service_id}.json"), **kwargs)

        if subscription_id:
            subscription_id = str(subscription_id).upper()

            # Properly set aliases if not given
            if "aliases" not in kwargs:
                data = json.loads(body)
                if "aliases" not in data:
                    data["aliases"] = []
                else:
                    data["aliases"] = list(filter(lambda a: not a.startswith("SUBSCRIPTION"), data["aliases"]))
                data["aliases"].append(f"SUBSCRIPTION_ID={subscription_id}")
                body = json_dumps(data)

            # Reset subscription id part in name
            if "name" not in kwargs:
                data = json.loads(body)
                name_parts = data["name"].split("_")
                name_parts[-1] = subscription_id[0:8]
                data["name"] = "_".join(name_parts)
                body = json_dumps(data)

        # Reset instance id part in name
        if "instance_id" in kwargs and "name" not in kwargs:
            data = json.loads(body)
            name_parts = data["name"].split("_")
            name_parts[-2] = str(kwargs["instance_id"])[0:8].upper()
            data["name"] = "_".join(name_parts)
            body = json_dumps(data)

        self.responses.add(
            "GET",
            f"/ims/services/:ims_service_id/{ims_service_id}",
            status=HTTPStatus.OK,
            content_type="application/json",
            body=body,
        )

    def get_corelink_trunk_service(self, http_status=HTTPStatus.OK, **kwargs):
        """2 mocks to get a trunk service back with 2 endpoints: endpoint 671188 PL, one endpoint 671230 IS."""
        if http_status == HTTPStatus.OK:
            body = render(read_file("ims/service_by_ims_service_id_2.json"), **kwargs)
            self.responses.add(
                "GET",
                "/ims/services/:ims_service_id/2",
                status=HTTPStatus.OK,
                content_type="application/json",
                body=body,
            )
            self.responses.add(
                "GET",
                "/ims/services/:ims_service_id/1",
                status=HTTPStatus.OK,
                content_type="application/json",
                body=body,
            )
        else:
            self.responses.add(
                "GET",
                "/ims/services/:ims_service_id/2",
                status=http_status,
                content_type="application/json",
                body=json_dumps({"reason": "Rejected for testing purposes"}),
            )

    def get_ims_port_by_id(self, ims_port_id, **kwargs):
        self.responses.add(
            "GET",
            f"/ims/ports/{ims_port_id}",
            body=render(read_file(f"ims/ims_port_by_id_{ims_port_id}.json"), **kwargs),
            content_type="application/json",
        )

    def get_node_by_name(self, node_name, **kwargs):
        self.responses.add(
            "GET",
            f"/ims/nodes/:ims_node_name/{node_name}",
            status=HTTPStatus.OK,
            content_type="application/json",
            body=render(read_file("ims/ims_node_by_name.json"), **kwargs),
        )

    def get_internal_ports(self, node):
        self.responses.add(
            "GET",
            f"/ims/internal_ports/node_name/{node}",
            status=HTTPStatus.OK,
            content_type="application/json",
            body=read_file(f"ims/internal_ports_{node.lower()}.json"),
        )

    def delete_internal_ports(self, port_id):
        self.responses.add("DELETE", f"/ims/internal_ports/{port_id}")

    def get_internal_port_by_id(self, internal_port_id, **kwargs):
        body = render(read_file(f"ims/internal_port_{internal_port_id}.json"), id=internal_port_id, **kwargs)
        self.responses.add(
            "GET",
            f"/ims/internal_ports/{internal_port_id}",
            status=HTTPStatus.OK,
            content_type="application/json",
            body=body,
        )

    def get_location_by_status(self, location_status):
        self.responses.add(
            "GET",
            f"/ims/locations/:status/{location_status}",
            status=HTTPStatus.OK,
            content_type="application/json",
            body=json_dumps([{"code": "ASD006A", "status": 6}]),
        )

    def get_vlans_by_ims_circuit_id(self, ims_circuit_id, body=None):
        if body is None:
            body = [
                {"start": 50, "end": 50, "sub_circuit_id": 25128},
                {"end": 45, "start": 24, "sub_circuit_id": 25128},
            ]
        self.responses.add(
            "GET",
            f"/ims/vlans/:msp/{ims_circuit_id}",
            status=HTTPStatus.OK,
            content_type="application/json",
            body=json_dumps(body),
        )

    def create_circuit_protection(self, circuit_protection_id):
        def respond(request):
            payload = {
                "id": circuit_protection_id.pop(0),
                "protection_circuit_id": 1,
                "worker_circuit_id": 1,
                "status": "IS",
            }
            return HTTPStatus.CREATED, {}, json_dumps(payload)

        self.responses.add_callback(
            "POST", "/ims/circuit_protections", callback=respond, content_type="application/json"
        )

    def create_internal_port(self, internal_port_ids):
        def respond(request):
            payload = {
                "id": internal_port_ids.pop(0),
                "port": "AE24",
                "node": "DT010A-JNX-01-VTB",
                "location": "DT010A",
            }
            return HTTPStatus.CREATED, {}, json_dumps(payload)

        self.responses.add_callback("POST", "/ims/internal_ports", callback=respond, content_type="application/json")

    def delete_circuit_protection(self, circuit_protection_id):
        self.responses.add("DELETE", f"/ims/circuit_protections/{circuit_protection_id}")

    def get_ims_circuit_protect_by_it(self, circuit_protection_id, **kwargs):
        body = render(read_file("ims/ims_circuit_protect_by_id.json"), **kwargs)
        self.responses.add(
            "GET", f"/ims/circuit_protections/{circuit_protection_id}", content_type="application/json", body=body
        )

    def get_node_by_id(self, ims_node_id, http_status=HTTPStatus.OK, **kwargs):
        if http_status == HTTPStatus.OK:
            body = render(read_file(f"ims/node_by_ims_node_id_{ims_node_id}.json"), id=ims_node_id, **kwargs)
            self.responses.add(
                "GET",
                f"/ims/nodes/:ims_node_id/{ims_node_id}",
                status=HTTPStatus.OK,
                content_type="application/json",
                body=body,
            )
        else:
            self.responses.add(
                "GET",
                f"/ims/nodes/:ims_node_id/{ims_node_id}",
                status=http_status,
                content_type="application/json",
                body=json_dumps({"reason": "Rejected for testing purposes"}),
            )

    def update_port_status(self, port_id, status):
        self.responses.add(
            "PUT",
            f"/ims/ports/{port_id}/{status}",
            content_type="application/json",
            status=HTTPStatus.OK,
            body=json_dumps({}),
        )

    def update_node_status(self, service_id, status):
        self.responses.add(
            "PUT",
            f"/ims/nodes/{service_id}/{status}",
            content_type="application/json",
            status=HTTPStatus.OK,
            body=json_dumps({}),
        )

    def node_by_location_and_status(self, location, status):
        self.responses.add(
            "GET",
            f"/ims/nodes/{location}/{status}",
            status=HTTPStatus.OK,
            content_type="application/json",
            body=read_file(f"ims/node_by_location_and_status_{location}_{status}.json"),
        )

    def get_free_ports_by_node_id_and_interface_type(self):
        self.responses.add(
            "GET",
            "/ims/ports/node/83735?mode=patched&iface_type=1000BASE-SX&status=free",
            body=read_file("ims/free_ports_by_node_id_and_interface_type.json"),
            match_querystring=True,
        )

    def get_port_services_by_node_name(self, node_name):
        body = render(read_file("ims/ims_port_services_by_node_name.json"))
        self.responses.add(
            "GET",
            f"/ims/nodes/port_service_ids/{node_name}",
            status=HTTPStatus.OK,
            content_type="application/json",
            body=body,
        )

    def get_organisation_by_uuid(self, uuid):
        body = render(read_file(f"ims/ims_organisation_{uuid}.json"))
        self.responses.add(
            "GET", f"/ims/organisations/{uuid}", status=HTTPStatus.OK, content_type="application/json", body=body
        )

    def get_organisations(self):
        self.responses.add(
            "GET",
            "/ims/organisations",
            body=read_file("ims/ims_organisations_subset.json"),
            status=HTTPStatus.OK,
            content_type="application/json",
        )

    def create_organisation(self, **kwargs):
        def callback(request):
            headers = {"content-type": "application/json"}
            payload = render(request.body, **kwargs)
            return (HTTPStatus.OK, headers, payload)

        self.responses.add_callback("POST", "/ims/organisations", callback=callback, content_type="application/json")

    def modify_organisation(self, guid, file=None, **kwargs):
        if file is not None:

            def callback(request):
                headers = {"content-type": "application/json"}
                payload = render(request.body, **kwargs)
                return (HTTPStatus.OK, headers, payload)

            self.responses.add_callback(
                "PUT", f"/ims/organisations/{guid}", callback=callback, content_type="application/json"
            )
        else:
            self.responses.add(
                "PUT",
                f"/ims/organisations/{guid}",
                body=read_file("ims/ims_organisation_rocteraa.json"),
                status=HTTPStatus.OK,
                content_type="application/json",
            )

    def delete_organisation_by_uuid(self, guid):
        self.responses.add("DELETE", f"/ims/organisations/{guid}", body=None, status=HTTPStatus.NO_CONTENT)
