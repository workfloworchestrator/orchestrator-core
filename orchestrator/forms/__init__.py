# Copyright 2019-2020 SURF.
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
from typing import ClassVar

from pydantic_forms.core import DisplayOnlyFieldType, generate_form, post_form
from pydantic_forms.core import FormPage as PydanticFormsFormPage
from pydantic_forms.types import JSON, InputForm, StateInputFormGenerator

__all__ = [
    "DisplayOnlyFieldType",
    "FormPage",
    "SubmitFormPage",
    "InputForm",
    "JSON",
    "StateInputFormGenerator",
    "generate_form",
    "post_form",
]


class FormPage(PydanticFormsFormPage):
    meta__: ClassVar[JSON] = {"hasNext": True}


class SubmitFormPage(FormPage):
    meta__: ClassVar[JSON] = {"hasNext": False}
