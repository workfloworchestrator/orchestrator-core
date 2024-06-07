#!/bin/sh
#
# create new set of generated code
#

# exit on first failing command
set -e

# data folder should only contain a minimal main.py
cd generate

export PYTHONPATH=../../../../..

# generate alembic configuration and folders
python main.py db init

# generate code for the two sample products
for YAML in ../product_config2.yaml ../product_config1.yaml ../product_config4.yaml
do
    python main.py generate product-blocks --config-file $YAML --no-dryrun --force
    python main.py generate product --config-file $YAML --no-dryrun --force
    python main.py generate workflows --config-file $YAML --no-dryrun --force
    python main.py generate migration --config-file $YAML
    python main.py generate unit-tests --config-file $YAML --no-dryrun --force
done
