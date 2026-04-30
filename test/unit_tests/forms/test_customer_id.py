# Copyright 2019-2026 SURF, GÉANT.
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

from orchestrator.core.forms.validators import CustomerId
from pydantic_forms.core import FormPage


def test_customer_id_schema():
    class Form(FormPage):
        customer_id: CustomerId

    expected = {
        "additionalProperties": False,
        "properties": {"customer_id": {"format": "customerId", "title": "Customer Id", "type": "string"}},
        "required": ["customer_id"],
        "title": "unknown",
        "type": "object",
    }

    assert Form.model_json_schema() == expected
