from products.product_blocks.example1 import AnnotatedInt, ExampleStrEnum1


def must_be_unused_to_change_mode_validator(example_str_enum_1: ExampleStrEnum1) -> ExampleStrEnum1:
    if False:  # TODO: implement validation for example_str_enum_1
        raise ValueError("Mode can only be changed when there are no services attached to it")

    return example_str_enum_1


def annotated_int_must_be_unique_validator(annotated_int: AnnotatedInt) -> AnnotatedInt:
    if False:  # TODO: implement validation for annotated_int
        raise ValueError("annotated_int must be unique for example1")

    return annotated_int
