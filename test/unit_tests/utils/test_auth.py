# Copyright 2019-2026 SURF, ESnet, GÉANT.
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

from oauth2_lib.fastapi import OIDCUserModel
from orchestrator.core.utils.auth import AuthContext
from orchestrator.core.workflow import (
    begin,
    done,
    step,
    workflow,
)


class User(OIDCUserModel):
    @property
    def user_name(self) -> str:
        return self.name


async def test_generic_authorizer():
    """Exercises a simple generic Authorizer against an AuthContext.

    This test is primarily to 1. exercise the type system for auth.py
    and 2. to provide a simple example usage.
    """

    async def generic_authorizer(context: AuthContext) -> bool:
        """Allows users to run workflows associated with their username.

        Ignores workflow action and per-step authorizations.
        """
        if not context.user or not context.workflow:
            return False

        _user_workflows = {
            "foo": ["some_workflow"],
        }

        name = context.user.user_name
        if name not in _user_workflows:
            return False

        return context.workflow.name in _user_workflows[name]

    @step("One")
    def one():
        return {}

    @workflow("Some workflow", authorize_callback=generic_authorizer)
    def some_workflow():
        return begin >> one >> done

    @workflow("Another workflow", authorize_callback=generic_authorizer)
    def another_workflow():
        return begin >> one >> done

    # bar cannot run some_workflow
    context = AuthContext(user=User(name="bar"), workflow=some_workflow, action="start_workflow")
    context.user.name = "bar"
    assert not await some_workflow.authorize_callback(context)
    # foo can run some_workflow
    context.user.name = "foo"
    assert await some_workflow.authorize_callback(context)
    # foo cannot run another_workflow
    context.workflow = another_workflow
    assert not await another_workflow.authorize_callback(context)
