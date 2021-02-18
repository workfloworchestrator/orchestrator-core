from http import HTTPStatus

from test.unit_tests.mock.helpers import read_file, render


class CrmMocks:
    def __init__(self, responses):
        self.responses = responses

    def get_organisation_by_uuid(self, uid, file="organisation_by_uuid.json", **kwargs):
        self.responses.add(
            "GET",
            f"/crm/organisations/{uid}",
            body=render(read_file("crm/" + file), **kwargs),
            status=HTTPStatus.OK,
            content_type="application/json",
        )

    def get_organisations(self, subset=False):
        if subset:
            body = read_file("crm/organisations_filtered_subset.json")
        else:
            body = read_file("crm/organisations_filtered.json")
        self.responses.add(
            "GET", "/crm/organisations", body=body, status=HTTPStatus.OK, content_type="application/json"
        )

    def get_locations(self, type=None):
        strict = True if type else False
        opt = f"?filter_name={type}" if type else ""
        self.responses.add(
            "GET",
            f"/crm/locations{opt}",
            body=read_file("crm/locations.json"),
            status=HTTPStatus.OK,
            match_querystring=strict,
            content_type="application/json",
        )

    def get_contacts_by_guid(self, guid):
        self.responses.add(
            "GET",
            f"/crm/contacts/{guid}",
            body=read_file("crm/contacts_by_uuid.json"),
            status=HTTPStatus.OK,
            content_type="application/json",
        )

    def get_addresses_by_guid(self, guid, file="addresses_by_guid.json"):
        self.responses.add(
            "GET",
            f"/crm/addresses/{guid}",
            body=read_file("crm/" + file),
            status=HTTPStatus.OK,
            content_type="application/json",
        )
