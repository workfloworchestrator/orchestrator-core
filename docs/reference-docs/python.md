# Python versions

[![Supported Python versions](https://img.shields.io/pypi/pyversions/orchestrator-core.svg?color=%2334D058)](https://pypi.org/project/orchestrator-core)

The orchestrator is ensured to work with multiple versions of Python 3. Currently the recommended version is 3.13.

One of the build artifacts of the orchestrator is a Docker image that can be used to run the orchestrator. This image is
based off the [official Python 3.13 image](https://hub.docker.com/_/python).

You can run this image as follows:
```bash
docker run -it docker pull ghcr.io/workfloworchestrator/orchestrator-core:latest
```

### Running it in a different way
Not everyone can or wants to use containers.
To this end, the oldest supported Python version is chosen such that it can run on bare metal or virtual Linux servers,
without the complexities and risks of compiling a newer version of Python.

## Adding support for new versions

We aim to add support for the latest Python 3 release within months of it becoming publicly available.

## Dropping support for old versions

Our policy is to support the same version of Python 3 available in [Debian-stable](https://packages.debian.org/stable/python3) and [Debian-oldstable](https://packages.debian.org/oldstable/python3).

When there is a new Debian-stable release, we will update the oldest Python version supported by orchestator-core to match it.

## Example

At the time of writing (April 2026), the latest Old Stable is `bookwork` which supports Python 3.11, and the latest Python 3.x release is 3.14. Thus the supported versions are: `3.11 - 3.14`

We expect to support Python 3.15 in the future.
