import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from get_data_script import (
    login, update_basic_hero_stats, update_portfolio, update_last_trades, 
    update_listings, update_hero_stats, update_hero_supply, update_bids, 
    update_hero_trades, update_tournament_status, update_star_history
)
from data_compiler import compile_data
import glob
import os
import feedparser
import streamlit.components.v1 as components
from datetime import datetime

###########################
# RSS Feed Parsing
###########################
# Set the number of initial tweets to load
INITIAL_TWEET_COUNT = 50

# RSS Feed Parsing with sorting by time
def extract_and_sort_tweets(feed_urls):
    tweets = []
    for feed_url in feed_urls:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            if "twitter.com" in entry.link or "x.com" in entry.link:
                published_time = datetime(*entry.published_parsed[:6])
                tweets.append({
                    "url": entry.link,
                    "published": published_time
                })
    
    # Sort tweets by published time in descending order (latest first)
    tweets.sort(key=lambda x: x["published"], reverse=True)
    
    return [tweet["url"] for tweet in tweets]

# Combine and sort multiple RSS feed URLs by time
rss_feed_urls = [
    "https://rss.app/feeds/AmeRmN5MSkkwKGXN.xml",
    "https://rss.app/feeds/EDa6EjIpUa04bSdv.xml"
]
tweet_urls = extract_and_sort_tweets(rss_feed_urls)

# Function to generate HTML for tweets
def generate_tweet_html(tweet_urls, count=INITIAL_TWEET_COUNT):
    tweet_divs = "\n".join([f'<div id="tweet-{i}"></div>' for i in range(count)])
    tweet_ids = ",".join([f'"{url.split("/")[-1]}"' for url in tweet_urls[:count]])

    html_code = f"""
    <div id="tweet-container" style="height: 100vh; overflow-y: auto;">
        {tweet_divs}
    </div>
    <script type="text/javascript">
        var tweetIds = [{tweet_ids}];
        
        function loadTweets() {{
            tweetIds.forEach(function(id, index) {{
                var tweetElement = document.getElementById('tweet-' + index);
                if (tweetElement && !tweetElement.hasChildNodes()) {{
                    twttr.widgets.createTweet(id, tweetElement, {{
                        align: 'center'
                    }});
                }}
            }});
        }}

        if (typeof twttr === 'undefined') {{
            var script = document.createElement("script");
            script.src = "https://platform.twitter.com/widgets.js";
            script.async = true;
            script.onload = function () {{
                loadTweets();
            }};
            document.head.appendChild(script);
        }} else {{
            loadTweets();
        }}
    </script>
    """
    return html_code

###########################
# Functions for Deck layout
###########################
def load_latest_file(pattern):
    files = glob.glob(pattern)
    if not files:
        return None
    latest_file = max(files, key=os.path.getmtime)
    return pd.read_csv(latest_file)

def display_deck(deck_df):
    # Calculate the total for 'Main_Last_4_Ave'
    total_main_last_4_ave = deck_df['Main_Last_4_Ave'].sum()

    # Display the deck name and total Main_Last_4_Ave
    st.markdown(f"### {deck_df['Deck_Name'].iloc[0]}")
    st.write(f"**Total Main Last 4 Average:** {total_main_last_4_ave:.2f}")

    # Create exactly 5 columns for each deck
    cols = st.columns(5)

    # Ensure we don't access columns out of range
    for idx in range(5):
        if idx < len(deck_df):  # If there's data for this column
            row = deck_df.iloc[idx]
            with cols[idx]:
                st.image(row['picture_url'], caption=row['hero_name'], width=100)
                st.write(f"Stars: {row['hero_stars']}")
                st.write(f"Rank: {row['current_rank']}")
                st.write(f"Gliding Score: {row['gliding_score']}")
                st.write(f"Main Last 4 Ave: {row['Main_Last_4_Ave']:.2f}")
        else:  # If no data for this column, leave it blank
            with cols[idx]:
                st.write("")




###########################


# Set page configuration
st.set_page_config(
    page_title="Fantasy Top Analytics",
    layout="wide"
    )

# Initialize WebDriver and Token placeholders in session state
if 'driver' not in st.session_state:
    st.session_state.driver = None
    st.session_state.token = None

if 'is_updating' not in st.session_state:
    st.session_state.is_updating = False

# Initialize rerun key in session state
if 'rerun_key' not in st.session_state:
    st.session_state.rerun_key = 0

# Function to update and compile data
def run_update_and_compile(selected_updates):
    st.session_state.is_updating = True
    st.session_state.update_status = "Starting update and compilation..."

    # Update the status message in the sidebar
    with st.sidebar:
        st.sidebar.info(st.session_state.update_status)

    try:
        if "Update Tournament Status" in selected_updates:
            st.session_state.update_status = "Updating Tournament Status..."
            with st.sidebar:
                st.sidebar.info(st.session_state.update_status)
            get_tournament_status(st.session_state.driver, st.session_state.token)

        if st.session_state.driver is None or st.session_state.token is None:
            st.session_state.update_status = "Logging in..."
            with st.sidebar:
                st.sidebar.info(st.session_state.update_status)
            st.session_state.driver, st.session_state.token = login()

        if "Update Tournament Scores" in selected_updates:
            st.session_state.update_status = "Updating Tournament Scores..."
            with st.sidebar:
                st.sidebar.info(st.session_state.update_status)
            update_tournament_status(st.session_state.driver, st.session_state.token)

        if "Update Basic Hero Stats" in selected_updates:
            st.session_state.update_status = "Updating Basic Hero Stats..."
            with st.sidebar:
                st.sidebar.info(st.session_state.update_status)
            update_basic_hero_stats(st.session_state.driver, st.session_state.token)
        
        if "Update Portfolio" in selected_updates:
            st.session_state.update_status = "Updating Portfolio..."
            with st.sidebar:
                st.sidebar.info(st.session_state.update_status)
            update_portfolio(st.session_state.driver, st.session_state.token)
        
        if "Update Last Trades" in selected_updates:
            st.session_state.update_status = "Updating Last Trades..."
            with st.sidebar:
                st.sidebar.info(st.session_state.update_status)
            update_last_trades(st.session_state.driver, st.session_state.token)
        
        if "Update Listings" in selected_updates:
            st.session_state.update_status = "Updating Listings..."
            with st.sidebar:
                st.sidebar.info(st.session_state.update_status)
            update_listings(st.session_state.driver)
        
        if "Update Hero Stats" in selected_updates:
            st.session_state.update_status = "Updating Hero Stats..."
            with st.sidebar:
                st.sidebar.info(st.session_state.update_status)
            update_hero_stats(st.session_state.driver, st.session_state.token)
        
        if "Update Hero Trades" in selected_updates:
            st.session_state.update_status = "Updating Hero Trades..."
            with st.sidebar:
                st.sidebar.info(st.session_state.update_status)
            update_hero_trades(st.session_state.driver, st.session_state.token)
        
        if "Update Hero Supply" in selected_updates:
            st.session_state.update_status = "Updating Hero Supply..."
            with st.sidebar:
                st.sidebar.info(st.session_state.update_status)
            update_hero_supply(st.session_state.driver, st.session_state.token)
        
        if "Update Bids" in selected_updates:
            st.session_state.update_status = "Updating Bids..."
            with st.sidebar:
                st.sidebar.info(st.session_state.update_status)
            update_bids(st.session_state.driver, st.session_state.token)

        if "Update Star History" in selected_updates:
            st.session_state.update_status = "Updating Star History..."
            with st.sidebar:
                st.sidebar.info(st.session_state.update_status)
            update_star_history(st.session_state.driver, st.session_state.token)
        
        st.session_state.update_status = "Compiling Data..."
        with st.sidebar:
            st.sidebar.info(st.session_state.update_status)
        compile_data()

        st.sidebar.success("Data update and compilation completed successfully!")

        # Simulate rerun by updating the session state key
        st.session_state.rerun_key = st.session_state.get('rerun_key', 0) + 1

    except Exception as e:
        st.sidebar.error(f"An error occurred: {str(e)}")
    finally:
        st.session_state.is_updating = False


# Sidebar for page navigation
st.sidebar.title("Navigation")

# Show the update status at the top of the sidebar
if st.session_state.is_updating:
    st.sidebar.info(st.session_state.update_status)

page_selection = st.sidebar.selectbox("Go to", ["Portfolio Data", "All Heroes", "Tournament Scores Over Time", "Best Decks"], index=0)

# Common CSS styling for the tables
def apply_table_styling():
    st.markdown("""
        <style>
        /* Container for the sticky header and metrics */
        .sticky-header {
            position: sticky;
            top: 0;
            z-index: 10;
            background-color: inherit; /* Match background color with the rest of the page */
            padding-top: 10px;
            padding-bottom: 10px;
            margin-bottom: 20px; /* Added margin to prevent overlap */
        }

        /* Styling for the DataFrame container */
        .dataframe-container {
            max-height: calc(100vh - 200px); /* Adjust height dynamically */
            overflow-y: auto;
        }

        /* Table styling */
        .dataframe {
            border-collapse: separate;
            border-spacing: 0;
        }
        .dataframe th, .dataframe td {
            padding: 8px;
            text-align: left;
            border: 1px solid #ddd;
        }
        .dataframe th {
            position: sticky;
            top: 0;
            z-index: 1;
            background-color: #f1f1f1;
            color: #333;
        }
        </style>
    """, unsafe_allow_html=True)


def apply_hover_highlight():
    st.markdown("""
        <style>
        .dataframe-container {
            position: relative;
        }
        .dataframe-container table {
            border-collapse: collapse;
            width: 100%;
        }
        .dataframe-container th,
        .dataframe-container td {
            padding: 8px;
            border: 1px solid #ddd;
            text-align: left;
            white-space: nowrap;
            overflow: hidden;
        }
        .dataframe-container tr:hover {
            background-color: #f1f1f1;
            color: #333;
        }
        .highlighted-cell {
            background-color: #ffeb3b !important;
        }
        .highlighted-row td {
            background-color: #f1f1f1 !important;
            color: #333 !important;
        }
        .highlighted-column {
            background-color: #ffeb3b !important;
            color: #333 !important;
        }
        .highlighted-header {
            border: 2px solid #ff5722 !important;  /* Add a border to the header cell */
            background-color: #ffeb3b !important;
            color: #333 !important;
        }
        </style>
        <script>
        document.addEventListener("DOMContentLoaded", function() {
            const table = document.querySelector('.dataframe-container table');
            const rows = table.querySelectorAll('tr');
            let hoveredRowIndex = -1;
            let hoveredColumnIndex = -1;

            table.addEventListener('mousemove', function(e) {
                const rect = table.getBoundingClientRect();
                const y = e.clientY - rect.top;
                const x = e.clientX - rect.left;

                let newRowIdx = -1;
                let newColIdx = -1;

                // Detect the hovered row
                for (let i = 1; i < rows.length; i++) {
                    const rowRect = rows[i].getBoundingClientRect();
                    if (y >= rowRect.top - rect.top && y <= rowRect.bottom - rect.top) {
                        newRowIdx = i;
                        break;
                    }
                }

                // Detect the hovered column
                if (newRowIdx >= 0) {
                    const cells = rows[newRowIdx].querySelectorAll('td, th');
                    for (let i = 0; i < cells.length; i++) {
                        const cellRect = cells[i].getBoundingClientRect();
                        if (x >= cellRect.left - rect.left && x <= cellRect.right - rect.left) {
                            newColIdx = i;
                            break;
                        }
                    }
                }

                // Update highlighting
                if (newRowIdx !== hoveredRowIndex || newColIdx !== hoveredColumnIndex) {
                    // Remove old highlights
                    if (hoveredRowIndex >= 0) {
                        rows[hoveredRowIndex].classList.remove('highlighted-row');
                    }
                    if (hoveredColumnIndex >= 0) {
                        rows.forEach(row => row.querySelectorAll('td, th')[hoveredColumnIndex].classList.remove('highlighted-cell', 'highlighted-column'));
                        table.querySelectorAll('th')[hoveredColumnIndex].classList.remove('highlighted-header');
                    }

                    // Add new highlights
                    if (newRowIdx >= 0) {
                        rows[newRowIdx].classList.add('highlighted-row');
                    }
                    if (newColIdx >= 0) {
                        rows.forEach(row => row.querySelectorAll('td, th')[newColIdx].classList.add('highlighted-cell', 'highlighted-column'));
                        table.querySelectorAll('th')[newColIdx].classList.add('highlighted-header');
                    }

                    hoveredRowIndex = newRowIdx;
                    hoveredColumnIndex = newColIdx;
                }
            });

            table.addEventListener('mouseleave', function() {
                if (hoveredRowIndex >= 0) {
                    rows[hoveredRowIndex].classList.remove('highlighted-row');
                    hoveredRowIndex = -1;
                }
                if (hoveredColumnIndex >= 0) {
                    rows.forEach(row => row.querySelectorAll('td, th')[hoveredColumnIndex].classList.remove('highlighted-cell', 'highlighted-column'));
                    table.querySelectorAll('th')[hoveredColumnIndex].classList.remove('highlighted-header');
                    hoveredColumnIndex = -1;
                }
            });
        });
        </script>
    """, unsafe_allow_html=True)


# Load your data
all_heroes_df = pd.read_csv('data/allHeroData.csv', dtype={'hero_id': str})
portfolio_df = pd.read_csv('data/portfolio.csv', dtype={'hero_id': str})


###########################
# Functions for Gradient Styling
###########################

# 1. Calculate the star frequency
star_counts = all_heroes_df['hero_stars'].value_counts().sort_index(ascending=False)
star_cumsum = star_counts.cumsum()

# 2. Define gradient colors (adjust to match your app's aesthetic)
gradient_colors = {
    7: "#444444",  # Lightest for 7 stars (but still dark)
    6: "#333333",  # Slightly darker for 6 stars
    5: "#292929",  # Finer gradient for 5 stars
    4: "#1f1f1f",  # Even finer gradient for 4 stars
    3: "#141414",  # Darker still for 3 stars
    2: "#000000",  # Pure black for 2 star
}
    

# 3. Generate CSS styles for the DataFrame rows
def generate_css_styles(df, star_cumsum, gradient_colors):
    styles = []
    for i, row in df.iterrows():
        rank = row['current_rank']
        stars = row['hero_stars']
        for star_level, cutoff in star_cumsum.items():
            if rank <= cutoff:
                styles.append(f'background-color: {gradient_colors[star_level]};')
                break
    return styles

# 4. Apply styles to the DataFrame HTML
def style_dataframe_with_gradients(df, star_cumsum, gradient_colors):
    styles = generate_css_styles(df, star_cumsum, gradient_colors)
    df_html = df.to_html(escape=False, index=False)
    
    for i, style in enumerate(styles):
        df_html = df_html.replace('<tr>', f'<tr style="{style}">', 1)
    
    return df_html

###########################
# End Functions for Gradient Styling
###########################




# Create a new column with HTML for images in both DataFrames
def create_profile_image_links(df):
    return df.apply(
        lambda x: f'<a href="https://fantasy.top/hero/{x["hero_handle"]}" target="_blank"><img src="{x["hero_profile_image_url"]}" width="50"></a>',
        axis=1
    )

all_heroes_df['Profile Image'] = create_profile_image_links(all_heroes_df)
portfolio_df['Profile Image'] = create_profile_image_links(portfolio_df)

# Drop the 'hero_profile_image_url' column as it's no longer needed
all_heroes_df = all_heroes_df.drop(columns=['hero_profile_image_url'])
portfolio_df = portfolio_df.drop(columns=['hero_profile_image_url'])

# Define your column groups for all_heroes_df
all_heroes_column_groups = {
    'Basic Info': ['Profile Image', 'hero_name', 'hero_handle'],
    'Current Fantasy': ['current_rank', 'fantasy_score'],
    'Stars': ['hero_stars'],
    'Supply': ['inflation_degree', 'rarity1Count', 'rarity2Count', 'rarity3Count', 'rarity4Count'],
    'Social Stats': ['tweet_count', 'hero_followers_count', 'hero_fantasy_score', 'hero_views'],
    'Market Data': ['rarity1_lowest_price', 'rarity2_lowest_price', 'rarity3_lowest_price', 'rarity4_lowest_price'],
    'Last Trade Data': ['rarity1lastSalePrice', 'rarity2lastSalePrice', 'rarity3lastSalePrice','rarity4lastSalePrice'],
    'Tournament Averages': ['Average', 'Main_Tournaments_Ave', 'Main_Last_4_Ave'],
    'Tournament Variances': ['Variance', 'Main_Tournaments_Variance', 'Main_Last_4_Variance'],
    'Tournament Standard Deviations': ['Standard_Deviation', 'Main_Tournaments_Standard_Deviation', 'Main_Last_4_Standard_Deviation'],
    'Tournament Z-Scores': ['Z_Score', 'Main_Tournaments_Z_Score', 'Main_Last_4_Z_Score'],
    'Value Analysis Bronze':  ['Price_to_Performance_Bronze', 'Coefficient_of_Variation_Bronze', 'Adjusted_Price_to_Performance_Bronze', 'Market_Relative_Price_to_Perf_Bronze', 'Adj_Price_to_Performance_Rank_Bronze'],
    'Value Analysis Silver':  ['Price_to_Performance_Silver', 'Coefficient_of_Variation_Silver', 'Adjusted_Price_to_Performance_Silver', 'Market_Relative_Price_to_Perf_Silver', 'Adj_Price_to_Performance_Rank_Silver']
}


# Define your column groups for portfolio_df
portfolio_column_groups = {
    'Portfolio Info': ['Profile Image', 'hero_name', 'hero_handle', 'rarity'],
    'Current Fantasy': ['current_rank', 'fantasy_score', 'gliding_score'],
    'Ownership': ['cards_number', 'listed_cards_number', 'in_deck'],
    'Stars': ['hero_stars'],
    'Market Values': ['lowestPrice', 'lastSalePrice', 'rarityCount', 'Total Value'],
    'Social Stats': ['hero_followers_count', 'hero_views'],
    'Tournament Averages': ['Average', 'Main_Tournaments_Ave', 'Main_Last_4_Ave']
}

def handle_filters_and_sorting(df, column_groups, default_sort_column, default_sort_ascending):
    # Expander for Filters
    with st.expander("Filters and Sorting", expanded=False):
        col1, col2, col3, col4 = st.columns(4, gap="small")

        # Sorting option
        with col1:
            sort_column = st.selectbox("Sort by", options=df.columns, index=list(df.columns).index(default_sort_column))
            sort_ascending = st.checkbox("Ascending", value=default_sort_ascending)
            df = df.sort_values(by=sort_column, ascending=sort_ascending)

        # Filters for stars and values
        with col2:
            if 'hero_stars' in df.columns:
                st.write("**Hero Stars Filter**")
                selected_stars = st.slider('Hero Stars', min_value=int(df['hero_stars'].min()), max_value=int(df['hero_stars'].max()), value=(int(df['hero_stars'].min()), int(df['hero_stars'].max())))
                df = df[(df['hero_stars'] >= selected_stars[0]) & (df['hero_stars'] <= selected_stars[1])]

        with col3:
            if 'Total Value Lowest Price' in df.columns:
                st.write("**Total Value Filter**")
                min_val, max_val = df['Total Value Lowest Price'].min(), df['Total Value Lowest Price'].max()
                selected_value_range = st.slider('Value Range', min_value=min_val, max_value=max_val, value=(min_val, max_val))
                df = df[(df['Total Value Lowest Price'] >= selected_value_range[0]) & (df['Total Value Lowest Price'] <= selected_value_range[1])]

        # Rarity filter
        with col4:
            if 'rarity' in df.columns:
                selected_rarity = st.multiselect('Select Rarity', options=df['rarity'].unique(), default=df['rarity'].unique())
                df = df[df['rarity'].isin(selected_rarity)]
    return df

# Create two main columns: one for content and one for the "right-hand sidebar"
col_main, col_sidebar = st.columns([3, 1])

# Left-hand Main Content Area
with col_main:
    if page_selection == "Portfolio Data":
        column_groups = portfolio_column_groups
        df = portfolio_df
        default_sort_column = 'gliding_score'
        default_sort_ascending = False

        df['Total Value Lowest Price'] = df['lowestPrice'] * df['cards_number']
        df['Total Value Last Sale Price'] = df['lastSalePrice'] * df['cards_number']

        # Fill NaN values with 0 to ensure they are included in the filter
        df['Total Value Lowest Price'] = df['Total Value Lowest Price'].fillna(0)

        total_portfolio_value_lowest = df['Total Value Lowest Price'].sum()
        total_portfolio_value_last_sale = df['Total Value Last Sale Price'].sum()
        total_cards_value = df['cards_number'].sum()

        if 'Total Value Lowest Price' not in portfolio_column_groups['Market Values']:
            portfolio_column_groups['Market Values'].append('Total Value Lowest Price')
        if 'Total Value Last Sale Price' not in portfolio_column_groups['Market Values']:
            portfolio_column_groups['Market Values'].append('Total Value Last Sale Price')

        st.markdown('<div class="sticky-header"><h2>My Portfolio</h2></div>', unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)

        col1.metric(label="Total Number of Cards", value=total_cards_value)
        col2.metric(label="Portfolio Value (Lowest Price)", value=f"{total_portfolio_value_lowest:,.2f} ETH")
        col3.metric(label="Portfolio Value (Last Sale Price)", value=f"{total_portfolio_value_last_sale:,.2f} ETH")

        df = handle_filters_and_sorting(df, column_groups, default_sort_column, default_sort_ascending)

        st.sidebar.subheader("Table Customisation")

        with st.sidebar.expander("Select Column Groups", expanded=False):
            selected_groups = st.multiselect(
                "Select column groups to display", 
                options=column_groups.keys(), 
                default=column_groups.keys(),
                key="portfolio_column_groups_multiselect"  # Assign a unique key here
            )

        selected_columns = []
        with st.sidebar.expander("Select Specific Columns", expanded=False):
            for group in selected_groups:
                st.write(f"Select specific columns from {group}:")
                selected_columns_group = st.multiselect(
                    f"{group} Columns", 
                    options=column_groups[group], 
                    default=column_groups[group],
                    key=f"{group}_columns_multiselect_portfolio"  # Assign a unique key here
                )
                selected_columns.extend(selected_columns_group)

        selected_columns = [col for col in selected_columns if col in df.columns]
        filtered_df = df[selected_columns]

        # Apply the table styling
        apply_table_styling()
        apply_hover_highlight()

        # Display the table with the sticky header
        st.markdown('<div class="dataframe-container">{}</div>'.format(filtered_df.to_html(escape=False, index=False)), unsafe_allow_html=True)
        
    # For the "All Heroes" page
    elif page_selection == "All Heroes":
        
        st.markdown('<div class="sticky-header"><h2>All Heroes</h2></div>', unsafe_allow_html=True)

        column_groups = all_heroes_column_groups
        df = all_heroes_df  # Use the correct DataFrame

        # Verify that "Total Value Lowest Price" is not in this DataFrame
        if 'Total Value Lowest Price' in df.columns:
            df = df.drop(columns=['Total Value Lowest Price'])
            print("'Total Value Lowest Price' column was removed.")

        default_sort_column = 'current_rank'
        default_sort_ascending = True

        # Apply sorting
        df = df.sort_values(by=default_sort_column, ascending=default_sort_ascending)

        # Apply filters and sorting   
        st.sidebar.subheader("Table Customisation")
        
        with st.sidebar.expander("Select Column Groups", expanded=False):
            selected_groups = st.multiselect(
                "Select column groups to display", 
                options=column_groups.keys(), 
                default=column_groups.keys(),
                key="all_heroes_column_groups_multiselect"  # Assign a unique key here
            )

        selected_columns = []
        with st.sidebar.expander("Select Specific Columns", expanded=False):
            for group in selected_groups:
                st.write(f"Select specific columns from {group}:")
                selected_columns_group = st.multiselect(
                    f"{group} Columns", 
                    options=column_groups[group], 
                    default=column_groups[group],
                    key=f"{group}_columns_multiselect_all_heroes"  # Assign a unique key here
                )
                selected_columns.extend(selected_columns_group)

        selected_columns = [col for col in selected_columns if col in df.columns]
        filtered_df = df[selected_columns]

        print(filtered_df.head())

        styled_html = style_dataframe_with_gradients(filtered_df, star_cumsum, gradient_colors)
        
        apply_table_styling()
        apply_hover_highlight()

        st.markdown(f'<div class="dataframe-container">{styled_html}</div>', unsafe_allow_html=True)

        

    elif page_selection == "Tournament Scores Over Time":
        st.title("Tournament Scores Over Time")

        filtered_df = all_heroes_df.copy()

        with st.expander("Filters and Sorting", expanded=False):
            col1, col2, col3 = st.columns(3)

            with col1:
                min_star, max_star = int(filtered_df['hero_stars'].min()), int(filtered_df['hero_stars'].max())
                selected_stars = st.slider('Filter by Hero Stars', min_value=min_star, max_value=max_star, value=(min_star, max_star))
                filtered_df = filtered_df[(filtered_df['hero_stars'] >= selected_stars[0]) & (filtered_df['hero_stars'] <= selected_stars[1])]

            with col2:
                min_price, max_price = st.slider(
                    'Price Range',
                    min_value=float(filtered_df['rarity4_lowest_price'].min()),
                    max_value=float(filtered_df['rarity4_lowest_price'].max()),
                    value=(float(filtered_df['rarity4_lowest_price'].min()), float(filtered_df['rarity4_lowest_price'].max())),
                    step=0.001,
                    format="%.3f"
                )
                filtered_df = filtered_df[(filtered_df['rarity4_lowest_price'] >= min_price) & (filtered_df['rarity4_lowest_price'] <= max_price)]

            with col3:
                average_type = st.radio("Select average type for top 5", options=["Main_Tournaments_Ave", "Main_Last_4_Ave"])

        selected_heroes = st.sidebar.multiselect('Select Heroes to Compare', options=filtered_df['hero_name'].unique())

        tournament_columns = [
            'Main 11', 'Main 10', 'Main 9', 'Main 8', 'Main 7', 'Main 6 *Sat/Sun Only*',
            'Main 5', 'All Rarities | 22 days', 'Main 4', 'Main 3', 'Common Only ✳️ Capped 20 🌟',
            'Rare Only 💠', 'Main 2', 'Main 1', 'Flash Tournament'
        ]

        if not selected_heroes:
            top_heroes = filtered_df.nlargest(5, average_type)['hero_name'].tolist()
        else:
            top_heroes = selected_heroes

        long_df = filtered_df.melt(id_vars=['hero_name'], value_vars=tournament_columns,
                                var_name='Tournament', value_name='Points')

        fig = go.Figure()

        for hero in long_df['hero_name'].unique():
            hero_data = long_df[long_df['hero_name'] == hero]

            hero_customdata = filtered_df[filtered_df['hero_name'] == hero][['rarity1_lowest_price', 'rarity2_lowest_price', 'rarity3_lowest_price', 'rarity4_lowest_price']].iloc[0].values

            opacity = 1.0 if hero in top_heroes else 0.2

            fig.add_trace(go.Scatter(
                x=hero_data['Tournament'],
                y=hero_data['Points'],
                mode='lines+markers',
                name=hero,
                opacity=opacity,
                hovertemplate=(
                    '<b>%{text}</b><br>' +
                    'Tournament: %{x}<br>' +
                    'Points: %{y}<br>' +
                    'Rarity 1 Price: %{customdata[0]:.3f}<br>' +
                    'Rarity 2 Price: %{customdata[1]:.3f}<br>' +
                    'Rarity 3 Price: %{customdata[2]:.3f}<br>' +
                    'Rarity 4 Price: %{customdata[3]:.3f}<extra></extra>'
                ),
                customdata=[hero_customdata] * len(hero_data),
                text=[hero] * len(hero_data)
            ))

        fig.update_layout(
            title="Tournament Scores Over Time",
            xaxis_title="Tournament",
            yaxis_title="Points",
            xaxis=dict(categoryorder="array", categoryarray=tournament_columns[::-1]),
            legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
            showlegend=True,
            width=2000,
            height=800
        )

        st.plotly_chart(fig, use_container_width=True)


    # Adding a new page for "Best Decks"
    if page_selection == "Best Decks":
        st.title("Best Decks")

        # Load the latest silver and bronze deck files
        silver_decks = load_latest_file('data/combined_best_decks_silver_*.csv')
        bronze_decks = load_latest_file('data/combined_best_decks_bronze_*.csv')

        # Combine silver and bronze decks into one dataframe if needed
        combined_decks = pd.concat([silver_decks, bronze_decks])

        if combined_decks is not None:
            # Display each deck by filtering by "Deck Name"
            deck_names = combined_decks['Deck_Name'].unique()
            for deck_name in deck_names:
                deck_df = combined_decks[combined_decks['Deck_Name'] == deck_name]
                display_deck(deck_df)
        else:
            st.error("No deck data available.")

# Right-hand RSS Feed Sidebar
with col_sidebar:
    st.subheader("Latest")

    # Render the tweet container with the initial tweets
    tweet_html = generate_tweet_html(tweet_urls, count=INITIAL_TWEET_COUNT)
    components.html(tweet_html, height=1400)


# Load your CSV data into a DataFrame
tournament_status_df = pd.read_csv('data/current_tournaments_standings.csv')

# Group by the 'Description' (which appears to be the competition name)
grouped_summary = tournament_status_df.groupby('Description').agg({
    'Deck No': 'count',  # Counting number of decks
    'ETH': 'sum',        # Summing ETH
    'Pack': 'sum',       # Summing Packs
    'Gold': 'sum'        # Summing Gold
}).reset_index()

# Rename the columns for better display
grouped_summary.columns = ['Competition', 'Number of Decks', 'Total ETH', 'Total Packs', 'Total Gold']

# Display the summary at the top of the app
st.sidebar.subheader("Tournament Summary")
st.sidebar.dataframe(grouped_summary)




# "Refresh Data" Section
st.sidebar.subheader("Refresh Data")

# "All" button for selecting all options
select_all = st.sidebar.checkbox("Select All")

# Checkboxes for individual updates
update_options = [
    "Update Tournament Scores",
    "Update Basic Hero Stats",
    "Update Portfolio",
    "Update Last Trades",
    "Update Listings",
    "Update Hero Stats",
    "Update Hero Trades",
    "Update Hero Supply",
    "Update Bids",
    "Update Star History"
]
selected_updates = st.sidebar.multiselect(
    "Select Updates", 
    options=update_options, 
    default=update_options if select_all else [],
    key="update_options_multiselect"  # Assign a unique key here
)

# Update button
if st.sidebar.button("Update and Compile Data"):
    if not st.session_state.is_updating:
        run_update_and_compile(selected_updates)
    else:
        st.warning("An update is already in progress.")
