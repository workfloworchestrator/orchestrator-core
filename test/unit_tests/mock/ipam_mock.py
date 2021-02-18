from http import HTTPStatus
from urllib.parse import quote

from nwastdlib.url import URL

from orchestrator.utils.json import json_dumps
from test.unit_tests.mock.helpers import read_file, render


class IpamMocks:
    def __init__(self, responses):
        self.responses = responses

    def get_all_prefixes_one_subscription_ipv6(self):
        self.responses.add(
            "GET",
            "/ipam/ip/prefix?vrf=2",
            body=read_file("ipam/ipam_all_ip_prefixes_vrf_2_one_subscription_ipv6.json"),
            content_type="application/json",
            match_querystring=True,
        )

    def get_all_prefixes_one_subscription_ipv4(self):
        self.responses.add(
            "GET",
            "/ipam/ip/prefix?vrf=2",
            body=read_file("ipam/ipam_all_ip_prefixes_vrf_2_one_subscription_ipv4.json"),
            content_type="application/json",
            match_querystring=True,
        )

    def get_all_prefixes(self):
        self.responses.add(
            "GET",
            "/ipam/ip/prefix?vrf=2",
            body=read_file("ipam/ipam_all_prefixes.json"),
            content_type="application/json",
            match_querystring=True,
        )

    def get_prefixes_by_prefix(self, prefix, vrf=1):
        self.responses.add(
            "GET",
            f"/ipam/ip/prefix/{quote(prefix)}?vrf={vrf}",
            body=read_file(f"ipam/ipam_prefix_by_prefix_{vrf}_{prefix.replace('/', '_')}.json"),
            content_type="application/json",
            match_querystring=True,
        )

    def get_prefixes_by_prefix_404(self, prefix, vrf=1):
        self.responses.add(
            "GET",
            f"/ipam/ip/prefix/{quote(prefix)}?vrf={vrf}",
            body=None,
            status=HTTPStatus.NOT_FOUND,
            content_type="application/json",
            match_querystring=True,
        )

    def get_prefix_by_prefix_id(self, id, **kwargs):
        body = render(read_file(f"ipam/ipam_prefix_{id}.json"), **kwargs)
        self.responses.add("GET", f"/ipam/ip/prefix/{id}", body=body, content_type="application/json")

    def get_prefix_by_prefix_id_404(self, id):
        self.responses.add(
            "GET", f"/ipam/ip/prefix/{id}", body=None, status=HTTPStatus.NOT_FOUND, content_type="application/json"
        )

    def update_prefix(self, id):
        # exception for the modify IP Prefix wf
        suffix = f"_{id}" if id in (32, 35) else ""
        self.responses.add(
            "PUT",
            f"/ipam/ip/prefix/{id}",
            status=HTTPStatus.NO_CONTENT,
            body=read_file(f"ipam/prefix_put_response{suffix}.json"),
            content_type="application/json",
        )

    def create_address(self, id, **kwargs):
        def callback(request):
            headers = {"content-type": "application/json"}
            payload = render(request.body, id=id.pop(0), **kwargs)
            return HTTPStatus.NO_CONTENT, headers, payload

        self.responses.add_callback("POST", "/ipam/ip/address", callback=callback, content_type="application/json")

    def create_prefix(self, id, **kwargs):
        def callback(request):
            headers = {"content-type": "application/json"}
            payload = render(request.body, id=id.pop(0), **kwargs)
            return (HTTPStatus.OK, headers, payload)

        self.responses.add_callback("POST", "/ipam/ip/prefix", callback=callback, content_type="application/json")

    def delete_prefix_with_prefix_id(self, prefix_id, recursive=False):
        recursive_str = ""
        if recursive:
            recursive_str = "?recursive=True"
        self.responses.add(
            "DELETE",
            f"/ipam/ip/prefix/{prefix_id}{recursive_str}",
            body=None,
            status=HTTPStatus.NO_CONTENT,
            match_querystring=True,
        )

    def delete_address_by_address_id(self, address_id):
        self.responses.add("DELETE", f"/ipam/ip/address/{address_id}", body=None, status=HTTPStatus.NO_CONTENT)

    def get_address_by_id(self, id=None, **kwargs):
        if id:
            self.responses.add(
                "GET",
                f"/ipam/ip/address/{id}",
                body=render(read_file(f"ipam/ipam_address_by_id_{id}.json"), **kwargs),
                content_type="application/json",
            )

    def get_dns_zone_by_name(self, zone_name):
        self.responses.add(
            "GET",
            f"/ipam/dns/zone/{zone_name}",
            body=read_file("ipam/ipam_dnszone_by_name_lookup.json"),
            content_type="application/json",
        )

    def get_dnsrecord_by_name(self, dns_zone, dns_record):
        self.responses.add(
            "GET",
            f"/ipam/dns/record/{dns_zone}/name/{dns_record}",
            body=read_file("ipam/dns_records.json"),
            content_type="application/json",
        )

    def set_dnsrecords_by_record(self):
        self.responses.add(
            "POST",
            "/ipam/dns/record/dev.vtb/name/ledn002a-jnx-01-vtb",
            body=read_file("ipam/dns_record.json"),
            content_type="application/json",
        )

    def put_dnsrecord_by_id(self, record_id, zone):
        self.responses.add(
            "PUT",
            f"/ipam/dns/record/{zone}/{record_id}",
            body=read_file("ipam/dns_record.json"),
            content_type="application/json",
        )

    def delete_ipaddress_by_id(self, id):
        self.responses.add(
            "DELETE", f"/ipam/ip/address/{id}", status=HTTPStatus.NO_CONTENT, content_type="application/json"
        )

    def put_address_by_id(self, id):
        self.responses.add(
            "PUT",
            f"/ipam/ip/address/{id}",
            body=render(read_file(f"ipam/address_put_{id}.json"), id=id),
            status=HTTPStatus.NO_CONTENT,
            content_type="application/json",
        )

    def get_free_prefixes_by_prefix(self, prefix, vrf=1, **kwargs):
        FREE_PREFIXES_DICT = {
            ("10.1.16.0/20", 1, 31, False): ["10.1.16.8/31", "10.1.16.10/31"],
            ("10.1.32.0/20", 1, 31, False): ["10.1.32.0/31", "10.1.32.2/31"],
            ("10.1.32.0/20", 1, 29, False): ["10.1.32.8/29", "10.1.32.16/29"],
            ("145.145.166.0/24", 1, 31, False): ["145.145.166.8/31", "145.145.166.10/31"],
            ("fd00:0:101::/48", 1, 127, False): ["fd00:0:101::12/128", "fd00:0:101::16/127"],
        }

        base_url = URL("/ipam/ip/prefix")
        self.responses.add(
            "GET",
            base_url / quote(prefix) / vrf / "free" // kwargs,
            body=json_dumps(FREE_PREFIXES_DICT.get((prefix, vrf, *kwargs.values()), [])),
            content_type="application/json",
            match_querystring=True,
        )
