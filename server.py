from flask import Flask, request, redirect, url_for, send_from_directory, jsonify
import os
from openai import OpenAI
import json
import requests

app = Flask(__name__)

server_url = 'test'

# Firestore
import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate('foodie-51699-firebase-adminsdk-bibws-5474607851.json')
firebase_admin.initialize_app(cred)

db = firestore.client()

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# API Source Code
RECIPE_API_KEY = "test"
RECIPE_API_KEY333 = "test"
RECIPE_API_URL = "https://api.spoonacular.com/recipes/findByIngredients"
SEARCH_API_URL = "https://api.spoonacular.com/food/ingredients/search"
INSTRUCTIONS_API_URL = "https://api.spoonacular.com/recipes/{id}/analyzedInstructions"
NUTRITION_API_URL = "https://api.spoonacular.com/recipes/{id}/nutritionWidget.json"
CUISINE_TYPE_API_URL = "https://api.spoonacular.com/recipes/cuisine"
RECIPE_ID_API_URL = "https://api.spoonacular.com/recipes/{id}/information"
INGREDIENTS_ID_API_URL = "https://api.spoonacular.com/recipes/{id}/ingredientWidget.json"
SEARCH_BY_NAME_URL = "https://api.spoonacular.com/recipes/complexSearch"

NUMBER_OF_RECIPES = 5
INGREDIENT_EXPAND_LIMIT = 5

def list2str(data):
    result = ""
    for ing in data:
        result += str(ing) + "\n"
    return result

def fetch_nutrition_info(recipe_id):
    """Fetch the nutrition information for a specific recipe by its ID."""
    url = NUTRITION_API_URL.format(id=recipe_id)
    params = {
        'apiKey': RECIPE_API_KEY
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch nutrition info for recipe ID {recipe_id}. Status code: {response.status_code}")
        return None



def fetch_ingredients_with_id(recipe_id):
    """Fetch recipie with id"""
    url = INGREDIENTS_ID_API_URL.format(id=recipe_id)
    params = {
        'apiKey': RECIPE_API_KEY
    }
    steps = []
    
    # Get related ingredients from api
    response = requests.get(url, params=params)
    for step in (response[0])['steps']:
        line = step['number'] + ". " + step['step']
        steps.append(line) 
        
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch ingredient info for recipe ID {recipe_id}. Status code: {response.status_code}")
        return None


def fetch_cuisine_type(title, ingredient_list_str):
    url = CUISINE_TYPE_API_URL
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    params = {
        'title' : title,
        'ingredientList' : ingredient_list_str,
        'language' : 'en',
        'apiKey': RECIPE_API_KEY
    }
    response = requests.post(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to cuisine type for title {title}. Status code: {response.status_code}")
        return None
    
def list2str(data):
    result = ""
    for ing in data:
        result += str(ing) + "\n"
    return result

def fetch_recipe_steps(recipe_id): 
    """Fetch detailed steps for a recipe using its ID."""
    
    url = INSTRUCTIONS_API_URL.format(id=recipe_id)
    params = {'apiKey': RECIPE_API_KEY}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch steps for recipe ID {recipe_id}. Status code: {response.status_code}")
        return []

    
def fetch_recipe_with_id(recipe_id):
    """Fetch recipie with id"""
    url = RECIPE_ID_API_URL.format(id=recipe_id)
    params = {
        'id' : recipe_id,
        'apiKey': RECIPE_API_KEY
    }
    
    # Get recipe info from api
    response = requests.get(url, params=params)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch recipe info for recipe ID {recipe_id}. Status code: {response.status_code}")
        return None


def organize_recipes(recipes_data, existing_ingredients):
    organized_recipes = []
    
    for recipe in recipes_data:
        nutrition_info = fetch_nutrition_info(recipe['id'])
        organized_nutr = [
            "calories " + nutrition_info['calories'], 
            "carbs " + nutrition_info['carbs'], 
            "fat " + nutrition_info['fat'],
            "protein " + nutrition_info['protein']
        ]
        
        instructions = fetch_recipe_steps(recipe['id'])
        inst_result = []
        for inst in instructions[0]['steps']:
            inst_num = inst['number']
            inst_stp = inst['step']
            inst_result.append(str(inst_num) + ". " + inst_stp)
            
        info_by_id = fetch_recipe_with_id(recipe['id'])
        cookingTime = info_by_id.get('cookingMinutes', 'Unknown')

        preferencesKeys = [
            key for key, value in {
                'vegetarian': info_by_id.get('vegetarian', False),
                'vegan': info_by_id.get('vegan', False),
                'glutenFree': info_by_id.get('glutenFree', False),
                'dairyFree': info_by_id.get('dairyFree', False),
                'veryHealthy': info_by_id.get('veryHealthy', False),
                'cheap': info_by_id.get('cheap', False),
            }.items() if value
        ]

        recipe_info = {
            'id': recipe['id'],
            'title': recipe['title'],
            'image': recipe['image'],
            'existing_ingredients': [],
            'non_existing_ingredients': [],
            'nutrients': organized_nutr,
            'steps': inst_result,
            'cuisine_type': [],
            'cooking_time': cookingTime,
            'preferences': preferencesKeys,
        }

        
        for ingredient in recipe['usedIngredients']:
            ingredient_name = ingredient['name'].lower()
            if ingredient_name in existing_ingredients:
                recipe_info['existing_ingredients'].append(ingredient_name)
            else:
                recipe_info['non_existing_ingredients'].append(ingredient_name)

        for ingredient in recipe.get('missedIngredients', []):
            ingredient_name = ingredient['name'].lower()
            recipe_info['non_existing_ingredients'].append(ingredient_name)
            
        cuisine_type = fetch_cuisine_type(recipe['title'], list2str(recipe_info['existing_ingredients'] + recipe_info['non_existing_ingredients'])).get('cuisine', 'Unknown')
        recipe_info['cuisine_type'] = cuisine_type
        
        organized_recipes.append(recipe_info)
    
    return organized_recipes


    
def fetch_and_save_recipes(adjusted_json):

    ingredients_string = ', '.join(adjusted_json['ingredients'])

    # Fetch recipes from the main API
    params = {
        'apiKey': RECIPE_API_KEY,
        'ingredients': ingredients_string,
        'addRecipeNutrition': True,
        'addRecipeInstructions': True,
        'number': 2
    }
    print("Searching recipes with ingredients:", params['ingredients'])
    response = requests.get(RECIPE_API_URL, params=params)

    if response.status_code == 200:
        recipe_data = response.json()

        organized_recipes = organize_recipes(recipe_data, ingredients_string)

        return organized_recipes
    else:
        print("Failed to retrieve recipes from Spoonacular.")


OPENAI_API_KEY = 'test'

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file part", 400

    file = request.files['file']

    if file.filename == '':
        return "No selected file", 400

    if file:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        # Generate the URL for the uploaded file
        file_url = url_for('uploaded_file', filename=file.filename, _external=True)
        print('Image uploaded')

        # Call the OpenAI API to analyze the image
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text",
                         "text": "Give me a list of things inside this fridge. Only give me the list. Maximum two words per item. Make these ingredients as basic as possible. Please give me only a list, no numbers no nothing, just a list of basic ingredients."},
                        {"type": "image_url", "image_url": {"url": file_url}}
                    ],
                }
            ],
            max_tokens=300,
        )

        # Process the response from OpenAI
        content = response.choices[0].message.content
        fridge_items = [item.strip('- ').strip().lower() for item in content.split('\n')]

        # Prepare the JSON response
        data = {'ingredients': fridge_items}

        # Return the JSON response
        return jsonify(data), 200


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/submit_json', methods=['POST'])
def submit_json():
    # Get JSON data from request
    if not request.is_json:
        return jsonify({"error": "Invalid JSON format"}), 400

    edited_json = request.get_json()   # json file received from front end
    
    # ingredients = edited_json.get('message', {}).get('message', {}).get('ingredients', [])
    # adjusted_json = {'ingredients': ingredients}
    adjusted_json = edited_json

    user_id = adjusted_json.get('user_id')
    ingredients = adjusted_json.get('ingredients')

    if not user_id or not ingredients:
        return jsonify({'error': 'user id or ingredients missing'}), 400

    user_ref = db.collection('users').document(user_id)
    user_ref.set({'fridge_ingredients': ingredients}, merge = True)
    
    # Simulate API's process to JSON, and return the result
    # Suppose api will return data like this (haven't check the json format yet)
    # just temporary data for testing
    '''
    mock_api_response = {
        "status": "success",
        "message": "JSON processed successfully by API.",
        "original_data": edited_json
    }
    '''
    # This is the part that I'll actually use

    # Send edited JSON to API
    # and receive response from api

    #api_response = requests.post('Recipe_API_URL', json=edited_json)
    api_response_json = fetch_and_save_recipes(adjusted_json)

    return jsonify(api_response_json), 200



@app.route('/get_ingredients/<user_id>', methods=['GET'])
def get_ingredients(user_id):
    user_ref = db.collection('users').document(user_id)
    user_data = user_ref.get()

    if not user_data.exists:
        return jsonify({'error': 'user not found'}), 404

    ingredients = user_data.to_dict().get('fridge_ingredients', [])


    return jsonify({'user_id': user_id, 'ingredients': ingredients}), 200

@app.route('/update_ingredients', methods=['POST'])
def update_ingredients():
    if not request.is_json:
        return jsonify({"error": "Invalid JSON format"}), 400

    data = request.get_json()
    
    user_id = data.get("user_id")
    new_ingredients = data.get("ingredients")

    if not user_id or not new_ingredients:
        return jsonify({"error": "User ID or ingredients list missing"}), 400

    user_ref = db.collection("users").document(user_id)
    user_data = user_ref.get()

    if not user_data.exists:
        return jsonify({"error": "User not found"}), 404

    user_ref.update({"fridge_ingredients": new_ingredients})

    return jsonify({"message": "Ingredients list updated successfully"}), 200


@app.route('/get_fav_recipes/<user_id>', methods=['GET'])
def get_fav_recipes(user_id):
    try:
        user_ref = db.collection('users').document(user_id)
        user_snapshot = user_ref.get()

        if not user_snapshot.exists:
            return jsonify({'error': 'User not found'}), 404

        user_data = user_snapshot.to_dict()
        user_fav_ids = user_data.get('favorites', [])

        result = []

        for recipe_id in user_fav_ids:
            try:
                recp_temp = fetch_recipe_with_id(recipe_id)
                if not recp_temp:
                    print(f"Recipe not found for ID: {recipe_id}")
                    continue

                preferencesKeys = [
                    key for key, value in {
                        'vegetarian': recp_temp.get('vegetarian', False),
                        'vegan': recp_temp.get('vegan', False),
                        'glutenFree': recp_temp.get('glutenFree', False),
                        'dairyFree': recp_temp.get('dairyFree', False),
                        'veryHealthy': recp_temp.get('veryHealthy', False),
                        'cheap': recp_temp.get('cheap', False),
                    }.items() if value
                ]

                
                # Extract relevant data from recp_temp
                recipe_info = {
                    'id': recipe_id,
                    'title': recp_temp.get('title', 'Unknown Title'),
                    'calories': recp_temp.get('nutrition', {}).get('calories', 'Unknown'),
                    'cuisine_type': recp_temp.get('cuisines', ['Unknown'])[0],  # Get the first cuisine type
                    'image': recp_temp.get('image', ''),
                    'ingredients': [ing['name'] for ing in recp_temp.get('extendedIngredients', [])],
                    'steps': [step['step'] for step in recp_temp.get('analyzedInstructions', [{}])[0].get('steps', [])],
                    'cooking_time': recp_temp.get('readyInMinutes', 'Unknown'),
                    'preferences': preferencesKeys
                }

                result.append(recipe_info)
            except Exception as e:
                print(f"Error processing recipe ID {recipe_id}: {e}")

        # Sort results by calories or any other field (e.g., title, cooking time)
        sorted_results = sorted(result, key=lambda x: x.get('calories', 0))

        return jsonify({"recipe_info": sorted_results}), 200

    except Exception as e:
        print(f"Error in get_fav_recipes: {e}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500


# Get random recipes
@app.route('/get_daily_recipes', methods=['POST'])
def get_daily_recipes():
    """
    Fetch a daily random recipe based on included tags sent in the JSON request.
    """
    # API Configuration
    RANDOM_RECIPE_API_URL = "https://api.spoonacular.com/recipes/random"

    if not request.is_json:
        return jsonify({"error": "Invalid JSON format"}), 400

    # Parse the JSON input
    data = request.get_json()
    include_tags = data.get("include_tags", [])  # Tags to include
    number_of_recipes = data.get("number", 1)    # Default to 1 recipe

    # Validate and format tags
    tags = ','.join(include_tags) if include_tags else ''  # Combine tags into a comma-separated string

    # Make the API call
    params = {
        "number": number_of_recipes,
        "apiKey": RECIPE_API_KEY,
    }
    if tags:
        params["tags"] = tags  # Use `tags` for Spoonacular API

    try:
        response = requests.get(RANDOM_RECIPE_API_URL, params=params)
        response.raise_for_status()
        recipes = response.json().get('recipes', [])

        # Extract relevant data
        result = []
        for recipe in recipes:
            try:
                recipe_info = {
                    'id': recipe.get('id', 'Unknown'),
                    'title': recipe.get('title', 'Unknown Title'),
                    'calories': recipe.get('nutrition', {}).get('calories', 'Unknown'),
                    'cuisine_type': recipe.get('cuisines', ['Unknown'])[0] if recipe.get('cuisines') else 'Unknown',
                    'image': recipe.get('image', ''),
                    'ingredients': [ing.get('name') for ing in recipe.get('extendedIngredients', [])],
                    'steps': [step['step'] for step in recipe.get('analyzedInstructions', [{}])[0].get('steps', [])],
                    'cooking_time': recipe.get('readyInMinutes', 'Unknown'),
                }
                result.append(recipe_info)
            except Exception as e:
                print(f"Error processing recipe: {e}")

        sorted_results = sorted(result, key=lambda x: x.get('calories', 0))

        return jsonify({"recipe_info": sorted_results}), 200

    except requests.exceptions.RequestException as e:
        print(f"Error fetching recipes: {e}")
        return jsonify({"error": "Failed to fetch recipes", "details": str(e)}), 500



@app.route('/save_recipe', methods = ['POST'])
def save_recipe():
    if not request.is_json:
        return jsonify({'error': 'Invalid JSON format'}), 400

    recipe_data = request.get_json()

    user_id = recipe_data.get("user_id")
    recipeId = recipe_data.get("recipeId")

    user_ref = db.collection('users').document(user_id)

    user_ref.update({'favorites': firestore.ArrayUnion([recipeId])})

    return jsonify({'message': 'Recipe saved to favorites'}), 200


# SBN
def list2str_SBN(data):
    result = ""
    for ing in data:
        result += str(ing['name']) + "\n"
    return result


def get_ingredient_list_SBN(data):
    result = []
    for ing in data:
        result.append(ing['name'])
    return result

def fetch_nutrition_info_SBN(recipe_id):
    url = NUTRITION_API_URL.format(id=recipe_id)
    params = {'apiKey': RECIPE_API_KEY}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"Failed to fetch nutrition info for recipe ID {recipe_id}"}
    
def fetch_recipe_steps_SBN(recipe_id):
    url = INSTRUCTIONS_API_URL.format(id=recipe_id)
    params = {'apiKey': RECIPE_API_KEY}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        results = response.json()
        inst_list = [f"{step['number']}. {step['step']}" for step in results[0]['steps']]
        return inst_list
    else:
        return {"error": f"Failed to fetch steps for recipe ID {recipe_id}"}
    
def fetch_info_by_keyword(keyword, number):
    url = SEARCH_BY_NAME_URL
    params = {'apiKey': RECIPE_API_KEY, 'number': number, 'query': keyword, 'titleMatch': keyword}
    response = requests.get(url, params=params)
    return response.json()

def fetch_info_by_id_SBN(recipe_id):
    url = RECIPE_ID_API_URL.format(id=recipe_id)
    params = {'apiKey': RECIPE_API_KEY}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"Failed to fetch information for recipe ID {recipe_id}"}


def organize_recipes_SBN(recipes_data):
    recipe_data_ids = [recipe['id'] for recipe in recipes_data['results']]
    organized_recipes = []

    for recipe_id in recipe_data_ids:
        print("Fetching recipe with id", recipe_id)
        recipe_info = fetch_info_by_id_SBN(recipe_id)
        if "error" in recipe_info:
            continue

        inst_result = fetch_recipe_steps_SBN(recipe_id)
        nutrition_info = fetch_nutrition_info_SBN(recipe_id)
        ingredient_list = get_ingredient_list_SBN(recipe_info['extendedIngredients'])
        cooking_time = recipe_info.get('cookingMinutes', "Unknown")  # Safely fetch cookingMinutes

        organized_nutr = [
            f"calories {nutrition_info['calories']}",
            f"carbs {nutrition_info['carbs']}",
            f"fat {nutrition_info['fat']}",
            f"protein {nutrition_info['protein']}"
        ]

        organized_info = {
            'id': recipe_info['id'],
            'title': recipe_info['title'],
            'image': recipe_info['image'],
            'ingredients': ingredient_list,
            'nutrients': organized_nutr,
            'steps': inst_result,
            'cooking_time': cooking_time  # Include cooking time
        }

        organized_recipes.append(organized_info)

    return organized_recipes

def fetch_and_return_recipes(keyword, number):
    """Search recipes by keyword, organize, and return them."""
    print("Searching recipes with keyword", keyword)
    response = fetch_info_by_keyword(keyword, number)
    if "error" in response:
        return {"error": "Failed to fetch recipes"}
    
    organized_recipes = organize_recipes_SBN(response)
    return organized_recipes

@app.route("/recipes/search", methods=["POST"])
def search_recipes_by_keyword():
    """
    Search recipes by keyword and return a list of recipes.
    JSON Body:
    - keyword (str): The keyword to search for.
    - number (int, optional): The number of recipes to return. Default is 5.

    Example Request:
    POST /recipes/search
    {
        "keyword": "lemon",
        "number": 2
    }
    """
    if not request.is_json:
        return jsonify({"error": "Invalid JSON format"}), 400

    data = request.get_json()
    keyword = data.get("keyword")
    number = int(data.get("number", 2))

    if not keyword:
        return jsonify({"error": "Keyword is required"}), 400

    try:
        recipes = fetch_and_return_recipes(keyword, number)
        return jsonify({"recipes": recipes})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
