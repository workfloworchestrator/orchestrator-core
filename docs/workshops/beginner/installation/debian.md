# Debian 11 (bullseye) installation instructions

How to install the orchestrator-core and orchestrator-core-gui on Debian 11 
(Bullseye) is described in the following steps.

### Step 1 - Install dependencies

First make sure the debian install is up to date. Then install the following
software dependencies:

* PostgreSQL (version >=11)
* Git
* virtualenvwrapper
* Node.js (version 14)

``` shell
sudo apt update
sudo apt upgrade --yes
curl -sL https://deb.nodesource.com/setup_14.x | sudo bash -
sudo apt-get install --yes postgresql git virtualenvwrapper nodejs
```

### Step 2 - Database setup

In step 1 the database server is already started as part of the apt
installation procedure. If the database server was previously installed and
stopped then start it again. Create the database with the following commands,
use `nwa` as password:

``` shell
sudo -u postgres createuser -sP nwa
sudo -u postgres createdb orchestrator-core -O nwa
```

For debug purposes, interact directly with the database start the PostgresSQL
interactive terminal:

``` shell
sudo -u postgres psql orchestrator-core
```

### Step 3 - Install orchestrator

The minimal version of Python is 3.9. Create a Python virtual environment and
install the orchestrator-core:

```shell
mkdir beginner-workshop
cd beginner-workshop
source /usr/share/virtualenvwrapper/virtualenvwrapper.sh
mkvirtualenv --python python3.9 beginner-workshop
pip install orchestrator-core
```

The next time in a new shell only activate the existing Python virtual
environment:

```shell
source /usr/share/virtualenvwrapper/virtualenvwrapper.sh
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

Install the Yarn package manager and use it to install the orcestrator 
client dependencies:

```shell
cd orchestrator-core-gui/
sudo npm install --global yarn
sudo npm install --global --save-dev npm-run-all
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
REACT_APP_BACKEND_URL=http://your_ip_address_here:3000
# and add the following:
DANGEROUSLY_DISABLE_HOST_CHECK=true
```

The `custom-example` folder contains some SURF specific modules that can be
used as an example. It must be linked to the folder `custom` in order for the
app to start:

```shell
(cd src && ln -s custom-example custom)
```
