# Changelog

All notable changes to this project will be documented in this file.
Please add a line to the unrelease section for every feature. If possible
reference the gitlab/github issue that is related to the change.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0-rc1] - 2021-12-22
### Breaking changes
- SQL-alchemy 1.4.x
- Refactored models to be compatible with SQL-Alchemy 1.4.x
- Minimum requirement of Postgres 12

### Features
- Python 3.10 support
- Pydantic v1.9.0a1
- Updated schemas to support Pydantic v1.9.0
- Implemented Websockets on Process detail, process-list and engine settings
- Precommit hook updates
- Nitpick updates
- Removal of deprecated functions, `change_subscription_lifecycle` and `get_product`


## [0.2.0] - 2021-10-25

### Breaking changes
- Added explicit `subscription_id` parameter to the ProductBlockModel.
- You must add a `product_block_relation` entry to the database if you need to stack product blocks in a domain model
- Some changes in helper functions

### Features
- Introduced hierarchical relationships across subscription boundaries
- Added some documentation
- Added new form field that gives the ability to add a divider to forms
- Better handling of empty optional fields
- Added websocket failed task banner.

## [0.0.21] - 2021-09-22
- Improved docs
- Allow pip -e installable packages.

## [0.0.20] - 2021-08-05

### Bugfix
- fix bug in saving subscriptions, we now explicitly refresh mapped objects.


## [0.0.19] - 2021-07-19

### Added

- Work with python 3.9

### Changed

- Don't add transitive subscription instance relations to parents of parents (this was unintended behaviour)

## [0.0.18] - 2021-07-09

### Added

- Add support for Abstract ProductBlockModels to abstract over common properties (If multiple types of parts are similar and you dont care about the concrete type)

## [0.0.17]

- TLC for python 3.9

## [older versions]

- Fixed database intialisation
- Project scaffolding
