class SearchUtilsError(Exception):
    """Base exception for this module."""

    pass


class ProductNotInRegistryError(SearchUtilsError):
    """Raised when a product is not found in the model registry."""

    pass


class ModelLoadError(SearchUtilsError):
    """Raised when a Pydantic model fails to load from a subscription."""

    pass
