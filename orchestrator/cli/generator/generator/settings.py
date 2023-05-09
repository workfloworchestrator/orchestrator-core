from pydantic import BaseSettings


class ProductGeneratorSettings(BaseSettings):
    PRODUCT_TYPES_PATH = "surf/products/product_types"
    PRODUCT_BLOCKS_PATH = "surf/products/product_blocks"
    EMAIL_TEMPLATE_PATH = "surf/products/services/mail_templates/product_types"
    WORKFLOWS_PATH = "surf/workflows"
    TEST_PRODUCT_TYPE_PATH = "test/unit_tests/domain/product_types"
    TEST_WORKFLOWS_PATH = "test/unit_tests/workflows"

    # Files that will be updated
    PRODUCT_REGISTRY_PATH = "surf/products/__init__.py"
    SUBSCRIPTION_DESCRIPTION_PATH = "surf/products/services/subscription.py"
    TRANSLATION_PATH = "surf/translations/en-GB.json"
    MAIL_SINGLE_DISPATCH_PATH = "surf/products/services/mail.py"


product_generator_settings = ProductGeneratorSettings()
