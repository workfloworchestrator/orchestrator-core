from orchestrator.api.helpers import product_block_paths


def test_product_block_paths(sub_list_union_overlap_subscription_1):
    paths = product_block_paths(sub_list_union_overlap_subscription_1)
    assert paths == [
        "product",
        "test_block.sub_block",
        "test_block.sub_block_2",
        "test_block.sub_block_list.0",
        "test_block",
        "list_union_blocks.0",
        "list_union_blocks.1",
    ]
