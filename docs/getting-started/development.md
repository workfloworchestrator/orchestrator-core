# Setting up a development environment

To add features to the repository follow the following procedure to setup a working development environment.

### Installation (Development)
Install the project and its dependancies to develop on the code.

#### Step 1 - install flit:
``` shell
pip install flit
```

#### Step 2 - install the development code:
``` shell
flit install --deps develop --symlink
```

!!! danger
    Make sure to use the flit binary that is installed in your environment. You can check the correct
    path by running
    ``` shell
    which flit
    ```

### Running tests
Run the unit-test suite to verify a correct setup.

#### Step 1 - Create a database

``` shell
createuser -sP nwa
createdb orchestrator-core-test -O nwa
```

#### Step 2 - Run tests
``` shell
pytest test/unit_tests
```

If you do not encounter any failures in the test, you should be able to develop features in the orchestrator-core.
