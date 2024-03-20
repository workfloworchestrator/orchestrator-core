# Changelog

## [Unreleased]
- Migrate most sqlalchemy queries to v2 functions
    - Moved `WorkflowTable.find_by_name` to `orchestrator.services.workflows.get_workflow_by_name`

## [2.0.0]
- Migrated to Pydantic v2

## [1.3.6]
- Implement search query resolvers for various models [\#288]

## [1.3.5]
- Refactor SQLAlchemy queries to use v2 select statements in graphql resolvers [\#386]
- Refactoring of callback steps
- Add TASK_LOG_RETENTION_DAYS env setting
- Add list of steps to workflow endpoints
- Add stateDelta information to process steps in graphql
- Add inUseByRelations data to subscription.productBlockInstances
- Added generic parser to support complex search queries [\#413]
- Several other fixes

## [1.3.1]
- Added support for asynchronous callback_steps [\#297](https://github.com/workfloworchestrator/orchestrator-core/issues/297)

## [1.2.0]
 - Removed the opentelemetry dependancy and added warnings to function calls
 - Renamed an error classes and added warnings

## [1.1.0]

### Breaking change
 - Changed `settings.CACHE_HOST` and `settings.CACHE_PORT` to `settings.CACHE_URI`
 - Add support for subscription metadata [\#266](https://github.com/workfloworchestrator/orchestrator-core/issues/266)

## [1.0.2]

- Allow user to extend the default translation set, instead of overwriting everything
- Return worker status information in the `/api/settings/worker-status` endpoint

## [0.4.0-rc1](https://github.com/workfloworchestrator/orchestrator-core/tree/0.4.0-rc1) (2022-03-08)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.3.8...0.4.0-rc1)

**Merged pull requests:**

- 1319 rename parent\_id and child\_id of product block relation to in\_use\_by\_id and dependent\_on\_id [\#107](https://github.com/workfloworchestrator/orchestrator-core/pull/107) ([github-actions[bot]](https://github.com/apps/github-actions))

## [0.3.8](https://github.com/workfloworchestrator/orchestrator-core/tree/0.3.8) (2022-03-08)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.3.8-rc2...0.3.8)

**Merged pull requests:**

- Update from bumpversion-0.3.8 [\#118](https://github.com/workfloworchestrator/orchestrator-core/pull/118) ([github-actions[bot]](https://github.com/apps/github-actions))
- Change other subscriptions endpoint with filtering statuses [\#116](https://github.com/workfloworchestrator/orchestrator-core/pull/116) ([tjeerddie](https://github.com/tjeerddie))
- Allow self-referencing product blocks [\#112](https://github.com/workfloworchestrator/orchestrator-core/pull/112) ([Mark90](https://github.com/Mark90))
- Update from 1297-parent\_ids [\#111](https://github.com/workfloworchestrator/orchestrator-core/pull/111) ([github-actions[bot]](https://github.com/apps/github-actions))

## [0.3.8-rc2](https://github.com/workfloworchestrator/orchestrator-core/tree/0.3.8-rc2) (2022-03-04)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.3.8-rc1...0.3.8-rc2)

**Merged pull requests:**

- Update from bumpversion-0.3.8-rc2 [\#117](https://github.com/workfloworchestrator/orchestrator-core/pull/117) ([github-actions[bot]](https://github.com/apps/github-actions))
- Change other subscriptions endpoint with filtering statuses [\#116](https://github.com/workfloworchestrator/orchestrator-core/pull/116) ([tjeerddie](https://github.com/tjeerddie))

## [0.3.8-rc1](https://github.com/workfloworchestrator/orchestrator-core/tree/0.3.8-rc1) (2022-03-01)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.3.7...0.3.8-rc1)

**Closed issues:**

- Allow self-referencing product blocks [\#108](https://github.com/workfloworchestrator/orchestrator-core/issues/108)

**Merged pull requests:**

- Update from bumpversion-0.3.8-rc1 [\#115](https://github.com/workfloworchestrator/orchestrator-core/pull/115) ([github-actions[bot]](https://github.com/apps/github-actions))
- Allow self-referencing product blocks [\#112](https://github.com/workfloworchestrator/orchestrator-core/pull/112) ([Mark90](https://github.com/Mark90))
- Update from 1297-parent\_ids [\#111](https://github.com/workfloworchestrator/orchestrator-core/pull/111) ([github-actions[bot]](https://github.com/apps/github-actions))

## [0.3.7](https://github.com/workfloworchestrator/orchestrator-core/tree/0.3.7) (2022-02-28)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.3.6...0.3.7)

**Merged pull requests:**

- Update from bumpversion-0.3.7 [\#114](https://github.com/workfloworchestrator/orchestrator-core/pull/114) ([github-actions[bot]](https://github.com/apps/github-actions))
- Revert "Update from 1297-how-other\_subscriptions-can-be-shown-on-the-… [\#113](https://github.com/workfloworchestrator/orchestrator-core/pull/113) ([pboers1988](https://github.com/pboers1988))

## [0.3.6](https://github.com/workfloworchestrator/orchestrator-core/tree/0.3.6) (2022-02-21)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.3.5...0.3.6)

**Merged pull requests:**

- bumpversion to 0.3.6 [\#106](https://github.com/workfloworchestrator/orchestrator-core/pull/106) ([tjeerddie](https://github.com/tjeerddie))
- pin markupsafe to keep jinja2 happy [\#105](https://github.com/workfloworchestrator/orchestrator-core/pull/105) ([tjeerddie](https://github.com/tjeerddie))
- Change create product blocks migration helper [\#104](https://github.com/workfloworchestrator/orchestrator-core/pull/104) ([tjeerddie](https://github.com/tjeerddie))
- Update from 1297-how-other\_subscriptions-can-be-shown-on-the-fw-subscription-id [\#86](https://github.com/workfloworchestrator/orchestrator-core/pull/86) ([github-actions[bot]](https://github.com/apps/github-actions))

## [0.3.5](https://github.com/workfloworchestrator/orchestrator-core/tree/0.3.5) (2022-02-16)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.3.4...0.3.5)

**Merged pull requests:**

- Bumped version to 0.3.5 [\#103](https://github.com/workfloworchestrator/orchestrator-core/pull/103) ([acidjunk](https://github.com/acidjunk))
- feat: make list of workflows usable-while-out-of-sync extensible [\#101](https://github.com/workfloworchestrator/orchestrator-core/pull/101) ([nemimccarter](https://github.com/nemimccarter))
- Update from 1330-fix-incorrect-check-of-is\_list\_type-in-orchestrator-core [\#100](https://github.com/workfloworchestrator/orchestrator-core/pull/100) ([github-actions[bot]](https://github.com/apps/github-actions))
- Update from 1318-cleanup-the-migration-helpers [\#94](https://github.com/workfloworchestrator/orchestrator-core/pull/94) ([github-actions[bot]](https://github.com/apps/github-actions))

## [0.3.4](https://github.com/workfloworchestrator/orchestrator-core/tree/0.3.4) (2022-02-14)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.3.3...0.3.4)

**Merged pull requests:**

- Refactor fixtures of test\_base unit tests and add tests for multiple relations list support [\#97](https://github.com/workfloworchestrator/orchestrator-core/pull/97) ([github-actions[bot]](https://github.com/apps/github-actions))
- Add scheduled build [\#95](https://github.com/workfloworchestrator/orchestrator-core/pull/95) ([Mark90](https://github.com/Mark90))
- Update from support-product-block-list-multiple-relations [\#91](https://github.com/workfloworchestrator/orchestrator-core/pull/91) ([github-actions[bot]](https://github.com/apps/github-actions))

## [0.3.3](https://github.com/workfloworchestrator/orchestrator-core/tree/0.3.3) (2022-02-08)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.3.3-rc2...0.3.3)

**Merged pull requests:**

- 0.3.3 release [\#92](https://github.com/workfloworchestrator/orchestrator-core/pull/92) ([pboers1988](https://github.com/pboers1988))
- Add support in product block for list with multiple related product blocks [\#90](https://github.com/workfloworchestrator/orchestrator-core/pull/90) ([tjeerddie](https://github.com/tjeerddie))
- Backup subscription details [\#87](https://github.com/workfloworchestrator/orchestrator-core/pull/87) ([acidjunk](https://github.com/acidjunk))

## [0.3.3-rc2](https://github.com/workfloworchestrator/orchestrator-core/tree/0.3.3-rc2) (2022-02-02)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.3.3-rc1...0.3.3-rc2)

**Merged pull requests:**

- Remove missing\_product\_blocks check in diff\_product\_in\_database [\#89](https://github.com/workfloworchestrator/orchestrator-core/pull/89) ([tjeerddie](https://github.com/tjeerddie))

## [0.3.3-rc1](https://github.com/workfloworchestrator/orchestrator-core/tree/0.3.3-rc1) (2022-01-31)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.3.3-rc...0.3.3-rc1)

**Merged pull requests:**

- Bumped dependancie [\#88](https://github.com/workfloworchestrator/orchestrator-core/pull/88) ([pboers1988](https://github.com/pboers1988))

## [0.3.3-rc](https://github.com/workfloworchestrator/orchestrator-core/tree/0.3.3-rc) (2022-01-31)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.3.2...0.3.3-rc)

**Merged pull requests:**

- Websocket add ping pong and close ws on server shutdown [\#85](https://github.com/workfloworchestrator/orchestrator-core/pull/85) ([tjeerddie](https://github.com/tjeerddie))
- Update from improve-in-sync-endpoint [\#84](https://github.com/workfloworchestrator/orchestrator-core/pull/84) ([github-actions[bot]](https://github.com/apps/github-actions))
- Add /api/processes/resume-all and distlock [\#83](https://github.com/workfloworchestrator/orchestrator-core/pull/83) ([github-actions[bot]](https://github.com/apps/github-actions))
- Update from 1301-cannot-flush-crm-cache [\#82](https://github.com/workfloworchestrator/orchestrator-core/pull/82) ([github-actions[bot]](https://github.com/apps/github-actions))
- Update from 1301-cannot-flush-crm-cache [\#81](https://github.com/workfloworchestrator/orchestrator-core/pull/81) ([github-actions[bot]](https://github.com/apps/github-actions))
- Update from add\_create\_from\_other\_product\_function [\#77](https://github.com/workfloworchestrator/orchestrator-core/pull/77) ([github-actions[bot]](https://github.com/apps/github-actions))

## [0.3.2](https://github.com/workfloworchestrator/orchestrator-core/tree/0.3.2) (2022-01-17)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.3.1...0.3.2)

**Merged pull requests:**

- Fix process endpoint regression in 0.3.0 [\#80](https://github.com/workfloworchestrator/orchestrator-core/pull/80) ([github-actions[bot]](https://github.com/apps/github-actions))

## [0.3.1](https://github.com/workfloworchestrator/orchestrator-core/tree/0.3.1) (2022-01-17)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.3.0...0.3.1)

**Merged pull requests:**

- Release [\#79](https://github.com/workfloworchestrator/orchestrator-core/pull/79) ([pboers1988](https://github.com/pboers1988))

## [0.3.0](https://github.com/workfloworchestrator/orchestrator-core/tree/0.3.0) (2022-01-17)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.3.0-rc1...0.3.0)

**Merged pull requests:**

- Updated orchestrator-core to be compatible with Pydantic 1.9.0 [\#78](https://github.com/workfloworchestrator/orchestrator-core/pull/78) ([github-actions[bot]](https://github.com/apps/github-actions))
- Update from add\_set\_insync\_api [\#76](https://github.com/workfloworchestrator/orchestrator-core/pull/76) ([github-actions[bot]](https://github.com/apps/github-actions))
- Example documents on setting up the Orchestrator Core [\#25](https://github.com/workfloworchestrator/orchestrator-core/pull/25) ([github-actions[bot]](https://github.com/apps/github-actions))

## [0.3.0-rc1](https://github.com/workfloworchestrator/orchestrator-core/tree/0.3.0-rc1) (2021-12-22)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.2.3...0.3.0-rc1)

**Merged pull requests:**

- Fix engine websocket endpoint [\#75](https://github.com/workfloworchestrator/orchestrator-core/pull/75) ([tjeerddie](https://github.com/tjeerddie))
- Update websocket all processes [\#74](https://github.com/workfloworchestrator/orchestrator-core/pull/74) ([tjeerddie](https://github.com/tjeerddie))
- Pydantic v1.9.0 [\#72](https://github.com/workfloworchestrator/orchestrator-core/pull/72) ([pboers1988](https://github.com/pboers1988))
- Update pyproject.toml [\#71](https://github.com/workfloworchestrator/orchestrator-core/pull/71) ([thijs-creemers](https://github.com/thijs-creemers))
- Update from 7\_implement\_websocket\_for\_engine\_settings [\#70](https://github.com/workfloworchestrator/orchestrator-core/pull/70) ([github-actions[bot]](https://github.com/apps/github-actions))
- Fix github unit tests workflow from getting stuck [\#69](https://github.com/workfloworchestrator/orchestrator-core/pull/69) ([github-actions[bot]](https://github.com/apps/github-actions))
- Add nitpick configuration and add it to pre-commit [\#68](https://github.com/workfloworchestrator/orchestrator-core/pull/68) ([tjeerddie](https://github.com/tjeerddie))
- Update from 1255-webserver-hot-reload-broken [\#67](https://github.com/workfloworchestrator/orchestrator-core/pull/67) ([github-actions[bot]](https://github.com/apps/github-actions))
- Update from add-more-docs [\#66](https://github.com/workfloworchestrator/orchestrator-core/pull/66) ([github-actions[bot]](https://github.com/apps/github-actions))
- Update from 1250-bug-in-scheduler [\#65](https://github.com/workfloworchestrator/orchestrator-core/pull/65) ([github-actions[bot]](https://github.com/apps/github-actions))
- Upgraded SQLAlchemy to 1.4.27 and SQLAlchemy-Searchable to 1.4.1 [\#64](https://github.com/workfloworchestrator/orchestrator-core/pull/64) ([Georgi2704](https://github.com/Georgi2704))
- Transition status mapping change [\#63](https://github.com/workfloworchestrator/orchestrator-core/pull/63) ([pboers1988](https://github.com/pboers1988))
- Remove regex as dependancy [\#62](https://github.com/workfloworchestrator/orchestrator-core/pull/62) ([pboers1988](https://github.com/pboers1988))
- Query the subscription instance parents for any other subscriptions [\#60](https://github.com/workfloworchestrator/orchestrator-core/pull/60) ([pboers1988](https://github.com/pboers1988))
- fix: Product Blocks not being linked to Products with create\(\) [\#10](https://github.com/workfloworchestrator/orchestrator-core/pull/10) ([howderek](https://github.com/howderek))

## [0.2.3](https://github.com/workfloworchestrator/orchestrator-core/tree/0.2.3) (2021-11-16)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.2.2...0.2.3)

**Merged pull requests:**

- Show a list of subscription ids if the product\_block is part of a dif… [\#59](https://github.com/workfloworchestrator/orchestrator-core/pull/59) ([pboers1988](https://github.com/pboers1988))
- Fix invalid date in process detail [\#58](https://github.com/workfloworchestrator/orchestrator-core/pull/58) ([github-actions[bot]](https://github.com/apps/github-actions))

## [0.2.2](https://github.com/workfloworchestrator/orchestrator-core/tree/0.2.2) (2021-11-08)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.2.1...0.2.2)

**Merged pull requests:**

- Improve websocket enable/disable functionality [\#57](https://github.com/workfloworchestrator/orchestrator-core/pull/57) ([tjeerddie](https://github.com/tjeerddie))
-  Add env variable `WEBSOCKETS_ON` to be able to turn off websockets [\#56](https://github.com/workfloworchestrator/orchestrator-core/pull/56) ([github-actions[bot]](https://github.com/apps/github-actions))

## [0.2.1](https://github.com/workfloworchestrator/orchestrator-core/tree/0.2.1) (2021-11-03)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.2.0...0.2.1)

**Merged pull requests:**

- Lifecycle [\#55](https://github.com/workfloworchestrator/orchestrator-core/pull/55) ([pboers1988](https://github.com/pboers1988))

## [0.2.0](https://github.com/workfloworchestrator/orchestrator-core/tree/0.2.0) (2021-10-25)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.1.0...0.2.0)

**Merged pull requests:**

- Update from websocket-process-list [\#53](https://github.com/workfloworchestrator/orchestrator-core/pull/53) ([github-actions[bot]](https://github.com/apps/github-actions))

## [0.1.0](https://github.com/workfloworchestrator/orchestrator-core/tree/0.1.0) (2021-10-22)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.21...0.1.0)

**Fixed bugs:**

- Following the README for dev setup installs a lot of packages outside your venv [\#17](https://github.com/workfloworchestrator/orchestrator-core/issues/17)

**Closed issues:**

- Some doc entries mention Flask [\#2](https://github.com/workfloworchestrator/orchestrator-core/issues/2)

**Merged pull requests:**

- Update from fix\_lifecycle\_data\_update\_for\_optional\_fields [\#54](https://github.com/workfloworchestrator/orchestrator-core/pull/54) ([github-actions[bot]](https://github.com/apps/github-actions))
- Update from pip-installable [\#51](https://github.com/workfloworchestrator/orchestrator-core/pull/51) ([github-actions[bot]](https://github.com/apps/github-actions))
- Update from pip-installable [\#50](https://github.com/workfloworchestrator/orchestrator-core/pull/50) ([github-actions[bot]](https://github.com/apps/github-actions))
- Update from divider [\#49](https://github.com/workfloworchestrator/orchestrator-core/pull/49) ([github-actions[bot]](https://github.com/apps/github-actions))
- Add ws process list endpoint for live updates in processes page [\#47](https://github.com/workfloworchestrator/orchestrator-core/pull/47) ([tjeerddie](https://github.com/tjeerddie))
- Pip installable [\#44](https://github.com/workfloworchestrator/orchestrator-core/pull/44) ([pboers1988](https://github.com/pboers1988))
- Update from docs [\#43](https://github.com/workfloworchestrator/orchestrator-core/pull/43) ([github-actions[bot]](https://github.com/apps/github-actions))
- Update from fix-flask-mentions [\#42](https://github.com/workfloworchestrator/orchestrator-core/pull/42) ([github-actions[bot]](https://github.com/apps/github-actions))
- websocket process detail: fix linting errors [\#41](https://github.com/workfloworchestrator/orchestrator-core/pull/41) ([tjeerddie](https://github.com/tjeerddie))
- Websocket process detail endpoint for live updates [\#40](https://github.com/workfloworchestrator/orchestrator-core/pull/40) ([tjeerddie](https://github.com/tjeerddie))
- Update from fix\_optional\_fields\_are\_not\_optional [\#39](https://github.com/workfloworchestrator/orchestrator-core/pull/39) ([github-actions[bot]](https://github.com/apps/github-actions))
- Deps [\#38](https://github.com/workfloworchestrator/orchestrator-core/pull/38) ([pboers1988](https://github.com/pboers1988))
- Docs [\#20](https://github.com/workfloworchestrator/orchestrator-core/pull/20) ([pboers1988](https://github.com/pboers1988))

## [0.0.21](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.21) (2021-09-22)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.1.1...0.0.21)

## [0.1.1](https://github.com/workfloworchestrator/orchestrator-core/tree/0.1.1) (2021-09-15)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.20...0.1.1)

**Merged pull requests:**

- Update from tree2 [\#37](https://github.com/workfloworchestrator/orchestrator-core/pull/37) ([github-actions[bot]](https://github.com/apps/github-actions))
- Update from tree [\#29](https://github.com/workfloworchestrator/orchestrator-core/pull/29) ([github-actions[bot]](https://github.com/apps/github-actions))

## [0.0.20](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.20) (2021-08-05)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.19...0.0.20)

**Merged pull requests:**

- Improve test code \(and fix found issues\) [\#34](https://github.com/workfloworchestrator/orchestrator-core/pull/34) ([github-actions[bot]](https://github.com/apps/github-actions))
- Update from update-opentelemetry [\#18](https://github.com/workfloworchestrator/orchestrator-core/pull/18) ([github-actions[bot]](https://github.com/apps/github-actions))

## [0.0.19](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.19) (2021-07-19)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.18...0.0.19)

**Merged pull requests:**

- Update from release [\#33](https://github.com/workfloworchestrator/orchestrator-core/pull/33) ([github-actions[bot]](https://github.com/apps/github-actions))
- Allow 3.9 [\#32](https://github.com/workfloworchestrator/orchestrator-core/pull/32) ([github-actions[bot]](https://github.com/apps/github-actions))
- Update from test [\#31](https://github.com/workfloworchestrator/orchestrator-core/pull/31) ([github-actions[bot]](https://github.com/apps/github-actions))
- Update from fix\_bug [\#30](https://github.com/workfloworchestrator/orchestrator-core/pull/30) ([github-actions[bot]](https://github.com/apps/github-actions))

## [0.0.18](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.18) (2021-07-09)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.17...0.0.18)

**Merged pull requests:**

- Update from changelog [\#28](https://github.com/workfloworchestrator/orchestrator-core/pull/28) ([github-actions[bot]](https://github.com/apps/github-actions))
- Update from service\_port\_super [\#26](https://github.com/workfloworchestrator/orchestrator-core/pull/26) ([github-actions[bot]](https://github.com/apps/github-actions))
- Remove flake8 issues and ignores [\#24](https://github.com/workfloworchestrator/orchestrator-core/pull/24) ([hmvp](https://github.com/hmvp))
- Make ProcessFailure details optional [\#23](https://github.com/workfloworchestrator/orchestrator-core/pull/23) ([hmvp](https://github.com/hmvp))

## [0.0.17](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.17) (2021-06-09)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.16...0.0.17)

**Merged pull requests:**

- Bump version: 0.0.16 → 0.0.17 [\#22](https://github.com/workfloworchestrator/orchestrator-core/pull/22) ([hmvp](https://github.com/hmvp))
- Improve mypy stuff [\#21](https://github.com/workfloworchestrator/orchestrator-core/pull/21) ([hmvp](https://github.com/hmvp))
- Mypy [\#19](https://github.com/workfloworchestrator/orchestrator-core/pull/19) ([pboers1988](https://github.com/pboers1988))

## [0.0.16](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.16) (2021-05-12)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.15...0.0.16)

**Merged pull requests:**

- Update Requirements to patch CVE [\#15](https://github.com/workfloworchestrator/orchestrator-core/pull/15) ([pboers1988](https://github.com/pboers1988))

## [0.0.15](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.15) (2021-05-10)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.14...0.0.15)

**Merged pull requests:**

- Update from upgrade-oauth2-lib [\#14](https://github.com/workfloworchestrator/orchestrator-core/pull/14) ([github-actions[bot]](https://github.com/apps/github-actions))
- Update for python 3.9 [\#13](https://github.com/workfloworchestrator/orchestrator-core/pull/13) ([hmvp](https://github.com/hmvp))

## [0.0.14](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.14) (2021-04-29)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.13...0.0.14)

**Merged pull requests:**

- Upgrade lib oauth to 1.0.4 and Sqlalchemy to 1.3.24 [\#12](https://github.com/workfloworchestrator/orchestrator-core/pull/12) ([acidjunk](https://github.com/acidjunk))

## [0.0.13](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.13) (2021-04-26)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.12...0.0.13)

**Merged pull requests:**

- Upgrade oauth lib [\#11](https://github.com/workfloworchestrator/orchestrator-core/pull/11) ([acidjunk](https://github.com/acidjunk))

## [0.0.12](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.12) (2021-04-08)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.11...0.0.12)

**Merged pull requests:**

- Serialisation [\#9](https://github.com/workfloworchestrator/orchestrator-core/pull/9) ([pboers1988](https://github.com/pboers1988))
- Tlc [\#8](https://github.com/workfloworchestrator/orchestrator-core/pull/8) ([hmvp](https://github.com/hmvp))
- Remove surf specific code. [\#7](https://github.com/workfloworchestrator/orchestrator-core/pull/7) ([pboers1988](https://github.com/pboers1988))

## [0.0.11](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.11) (2021-04-06)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.10...0.0.11)

## [0.0.10](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.10) (2021-04-01)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.9...0.0.10)

## [0.0.9](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.9) (2021-03-31)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.8...0.0.9)

**Merged pull requests:**

- Improve error handling [\#6](https://github.com/workfloworchestrator/orchestrator-core/pull/6) ([hmvp](https://github.com/hmvp))

## [0.0.8](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.8) (2021-03-31)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.7...0.0.8)

**Merged pull requests:**

- Add get\_relations function for subscriptions [\#5](https://github.com/workfloworchestrator/orchestrator-core/pull/5) ([freezas](https://github.com/freezas))

## [0.0.7](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.7) (2021-03-30)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.6...0.0.7)

## [0.0.6](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.6) (2021-03-30)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.5...0.0.6)

## [0.0.5](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.5) (2021-03-30)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.4...0.0.5)

## [0.0.4](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.4) (2021-03-30)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.3...0.0.4)

## [0.0.3](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.3) (2021-03-25)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.2...0.0.3)

## [0.0.2](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.2) (2021-03-25)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.2rc11...0.0.2)

**Merged pull requests:**

- Database interaction commands [\#4](https://github.com/workfloworchestrator/orchestrator-core/pull/4) ([pboers1988](https://github.com/pboers1988))
- Database setup changes [\#3](https://github.com/workfloworchestrator/orchestrator-core/pull/3) ([pboers1988](https://github.com/pboers1988))

## [0.0.2rc11](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.2rc11) (2021-03-24)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.2rc10...0.0.2rc11)

## [0.0.2rc10](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.2rc10) (2021-03-24)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.2rc9...0.0.2rc10)

## [0.0.2rc9](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.2rc9) (2021-03-24)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.2rc8...0.0.2rc9)

## [0.0.2rc8](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.2rc8) (2021-03-23)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.2rc6...0.0.2rc8)

## [0.0.2rc6](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.2rc6) (2021-03-23)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.2rc5...0.0.2rc6)

## [0.0.2rc5](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.2rc5) (2021-03-22)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.2rc4...0.0.2rc5)

## [0.0.2rc4](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.2rc4) (2021-03-22)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.2-rc3...0.0.2rc4)

## [0.0.2-rc3](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.2-rc3) (2021-03-18)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.2-rc2...0.0.2-rc3)

## [0.0.2-rc2](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.2-rc2) (2021-03-03)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.2-rc1...0.0.2-rc2)

## [0.0.2-rc1](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.2-rc1) (2021-02-25)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.1-rc3...0.0.2-rc1)

**Merged pull requests:**

- feat: Add methods to helpers.py to simplify data migrations [\#1](https://github.com/workfloworchestrator/orchestrator-core/pull/1) ([howderek](https://github.com/howderek))

## [0.0.1-rc3](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.1-rc3) (2021-02-24)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.1-rc2...0.0.1-rc3)

## [0.0.1-rc2](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.1-rc2) (2021-02-24)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/0.0.1-rc1...0.0.1-rc2)

## [0.0.1-rc1](https://github.com/workfloworchestrator/orchestrator-core/tree/0.0.1-rc1) (2021-02-24)

[Full Changelog](https://github.com/workfloworchestrator/orchestrator-core/compare/4bd2d5ca7160861223fefc8881a77fd1d4dfdbed...0.0.1-rc1)



\* *This Changelog was automatically generated by [github_changelog_generator](https://github.com/github-changelog-generator/github-changelog-generator)*
