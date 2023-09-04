import strawberry


@strawberry.type
class DefaultCustomerType:
    fullname: str
    shortcode: str
    identifier: str
