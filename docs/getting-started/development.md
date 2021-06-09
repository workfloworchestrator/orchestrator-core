# Setting up a development environment

To add features to the repository follow the following procedure to setup a working development environment.

## Installation (Development)
Install the project and its dependancies to develop on the code.

### Step 1 - install flit:
```console
pip install flit
```

### Step 2 - install the development code:
```console
flit install --deps develop --symlink
```

## Running tests
Run the unit-test suite to verify a correct setup.

### Step 1 - Create a database

```console
createuser -sP nwa
createdb orchestrator-core-test -O nwa
```

### Step 2 - Run tests
```console
pytest test/unit_tests
```

If you do not encounter any failures in the test, you should be able to develop features in the orchestrator-core.
