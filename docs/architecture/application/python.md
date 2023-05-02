# Python versions

[![Supported Python versions](https://img.shields.io/pypi/pyversions/orchestrator-core.svg?color=%2334D058)](https://pypi.org/project/orchestrator-core)

The orchestrator is ensured to work with multiple versions of Python 3.

At SURF the orchestrator runs in a Docker image which makes updating the "installed python" as trivial as bumping the [base image](https://hub.docker.com/_/python/).
But not everyone can or wants to use containers.
To this end, the oldest supported Python version is chosen such that it can run on bare metal or virtual Linux servers, without the complexities and risks of compiling a newer version of Python.

## Adding support for new versions

We aim to add support for the latest Python 3 release within months of it becoming publicly available.

## Dropping support for old versions

Our policy is to support the same version of Python 3 available in [Debian-stable](https://packages.debian.org/stable/python3).

When there is a new Debian-stable release, we will update the oldest Python version supported by orchestator-core to match it.

## Example

At the time of writing (April 2023), the latest Debian is 11 which supports Python 3.9, and the latest Python 3.x release is 3.11. Thus the supported versions are: `3.9 3.10 3.11`

Debian 12's release is currently estimated for June 2023, and it looks like it will ship with Python 3.11. That means we can reduce the supported versions to: `3.11`

Python 3.12 is scheduled to release in October 2023, which we'll then add to the supported versions: `3.11 3.12`
