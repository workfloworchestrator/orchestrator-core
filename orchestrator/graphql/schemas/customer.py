import strawberry


@strawberry.type
class CustomerType:
    customer_id: str
    fullname: str
    shortcode: str
