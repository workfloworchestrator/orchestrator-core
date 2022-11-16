# MacOS version 12 (Monterey) installation instructions

How to install the orchestrator-core and orchestrator-core-gui on MacOS version
12 (Monterey) is described in the following steps.

### Step 1 - Install dependencies

This installation instruction assumes the use of [Homebrew](https://brew.sh/).
The following software dependencies need to be installed:

* Python 3.9
* PostgreSQL (version >=11)
* virtualenvwrapper (or use any other tool to create virtual Python 
  environments)
* Node.js (version 14)
* yarn

``` shell
brew install python@3.9 postgresql@13 virtualenvwrapper node@14 yarn
```

### Step 2 - Database setup

Start the database server and create the database with the following commands,
use `nwa` as password:

``` shell
brew services start postgresql@13
createuser -sP nwa
createdb orchestrator-core -O nwa
```

For debug purposes, interact directly with the database by starting the
PostgresSQL interactive terminal:

``` shell
psql orchestrator-core
```

### Step 3 - Install orchestrator

The minimal version of Python is 3.9. Create a Python virtual environment and
install the orchestrator-core:

```shell
mkdir beginner-workshop
cd beginner-workshop
source virtualenvwrapper.sh
mkvirtualenv --python python3.9 beginner-workshop
pip install orchestrator-core
```

The next time in a new shell only activate the existing Python virtual
environment:

```shell
source virtualenvwrapper.sh
workon beginner-workshop
```

### Step 4 - Init orchestrator:

Create a `main.py` file with the following content:

``` python
from orchestrator import OrchestratorCore
from orchestrator.cli.main import app as core_cli
from orchestrator.settings import AppSettings

app = OrchestratorCore(base_settings=AppSettings())

if __name__ == "__main__":
    core_cli()
```

Commit the just created main.py to git:

```shell
git init
# in case git was never used before, configure default branch, email and name
git config init.defaultBranch main
git config user.email "you@example.com"
git config user.name "Your Name"
# add and commit main.py
git add main.py
git commit -m "Initial commit"
```

Note that your local git must contain at least one commit because otherwise the
`db init` below will fail.

Initialize the database and run all the database migrations:

```shell
PYTHONPATH=. python main.py db init
PYTHONPATH=. python main.py db upgrade heads
```

### Step 5 - Install orchestrator client

Install the orchestrator client in the parent directory of the orchestrator:

```shell
cd ..
git clone https://github.com/workfloworchestrator/orchestrator-core-gui.git
```

When multiple version of Node.js are installed, make sure node@14 is being
used, this can be achieved by explicitly prepending it to the shell PATH.  Use
the Yarn package manager to install the orchestrator client dependencies:

```shell
cd orchestrator-core-gui/
export PATH="/usr/local/opt/node@14/bin:$PATH"
yarn install
```

### Step 6 - Init orchestrator client:

Use the supplied environment variable defaults:

```shell
cp .env.local.example .env.local
```

And make the following changes:

```shell
# change the existing REACT_APP_BACKEND_URL variable value into:
REACT_APP_BACKEND_URL=http://127.0.0.1:3000
# and add the following:
DANGEROUSLY_DISABLE_HOST_CHECK=true
```

The `custom-example` folder contains some SURF specific modules that can be
used as an example. It must be linked to the folder `custom` in order for the
app to start:

```shell
(cd src && ln -s custom-example custom)
```
