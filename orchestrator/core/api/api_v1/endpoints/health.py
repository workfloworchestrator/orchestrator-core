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

from http import HTTPStatus

import structlog
from fastapi import Depends
from fastapi.routing import APIRouter
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.api.error_handling import raise_status
from orchestrator.core.db import ProductTable, get_async_session

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/", response_model=str)
async def get_health(session: AsyncSession = Depends(get_async_session)) -> str:
    try:
        stmt = select(ProductTable.name).limit(1)
        await session.execute(stmt)
    except OperationalError as e:
        logger.warning("Health endpoint returned: notok!")
        logger.debug("Health endpoint error details", error=str(e))
        raise_status(HTTPStatus.INTERNAL_SERVER_ERROR)
    return "OK"
