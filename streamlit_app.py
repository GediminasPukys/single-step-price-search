import streamlit as st
import json
import time
from openai import OpenAI
from pydantic import BaseModel
from typing import Dict, List, Any, Optional

# Page configuration
st.set_page_config(
    page_title="Lithuanian Market Product Analyzer",
    page_icon="🔍",
    layout="wide"
)

# Title and description
st.title("🔍 Lithuanian Market Product Analyzer")
st.markdown("""
This application analyzes Lithuanian market products based on a technical specification.
It queries the OpenAI API to gather structured product information and evaluates each product.
""")

# Check if API key is configured
if 'openai_api_key' not in st.secrets.get("config", {}):
    st.error("""
    ⚠️ OpenAI API key not found in secrets.

    1. Create a `.streamlit/secrets.toml` file with your OpenAI API key:
    ```
    [config]
    openai_api_key = "your_openai_api_key"
    ```

    2. Restart the application.
    """)
    st.stop()

# Get the API key from secrets
OPENAI_API_KEY = st.secrets["config"]["openai_api_key"]

# Create tabs for different sections
tab1, tab2, tab3 = st.tabs(["Product Search", "Search History", "About"])

with tab1:
    st.header("Search for Products")

    # Product category input
    st.subheader("Product Category/Group")
    product_category = st.text_input(
        "Enter the product category or group:",
        placeholder="Example: kuras / degalai, Smartphones, Laptops, Vitamins"
    )

    # Product name input
    product_name = st.text_input(
        "Enter the product name:",
        placeholder="Example: benzinas, iPhone, Vitamin D, Nike Air Max"
    )

    # Technical specification input
    st.subheader("Enter Technical Specification")
    tech_spec = st.text_area(
        "Technical specifications for the product you're looking for:",
        height=200,
        placeholder="Example: 95 oktaninio skaičiaus arba 95 benzinas"
    )

    # Price Calculation Objective
    st.subheader("Price Calculation Objective")

    price_calculation_options = {
        "none": "No special calculation (standard price)",
        "unit": "Price per unit (e.g., per item)",
        "kg": "Price per kilogram",
        "liter": "Price per liter",
        "package": "Price per package"
    }

    price_calc_objective = st.selectbox(
        "Select how you want prices to be calculated:",
        options=list(price_calculation_options.keys()),
        format_func=lambda x: price_calculation_options[x]
    )

    # Additional input for custom calculation if needed
    custom_calc_unit = None
    if price_calc_objective != "none":
        st.info(f"Products will be evaluated based on {price_calculation_options[price_calc_objective]}")

        if price_calc_objective == "unit":
            custom_calc_unit = st.text_input(
                "Specify unit type (e.g., tablet, pill, piece):",
                placeholder="Leave empty for generic 'unit'"
            )


    # Define a simpler approach - don't use Pydantic models for parsing
    # Instead, we'll process the JSON directly

    # Function to search and analyze products
    def search_and_analyze_products(category, product_name, tech_spec, price_calc_objective, api_key):
        client = OpenAI(api_key=api_key)

        prompt = f"""
        Analyze the Lithuanian market for {category} and gather detailed product information according to the following:
                     product name: {product_name}
                     product specification: {tech_spec}

        2. Verify the product is currently available for purchase
        3. Gather accurate pricing in EUR
        4. Evaluate technical specification requirements one by one
        """

        # Add price calculation objective if selected
        if price_calc_objective != "none":
            if price_calc_objective == "unit":
                unit_type = custom_calc_unit if custom_calc_unit else "unit"
                prompt += f"\n5. Calculate and include price per {unit_type} for each product"
            elif price_calc_objective == "kg":
                prompt += "\n5. Calculate and include price per kilogram for each product"
            elif price_calc_objective == "liter":
                prompt += "\n5. Calculate and include price per liter for each product"
            elif price_calc_objective == "package":
                prompt += "\n5. Calculate and include price per package for each product"

        # JSON format instructions
        prompt += """
        IMPORTANT: Your response MUST be formatted EXACTLY as a valid JSON array of product objects.
        Each product in the array should have the following fields:

        [
          {
            "provider": "Company selling the product",
            "provider_website": "Main website domain (e.g., telia.lt)",
            "provider_url": "Full URL to the specific product page",
            "product_name": "Complete product name with model",
            "product_properties": {
              "key_spec1": "value1",
              "key_spec2": "value2"
            },
            "product_sku": "Any product identifiers (SKU, UPC, model number)",
            "product_price": 299.99,
        """

        # Add price calculation field based on objective
        if price_calc_objective != "none":
            prompt += f"""
            "price_per_{price_calc_objective}": 9.99,"""
            if price_calc_objective == "unit" and custom_calc_unit:
                prompt += f"""
            "unit_type": "{custom_calc_unit}","""

        prompt += """
            "evaluation": "Detailed assessment of how the product meets or fails each technical specification"
          }
        ]

        DO NOT include any explanation, preamble, or additional text - ONLY provide the JSON array.
        """

        try:
            # Use the OpenAI chat completions API instead of the parse function
            completion = client.chat.completions.create(
                model="gpt-4o-search-preview",
                web_search_options={
                    "user_location": {
                        "type": "approximate",
                        "country": "LT",
                        "city": "Vilnius",
                    }
                },
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2
            )

            response_text = completion.choices[0].message.content

            # Process the response
            try:
                # Try to parse JSON from response
                import re
                json_match = re.search(r'(\[\s*{.*}\s*\]|\{\s*"products"\s*:\s*\[.*\]\s*\})', response_text, re.DOTALL)

                if json_match:
                    json_str = json_match.group(0)
                    products_data = json.loads(json_str)
                else:
                    products_data = json.loads(response_text)

                # Check if the response is a list or contains a 'products' key
                if isinstance(products_data, dict) and "products" in products_data:
                    products_json = products_data["products"]
                else:
                    products_json = products_data
            except Exception as e:
                st.error(f"Could not parse JSON from API response: {str(e)}")
                products_json = []

            return products_json

        except Exception as e:
            st.error(f"API request failed: {str(e)}")
            return []


    # Function to display the results
    def display_results(all_products, category, product_name, price_calc_objective):
        if not all_products:
            st.error("No products found or error occurred during analysis.")
            return

        # Display the products
        st.subheader(f"Found {len(all_products)} Products for {product_name} in {category} category")

        # Display results in expandable sections
        for i, product in enumerate(all_products):
            product_title = f"{i + 1}. {product.get('product_name', 'Unknown Product')} - €{product.get('product_price', 'N/A')}"

            # Add price calculation to title if available
            if price_calc_objective != "none":
                price_per_key = f"price_per_{price_calc_objective}"
                if price_per_key in product:
                    unit_display = ""
                    if price_calc_objective == "unit" and "unit_type" in product:
                        unit_display = f"/{product['unit_type']}"
                    elif price_calc_objective == "kg":
                        unit_display = "/kg"
                    elif price_calc_objective == "liter":
                        unit_display = "/L"
                    elif price_calc_objective == "package":
                        unit_display = "/pkg"

                    product_title += f" (€{product.get(price_per_key, 'N/A')}{unit_display})"

            with st.expander(product_title):
                col1, col2 = st.columns([1, 2])

                with col1:
                    st.markdown(f"**Provider:** {product.get('provider', 'N/A')}")
                    st.markdown(f"**Website:** {product.get('provider_website', 'N/A')}")
                    if 'provider_url' in product and product['provider_url']:
                        st.markdown(f"**Product Link:** [View Product]({product['provider_url']})")
                    st.markdown(f"**SKU/ID:** {product.get('product_sku', 'N/A')}")
                    st.markdown(f"**Price:** €{product.get('product_price', 'N/A')}")

                    # Display price calculation if available
                    if price_calc_objective != "none":
                        price_per_key = f"price_per_{price_calc_objective}"
                        if price_per_key in product:
                            unit_display = ""
                            if price_calc_objective == "unit" and "unit_type" in product:
                                unit_display = f"/{product['unit_type']}"
                            elif price_calc_objective == "kg":
                                unit_display = "/kg"
                            elif price_calc_objective == "liter":
                                unit_display = "/L"
                            elif price_calc_objective == "package":
                                unit_display = "/pkg"

                            st.markdown(
                                f"**Price per {price_calc_objective.capitalize()}:** €{product.get(price_per_key, 'N/A')}{unit_display}")

                with col2:
                    st.subheader("Product Properties")
                    properties = product.get('product_properties', {})
                    if properties:
                        for key, value in properties.items():
                            st.markdown(f"**{key}:** {value}")
                    else:
                        st.write("No detailed properties available.")

                    st.subheader("Technical Evaluation")
                    evaluation = product.get('evaluation', 'No evaluation available.')
                    st.write(evaluation)

        # Show raw JSON option
        with st.expander("View Raw JSON Response"):
            st.json(all_products)


    # Search button
    if st.button("Search Products", type="primary", disabled=not (product_category and product_name)):
        if not product_category or not product_name:
            st.warning("Please enter both product category and product name to continue.")
            st.stop()

        with st.spinner(
                f"Analyzing Lithuanian market for {product_name} in {product_category} category... (this may take 1-2 minutes)"):
            # Single search approach
            all_products = search_and_analyze_products(
                product_category,
                product_name,
                tech_spec,
                price_calc_objective,
                OPENAI_API_KEY
            )

            if all_products:
                # Save to session state for history
                if "search_history" not in st.session_state:
                    st.session_state.search_history = []

                history_entry = {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "category": product_category,
                    "product_name": product_name,
                    "tech_spec": tech_spec,
                    "price_calc_objective": price_calc_objective,
                    "results": all_products
                }
                st.session_state.search_history.append(history_entry)

                # Display the results
                display_results(all_products, product_category, product_name, price_calc_objective)
            else:
                st.error("No products found matching your specifications.")

with tab2:
    st.header("Search History")

    if "search_history" not in st.session_state or not st.session_state.search_history:
        st.info("No search history yet. Search for products to see your history here.")
    else:
        for i, entry in enumerate(reversed(st.session_state.search_history)):
            # Add category and product name to history entry title
            category_info = f"[{entry.get('category', 'Unknown')}]"
            product_info = f"{entry.get('product_name', 'Unknown Product')}"
            price_calc_info = ""
            if "price_calc_objective" in entry and entry["price_calc_objective"] != "none":
                price_calc_info = f" (Price per {entry['price_calc_objective']})"

            with st.expander(f"{entry['timestamp']} - {category_info} {product_info} {price_calc_info}"):
                st.markdown(f"**Category:** {entry.get('category', 'None')}")
                st.markdown(f"**Product:** {entry.get('product_name', 'None')}")
                st.markdown(f"**Search Query:**\n{entry['tech_spec']}")

                # Show price calculation objective if available
                if "price_calc_objective" in entry and entry["price_calc_objective"] != "none":
                    st.markdown(f"**Price Calculation:** Price per {entry['price_calc_objective']}")

                st.markdown(f"**Results:** {len(entry['results'])} products found")

                # Display results again
                for j, product in enumerate(entry['results']):
                    # Basic product info
                    product_info = f"**{j + 1}. {product.get('product_name', 'Unknown Product')}** - €{product.get('product_price', 'N/A')}"

                    # Add price calculation if available
                    if "price_calc_objective" in entry and entry["price_calc_objective"] != "none":
                        price_per_key = f"price_per_{entry['price_calc_objective']}"
                        if price_per_key in product:
                            unit_display = ""
                            if entry["price_calc_objective"] == "unit" and "unit_type" in product:
                                unit_display = f"/{product['unit_type']}"
                            elif entry["price_calc_objective"] == "kg":
                                unit_display = "/kg"
                            elif entry["price_calc_objective"] == "liter":
                                unit_display = "/L"
                            elif entry["price_calc_objective"] == "package":
                                unit_display = "/pkg"

                            product_info += f" (€{product.get(price_per_key, 'N/A')}{unit_display})"

                    st.markdown(product_info)
                    st.markdown(
                        f"Provider: {product.get('provider', 'N/A')} | [View Product]({product.get('provider_url', '#')})")

                # Option to view full details
                if st.button(f"View Full Details #{i}", key=f"history_{i}"):
                    display_results(entry['results'], entry['category'], entry['product_name'],
                                    entry['price_calc_objective'])

with tab3:
    st.header("About This Application")

    st.markdown("""
    ## Lithuanian Market Product Analyzer (Single Search Version)

    This application helps you find and compare products available in the Lithuanian market
    based on technical specifications you provide. It leverages the OpenAI API to search
    for and analyze products from various Lithuanian retailers.

    ### How to Use

    1. Enter the product category or group (e.g., "kuras / degalai", Smartphones)
    2. Enter the product name (e.g., "benzinas", iPhone)
    3. Enter the technical specifications (e.g., "95 oktaninio skaičiaus arba 95 benzinas")
    4. Select a price calculation objective if you want to compare prices on a specific basis
    5. Click "Search Products"
    6. Review the results, which show:
       - Product details and standard pricing
       - Price calculations based on your selected objective (per kg, per unit, etc.)
       - Technical specifications evaluation
       - Links to product pages

    ### Tips for Best Results

    - Be specific with your product category and name
    - Include both must-have and nice-to-have features in your specifications
    - Specify brand preferences if you have any
    - Include price range if relevant
    - Use the price calculation objectives for better comparison between products (e.g., price per kg for groceries)

    ### Technical Details

    This application uses:
    - Streamlit for the web interface
    - OpenAI API with advanced search capabilities for Lithuanian market research
    - Direct search that finds and analyzes products in a single step
    - Pydantic models for structured data handling
    - Specialized price calculations for better product comparison

    ### Privacy Note

    Your search queries and technical specifications are sent to the OpenAI API
    to generate results. No personal information is stored or shared beyond what is 
    necessary for the application to function.
    """)

# Footer
st.markdown("---")
st.markdown("© 2025 Lithuanian Market Product Analyzer | Powered by OpenAI API")