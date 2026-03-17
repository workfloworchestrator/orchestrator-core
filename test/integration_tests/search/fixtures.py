# Copyright 2019-2025 SURF, GÉANT.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from uuid import UUID

from orchestrator.domain.lifecycle import ProductLifecycle
from orchestrator.types import SubscriptionLifecycle

# =============================================================================
# Product
# =============================================================================

TEST_PRODUCT = {
    "product_id": UUID("10000000-0000-0000-0000-000000000001"),
    "name": "Test Search Product",
    "description": "A simple product for search testing",
    "product_type": "TestSearch",
    "tag": "TEST_SEARCH",
    "status": ProductLifecycle.ACTIVE,
}

# =============================================================================
# Subscription IDs
# =============================================================================

# Commonly used subscription IDs for testing
PANCAKES_ID = UUID("20000000-0000-0000-0000-000000000018")
SHRIMP_SCAMPI_ID = UUID("20000000-0000-0000-0000-000000000022")  # Provisioning status

# =============================================================================
# Test Subscriptions
# =============================================================================

TEST_SUBSCRIPTIONS = [
    # Italian Cuisine
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000001"),
        "description": "Spicy Italian pasta with fresh tomatoes, basil, and parmesan cheese",
        "customer_id": UUID("30000000-0000-0000-0000-000000000001"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000002"),
        "description": "Classic Italian margherita pizza with mozzarella and fresh basil leaves",
        "customer_id": UUID("30000000-0000-0000-0000-000000000002"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000003"),
        "description": "Creamy Italian risotto with mushrooms and white wine reduction",
        "customer_id": UUID("30000000-0000-0000-0000-000000000003"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    # Desserts and Sweets
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000004"),
        "description": "Chocolate chip cookies with vanilla extract and brown sugar",
        "customer_id": UUID("30000000-0000-0000-0000-000000000004"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000005"),
        "description": "Rich chocolate cake with dark chocolate ganache and cocoa powder",
        "customer_id": UUID("30000000-0000-0000-0000-000000000005"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000006"),
        "description": "Vanilla cheesecake with strawberry topping and graham cracker crust",
        "customer_id": UUID("30000000-0000-0000-0000-000000000006"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    # Asian Cuisine
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000007"),
        "description": "Spicy Thai curry with coconut milk, lemongrass, and vegetables",
        "customer_id": UUID("30000000-0000-0000-0000-000000000007"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000008"),
        "description": "Japanese sushi rolls with fresh salmon, avocado, and cucumber",
        "customer_id": UUID("30000000-0000-0000-0000-000000000008"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000009"),
        "description": "Chinese fried rice with vegetables, eggs, and soy sauce",
        "customer_id": UUID("30000000-0000-0000-0000-000000000009"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    # Vegetarian and Healthy
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000010"),
        "description": "Vegetarian quinoa salad with chickpeas, cucumber, and lemon dressing",
        "customer_id": UUID("30000000-0000-0000-0000-000000000010"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000011"),
        "description": "Vegan Buddha bowl with tofu, sweet potato, and tahini sauce",
        "customer_id": UUID("30000000-0000-0000-0000-000000000011"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000012"),
        "description": "Fresh Greek salad with feta cheese, olives, and olive oil",
        "customer_id": UUID("30000000-0000-0000-0000-000000000012"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    # Mexican Cuisine
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000013"),
        "description": "Spicy Mexican tacos with grilled chicken, salsa, and guacamole",
        "customer_id": UUID("30000000-0000-0000-0000-000000000013"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000014"),
        "description": "Cheese quesadilla with peppers, onions, and sour cream",
        "customer_id": UUID("30000000-0000-0000-0000-000000000014"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    # American Classics
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000015"),
        "description": "Classic American burger with lettuce, tomato, and cheddar cheese",
        "customer_id": UUID("30000000-0000-0000-0000-000000000015"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000016"),
        "description": "BBQ pulled pork sandwich with coleslaw and pickles",
        "customer_id": UUID("30000000-0000-0000-0000-000000000016"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    # Breakfast Items
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000017"),
        "description": "French toast with maple syrup, butter, and fresh berries",
        "customer_id": UUID("30000000-0000-0000-0000-000000000017"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    {
        "subscription_id": PANCAKES_ID,
        "description": "Fluffy pancakes with blueberries and whipped cream",
        "customer_id": UUID("30000000-0000-0000-0000-000000000018"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    # Soups and Stews
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000019"),
        "description": "Hearty vegetable soup with carrots, celery, and herbs",
        "customer_id": UUID("30000000-0000-0000-0000-000000000019"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000020"),
        "description": "Creamy tomato soup with basil and croutons",
        "customer_id": UUID("30000000-0000-0000-0000-000000000020"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    # Seafood
    {
        "subscription_id": UUID("20000000-0000-0000-0000-000000000021"),
        "description": "Grilled salmon with lemon butter sauce and dill",
        "customer_id": UUID("30000000-0000-0000-0000-000000000021"),
        "insync": True,
        "status": SubscriptionLifecycle.ACTIVE,
    },
    {
        "subscription_id": SHRIMP_SCAMPI_ID,
        "description": "Shrimp scampi with garlic, white wine, and parsley",
        "customer_id": UUID("30000000-0000-0000-0000-000000000022"),
        "insync": False,
        "status": SubscriptionLifecycle.PROVISIONING,
    },
]

# =============================================================================
# Query Strings
# =============================================================================

QUERY_SPICY_ITALIAN = "spicy Italian food"
QUERY_CHOCOLATE_DESSERT = "chocolate dessert"
QUERY_VEGETARIAN_MEALS = "vegetarian meals"
QUERY_BREAKFAST_SYRUP = "breakfast with syrup"
QUERY_SALMON_LEMON = "salmon with lemon"
QUERY_CHEESE_PIZZA = "cheese pizza"
QUERY_ASIAN_CUISINE = "Asian cuisine"
QUERY_ITALIAN = "italian"
QUERY_CHOCOLATE = "chocolate"
QUERY_PANCAKES = "pancakes"

# =============================================================================
# Ground Truth Queries
# =============================================================================

# Ground truth queries used for recording embeddings, rankings, and testing
# All queries have embeddings and expected rankings recorded
GROUND_TRUTH_QUERIES = [
    # Multi-word queries (test semantic retriever)
    {
        "query_text": QUERY_SPICY_ITALIAN,
        "description": "Test semantic matching for cuisine type and flavor profile",
    },
    {
        "query_text": QUERY_CHOCOLATE_DESSERT,
        "description": "Test specific ingredient and category matching",
    },
    {
        "query_text": QUERY_VEGETARIAN_MEALS,
        "description": "Test dietary preference matching",
    },
    {
        "query_text": QUERY_ASIAN_CUISINE,
        "description": "Test regional cuisine classification",
    },
    {
        "query_text": QUERY_BREAKFAST_SYRUP,
        "description": "Test meal type and ingredient matching",
    },
    {
        "query_text": QUERY_SALMON_LEMON,
        "description": "Test specific dish and flavor pairing",
    },
    {
        "query_text": QUERY_CHEESE_PIZZA,
        "description": "Test common ingredient and dish type",
    },
    # Single-word queries (test hybrid retriever)
    {
        "query_text": QUERY_ITALIAN,
        "description": "Test hybrid retrieval for single-word cuisine query",
    },
    {
        "query_text": QUERY_CHOCOLATE,
        "description": "Test hybrid retrieval for single-word ingredient",
    },
    {
        "query_text": QUERY_PANCAKES,
        "description": "Test hybrid retrieval with exact match",
    },
]
