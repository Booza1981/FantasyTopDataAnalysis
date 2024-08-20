import os
import re
import json
import time
import random
import glob
import sys
import requests
import pandas as pd
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
from fake_useragent import UserAgent


# Load environment variables from .env file
load_dotenv()


# Global Variables
PLAYER_ID = os.getenv("PLAYER_ID")
URL_GRAPHQL = os.getenv("URL_GRAPHQL")
URL_REST = os.getenv("URL_REST")
DATA_FOLDER = 'data'

COOKIES_FILE = 'cookies.pkl'
SESSION_FILE = 'session.pkl'
LOCAL_STORAGE_FILE = 'local_storage.pkl'

print(f"DATA_FOLDER is set to: {DATA_FOLDER}")


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

# WebDriver and Login

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
    driver = webdriver.Chrome(options=options)
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
            print("Login successful: The element has children.")
            return True
        else:
            print("Login failed: The element does not have children.")
            return False
        
    except TimeoutException:
        print("The element was not found on the page.")
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

# Data Download Functions

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

def download_portfolio(token):
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
            trades(
              order_by: {hero_rarity_index: asc, created_at: desc}
              distinct_on: hero_rarity_index
            ) {
              id
              hero_rarity_index
              price
            }
          }
        }
      }
    }
    """
    variables_get_cards = {
        "id": PLAYER_ID,
        "limit": 50,
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
                    'hero_id': hero_data['id'],
                    'hero_name': hero_data['name'],
                    'hero_handle': hero_data['handle'],
                    'hero_profile_image_url': hero_data['profile_image_url_https'],
                    'hero_followers_count': hero_data['followers_count'],
                    'hero_stars': hero_data['stars'],
                    'hero_fantasy_score': hero_data['current_score']['fantasy_score'],
                    'hero_views': hero_data['current_score']['views'],
                    'hero_current_rank': hero_data['current_score']['current_rank'],
                    'hero_trades': [
                        {
                            'trade_id': trade['id'],
                            'hero_rarity_index': trade['hero_rarity_index'],
                            'price': trade['price']
                        } for trade in hero_data['trades']
                    ]
                }
                card_list.append(card_info)
            return card_list
        
    all_cards_list = []
    while True:
        cards_response = send_graphql_request(query_get_cards, variables_get_cards, token)
        portfolio_list = extract_portfolio_data(cards_response)
        if not portfolio_list:
            break
        all_cards_list.extend(portfolio_list)
        variables_get_cards['offset'] += variables_get_cards['limit']
    
    portfolio_df = pd.DataFrame(all_cards_list)
    portfolio_df.drop(columns=['owner', 'card_id', 'card_owner'], inplace=True)
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
                'hero_last_sale_price': hero_data['last_sale'][0]['price'] if hero_data['last_sale'] else None,
                'hero_floor_price': hero_data['floor'][0]['lowest_price'] if hero_data['floor'] else None
            }
            hero_list.append(hero_info)
        return hero_list
    
    query_get_heros_with_stats = """
    query GET_HEROS_WITH_STATS($offset: Int = 0, $limit: Int = 20, $order_by: [twitter_data_current_order_by!] = {current_rank: asc}, $search: String = "") @cached(ttl: 300) {
      twitter_data_current(
        order_by: $order_by
        offset: $offset
        limit: $limit
        where: {hero: {_or: [{name: {_ilike: $search}}, {handle: {_ilike: $search}}], is_pending_hero: {_eq: false}}}
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
    if 'hero_volume' in all_heros_df.columns:
      all_heros_df['hero_volume'] = all_heros_df['hero_volume'].apply(convert_to_eth)
    all_heros_df['hero_last_sale_price'] = all_heros_df['hero_last_sale_price'].apply(convert_to_eth)
    all_heros_df.drop(columns=['previous_rank', 'hero_last_sale_price', 'hero_floor_price'], inplace=True)
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
                        status_message = f"Fetching data for hero {hero_id} ({index+1}/{total_heroes}), attempt {retries+1}"
                        sys.stdout.write(status_message)
                        sys.stdout.flush()
                        response = send_graphql_request(query=query, variables=variables, token=token)
                        supply_df = process_get_supply_per_hero_id(response, hero_id)
                        all_supplies.append(supply_df)
                        sys.stdout.write(f"Successfully fetched data for hero {hero_id}          \n")
                        sys.stdout.flush()
                        time.sleep(delay)
                        break
                    except Exception as e:
                        sys.stdout.write(f"Error fetching data for hero {hero_id}: {e}          \r")
                        sys.stdout.flush()
                        retries += 1
                        time.sleep(delay * retries)
                        if retries >= max_retries:
                            sys.stdout.write(f"Failed to fetch data for hero {hero_id} after {max_retries} attempts\n")
                            sys.stdout.flush()
                pbar.update(1)
        return pd.concat(all_supplies, ignore_index=True)
    
    all_hero_supplies_df = get_supply_per_hero_id(URL_GRAPHQL, query_get_supply_per_hero_id, hero_id_list, token)
    all_hero_supplies_df = all_hero_supplies_df.rename(columns={'heroId': 'hero_id'})
    return all_hero_supplies_df

def get_bids(hero_id_list, token, cookies):
    def get_highest_bids_for_hero(hero_id, token, cookies, delay=2, max_retries=3):
        hero_bids = {'hero_id': hero_id}
        for rarity in range(1, 5):
            params = {
                'hero_id': hero_id,
                'rarity': rarity,
                'include_orderbook': 'true',
                'include_personal_bids': 'true',
            }
            retries = 0
            while retries < max_retries:
                try:
                    status_message = f"Fetching data for hero {hero_id} rarity {rarity}, attempt {retries + 1}\r"
                    sys.stdout.write(status_message)
                    sys.stdout.flush()
                    response = send_graphql_request(request_type='rest', params=params, token=token, cookies=cookies)
                    highest_bid = 0
                    if response.get('orderbook_bids'):
                        highest_bid = max(int(bid['price']) for bid in response['orderbook_bids'])
                        highest_bid /= 1e18
                    hero_bids[f'rarity{rarity}HighestBid'] = highest_bid
                    break
                except Exception as e:
                    sys.stdout.write(f"Error fetching data for hero {hero_id} rarity {rarity}: {e}, attempt {retries + 1}\r")
                    sys.stdout.flush()
                    retries += 1
                    time.sleep(delay * retries)
            if retries >= max_retries:
                sys.stdout.write(f"Failed to fetch data for hero {hero_id} rarity {rarity} after {max_retries} attempts\n")
                sys.stdout.flush()
                hero_bids[f'rarity{rarity}HighestBid'] = None
        return hero_bids
    
    def collect_highest_bids(hero_id_list, token, cookies, delay=7, max_retries=3):
        data = []
        total_heroes = len(hero_id_list)
        for index, hero_id in enumerate(hero_id_list):
            status_message = f"Processing hero {hero_id} ({index + 1}/{total_heroes})...\r"
            sys.stdout.write(status_message)
            sys.stdout.flush()
            hero_bids = get_highest_bids_for_hero(hero_id, token, cookies, delay, max_retries)
            data.append(hero_bids)
            sys.stdout.write(f"Completed {index + 1} out of {total_heroes}\n")
            sys.stdout.flush()
            time.sleep(delay)
        highest_bids_df = pd.DataFrame(data)
        return highest_bids_df
    
    highest_bids_df = collect_highest_bids(hero_id_list, token, cookies)
    return highest_bids_df


def download_hero_trades(hero_ids, token):
    all_trades_data = []

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

    headers = {
        'authorization': f'Bearer {token}',
        'content-type': 'application/json'
    }

    timestamp = (datetime.utcnow() - timedelta(days=30)).isoformat()

    for hero_id in tqdm(hero_ids, desc="Fetching hero trades data"):
        variables = {
            "hero_id": str(hero_id),
            "timestamp": timestamp
        }
        payload = {
            "query": query,
            "variables": variables,
            "operationName": "GET_HERO_TRADES_CHART"
        }

        try:
            response = requests.post(URL_GRAPHQL, headers=headers, json=payload)
            response_data = response.json()

            if 'errors' in response_data:
                print(f"Error fetching hero trades for hero_id {hero_id}: {response_data['errors']}")
                continue

            trades = response_data.get('data', {}).get('indexer_trades', [])
            for trade in trades:
                trade_data = {
                    'hero_id': hero_id,
                    'timestamp': trade['timestamp'],
                    'rarity': trade['card']['rarity'],
                    'price': trade['price']
                }
                all_trades_data.append(trade_data)

        except Exception as e:
            print(f"Failed to fetch data for hero_id {hero_id}: {e}")

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

def get_latest_file(directory, prefix):
    files = glob.glob(os.path.join(directory, f'{prefix}*.csv'))
    if not files:
        raise FileNotFoundError(f"No files starting with '{prefix}' found in {directory}")
    latest_file = max(files, key=os.path.getmtime)
    return latest_file

def get_hero_data_list(target_data):
    assert target_data in ['id', 'handle'], f"Invalid target_data: {target_data}. Expected 'id' or 'handle'."
    
    if target_data == 'id':
        hero_stats_df = pd.read_csv(get_latest_file(DATA_FOLDER, 'hero_stats'))
        return hero_stats_df['hero_id'].to_list()
    elif target_data == "handle":
        basic_hero_stats_df = pd.read_csv(get_latest_file(DATA_FOLDER, 'basic_hero_stats'))
        return basic_hero_stats_df['hero_handle'].to_list()

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

# Main Execution Function with Reusable Driver and Token

def main():
    driver, token = login()
    try:
        # update_basic_hero_stats(driver, token)
        # update_portfolio(driver, token)
        # update_last_trades(driver, token)
        # update_listings(driver)
        update_hero_stats(driver, token)
        # update_hero_trades(driver, token)
        # update_hero_supply(driver, token)
        # update_bids(driver, token)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()