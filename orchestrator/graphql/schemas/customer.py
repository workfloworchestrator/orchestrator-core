import strawberry


@strawberry.federation.type(keys=["customerId"])
class CustomerType:
    customer_id: str
    fullname: str
    shortcode: str
