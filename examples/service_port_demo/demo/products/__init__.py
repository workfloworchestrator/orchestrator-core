from demo.products.product_types.sp import ServicePort
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY

SUBSCRIPTION_MODEL_REGISTRY.update(
    {
        "service-port": ServicePort,
    }
)