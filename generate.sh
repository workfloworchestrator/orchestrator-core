#!/bin/bash

# folders for generated code
export PRODUCT_TYPES_PATH="products/product_types"
export PRODUCT_BLOCKS_PATH="products/product_blocks"
export WORKFLOWS_PATH="workflows"
export TEST_PRODUCT_TYPE_PATH="test/unit_tests/domain/product_types"
export TEST_WORKFLOWS_PATH="test/unit_tests/workflows"
# files that are updated
export PRODUCT_REGISTRY_PATH="products/__init__.py"
export SUBSCRIPTION_DESCRIPTION_PATH="products/services/subscription.py"
TRANSLATION_FOLDER="translations"
export TRANSLATION_PATH="${TRANSLATION_FOLDER}/en-GB.json"

mkdir -pv "${PRODUCT_TYPES_PATH}" "${PRODUCT_BLOCKS_PATH}" "${WORKFLOWS_PATH}" "${TEST_PRODUCT_TYPE_PATH}" "${TEST_WORKFLOWS_PATH}" "${TRANSLATION_FOLDER}"

WORKFLOWS_INIT_FILE="${WORKFLOWS_PATH}/__init__.py"
if test ! -f "${WORKFLOWS_INIT_FILE}"
then
    echo "from orchestrator.workflows import LazyWorkflowInstance" >> "${WORKFLOWS_INIT_FILE}"
fi

for CONFIG_FILE in /Users/hanst/Sources/workfloworchestrator/example-orchestrator-advanced/product_models/*.yaml
#for CONFIG_FILE in product_models/circuit.yaml
do
    PYTHONPATH=. python ./orchestrator/cli/main.py generate product --config-file "${CONFIG_FILE}" --no-dryrun --force
    PYTHONPATH=. python ./orchestrator/cli/main.py generate product-blocks --config-file "${CONFIG_FILE}" --no-dryrun --force
    PYTHONPATH=. python ./orchestrator/cli/main.py generate workflows --config-file "${CONFIG_FILE}" --no-dryrun --force
    PYTHONPATH=. python ./orchestrator/cli/main.py generate migration --config-file "${CONFIG_FILE}" --no-dryrun --force
    PYTHONPATH=. python ./orchestrator/cli/main.py generate unit-tests --config-file "${CONFIG_FILE}" --no-dryrun --force
done
