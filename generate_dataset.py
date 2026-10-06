import json
import os

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()


def save_to_database(df):
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        database=os.getenv("POSTGRES_DB", "postgres"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "password"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
    )
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    product_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    price NUMERIC(10, 2) NOT NULL,
                    stock_quantity INTEGER NOT NULL,
                    rating REAL NOT NULL,
                    description TEXT NOT NULL,
                    description_vector vector(384) NOT NULL
                )
            """)
            cur.executemany("""
                INSERT INTO products (
                    product_id, name, category, price, stock_quantity, rating,
                    description, description_vector
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (product_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    category = EXCLUDED.category,
                    price = EXCLUDED.price,
                    stock_quantity = EXCLUDED.stock_quantity,
                    rating = EXCLUDED.rating,
                    description = EXCLUDED.description,
                    description_vector = EXCLUDED.description_vector
            """, [
                (
                    row.product_id, row.name, row.category, row.price,
                    row.stock_quantity, row.rating, row.description,
                    row.description_vector,
                )
                for row in df.itertuples(index=False)
            ])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# 1. Create a small, highly semantic sample dataset with 100 products.
products_list = [
    # Category: Breakfast & Cereals
    {"product_id": 1, "name": "Organic Rolled Oats", "category": "Breakfast", "price": 5.99, "stock_quantity": 120, "rating": 4.7, "description": "Whole grain rolled oats, perfect for a healthy high-fiber breakfast."},
    {"product_id": 2, "name": "Gluten-Free Granola", "category": "Breakfast", "price": 8.50, "stock_quantity": 45, "rating": 4.5, "description": "Crunchy gluten-free oats toasted with honey, almonds, and dried cranberries."},
    {"product_id": 3, "name": "Honey Almond Muesli", "category": "Breakfast", "price": 7.25, "stock_quantity": 60, "rating": 4.2, "description": "A rustic blend of raw rolled oats, sliced almonds, raisins, and a touch of wild honey."},
    {"product_id": 4, "name": "Chia Seed Protein Porridge", "category": "Breakfast", "price": 11.99, "stock_quantity": 30, "rating": 4.6, "description": "Warm morning cereal packed with superfood omega-3 chia seeds and plant protein."},
    {"product_id": 5, "name": "Instant Maple Oatmeal Packs", "category": "Breakfast", "price": 4.50, "stock_quantity": 200, "rating": 4.0, "description": "Quick-cooking sweetened porridge with natural maple syrup flavor for busy mornings."},
    {"product_id": 6, "name": "Crispy Bran Flakes", "category": "Breakfast", "price": 5.20, "stock_quantity": 85, "rating": 3.9, "description": "High-density wheat bran flakes designed for optimal digestive health and morning fiber."},
    {"product_id": 7, "name": "Puffed Quinoa Cereal", "category": "Breakfast", "price": 6.80, "stock_quantity": 40, "rating": 4.1, "description": "Light, crispy whole grain quinoa puffs, completely sugar-free and allergen-friendly."},
    {"product_id": 8, "name": "Freeze-Dried Strawberry Cereal", "category": "Breakfast", "price": 7.99, "stock_quantity": 55, "rating": 4.4, "description": "Corn and oat flakes mixed with tart, crispy real strawberry slices."},
    {"product_id": 9, "name": "Steel Cut Irish Oats", "category": "Breakfast", "price": 6.50, "stock_quantity": 70, "rating": 4.8, "description": "Coarsely chopped whole oat groats for a thick, hearty, and chewy morning porridge."},
    {"product_id": 10, "name": "Cinnamon Buckwheat Flakes", "category": "Breakfast", "price": 7.10, "stock_quantity": 25, "rating": 4.3, "description": "Ancient grain buckwheat cereal seasoned with organic Ceylon cinnamon."},

    # Category: Dairy & Alternatives
    {"product_id": 11, "name": "Greek Yogurt (0% Fat)", "category": "Dairy", "price": 4.99, "stock_quantity": 150, "rating": 4.8, "description": "Thick and creamy strained yogurt, high protein and low sugar dessert or snack."},
    {"product_id": 12, "name": "Organic Whole Milk", "category": "Dairy", "price": 3.80, "stock_quantity": 90, "rating": 4.6, "description": "Rich and creamy pasteurized whole cow's milk sourced from grass-fed local farms."},
    {"product_id": 13, "name": "Unsweetened Almond Milk", "category": "Dairy", "price": 3.99, "stock_quantity": 110, "rating": 4.3, "description": "A light, nutty plant-based milk alternative with zero added sugar and minimal calories."},
    {"product_id": 14, "name": "Oat Milk Barista Edition", "category": "Dairy", "price": 5.50, "stock_quantity": 75, "rating": 4.9, "description": "Extra creamy plant milk formulated to steam and foam perfectly for coffee and lattes."},
    {"product_id": 15, "name": "Grass-Fed Salted Butter", "category": "Dairy", "price": 6.25, "stock_quantity": 40, "rating": 4.7, "description": "Churned cream butter with a rich golden hue and a delicate touch of sea salt."},
    {"product_id": 16, "name": "Cottage Cheese (Low Fat)", "category": "Dairy", "price": 5.10, "stock_quantity": 65, "rating": 4.4, "description": "Curd cheese high in casein protein, ideal for bodybuilders and evening healthy snacks."},
    {"product_id": 17, "name": "Aged White Cheddar Blocks", "category": "Dairy", "price": 8.99, "stock_quantity": 50, "rating": 4.6, "description": "Sharp, sharp-flavored dairy cheese aged for 12 months for maximum complexity."},
    {"product_id": 18, "name": "Organic Sour Cream", "category": "Dairy", "price": 3.50, "stock_quantity": 80, "rating": 4.2, "description": "Tangy and rich cultured cream paste, perfect for baking or topping savory dishes."},
    {"product_id": 19, "name": "Coconut Cream Yogurt", "category": "Dairy", "price": 6.00, "stock_quantity": 35, "rating": 4.1, "description": "A dairy-free, rich vegan yogurt alternative fermented from pure pressed coconut milk."},
    {"product_id": 20, "name": "Grated Parmesan Cheese", "category": "Dairy", "price": 7.50, "stock_quantity": 100, "rating": 4.5, "description": "Authentic Italian hard cheese finely grated for dusting over pasta and fresh salads."},

    # Category: Bakery & Low-Carb
    {"product_id": 21, "name": "Keto Almond Flour Bread", "category": "Bakery", "price": 9.99, "stock_quantity": 20, "rating": 4.4, "description": "Low carb, high fat bread made with almond flour. Perfect for a keto diet."},
    {"product_id": 22, "name": "Sourdough Boule", "category": "Bakery", "price": 6.50, "stock_quantity": 15, "rating": 4.8, "description": "Artisanal crusty bread naturally fermented using a wild yeast starter culture."},
    {"product_id": 23, "name": "Whole Wheat Tortillas", "category": "Bakery", "price": 3.99, "stock_quantity": 140, "rating": 4.1, "description": "Soft, high-fiber flatbread wraps ideal for clean eating burritos or sandwich wraps."},
    {"product_id": 24, "name": "Flaxseed Protein Bagels", "category": "Bakery", "price": 7.40, "stock_quantity": 28, "rating": 4.3, "description": "Dense, chewy morning bakery bagels boosted with ground flaxseeds and pea isolate protein."},
    {"product_id": 25, "name": "Gluten-Free Brown Rice Bread", "category": "Bakery", "price": 8.20, "stock_quantity": 22, "rating": 3.8, "description": "Soft sliced sandwich bread engineered for wheat sensitivities and allergies."},
    {"product_id": 26, "name": "Brioche Hamburger Buns", "category": "Bakery", "price": 5.99, "stock_quantity": 45, "rating": 4.6, "description": "Sweet, buttery, and soft French-style enriched bread buns for gourmet burgers."},
    {"product_id": 27, "name": "Sprouted Grain Seed Bread", "category": "Bakery", "price": 8.75, "stock_quantity": 30, "rating": 4.7, "description": "Living grain bread loaded with sprouted chia, sesame, sunflower, and pumpkin seeds."},
    {"product_id": 28, "name": "French Butter Croissants", "category": "Bakery", "price": 4.80, "stock_quantity": 12, "rating": 4.9, "description": "Flaky, laminated multi-layered pastry with an intense rich buttery aroma."},
    {"product_id": 29, "name": "Low-GI Oats & Honey Loaf", "category": "Bakery", "price": 6.10, "stock_quantity": 50, "rating": 4.2, "description": "Sandwich bread designed with a slow glycemic release to avoid blood sugar spikes."},
    {"product_id": 30, "name": "Almond Flour Blueberry Muffins", "category": "Bakery", "price": 7.99, "stock_quantity": 18, "rating": 4.5, "description": "Moist, grain-free sweet bakery treats sweetened with stevia for diabetic diets."},

    # Category: Supplements & Fitness Fuel
    {"product_id": 31, "name": "Whey Isolate Protein Powder", "category": "Supplements", "price": 45.99, "stock_quantity": 40, "rating": 4.8, "description": "Pure vanilla whey protein isolate for post-workout muscle recovery and gym fuel."},
    {"product_id": 32, "name": "Plant Protein Powder (Chocolate)", "category": "Supplements", "price": 39.99, "stock_quantity": 35, "rating": 4.5, "description": "Vegan friendly protein blend made from organic peas, brown rice, and hemp seeds."},
    {"product_id": 33, "name": "Creatine Monohydrate Pure", "category": "Supplements", "price": 24.99, "stock_quantity": 80, "rating": 4.9, "description": "Unflavored powder to increase cellular energy, athletic power, and workout performance."},
    {"product_id": 34, "name": "Pre-Workout Energy Powder", "category": "Supplements", "price": 34.99, "stock_quantity": 50, "rating": 4.3, "description": "High-caffeine formula with beta-alanine to boost focus, endurance, and gym stamina."},
    {"product_id": 35, "name": "BCAA Hydration Mix", "category": "Supplements", "price": 21.50, "stock_quantity": 65, "rating": 4.4, "description": "Branched-chain amino acids with added electrolytes for intra-workout muscle endurance."},
    {"product_id": 36, "name": "Hydrolyzed Collagen Peptides", "category": "Supplements", "price": 29.99, "stock_quantity": 70, "rating": 4.6, "description": "Dissolvable flavorless powder targeted at joint health, radiant skin, and hair thickness."},
    {"product_id": 37, "name": "Vegan Omega-3 Algae Oil", "category": "Supplements", "price": 26.00, "stock_quantity": 45, "rating": 4.7, "description": "Plant-derived DHA and EPA fatty acid softgels supporting brain health without fish burps."},
    {"product_id": 38, "name": "Magnesium Glycinate Capsules", "category": "Supplements", "price": 18.99, "stock_quantity": 110, "rating": 4.8, "description": "Highly absorbable mineral supplement to reduce muscle cramps and promote deep sleep."},
    {"product_id": 39, "name": "Organic Wheatgrass Powder", "category": "Supplements", "price": 22.50, "stock_quantity": 30, "rating": 4.1, "description": "Dehydrated green superfood juice powder packed with chlorophyll and trace minerals."},
    {"product_id": 40, "name": "High-Potency Vitamin D3+K2", "category": "Supplements", "price": 19.99, "stock_quantity": 130, "rating": 4.7, "description": "Liquid softgels calibrated for bone strength, arterial health, and immune support."},

    # Category: Snacks & Guilt-Free Sweets
    {"product_id": 41, "name": "Dark Chocolate Almonds", "category": "Snacks", "price": 6.99, "stock_quantity": 140, "rating": 4.6, "description": "Roasted almonds coated in 70% dark chocolate. A guilt-free sweet treat."},
    {"product_id": 42, "name": "Sea Salt Baked Rice Crisps", "category": "Snacks", "price": 3.49, "stock_quantity": 220, "rating": 4.0, "description": "Light, crunchy air-popped savory crackers, exceptionally low in total fats and calories."},
    {"product_id": 43, "name": "Spicy Barbecue Beef Jerky", "category": "Snacks", "price": 8.99, "stock_quantity": 60, "rating": 4.5, "description": "Premium lean grass-fed beef strips cured in a smoky hot chili marinade."},
    {"product_id": 44, "name": "Organic Air-Popped Popcorn", "category": "Snacks", "price": 4.20, "stock_quantity": 100, "rating": 4.3, "description": "Whole grain corn kernels popped with minimal coconut oil and dusted with pink salt."},
    {"product_id": 45, "name": "Roasted Salted Pistachios", "category": "Snacks", "price": 9.50, "stock_quantity": 75, "rating": 4.8, "description": "Whole in-shell premium nuts, rich in healthy fats, fiber, and heart-healthy antioxidants."},
    {"product_id": 46, "name": "Salt & Vinegar Seaweed Snacks", "category": "Snacks", "price": 2.99, "stock_quantity": 180, "rating": 4.2, "description": "Paper-thin crispy roasted nori sheets seasoned with a tangy, low-calorie punch."},
    {"product_id": 47, "name": "Baked Apple Cinnamon Chips", "category": "Snacks", "price": 5.30, "stock_quantity": 50, "rating": 4.1, "description": "Dehydrated sweet apple slices with zero added sugars or preservatives."},
    {"product_id": 48, "name": "Peanut Butter Protein Bar", "category": "Snacks", "price": 3.50, "stock_quantity": 250, "rating": 4.4, "description": "Chewy, dense meal replacement bar engineered to give slow-burning athletic energy."},
    {"product_id": 49, "name": "Cheddar Cheese Baked Crackers", "category": "Snacks", "price": 4.10, "stock_quantity": 115, "rating": 4.2, "description": "Crispy savory snack biscuits made with genuine aged cheese and unbleached flour."},
    {"product_id": 50, "name": "Freeze-Dried Mango Bites", "category": "Snacks", "price": 6.50, "stock_quantity": 40, "rating": 4.6, "description": "Crunchy fruit bites capturing the intense sweet tropical flavor of ripe mangoes."},

    # Category: Condiments, Oils & Sauces
    {"product_id": 51, "name": "Avocado Mayo", "category": "Condiments", "price": 7.99, "stock_quantity": 65, "rating": 4.5, "description": "Creamy mayonnaise made with pure avocado oil, zero sugar, keto friendly."},
    {"product_id": 52, "name": "Sriracha Hot Chilli Sauce", "category": "Condiments", "price": 4.50, "stock_quantity": 130, "rating": 4.7, "description": "Spicy chili pepper paste with garlic, adds a fiery kick to any meal."},
    {"product_id": 53, "name": "Extra Virgin Olive Oil", "category": "Condiments", "price": 14.99, "stock_quantity": 85, "rating": 4.8, "description": "Cold-pressed Mediterranean cooking oil, rich in monounsaturated fats and polyphenols."},
    {"product_id": 54, "name": "Organic Apple Cider Vinegar", "category": "Condiments", "price": 5.99, "stock_quantity": 90, "rating": 4.4, "description": "Raw unfiltered vinegar containing the beneficial probiotic 'mother' culture."},
    {"product_id": 55, "name": "Low-Sodium Soy Sauce", "category": "Condiments", "price": 3.75, "stock_quantity": 110, "rating": 4.3, "description": "Traditionally brewed savory umami condiment with 40% less salt than standard versions."},
    {"product_id": 56, "name": "Dijon Mustard with White Wine", "category": "Condiments", "price": 4.99, "stock_quantity": 70, "rating": 4.2, "description": "Sharp, spicy French mustard blended with real chardonnay for gourmet dressings."},
    {"product_id": 57, "name": "Pure Organic Maple Syrup", "category": "Condiments", "price": 12.50, "stock_quantity": 40, "rating": 4.8, "description": "Grade-A dark amber tree sap syrup with an intense, unrefined caramel sweetness."},
    {"product_id": 58, "name": "Unrefined Organic Coconut Oil", "category": "Condiments", "price": 8.40, "stock_quantity": 55, "rating": 4.5, "description": "Cold-pressed aromatic cooking fat, excellent for vegan baking or high-heat frying."},
    {"product_id": 59, "name": "Garlic Infused Hot Honey", "category": "Condiments", "price": 10.99, "stock_quantity": 30, "rating": 4.6, "description": "Sweet wildflower honey steeped with ghost peppers and crushed roasted garlic."},
    {"product_id": 60, "name": "Balsamic Glaze of Modena", "category": "Condiments", "price": 9.25, "stock_quantity": 45, "rating": 4.7, "description": "Thick, sweet, reduced vinegar syrupy glaze for drizzling on caprese salads and pizzas."},

    # Category: Beverages & Refreshments
    {"product_id": 61, "name": "Double Espresso Cold Brew", "category": "Beverages", "price": 4.50, "stock_quantity": 80, "rating": 4.6, "description": "Strong black unsweetened coffee over ice for an intense energy boost."},
    {"product_id": 62, "name": "Chamomile Herbal Tea", "category": "Beverages", "price": 5.20, "stock_quantity": 120, "rating": 4.7, "description": "Calming organic herbal tea, naturally caffeine-free for late night relaxation."},
    {"product_id": 63, "name": "Organic Ceremonial Matcha", "category": "Beverages", "price": 24.99, "stock_quantity": 25, "rating": 4.9, "description": "Finely ground Japanese green tea powder, rich in clean l-theanine focused energy."},
    {"product_id": 64, "name": "Sparkling Lime Kombucha", "category": "Beverages", "price": 3.99, "stock_quantity": 60, "rating": 4.4, "description": "Fermented living tea effervescent with active gut-friendly probiotics and lime."},
    {"product_id": 65, "name": "Electrolyte Coconut Water", "category": "Beverages", "price": 2.99, "stock_quantity": 140, "rating": 4.5, "description": "Pure isotonic tropical liquid directly from fresh young coconuts for hydration."},
    {"product_id": 66, "name": "Ginger Lemon Herbal Tonic", "category": "Beverages", "price": 4.00, "stock_quantity": 50, "rating": 4.3, "description": "Spicy, warming juice immunity shot featuring fresh ginger root and squeezed lemons."},
    {"product_id": 67, "name": "Sparkling Mineral Water", "category": "Beverages", "price": 1.99, "stock_quantity": 200, "rating": 4.6, "description": "Crisp carbonated spring water bottled at the source with zero artificial sweeteners."},
    {"product_id": 68, "name": "Earl Grey Bergamot Black Tea", "category": "Beverages", "price": 5.50, "stock_quantity": 95, "rating": 4.4, "description": "Bold black tea leaves scented with the refined oil of Italian citrus bergamot fruits."},
    {"product_id": 69, "name": "Sugar-Free Energy Drink", "category": "Beverages", "price": 3.25, "stock_quantity": 160, "rating": 4.1, "description": "Carbonated focus beverage packed with B-vitamins, taurine, and high dose caffeine."},
    {"product_id": 70, "name": "Roasted Dandelion Root Coffee", "category": "Beverages", "price": 6.99, "stock_quantity": 40, "rating": 4.2, "description": "An herbal, earthy caffeine-free substitute that mimics the deep flavor profile of espresso."},

    # Category: Grains, Pasta & Plant Carbs
    {"product_id": 71, "name": "Organic Quinoa Grain Mix", "category": "Grains", "price": 6.99, "stock_quantity": 90, "rating": 4.6, "description": "Tri-color complete plant-based protein ancient seeds, great substitute for white rice."},
    {"product_id": 72, "name": "Brown Jasmine Rice", "category": "Grains", "price": 5.50, "stock_quantity": 100, "rating": 4.4, "description": "Long-grain aromatic whole rice containing all its natural nutrient-dense bran layers."},
    {"product_id": 73, "name": "Red Lentil Penne Pasta", "category": "Grains", "price": 4.99, "stock_quantity": 75, "rating": 4.5, "description": "Grain-free, gluten-free pasta high in natural iron and clean legume plant protein."},
    {"product_id": 74, "name": "Basmati White Rice Premium", "category": "Grains", "price": 7.99, "stock_quantity": 120, "rating": 4.7, "description": "Fluffy, fragrant long-grain rice curated specifically for Indian and Middle Eastern curries."},
    {"product_id": 75, "name": "Organic Black Chia Seeds", "category": "Grains", "price": 5.99, "stock_quantity": 80, "rating": 4.5, "description": "Hydrophilic tiny seeds that expand into a gel, rich in fiber and alpha-linolenic acids."},
    {"product_id": 76, "name": "Hemp Seed Hearts (Shelled)", "category": "Grains", "price": 8.99, "stock_quantity": 45, "rating": 4.8, "description": "Raw shelled nutty seeds bursting with essential fatty acids and clean plant nutrition."},
    {"product_id": 77, "name": "Whole Wheat Spaghetti", "category": "Grains", "price": 2.49, "stock_quantity": 150, "rating": 4.3, "description": "Traditional Italian long noodles extruded from high-fiber durum wheat semolina flour."},
    {"product_id": 78, "name": "Pearl Couscous (Israeli)", "category": "Grains", "price": 3.99, "stock_quantity": 60, "rating": 4.2, "description": "Toasted giant wheat pasta spheres that present a delightfully chewy texture when steamed."},
    {"product_id": 79, "name": "Organic Amaranth Grain", "category": "Grains", "price": 5.80, "stock_quantity": 35, "rating": 4.0, "description": "Tiny ancient Aztec grain with an earthy flavor profile, ideal for hot porridge or baking."},
    {"product_id": 80, "name": "Wild Rice Artisan Blend", "category": "Grains", "price": 7.50, "stock_quantity": 50, "rating": 4.4, "description": "A mix of long-grain dark aquatic grass seeds and brown rice for complex textures."},

    # Category: Proteins & Fresh Meats / Seafood
    {"product_id": 81, "name": "Grass-Fed Ribeye Steak", "category": "Proteins", "price": 18.99, "stock_quantity": 25, "rating": 4.9, "description": "Premium marbled beef cut pasture-raised without antibiotics, high in iron and protein."},
    {"product_id": 82, "name": "Organic Boneless Chicken Breast", "category": "Proteins", "price": 9.50, "stock_quantity": 55, "rating": 4.6, "description": "Lean, skinless fresh poultry breast meat, the staple protein source for muscle growth."},
    {"product_id": 83, "name": "Wild-Caught Alaskan Salmon", "category": "Proteins", "price": 14.99, "stock_quantity": 20, "rating": 4.8, "description": "Fresh cold-water fish fillet dense with anti-inflammatory omega-3 fatty marine oils."},
    {"product_id": 84, "name": "Extra Firm Organic Tofu", "category": "Proteins", "price": 3.25, "stock_quantity": 90, "rating": 4.4, "description": "Pressed soybean curd block, an adaptable vegan protein source that absorbs sauces well."},
    {"product_id": 85, "name": "Lean Ground Turkey (93%)", "category": "Proteins", "price": 6.99, "stock_quantity": 40, "rating": 4.2, "description": "Fresh ground white turkey poultry meat, a low-fat substitute for traditional beef burgers."},
    {"product_id": 86, "name": "Fresh Tiger Prawns (Shelled)", "category": "Proteins", "price": 12.99, "stock_quantity": 30, "rating": 4.5, "description": "Succulent seafood shrimp, extremely low calorie and cooking incredibly fast in a pan."},
    {"product_id": 87, "name": "Pasture-Raised Large Eggs", "category": "Proteins", "price": 5.50, "stock_quantity": 110, "rating": 4.8, "description": "Fresh farm eggs with rich orange yolks, providing an ideal bioavailable nutrient profile."},
    {"product_id": 88, "name": "Smoked Salmon Slices", "category": "Proteins", "price": 8.99, "stock_quantity": 35, "rating": 4.7, "description": "Cold-smoked ocean fish cured with sea salt, perfect for breakfast bagels or appetizers."},
    {"product_id": 89, "name": "Plant-Based Burger Patties", "category": "Proteins", "price": 7.99, "stock_quantity": 50, "rating": 4.3, "description": "Vegan meat alternative engineered to mimic the sizzle, color, and savory flavor of beef."},
    {"product_id": 90, "name": "Fresh Pork Tenderloin Cuts", "category": "Proteins", "price": 10.50, "stock_quantity": 28, "rating": 4.4, "description": "Succulent, extra-lean cuts of pork meat that roast beautifully with herbs."},

    # Category: Fruits, Vegetables & Fresh Produce
    {"product_id": 91, "name": "Organic Hass Avocados", "category": "Produce", "price": 2.50, "stock_quantity": 120, "rating": 4.7, "description": "Creamy fresh green fruits loaded with heart-healthy monounsaturated good fats."},
    {"product_id": 92, "name": "Fresh Organic Spinach Leaves", "category": "Produce", "price": 3.99, "stock_quantity": 45, "rating": 4.5, "description": "Pre-washed crisp green salad leaves packed with iron, folate, and essential vitamins."},
    {"product_id": 93, "name": "Fresh Blueberries (Clamshell)", "category": "Produce", "price": 4.50, "stock_quantity": 70, "rating": 4.8, "description": "Plump, sweet antioxidant superfood berries, perfect for mixing into morning oats."},
    {"product_id": 94, "name": "Organic Bunch of Bananas", "category": "Produce", "price": 1.99, "stock_quantity": 150, "rating": 4.6, "description": "Fresh potassium-rich natural energy snacks, ideal pre-workout or for baking bread."},
    {"product_id": 95, "name": "Sweet Honeycrisp Apples", "category": "Produce", "price": 2.99, "stock_quantity": 85, "rating": 4.4, "description": "Juicy, crisp sweet orchard apples with a distinct loud crunch and vibrant red skin."},
    {"product_id": 96, "name": "Fresh Broccoli Florets", "category": "Produce", "price": 3.20, "stock_quantity": 60, "rating": 4.3, "description": "Cruciferous green vegetable spears high in vitamin C and anti-cancer fiber networks."},
    {"product_id": 97, "name": "Vine-Ripened Roma Tomatoes", "category": "Produce", "price": 3.50, "stock_quantity": 90, "rating": 4.2, "description": "Plump, savory fresh red tomatoes, perfect for cooking Italian sauces or fresh salads."},
    {"product_id": 98, "name": "Organic Sweet Potatoes", "category": "Produce", "price": 2.20, "stock_quantity": 110, "rating": 4.5, "description": "Nutrient-dense orange root tubers offering slow-burning complex carbohydrates."},
    {"product_id": 99, "name": "Fresh Garlic Bulbs", "category": "Produce", "price": 1.50, "stock_quantity": 200, "rating": 4.6, "description": "Pungent, highly aromatic seasoning bulb known for immune support and depth of flavor."},
    {"product_id": 100, "name": "Crisp English Seedless Cucumber", "category": "Produce", "price": 1.99, "stock_quantity": 130, "rating": 4.3, "description": "Hydrating, mild crunchy green garden vegetable, excellent for slicing into fresh salads."}
]

# Convert it directly to a DataFrame.
df = pd.DataFrame(products_list)

# 2. Load the lightweight local embedding model
print("Loading local embedding model (all-MiniLM-L6-v2)...")
model = SentenceTransformer('all-MiniLM-L6-v2')

# 3. Generate 384-dimensional vectors from descriptions
print("Generating vector embeddings...")
embeddings = model.encode(df['description'].tolist())

# 4. Convert numpy arrays to lists/strings so they fit nicely into Postgres/CSV
df['description_vector'] = [json.dumps(vec.tolist()) for vec in embeddings]

# 5. Save out for the students
df.to_csv('products_precalculated.csv', index=False)
save_to_database(df)
print(f"✅ Success! Generated embeddings and seeded {len(df)} products into PostgreSQL.")
print("✅ 'products_precalculated.csv' generated with vector embeddings.")