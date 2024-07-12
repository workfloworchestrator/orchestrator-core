# Setting up a development environment

To add features to the repository follow the following procedure to setup a working development environment.

### Installation (Development)
Install the project and its dependencies to develop on the code.

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


### Adding to the documentation
Documentation for the Orchestrator is written by using [Mkdocs](https://www.mkdocs.org/). To contribute to them
follow the instructions above to `step 2`, you can then develop them locally by running:

```bash
mkdocs serve
```

This should make the docs available on your local machine here: [http://127.0.0.1:8000/orchestrator-core/](http://127.0.0.1:8000/orchestrator-core/)

### Useful settings

#### SQLAlchemy logging

WFO uses [SQLAlchemy](https://www.sqlalchemy.org/) for its ORM and DB connection management capabilities.

To get information about which DB queries it is performing, adjust it's loglevel through this environment variable:

```bash
LOG_LEVEL_SQLALCHEMY_ENGINE=INFO
```

Set it to `DEBUG` for even more information.

**This generates a *lot* of logging! It is not recommended to use this in production.**
