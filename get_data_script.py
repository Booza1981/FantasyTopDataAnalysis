import os
import re
import json
import time
import random
import glob
import sys
import requests
import pandas as pd
import numpy as np
import pickle
from dotenv import load_dotenv
from datetime import datetime, timedelta
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from fake_useragent import UserAgent
import platform


# Load environment variables from .env file
load_dotenv()


# Global Variables
PLAYER_ID = os.getenv("PLAYER_ID")
URL_GRAPHQL = os.getenv("URL_GRAPHQL")
URL_REST = os.getenv("URL_REST")
DATA_FOLDER = os.getenv("DATA_FOLDER")

print(DATA_FOLDER)

# Required environment variables
required_env_vars = [
    'TWITTER_USERNAME',
    'TWITTER_PASSWORD',
    'PLAYER_ID',
    'URL_GRAPHQL',
    'URL_REST',
    'DATA_FOLDER',
]

# Check if all required environment variables are set
missing_env_vars = [var for var in required_env_vars if not os.getenv(var)]

if missing_env_vars:
    print(f"Error: Missing required environment variables: {', '.join(missing_env_vars)}")
    print("Please ensure all required environment variables are set.")
    sys.exit(1)  # Exit the script if any environment variables are missing

# If all environment variables are loaded, proceed with the rest of the script

# Determine the platform
is_windows = platform.system().lower() == "windows"

# Expand the tilde only on Unix-like systems
if DATA_FOLDER.startswith("~") and not is_windows:
    DATA_FOLDER = os.path.expanduser(DATA_FOLDER)
else:
    DATA_FOLDER = os.path.abspath(DATA_FOLDER)

# Create the directory if it doesn't exist
if not os.path.exists(DATA_FOLDER):
    print (f"Creating directory: {DATA_FOLDER}")
    os.makedirs(DATA_FOLDER)

COOKIES_FILE = 'cookies.pkl'
SESSION_FILE = 'session.pkl'
LOCAL_STORAGE_FILE = 'local_storage.pkl'


# Twitter login details from environment variables
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD")

# Utility Functions

def save_data(driver, filepath, data):
 with open(filepath, 'wb') as file:
     pickle.dump(data, file)

def load_data(filepath):
 try:
     with open(filepath, 'rb') as file:
         return pickle.load(file)
 except FileNotFoundError:
     print(f"File {filepath} not found. Proceeding without loading data.")
     return None
 
def save_browser_data(driver):
    session_storage = driver.execute_script("return window.sessionStorage;")
    save_data(driver, SESSION_FILE, session_storage)

    local_storage = driver.execute_script("return window.localStorage;")
    save_data(driver, LOCAL_STORAGE_FILE, local_storage)
    
    cookies = {
        'fantasy_top': driver.get_cookies(),
        'privy_fantasy_top': []
    }
    driver.get('https://privy.fantasy.top')
    cookies['privy_fantasy_top'] = driver.get_cookies()
    save_data(driver, COOKIES_FILE, cookies)

    driver.get("https://www.fantasy.top/home")
    
def load_browser_data(driver):
    session_storage = load_data(SESSION_FILE)
    if session_storage:
        for key, value in session_storage.items():
            driver.execute_script(f"window.sessionStorage.setItem('{key}', '{value}');")

    local_storage = load_data(LOCAL_STORAGE_FILE)
    if local_storage:
        for key, value in local_storage.items():
            driver.execute_script(f"window.localStorage.setItem('{key}', '{value}');")

    cookies = load_data(COOKIES_FILE)
    if cookies:
        driver.get('https://www.fantasy.top')
        for cookie in cookies['fantasy_top']:
            driver.add_cookie(cookie)
        driver.get('https://privy.fantasy.top')
        for cookie in cookies['privy_fantasy_top']:
            driver.add_cookie(cookie)
        driver.get("https://www.fantasy.top/home")

def clear_browser_data(driver):
    # Clear cookies
    driver.delete_all_cookies()
    print("Cookies cleared.")

    # Clear session storage
    driver.execute_script("window.sessionStorage.clear();")
    print("Session storage cleared.")

    # Clear local storage
    driver.execute_script("window.localStorage.clear();")
    print("Local storage cleared.")

def convert_to_eth(value):
    try:
        if pd.isna(value):
            return None
        return int(float(value)) / 1e18
    except (ValueError, TypeError) as e:
        print(f"Error converting value {value}: {e}")
        return None

def save_df_as_csv(df, filename, folder=DATA_FOLDER):
    # Check if DataFrame is empty
    if df.empty:
        print(f"DataFrame {df} is empty. No {filename} file will be saved.")
        return
    
    # Proceed with saving the file if not empty
    timestamp = datetime.now().strftime('%y%m%d_%H%M')
    filename_with_timestamp = f"{filename}_{timestamp}.csv"
    if not os.path.exists(folder):
        os.makedirs(folder)
    full_path = os.path.join(folder, filename_with_timestamp)
    df.to_csv(full_path, index=False)
    print(f"DataFrame saved as {full_path}")


def print_runtime(func, *args, **kwargs):
    print(f'Calling {func.__name__}')
    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()
    runtime = end_time - start_time
    print(f'{func.__name__} took {runtime:.4f} seconds to execute')
    return result

############################################################################
# WebDriver and Login
############################################################################

def get_random_user_agent():
    ua = UserAgent(platforms='pc')
    return ua.random

def setup_driver():
    
    options = webdriver.ChromeOptions()
    options.add_argument(f"user-agent={get_random_user_agent()}")
    options.add_argument("--headless")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    print(ChromeDriverManager().install())
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def login_to_fantasy(driver, username, password):
    driver.get("https://www.fantasy.top/home")
    wait = WebDriverWait(driver, 5)

    try:
        # Try to find the "Continue" button, which appears if already logged in
        continue_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Continue')]")))
        continue_button.click()
        print("Already logged in. Clicked 'Continue' button.")
    except TimeoutException:
        print("Continue button not found. Proceeding with login.")

        # If "Continue" button is not found, proceed with Twitter login
        try:
            button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[style*='background: linear-gradient'][class*='rounded-md']")))
            button.click()
            modal_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Twitter')]")))
            modal_button.click()
            time.sleep(2)
            actions = ActionChains(driver)
            actions.send_keys(Keys.ESCAPE).perform()
            username_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='text'][autocomplete='username']")))
            username_input.send_keys(username)
            next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']/ancestor::button")))
            next_button.click()
            password_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='password'][type='password']")))
            password_input.send_keys(password)
            login_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='LoginForm_Login_Button']")))
            login_button.click()
            close_popup_if_appears(driver)
            authorize_if_appears(driver)
            accept_terms_if_appears(driver)
            driver.get("https://www.fantasy.top/home")
            print("Logged In Successfully")
        except TimeoutException:
            print("Twitter login flow elements not found. Login might have failed.")

def check_login_success(driver):
    try:
        # Wait for the element to be present
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.hidden.h-full.items-center.gap-x-2.md\\:flex"))
        )
        
        # Execute JavaScript to check if the element has any child nodes
        has_children = driver.execute_script(
            "return arguments[0].children.length > 0;", element
        )
        
        if has_children:
            print("Login check successful: The element has children.")
            return True
        else:
            print("Login check failed: The element does not have children.")
            return False
        
    except TimeoutException:
        print("Timed Out:The element was not found on the page.")
        return False
    
def close_popup_if_appears(driver):
    try:
        close_popup_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='xMigrationBottomBar']"))
        )
        close_popup_button.click()
    except TimeoutException:
        print("Close popup button did not appear.")

def authorize_if_appears(driver):
    try:
        authorize_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='OAuth_Consent_Button']"))
        )
        authorize_button.click()
    except TimeoutException:
        print("Authorize app button did not appear.")

def accept_terms_if_appears(driver):
    try:
        accept_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.sc-fqkvVR.sc-iGgWBj.dQeymh.httOiR"))
        )
        accept_button.click()
    except TimeoutException:
        print("Accept button did not appear.")

def login():
    driver = setup_driver()
    driver.get("https://www.fantasy.top/home")

     # Load cookies and session storage
    load_browser_data(driver)
    driver.refresh()

    if check_login_success(driver) == False:
        clear_browser_data(driver)
        login_to_fantasy(driver, TWITTER_USERNAME, TWITTER_PASSWORD)

    # Save updated cookies and session storage
    save_browser_data(driver)

    time.sleep(2)
    actions = ActionChains(driver)
    actions.send_keys(Keys.ESCAPE).perform()

    token = driver.execute_script("return localStorage.getItem('jwtToken');")

    return driver, token

############################################################################
# Data Download Supporting Functions
############################################################################

def send_graphql_request(query=None, variables=None, token=None, request_type='graphql', params=None, cookies=None):
    if request_type == 'graphql':
        payload = json.dumps({
            "query": query,
            "variables": variables
        })
        headers = {
                'authorization': f'Bearer {token}',
                'content-type': 'application/json',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
                'accept': '*/*',
                'origin': 'https://fantasy.top',
                'sec-fetch-site': 'cross-site',
                'sec-fetch-mode': 'cors',
                'sec-fetch-dest': 'empty',
                'referer': 'https://fantasy.top/',
                'accept-encoding': 'gzip, deflate, br, zstd',
                'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
                'sec-ch-ua': '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"'
            }

        response = requests.post(URL_GRAPHQL, headers=headers, data=payload, cookies=cookies)
        response.raise_for_status()
        return response.json()
    
    elif request_type == 'rest':
        headers = {
            'accept': '*/*',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'authorization': f'Bearer {token}',
            'priority': 'u=1, i',
            'referer': 'https://fantasy.top/marketplace',
            'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        }
        response = requests.get(URL_REST, params=params, headers=headers, cookies=cookies)
        response.raise_for_status()
        return response.json()

def retry_request(func, max_retries=5, base_delay=1, max_delay=60, *args, **kwargs):
    """
    Retry a function call with exponential backoff and jitter.

    :param func: The function to retry.
    :param max_retries: Maximum number of retries.
    :param base_delay: Initial delay between retries in seconds.
    :param max_delay: Maximum delay between retries in seconds.
    :param *args, **kwargs: Arguments to pass to the function.
    :return: The result of the function call if successful.
    """
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if 'rate limit' in str(e).lower():
                if attempt == max_retries - 1:
                    raise  # Re-raise the exception if this was the last attempt
                
                # Calculate delay with exponential backoff and jitter
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                
                print(f"Rate limit exceeded. Retrying in {delay:.2f} seconds. (Attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                raise  # Re-raise the exception if it's not a rate limit error

    raise Exception(f"Function failed after {max_retries} attempts")

############################################################################
# Data Download Functions
############################################################################

def download_listings(driver):
    actions = ActionChains(driver)
    # Open DevTools
    actions.send_keys(Keys.F12).perform() 
    driver.get('https://fantasy.top/marketplace')
    time.sleep(5)
    actions.send_keys(Keys.ESCAPE).perform()
    try:
        main_element = driver.find_element(By.TAG_NAME, "main")
        main_element.click()
    except ElementClickInterceptedException:
        actions.send_keys(Keys.ESCAPE).perform()
        driver.get('https://fantasy.top/marketplace')
        time.sleep(5)
        main_element = driver.find_element(By.TAG_NAME, "main")
        main_element.click()
    time.sleep(2)
    
    all_logs = []
    num_iterations = 10
    interval = 3
    
    for _ in range(num_iterations):
        logs = driver.get_log("performance")
        all_logs.extend(logs)
        actions.send_keys(Keys.PAGE_DOWN).perform()
        time.sleep(interval)
    
    websocket_messages = []
    for log in all_logs:
        message = json.loads(log['message'])['message']
        
        # Print the log level to identify which ones are useful
        if 'level' in message:
            print(f"Log Level: {message['level']}")

        if message['method'] == 'Network.webSocketFrameReceived':
            try:
                payload = json.loads(message['params']['response']['payloadData'])
                if 'payload' in payload and 'data' in payload['payload']:
                    websocket_messages.append(payload)
            except (json.JSONDecodeError, KeyError):
                continue
    
    # Overwrite the JSON file with fresh data
    json_file_path = 'websocket_messages.json'
    with open(json_file_path, 'w') as f:
        json.dump(websocket_messages, f, indent=4)
    
    processed_data = []
    for message in websocket_messages:
        if 'payload' in message and 'data' in message['payload']:
            orders = message['payload']['data']['unique_sell_orders_stream']
            for order in orders:
                hero_data = order.get('hero', None)
                if hero_data is not None:  # Ensure hero_data is not None
                    hero_info = {
                        'hero_id': order['hero_id'],
                        'lowest_price': order['lowest_price'],
                        'order_count': order['order_count'],
                        'sell_order_id': order['sell_order_id'],
                        'hero_rarity_index': order['hero_rarity_index'],
                        'gliding_score': order['gliding_score'],
                        'updated_at': order['updated_at'],
                        'hero_followers_count': hero_data.get('followers_count', None),
                        'hero_handle': hero_data.get('handle', None),
                        'hero_name': hero_data.get('name', None),
                        'hero_stars': hero_data.get('stars', None),
                        'current_rank': hero_data.get('current_score', {}).get('current_rank', None) if hero_data.get('current_score') else None,
                        'previous_rank': hero_data.get('current_score', {}).get('previous_rank', None) if hero_data.get('current_score') else None,
                        'views': hero_data.get('current_score', {}).get('views', None) if hero_data.get('current_score') else None,
                        'fantasy_score': hero_data.get('current_score', {}).get('fantasy_score', None) if hero_data.get('current_score') else None
                    }
                    processed_data.append(hero_info)
    
    # Close DevTools
    actions.send_keys(Keys.F12).perform()

    # Delete the JSON file after processing
    if os.path.exists(json_file_path):
        os.remove(json_file_path)
        print(f"Deleted the file: {json_file_path}")
    else:
        print(f"The file {json_file_path} does not exist")

    raw_listings_df = pd.DataFrame(processed_data)
    listings_df = raw_listings_df.drop_duplicates(subset=['hero_id', 'hero_rarity_index'])
    listings_df.loc[:, 'rarity'] = listings_df['hero_rarity_index'].str.split('_').str[1]
    listings_df.loc[:, 'rarity'] = 'rarity' + listings_df['rarity']
    pivot_df = listings_df.pivot_table(
        index='hero_id',
        columns='rarity',
        values=['lowest_price', 'order_count'],
        aggfunc='first'
    )
    pivot_df.columns = [f'{col[1]}_{col[0]}' for col in pivot_df.columns]
    pivot_df.reset_index(inplace=True)
    hero_info_columns = ['hero_id', 'hero_handle', 'hero_name', 'hero_stars', 'hero_followers_count', 
                         'current_rank', 'previous_rank', 'views', 'fantasy_score']
    unique_hero_info = listings_df[hero_info_columns].drop_duplicates(subset=['hero_id'])
    final_df = pd.merge(unique_hero_info, pivot_df, on='hero_id')
    final_df.drop(columns=['hero_name', 'hero_followers_count', 
                           'current_rank', 'previous_rank', 'views', 'fantasy_score'], inplace=True)
    final_df = final_df.rename(columns={'heroId': 'hero_id'})
    return final_df

def download_portfolio(token):
    # Updated GraphQL query to match the Postman query
    query_get_cards = """
    query GET_CARDS($id: String!, $limit: Int = 100, $offset: Int = 0, $where: i_beta_player_cards_type_bool_exp = {}, $sort_order: String = "") {
      get_player_cards: get_player_cards_new(
        args: {p_owner: $id, p_limit: $limit, p_offset: $offset, p_sort_order: $sort_order}
        where: $where
      ) {
        owner
        hero_rarity_index
        cards_number
        listed_cards_number
        in_deck
        card {
          id
          owner
          gliding_score
          hero_rarity_index
          in_deck
          picture_url
          token_id
          hero_rarity_index
          rarity
          sell_order {
            id
            price_numeric
          }
          hero {
            id
            name
            handle
            profile_image_url_https
            followers_count
            flags {
              flag_id
            }
            stars
            current_score {
              fantasy_score
              views
              current_rank
            }
          }
          floor_price
          bids(limit: 1, order_by: {price: desc}) {
            id
            price
          }
        }
      }
    }
    """
    
    variables_get_cards = {
        "id": PLAYER_ID,
        "limit": 50,  # Maintain your limit of 50
        "offset": 0,
        "where": {
            "card": {
                "hero": {
                    "_or": [
                        {"name": {"_ilike": "%%"}},
                        {"handle": {"_ilike": "%%"}}
                    ]
                },
                "rarity": {"_in": ["1", "2", "3", "4"]}
            }
        },
        "sort_order": "cards_score"
    }
    
    def extract_portfolio_data(cards_response):
        if 'errors' in cards_response:
            print('Errors:', cards_response['errors'])
            return []
        else:
            cards = cards_response.get('data', {}).get('get_player_cards', [])
            card_list = []
            for card_entry in cards:
                card_data = card_entry['card']
                hero_data = card_data['hero']
                card_info = {
                    'owner': card_entry['owner'],
                    'hero_rarity_index': card_entry['hero_rarity_index'],
                    'cards_number': card_entry['cards_number'],
                    'listed_cards_number': card_entry['listed_cards_number'],
                    'in_deck': card_entry['in_deck'],
                    'card_id': card_data['id'],
                    'card_owner': card_data['owner'],
                    'gliding_score': card_data['gliding_score'],
                    'card_in_deck': card_data['in_deck'],
                    'picture_url': card_data['picture_url'],
                    'token_id': card_data['token_id'],
                    'rarity': card_data['rarity'],
                    'floor_price': card_data.get('floor_price'),
                    'bids': [
                        {
                            'bid_id': bid['id'],
                            'price': bid['price']
                        } for bid in card_data.get('bids', [])
                    ],
                    # Hero fields
                    'hero_id': hero_data['id'],
                    'hero_name': hero_data['name'],
                    'hero_handle': hero_data['handle'],
                    'hero_profile_image_url': hero_data['profile_image_url_https'],
                    'hero_followers_count': hero_data['followers_count'],
                    'hero_stars': hero_data['stars'],
                    'hero_fantasy_score': hero_data['current_score']['fantasy_score'],
                    'hero_views': hero_data['current_score']['views'],
                    'hero_current_rank': hero_data['current_score']['current_rank'],
                    # Flag fields as per Postman request
                    'hero_flags': [
                        {
                            'flag_id': flag['flag_id']
                        } for flag in hero_data.get('flags', [])
                    ]
                }
                card_list.append(card_info)
            return card_list
        
    all_cards_list = []
    while True:
        cards_response = send_graphql_request(query=query_get_cards, variables=variables_get_cards, token=token)
        portfolio_list = extract_portfolio_data(cards_response)
        if not portfolio_list:
            break
        all_cards_list.extend(portfolio_list)
        variables_get_cards['offset'] += variables_get_cards['limit']
    
    # Convert to DataFrame and ensure it contains all the needed columns
    portfolio_df = pd.DataFrame(all_cards_list)
    
    # Drop columns conditionally if they exist in the DataFrame
    columns_to_drop = ['owner', 'card_id', 'card_owner']
    portfolio_df = portfolio_df.drop(columns=[col for col in columns_to_drop if col in portfolio_df.columns], inplace=False)
    
    return portfolio_df


def download_basic_hero_stats(token):
    def extract_heros_data(response_data):
        if 'errors' in response_data:
            print('Errors:', response_data['errors'])
            return []
        heros = response_data.get('data', {}).get('twitter_data_current', [])
        hero_list = []
        for hero_entry in heros:
            hero_data = hero_entry['hero']
            hero_info = {
                'current_rank': hero_entry['current_rank'],
                'previous_rank': hero_entry['previous_rank'],
                'views': hero_entry['views'],
                'tweet_count': hero_entry['tweet_count'],
                'fantasy_score': hero_entry['fantasy_score'],
                'reach': hero_entry['reach'],
                'avg_views': hero_entry['avg_views'],
                'hero_followers_count': hero_data['followers_count'],
                'hero_name': hero_data['name'],
                'hero_handle': hero_data['handle'],
                'hero_profile_image_url': hero_data['profile_image_url_https'],
                'hero_volume': hero_data['volume']['aggregate']['sum']['price'] if hero_data['volume']['aggregate']['sum']['price'] is not None else 0,
                # Safely handle the hero_last_sale_price field
                'hero_last_sale_price': hero_data['last_sale'][0]['price'] if hero_data.get('last_sale') and len(hero_data['last_sale']) > 0 else None,
                # Safely handle the hero_floor_price field
                'hero_floor_price': hero_data['floor'][0]['lowest_price'] if hero_data.get('floor') and len(hero_data['floor']) > 0 else None
            }
            hero_list.append(hero_info)
        return hero_list
    
    # Modified GraphQL query to remove 'is_pending_hero'
    query_get_heros_with_stats = """
    query GET_HEROS_WITH_STATS($offset: Int = 0, $limit: Int = 20, $order_by: [twitter_data_current_order_by!] = {current_rank: asc}, $search: String = "") @cached(ttl: 300) {
      twitter_data_current(
        order_by: $order_by
        offset: $offset
        limit: $limit
        where: {hero: {_or: [{name: {_ilike: $search}}, {handle: {_ilike: $search}}], status: {_eq: "HERO"}}}
      ) {
        current_rank
        previous_rank
        views
        tweet_count
        fantasy_score
        reach
        avg_views
        hero {
          followers_count
          name
          handle
          profile_image_url_https
          volume: trades_aggregate {
            aggregate {
              sum {
                price
              }
            }
          }
          last_sale: trades(limit: 1) {
            price
          }
          floor: unique_sell_orders(order_by: {lowest_price: asc_nulls_last}, limit: 1) {
            lowest_price
          }
        }
      }
    }
    """
    
    variables_get_heros_with_stats = {
        "offset": 0,
        "order_by": {
            "fantasy_score": "desc"
        },
        "limit": 20,
        "search": "%%"
    }
    
    all_heros_list = []
    while True:
        heros_with_stats_response = send_graphql_request(query=query_get_heros_with_stats, variables=variables_get_heros_with_stats, token=token)
        heros_list = extract_heros_data(heros_with_stats_response)
        if not heros_list:
            break
        all_heros_list.extend(heros_list)
        variables_get_heros_with_stats['offset'] += variables_get_heros_with_stats['limit']
    
    all_heros_df = pd.DataFrame(all_heros_list)
    
    # Convert hero_volume and hero_last_sale_price to ETH where applicable
    if 'hero_volume' in all_heros_df.columns:
        all_heros_df['hero_volume'] = all_heros_df['hero_volume'].apply(convert_to_eth)
    
    if 'hero_last_sale_price' in all_heros_df.columns:
        all_heros_df['hero_last_sale_price'] = all_heros_df['hero_last_sale_price'].apply(convert_to_eth)

    # Drop columns if they exist in the DataFrame
    all_heros_df.drop(columns=['previous_rank', 'hero_last_sale_price', 'hero_floor_price'], inplace=True, errors='ignore')
    
    # Reorder the columns
    columns_order = ['current_rank', 'hero_name', 'hero_handle'] + [col for col in all_heros_df.columns if col not in ['current_rank', 'hero_name', 'hero_handle']]
    all_heros_df = all_heros_df[columns_order]
    
    return all_heros_df

def get_hero_stats(handle_list, token):
    
    '''
    Iterates an api call for each hero 
    '''
    def adjust_date(created_at_str):
        try:
            created_at = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%S.%f')
        except ValueError:
            created_at = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%S')
        if created_at.time() < datetime.strptime("12:00", "%H:%M").time():
            adjusted_date = created_at - timedelta(days=1)
        else:
            adjusted_date = created_at
        return adjusted_date.date()
    
    def parse_datetime(created_at_str):
        try:
            timestamp = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%S.%f')
        except ValueError:
            timestamp = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%S')
        return timestamp
        
    def get_hero_data(handle, token):
        # GraphQL query string
        query_get_hero_by_handle = """
        query GET_HERO_BY_HANDLE($handle: String!) {
        heroes: twitter_data_heroes(
            where: {handle: {_eq: $handle}, status: {_eq: "HERO"}}
        ) {
            followers_count
            is_player
            handle
            id
            name
            profile_image_url_https
            distribution_probability {
            inflation_degree
            }
            current_score {
            fantasy_score
            current_rank
            views
            }
            score_history(order_by: {created_at: desc}, limit: 300) {
            id
            fantasy_score
            current_rank
            created_at
            }
            tournament_scores(order_by: {created_at: asc}) {
            id
            current_rank
            views
            created_at
            }
            tweets(order_by: {views: desc}, where: {type: {_nin: ["Retweet", "Reply"]}}) {
            post_id
            bookmarks
            likes
            quotes
            replies
            retweets
            views
            created_at
            type
            fire_score
            impact_score
            health_score
            top_interacting_users
            }
            cards(limit: 1) {
            id
            picture_url
            rarity
            }
            cards_aggregate {
            aggregate {
                count
            }
            }
            trades(limit: 1, order_by: {timestamp: desc}) {
            id
            price
            }
            floor: unique_sell_orders(order_by: {lowest_price: asc_nulls_last}, limit: 4) {
            lowest_price
            hero_rarity_index
            }
        }
        }
        """
        variables = {"handle": handle}
        response_data = send_graphql_request(query=query_get_hero_by_handle, variables=variables, token=token)
        if 'errors' in response_data:
            print(f"Error fetching data for handle {handle}: {response_data['errors']}")
            return None
        hero_data = response_data.get('data', {}).get('heroes', [])
        if not hero_data:
            print(f"No data found for handle {handle}")
            return None
        return hero_data[0]
    
    def process_hero_data(hero_data):
        processed_data = {
            "handle": hero_data["handle"],
            "id": hero_data["id"],
            "inflation_degree": hero_data["distribution_probability"]["inflation_degree"] if hero_data["distribution_probability"] else None
        }
        score_history = hero_data.get("score_history", [])
        score_history_dict = {}
        closest_to_midnight = {}
    
        for entry in score_history:
            created_at = entry["created_at"]
            date = adjust_date(created_at)
            timestamp = parse_datetime(created_at)
            closing_score_key = f"{date} Closing Score"
            closing_rank_key = f"{date} Closing Rank"
            midnight = datetime.combine(date, datetime.min.time())
            time_diff = abs((timestamp - midnight).total_seconds())
            if closing_score_key not in closest_to_midnight or time_diff < closest_to_midnight[closing_score_key]:
                closest_to_midnight[closing_score_key] = time_diff
                score_history_dict[closing_score_key] = entry["fantasy_score"]
                score_history_dict[closing_rank_key] = entry["current_rank"]
        processed_data.update(score_history_dict)
        tournament_scores = hero_data.get("tournament_scores", [])
        for entry in tournament_scores:
            try:
                date = datetime.strptime(entry["created_at"], '%Y-%m-%dT%H:%M:%S.%f').date()
            except ValueError:
                date = datetime.strptime(entry["created_at"], '%Y-%m-%d').date()
            tournament_rank_key = f"{date} Tournament Rank"
            processed_data[tournament_rank_key] = entry["current_rank"]
        return processed_data

    all_hero_data = []
    for handle in tqdm(handle_list, desc="Processing heroes"):
        hero_data = get_hero_data(handle, token)
        if hero_data:
            processed_data = process_hero_data(hero_data)
            all_hero_data.append(processed_data)
        time.sleep(random.uniform(1, 3))
    
    hero_scores = pd.DataFrame(all_hero_data)
    hero_scores = hero_scores.rename(columns={'handle': 'hero_handle', 'id': 'hero_id'})
    return hero_scores

def get_hero_supply(hero_id_list, token):
    query_get_supply_per_hero_id = """
    query GET_SUPPLY_PER_HERO_ID($heroId: String!) @cached(ttl: 3600) {
      rarity1Count: indexer_cards_aggregate(
        where: {hero_id: {_eq: $heroId}, rarity: {_eq: 1}, owner: {_neq: "0x0000000000000000000000000000000000000000"}}
      ) {
        aggregate {
          count
        }
      }
      rarity2Count: indexer_cards_aggregate(
        where: {hero_id: {_eq: $heroId}, rarity: {_eq: 2}, owner: {_neq: "0x0000000000000000000000000000000000000000"}}
      ) {
        aggregate {
          count
        }
      }
      rarity3Count: indexer_cards_aggregate(
        where: {hero_id: {_eq: $heroId}, rarity: {_eq: 3}, owner: {_neq: "0x0000000000000000000000000000000000000000"}}
      ) {
        aggregate {
          count
        }
      }
      rarity4Count: indexer_cards_aggregate(
        where: {hero_id: {_eq: $heroId}, rarity: {_eq: 4}, owner: {_neq: "0x0000000000000000000000000000000000000000"}}
      ) {
        aggregate {
          count
        }
      }
      burnedCardsCount: indexer_cards_aggregate(
        where: {hero_id: {_eq: $heroId}, owner: {_eq: "0x0000000000000000000000000000000000000000"}}
      ) {
        aggregate {
          count
        }
      }
      utilityCount: indexer_cards_aggregate(
        where: {hero_id: {_eq: $heroId}, in_deck: {_eq: true}, owner: {_neq: "0x0000000000000000000000000000000000000000"}}
      ) {
        aggregate {
          count
        }
      }
    }
    """
    
    def process_get_supply_per_hero_id(response, hero_id):
        if 'errors' in response:
            print('Errors:', response['errors'])
            return pd.DataFrame()
        data = response.get('data', {})
        supply_data = {
            'heroId': hero_id,
            'rarity1Count': data['rarity1Count']['aggregate']['count'],
            'rarity2Count': data['rarity2Count']['aggregate']['count'],
            'rarity3Count': data['rarity3Count']['aggregate']['count'],
            'rarity4Count': data['rarity4Count']['aggregate']['count'],
            'burnedCardsCount': data['burnedCardsCount']['aggregate']['count'],
            'utilityCount': data['utilityCount']['aggregate']['count']
        }
        return pd.DataFrame([supply_data])
    
    def get_supply_per_hero_id(url, query, hero_id_list, token, delay=1, max_retries=3):
        all_supplies = []
        total_heroes = len(hero_id_list)
        with tqdm(total=total_heroes, desc="Fetching hero data") as pbar:
            for index, hero_id in enumerate(hero_id_list):
                variables = {"heroId": str(hero_id)}
                retries = 0
                while retries < max_retries:
                    try:
                        status_message = f"Fetching data for hero {hero_id} ({index+1}/{total_heroes}), attempt {retries+1} "
                        sys.stdout.write('\r' + status_message)
                        sys.stdout.flush()
                        response = send_graphql_request(query=query, variables=variables, token=token)
                        supply_df = process_get_supply_per_hero_id(response, hero_id)
                        all_supplies.append(supply_df)
                        sys.stdout.write(f"\rSuccessfully fetched data for hero {hero_id}          \n")
                        sys.stdout.flush()
                        time.sleep(delay)
                        break
                    except Exception as e:
                        sys.stdout.write(f"\rError fetching data for hero {hero_id}: {e}          \r")
                        sys.stdout.flush()
                        retries += 1
                        time.sleep(delay * retries)
                        if retries >= max_retries:
                            sys.stdout.write(f"\rFailed to fetch data for hero {hero_id} after {max_retries} attempts\n")
                            sys.stdout.flush()
                pbar.update(1)
        return pd.concat(all_supplies, ignore_index=True)
    
    all_hero_supplies_df = get_supply_per_hero_id(URL_GRAPHQL, query_get_supply_per_hero_id, hero_id_list, token)
    all_hero_supplies_df = all_hero_supplies_df.rename(columns={'heroId': 'hero_id'})
    return all_hero_supplies_df

def get_bids(hero_id_list, token, cookies):
    def get_highest_bids_for_hero(hero_id, token, cookies, rarity, delay=2, max_retries=3):
        hero_bids = {'hero_id': hero_id}
        params = {
            'hero_id': hero_id,
            'rarity': rarity,
            'include_orderbook': 'true',
            'include_personal_bids': 'true',
        }
        
        def request_func():
            response = send_graphql_request(request_type='rest', params=params, token=token, cookies=cookies)
            highest_bid = 0
            if response.get('orderbook_bids'):
                highest_bid = max(int(bid['price']) for bid in response['orderbook_bids'])
                highest_bid /= 1e18
            hero_bids[f'rarity{rarity}HighestBid'] = highest_bid
            return hero_bids
        
        result = retry_request(func=request_func, max_retries=max_retries, base_delay=delay)
        if result is None:
            tqdm.write(f"Failed to fetch data for hero {hero_id} rarity {rarity} after {max_retries} attempts")
            hero_bids[f'rarity{rarity}HighestBid'] = None
        
        return hero_bids
    
    def collect_highest_bids(hero_id_list, token, cookies, delay=7, max_retries=3):
        data = []
        total_heroes = len(hero_id_list)

        for rarity in range(4, 0, -1):  # Start from rarity 4 to 1
            tqdm.write(f"Processing rarity {rarity} for all heroes...")
            for index, hero_id in tqdm(enumerate(hero_id_list), total=total_heroes, desc=f"Rarity {rarity} Progress"):
                hero_bids = get_highest_bids_for_hero(hero_id, token, cookies, rarity, delay, max_retries)
                if hero_id in [d.get('hero_id') for d in data]:
                    existing_data = next(item for item in data if item['hero_id'] == hero_id)
                    existing_data.update(hero_bids)
                else:
                    data.append(hero_bids)
                time.sleep(delay)
        
        highest_bids_df = pd.DataFrame(data)
        return highest_bids_df
    
    highest_bids_df = collect_highest_bids(hero_id_list, token, cookies)
    return highest_bids_df

def download_hero_trades(hero_ids, token, max_retries=3):
    all_trades_data = []
    failed_requests = []
    query = """
    query GET_HERO_TRADES_CHART($hero_id: String!, $timestamp: timestamptz!) {
      indexer_trades(
        order_by: {timestamp: desc}
        where: {card: {hero_id: {_eq: $hero_id}}, timestamp: {_gte: $timestamp}}
      ) {
        timestamp
        card {
          rarity
          timestamp
        }
        price
      }
    }
    """
    timestamp = (datetime.utcnow() - timedelta(days=30)).isoformat()

    def process_hero(hero_id):
        variables = {
            "hero_id": str(hero_id),
            "timestamp": timestamp
        }

        def request_func():
            response_data = send_graphql_request(query=query, variables=variables, token=token)
            
            if 'errors' in response_data:
                error_message = response_data['errors'][0].get('message', '')
                if 'rate limit' in error_message.lower():
                    raise Exception(f"Rate limit exceeded for hero_id {hero_id}")
                else:
                    raise ValueError(f"Error fetching hero trades for hero_id {hero_id}: {error_message}")

            trades = response_data.get('data', {}).get('indexer_trades', [])
            return [
                {
                    'hero_id': hero_id,
                    'timestamp': trade['timestamp'],
                    'rarity': trade['card']['rarity'],
                    'price': convert_to_eth(trade['price'])
                }
                for trade in trades
            ]
        
        try:
            return retry_request(request_func, max_retries=3, base_delay=2, max_delay=30)
        except Exception as e:
            print(f"Failed to fetch data for hero_id {hero_id}: {str(e)}")
            return None

    with tqdm(hero_ids, desc="Fetching hero trades data") as pbar:
        for hero_id in pbar:
            result = process_hero(hero_id)
            if result is not None:
                all_trades_data.extend(result)
            else:
                failed_requests.append(hero_id)
            
            time.sleep(0.1)  # Small delay between requests

    # Retry failed requests
    if failed_requests:
        print(f"Retrying {len(failed_requests)} failed requests...")
        for hero_id in tqdm(failed_requests, desc="Retrying failed requests"):
            result = process_hero(hero_id)
            if result is not None:
                all_trades_data.extend(result)
            time.sleep(1)  # Longer delay for retries

    return pd.DataFrame(all_trades_data)

def get_last_trades(token):
    
    query_get_last_trade = """
    query GET_LAST_TRADE {
      indexer_trades(
        distinct_on: hero_rarity_index
        order_by: {hero_rarity_index: asc, timestamp: desc}
      ) {
        id
        hero_rarity_index
        price
        timestamp
      }
    }
    """
    
    def process_get_last_trade(response):
        if 'errors' in response:
            print('Errors:', response['errors'])
            return pd.DataFrame()
        trades = response.get('data', {}).get('indexer_trades', [])
        last_trade_data = []
        for trade in trades:
            hero_id, rarity = trade['hero_rarity_index'].split('_')
            last_trade_data.append({
                'heroId': hero_id,
                'rarity': f'rarity{rarity}',
                'lastSalePrice': convert_to_eth(trade['price']),
                'lastSaleTime': trade['timestamp']
            })
        return pd.DataFrame(last_trade_data)
    
    def get_last_trade(url, query, token):
        response = send_graphql_request(query=query, token=token)
        last_trade_df = process_get_last_trade(response)
        return last_trade_df
    
    last_trade_df = get_last_trade(URL_GRAPHQL, query_get_last_trade, token)
    pivoted_df = last_trade_df.pivot(index='heroId', columns='rarity', values=['lastSalePrice', 'lastSaleTime'])
    pivoted_df.columns = [f'{col[1]}{col[0]}' for col in pivoted_df.columns]
    pivoted_df.reset_index(inplace=True)
    pivoted_df = pivoted_df.rename(columns={'heroId': 'hero_id'})
    return pivoted_df

def get_hero_stars(token):

    QUERY_STAR_HISTORY_TABLE = """
        query QUERY_STAR_HISTORY_TABLE($limit: Int, $offset: Int) {
        twitter_data_heroes(
            limit: $limit
            offset: $offset
            order_by: {star_gain: desc_nulls_last}
            where: {status: {_eq: "HERO"}}
        ) {
            id
            handle
            profile_image_url_https
            stars
            name
            star_gain
        }
        }
        """
    
    def fetch_star_history_data(token, batch_size=20):
        all_heroes = []
        offset = 0
        
        while True:
            variables = {
                "limit": batch_size,
                "offset": offset
            }

            response = send_graphql_request(query=QUERY_STAR_HISTORY_TABLE, variables=variables, token=token)
            
            if 'errors' in response:
                print('Errors:', response['errors'])
                break  # Exit the loop on error
            
            heroes = response.get('data', {}).get('twitter_data_heroes', [])
            
            if not heroes:
                break  # Exit the loop if no more heroes are returned

            for hero in heroes:
                hero_info = {
                    'id': hero['id'],
                    'handle': hero['handle'],
                    'profile_image_url_https': hero['profile_image_url_https'],
                    'stars': hero['stars'],
                    'name': hero['name'],
                    'star_gain': hero['star_gain']
                }
                all_heroes.append(hero_info)
            
            offset += batch_size  # Move to the next batch
    
        return pd.DataFrame(all_heroes)
    
    return fetch_star_history_data(token)

def get_all_tournaments(url, gte, lte, token, player_id, filter_and_cleanse=True):
    ''' 
    Function to get all tournaments within a given time range and process the data.
    url: URL for the GraphQL endpoint
    gte: Start date in ISO format (e.g., '2022-01-01T00:00:00Z') 
    lte: End date in ISO format (e.g., '2022-01-31T23:59:59Z')
    player_id: Player ID for the tournaments (can be left as blank string if not needed)
    token: Authorization token for the GraphQL endpoint 
    filter_and_cleanse: Boolean flag to filter and cleanse the data to a unique list of tournaments that store the hero data(default is True)
    '''
    # Define the query
    query_get_tournaments_by_time = """
    query GET_TOURNAMENTS_BY_TIME($gte: timestamptz!, $lte: timestamptz!, $player_id: String!) {
      tournaments_tournament(
        where: {start_date: {_gte: $gte, _lte: $lte}}
        order_by: {start_date: desc}
      ) {
        id
        name
        description
        start_date
        end_date
        is_main
        league
        tournament_number
        player_history_count: players_history_aggregate(
          where: {player_id: {_eq: $player_id}}
        ) {
          aggregate {
            count
          }
        }
        total_players_count: players_history_aggregate {
          aggregate {
            count
          }
        }
        rewards {
          type
          distribution(path: "[0].reward")
          total_supply
        }
      }
    }
    """

    def parse_datetime(date_str):
        try:
            return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%fZ')
        except ValueError:
            return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S%z')

    def process_get_tournaments_by_time(response):
        if 'errors' in response:
            print('Errors:', response['errors'])
            return pd.DataFrame()

        tournaments = response.get('data', {}).get('tournaments_tournament', [])

        tournaments_data = []
        for tournament in tournaments:
            rewards_data = tournament.get('rewards', [{}])[0]
            tournaments_data.append({
                'id': tournament['id'],
                'name': tournament['name'],
                'description': tournament['description'],
                'start_date': tournament['start_date'],
                'end_date': tournament['end_date'],
                'start_day': parse_datetime(tournament['start_date']).strftime('%A'), 
                'end_day': parse_datetime(tournament['end_date']).strftime('%A'),
                'is_main': tournament['is_main'],
                'league': tournament['league'],
                'tournament_number': tournament['tournament_number'],
                'player_history_count': tournament['player_history_count']['aggregate']['count'],
                'total_players_count': tournament['total_players_count']['aggregate']['count'],
                'reward_type': rewards_data.get('type'),
                'reward_distribution': rewards_data.get('distribution'),
                'reward_total_supply': rewards_data.get('total_supply')
            })

        return pd.DataFrame(tournaments_data)

    def cleanse_name(name):
        name = re.sub(r'[^\w\s]', '', name)  # Remove all non-alphanumeric characters except whitespace
        name = re.sub(r'\s+', ' ', name)  # Replace multiple spaces with a single space
        return name.strip()  # Remove leading and trailing spaces

    def fix_name(row):
        # Check if 'main' is in either 'name' or 'description', and 'tournament_number' is not NaN
        if ('main' in row['name'].lower() or 'main' in row['description'].lower()) and not pd.isna(row['tournament_number']):
            return 'Main ' + str(row['tournament_number']).split('.')[0]
        else:
            return row['name']

    # Function to get tournaments and process them
    def fetch_and_process_tournaments():
      # Define query variables
      variables = {
          "gte": gte,
          "lte": lte,
          "player_id": player_id
      }
      
      # Send request and get the response
      response = send_graphql_request(query_get_tournaments_by_time, variables, token=token)
      
      # Process the response into a DataFrame
      tournaments_df = process_get_tournaments_by_time(response)
      
      # If filter_and_cleanse is False, return the raw DataFrame
      if not filter_and_cleanse:
          return tournaments_df
      
      # Filter and cleanse the DataFrame to get a list of unique tournaments that contain the hero tournament data. Where there are multiple leagues in the same tournament the league with the lowest number contains the hero tournament data, except for Main 2 and Main 3 where the highest league number contains the hero tournament data.
      # Custom sort logic to handle Main 2 and Main 3 differently
      def custom_sort_key(row):
          if row['is_main'] and row['tournament_number'] == 2:
              return -row['league']  # Sort in descending order for Main 2 (highest league number first)
          elif row['is_main'] and row['tournament_number'] == 3:
              return -row['league']  # Sort in descending order for Main 3 (highest league number first)
          else:
              return row['league']  # Sort in ascending order for other tournaments
      
      # Apply the custom sort logic and create a new column for sorting
      tournaments_df['custom_sort_key'] = tournaments_df.apply(custom_sort_key, axis=1)
      
      # Sort the DataFrame by 'start_date', 'end_date', and the custom sort key
      tournaments_df_sorted = tournaments_df.sort_values(by=['start_date', 'end_date', 'custom_sort_key'], ascending=[True, True, True])
      
      # Drop duplicates based on 'start_date' and 'end_date', keeping the desired league
      tournaments_df_filtered = tournaments_df_sorted.drop_duplicates(subset=['start_date', 'end_date'], keep='first')
      
      # Cleanse and simplify tournament names
      tournaments_df_filtered['name'] = tournaments_df_filtered['name'].apply(cleanse_name)
      tournaments_df_filtered['simplified_name'] = tournaments_df_filtered.apply(fix_name, axis=1)
      
      # Drop the temporary 'custom_sort_key' column
      tournaments_df_filtered = tournaments_df_filtered.drop(columns=['custom_sort_key'])
      
      return tournaments_df_filtered

    # Fetch and process tournaments
    return fetch_and_process_tournaments()

# Function to get tournament stats for a specific tournament_id
def get_tournament_stats(tournament_id, token):
    query_get_heros_with_stats_tournament = """
    query GET_HEROS_WITH_STATS_TOURNAMENT($tournament_id: String = "", $offset: Int = 0, $limit: Int = 20, $order_by: [twitter_data_tournament_history_order_by!] = {current_rank: asc}, $search: String = "") {
      twitter_data_current: twitter_data_tournament_history(
        where: {id: {_eq: $tournament_id}, hero: {_or: [{name: {_ilike: $search}}, {handle: {_ilike: $search}}]}}
        order_by: $order_by
        offset: $offset
        limit: $limit
      ) {
        current_rank
        previous_rank
        views
        tweet_count
        fantasy_score
        reach
        avg_views
        hero {
          followers_count
          name
          handle
          profile_image_url_https
          volume: trades_aggregate {
            aggregate {
              sum {
                price
              }
            }
          }
          last_sale: trades(limit: 1) {
            price
          }
          floor: unique_sell_orders(order_by: {lowest_price: asc_nulls_last}, limit: 1) {
            lowest_price
          }
        }
      }
    }
    """
    
    def process_get_heros_with_stats_tournament(response):
        if 'errors' in response:
            print('Errors:', response['errors'])
            return pd.DataFrame()
        
        heros = response.get('data', {}).get('twitter_data_current', [])
        
        heros_data = []
        for hero_entry in heros:
            hero = hero_entry['hero']
            heros_data.append({
                'current_rank': hero_entry['current_rank'],
                'previous_rank': hero_entry['previous_rank'],
                'views': hero_entry['views'],
                'tweet_count': hero_entry['tweet_count'],
                'fantasy_score': hero_entry['fantasy_score'],
                'reach': hero_entry['reach'],
                'avg_views': hero_entry['avg_views'],
                'hero_followers_count': hero['followers_count'],
                'hero_name': hero['name'],
                'hero_handle': hero['handle'],
                'hero_profile_image_url': hero['profile_image_url_https'],
                'hero_volume': convert_to_eth(hero['volume']['aggregate']['sum']['price']),
                'hero_last_sale_price': convert_to_eth(hero['last_sale'][0]['price']),
                'hero_floor_price': convert_to_eth(hero['floor'][0]['lowest_price'])
            })
        
        return pd.DataFrame(heros_data)
    
    def get_heros_with_stats_tournament(url, query, tournament_id, offset, limit, order_by, search, token, max_retries=5, delay=2):
      variables = {
          "tournament_id": tournament_id,
          "offset": offset,
          "order_by": order_by,
          "limit": limit,
          "search": search
      }

      retries = 0
      while retries < max_retries:
          response = send_graphql_request(query, variables, token=token)
          if 'errors' in response:
              error_code = response['errors'][0]['extensions']['code']
              if error_code == 'rate-limit-exceeded':
                  print(f"Rate limit exceeded, sleeping for {delay} seconds. Attempt {retries + 1}/{max_retries}")
                  time.sleep(delay)
                  delay *= 2  # Exponential backoff
                  retries += 1
              else:
                  print(f"Query: {query}")
                  print(f"Variables: {variables}")
                  raise Exception(f"Error fetching data: {response['errors']}")
          else:
              return process_get_heros_with_stats_tournament(response)
      raise Exception("Max retries exceeded")

    
    # Get hero stats for the specified tournament
    offset = 0
    order_by = {"fantasy_score": "desc"}
    limit = 200
    search = "%%"

    
    heros_with_stats_tournament_df = get_heros_with_stats_tournament(URL_GRAPHQL, query_get_heros_with_stats_tournament, tournament_id, offset, limit, order_by, search, token)
    
    return heros_with_stats_tournament_df

# Function to get stats for all tournaments in the DataFrame, with an option to check for existing files. If check_existing is false, it will fetch data for all tournaments.
def update_tournaments_stats(token, check_existing=True):

    gte = "1970-01-01T00:00:00.000Z"
    lte = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    # Get filtered and cleansed results
    tournaments_df = get_all_tournaments(URL_GRAPHQL, gte, lte, token, player_id= "")

    for idx, row in tournaments_df.iterrows():
        tournament_id = row['id']
        simplified_name = row['simplified_name'].replace(' ', '_')
        tournament_start = row['start_date'].split('T')[0]  # Assuming ISO format (YYYY-MM-DDTHH:MM:SS)
        tournament_end = row['end_date'].split('T')[0]

        print(f"Processing tournament: {simplified_name} (ID: {tournament_id})")

        try:
            # Generate the directory and file path
            tournament_results_folder = os.path.join(DATA_FOLDER, 'tournament_results')
            os.makedirs(tournament_results_folder, exist_ok=True)
            csv_filename = f"{simplified_name}_{tournament_start}_{tournament_end}.csv"
            file_path = os.path.join(tournament_results_folder, csv_filename)

            # Check if the file already exists, if enabled
            if check_existing and os.path.isfile(file_path):
                print(f"File {csv_filename} already exists. Skipping API call.")
                continue  # Skip fetching data if the file already exists

            # Fetch the tournament stats if the file doesn't exist
            tournament_stats_df = get_tournament_stats(tournament_id, token)

            if len(tournament_stats_df) > 0:
                # Save to CSV
                tournament_stats_df.to_csv(file_path, index=False)
                print(f"DataFrame for {simplified_name} saved to {file_path} with {len(tournament_stats_df)} rows")
            else:
                print(f"No data for tournament {simplified_name} (ID: {tournament_id})")

        except Exception as e:
            print(f"Failed to fetch data for tournament {tournament_id} with error: {str(e)}")

def get_tournament_status(player_id, token):
    def get_registered_tournament_data(player_id, token):
        query_get_registered_tournament_ids = """
        query GET_REGISTERED_TOURNAMENT_IDS($player_id: String!) {
            tournaments_current_players(
            where: {player_id: {_eq: $player_id}}
            distinct_on: tournament_id
            ) {
            tournament_id
            tournament {
                id
                name
                description
                start_date
                end_date
                is_main
                league
                is_visible
                tournament_number
                reward_image
                rewards {
                type
                distribution(path: "[0].reward")
                total_supply
                total_distribution: distribution
                }
                current_players_aggregate(where: {is_registered: {_eq: true}}) {
                aggregate {
                    count
                }
                }
                players_history_aggregate {
                aggregate {
                    count
                }
                }
                flags
                players_history(where: {player_id: {_eq: $player_id}}) {
                id
                rank
                rewards_details
                score
                }
                current_players(where: {player_id: {_eq: $player_id}}) {
                is_registered
                rank
                score
                }
            }
            }
        }
        """

        variables = {
            "player_id": player_id
        }

        response = send_graphql_request(query=query_get_registered_tournament_ids, variables=variables, token=token)
        return response

    def extract_registered_tournament_data(response):
        tournaments = response.get('data', {}).get('tournaments_current_players', [])
        data = []
        
        for tournament_entry in tournaments:
            tournament = tournament_entry['tournament']
            description = tournament['description']
            
            for player in tournament['current_players']:
                row = {
                    'Description': description,
                    'Deck No': len(data) + 1,  # Assuming Deck No is just a sequential index
                    'Rank': player['rank']
                }
                
                # Initialize rewards
                row['ETH'] = 0
                row['Pack'] = 0
                row['Gold'] = 0
                
                # Check rewards for each type
                for reward in tournament['rewards']:
                    total_distribution = reward['total_distribution']
                    
                    # Handle total_distribution being a list or a dictionary
                    if isinstance(total_distribution, list):
                        for dist in total_distribution:
                            if dist['start'] <= player['rank'] <= dist['end']:
                                if reward['type'] == 'ETH':
                                    row['ETH'] = dist['reward']
                                elif reward['type'] == 'PACK':
                                    row['Pack'] = dist['reward']
                                elif reward['type'] == 'GOLD':
                                    row['Gold'] = dist['reward']
                    elif isinstance(total_distribution, dict):
                        # If it's a dictionary, handle it accordingly
                        max_value = total_distribution.get('max')
                        min_value = total_distribution.get('min')
                        # You can add logic here to handle this case if applicable
                        # For now, let's skip this as it's not clear how to handle it
                        continue
                
                data.append(row)
        
        return pd.DataFrame(data)

    def create_trournament_rank_rewards_table(token):
        response = get_registered_tournament_data(player_id, token)
        tournament_standings = extract_registered_tournament_data(response)
        
        # Convert the tournament data to a DataFrame (if necessary) and save it as a CSV
        
        return tournament_standings
        #  save_df_as_csv(tournaments_df, 'registered_tournaments')

    current_tournaments_standings = create_trournament_rank_rewards_table(token)

    return current_tournaments_standings


############################################################################
# Functions to provide seed data to the main functions
############################################################################


def get_latest_file(directory, prefix):
    files = glob.glob(os.path.join(directory, f'{prefix}*.csv'))
    if not files:
        raise FileNotFoundError(f"No files starting with '{prefix}' found in {directory}")
    latest_file = max(files, key=os.path.getmtime)
    return latest_file

def get_hero_data_list(target_data):
    assert target_data in ['id', 'handle'], f"Invalid target_data: {target_data}. Expected 'id' or 'handle'."
    
    if target_data == 'id':
        hero_stats_df = pd.read_csv(get_latest_file(DATA_FOLDER, 'star_history'))
        return hero_stats_df['id'].to_list()
    elif target_data == "handle":
        basic_hero_stats_df = pd.read_csv(get_latest_file(DATA_FOLDER, 'star_history'))
        return basic_hero_stats_df['handle'].to_list()
    

############################################################################
# Functions for saving data to CSV
############################################################################

def update_basic_hero_stats(driver, token):
    basic_hero_stats_df = print_runtime(download_basic_hero_stats, token)
    save_df_as_csv(basic_hero_stats_df, 'basic_hero_stats')

def update_portfolio(driver, token):
    portfolio_df = print_runtime(download_portfolio, token)
    save_df_as_csv(portfolio_df, 'portfolio')

def update_last_trades(driver, token):
    last_trades_df = print_runtime(get_last_trades, token)
    save_df_as_csv(last_trades_df, 'last_trades')

def update_listings(driver):
    listings_df = print_runtime(download_listings, driver)
    save_df_as_csv(listings_df, 'listings')

def update_hero_stats(driver, token):
    hero_handles = get_hero_data_list('handle')
    hero_stats_df = print_runtime(get_hero_stats, hero_handles, token)
    save_df_as_csv(hero_stats_df, 'hero_stats')

def update_hero_trades(driver, token):
    hero_ids = get_hero_data_list('id')
    hero_trades_df = print_runtime(download_hero_trades, hero_ids, token)
    save_df_as_csv(hero_trades_df, 'hero_trades')
    
def update_hero_supply(driver, token):
    hero_ids = get_hero_data_list('id')
    hero_supply_df = print_runtime(get_hero_supply, hero_ids, token)
    save_df_as_csv(hero_supply_df, 'hero_card_supply')

def update_bids(driver, token):
    hero_ids = get_hero_data_list('id')
    cookies = {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}
    bids_df = print_runtime(get_bids, hero_ids, token, cookies)
    save_df_as_csv(bids_df, 'bids')

def update_star_history(driver, token):
    star_history_df = print_runtime(get_hero_stars, token)
    save_df_as_csv(star_history_df, 'star_history')

def update_tournament_history(driver, token):
    print_runtime(update_tournaments_stats, token)

def update_tournament_status(driver, token):
    tournament_standings = print_runtime(get_tournament_status, PLAYER_ID, token)
    tournament_standings.to_csv(DATA_FOLDER +'/current_tournament_standings.csv')


# Main Execution Function with Reusable Driver and Token

def main():
    driver, token = login()
    try:
        update_star_history(driver, token)
        update_tournament_status(PLAYER_ID, token)
        update_basic_hero_stats(driver, token)
        update_portfolio(driver, token) 
        # update_last_trades(driver, token)
        update_listings(driver)
        update_hero_stats(driver, token)
        update_hero_trades(driver, token)
        update_hero_supply(driver, token)
        update_bids(driver, token)
        update_tournament_history(driver, token)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()