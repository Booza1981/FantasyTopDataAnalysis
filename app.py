import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# Load your data
all_heroes_df = pd.read_csv('data/allHeroData.csv', dtype={'hero_id': str})
portfolio_df = pd.read_csv('data/portfolio.csv', dtype={'hero_id': str})

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
    'Social Stats': ['hero_followers_count', 'hero_fantasy_score', 'hero_views'],
    'Market Data': ['rarity1_lowest_price', 'rarity2_lowest_price', 'rarity3_lowest_price', 'rarity4_lowest_price'],
    'Tournament Averages': ['Average', 'Main_Tournaments_Ave', 'Main_Last_4_Ave']
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

st.set_page_config(layout="wide")

# Sidebar for page navigation
st.sidebar.title("Navigation")
page_selection = st.sidebar.selectbox("Go to", ["Portfolio Data", "All Heroes", "Tournament Scores Over Time"], index=0)

# Add the "Selections" subheader in the sidebar
st.sidebar.subheader("Selections")

# Common CSS styling for the tables
def apply_table_styling():
    st.markdown("""
        <style>
        .dataframe {
            max-height: 500px;
            overflow: auto;
            border-collapse: separate;
            border-spacing: 0;
        }
        .dataframe th, .dataframe td {
            padding: 8px;
            text-align: left;
            border: 1px solid #ddd;  /* Add grid lines to the table */
        }
        thead th {
            position: sticky;
            top: 0;
            z-index: 2;
            background-color: #f1f1f1;
            color: #333;  /* Darker text color */
        }
        tbody th {
            position: sticky;
            left: 0;
            z-index: 1;
            background-color: #f1f1f1;
            color: #333;  /* Darker text color */
        }
        tbody td:first-child {
            position: sticky;
            left: 0;
            background-color: #f1f1f1;
            z-index: 1;
        }
        thead th:first-child {
            position: sticky;
            top: 0;
            left: 0;
            z-index: 3;
            background-color: #f1f1f1;
            color: #333;  /* Darker text color */
        }
        tbody td img {
            z-index: 0;
        }
        </style>
    """, unsafe_allow_html=True)

# Function to handle filtering and sorting logic
def handle_filters_and_sorting(df, column_groups, default_sort_column, default_sort_ascending):
    # Expander for Filters
    with st.expander("Filters and Sorting", expanded=False):
        # Column-based layout for sorting and filters
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

# Portfolio Data Section
if page_selection == "Portfolio Data":
    # Portfolio View
    column_groups = portfolio_column_groups
    df = portfolio_df
    default_sort_column = 'gliding_score'
    default_sort_ascending = False

    # Calculate total values based on lowest price and last sale price
    df['Total Value Lowest Price'] = df['lowestPrice'] * df['cards_number']
    df['Total Value Last Sale Price'] = df['lastSalePrice'] * df['cards_number']

    total_portfolio_value_lowest = df['Total Value Lowest Price'].sum()
    total_portfolio_value_last_sale = df['Total Value Last Sale Price'].sum()
    total_cards_value = df['cards_number'].sum()

    # Ensure 'Total Value' columns are included in the column groups for display
    if 'Total Value Lowest Price' not in portfolio_column_groups['Market Values']:
        portfolio_column_groups['Market Values'].append('Total Value Lowest Price')
    if 'Total Value Last Sale Price' not in portfolio_column_groups['Market Values']:
        portfolio_column_groups['Market Values'].append('Total Value Last Sale Price')

    # My Portfolio Title and Metrics
    st.title("My Portfolio")

    # Create metrics for the portfolio
    col1, col2, col3 = st.columns(3)

    # Total number of cards
    col1.metric(label="Total Number of Cards", value=total_cards_value)

    # Portfolio value based on the lowest price
    col2.metric(label="Portfolio Value (Lowest Price)", value=f"{total_portfolio_value_lowest:,.2f} ETH")

    # Portfolio value based on the last sale price
    col3.metric(label="Portfolio Value (Last Sale Price)", value=f"{total_portfolio_value_last_sale:,.2f} ETH")

    # Apply filters and sorting
    df = handle_filters_and_sorting(df, column_groups, default_sort_column, default_sort_ascending)

    # Sidebar for column selection
    with st.sidebar.expander("Select Column Groups"):
        selected_groups = st.multiselect("Select column groups to display", options=column_groups.keys(), default=column_groups.keys())

    selected_columns = []
    with st.sidebar.expander("Select Specific Columns"):
        for group in selected_groups:
            st.write(f"Select specific columns from {group}:")
            selected_columns_group = st.multiselect(f"{group} Columns", options=column_groups[group], default=column_groups[group])
            selected_columns.extend(selected_columns_group)

    selected_columns = [col for col in selected_columns if col in df.columns]
    filtered_df = df[selected_columns]

    # Apply the common table styling
    apply_table_styling()

    # Convert the DataFrame to HTML, allowing the image tags to render
    st.write(f'<div class="dataframe">{filtered_df.to_html(escape=False, index=False)}</div>', unsafe_allow_html=True)

elif page_selection == "All Heroes":

    # Title for the app
    st.title("All Heroes")

    # All Heroes View
    column_groups = all_heroes_column_groups
    df = all_heroes_df
    default_sort_column = 'current_rank'
    default_sort_ascending = True

    df = handle_filters_and_sorting(df, column_groups, default_sort_column, default_sort_ascending)

    # Sidebar for column selection
    with st.sidebar.expander("Select Column Groups"):
        selected_groups = st.multiselect("Select column groups to display", options=column_groups.keys(), default=column_groups.keys())

    selected_columns = []
    with st.sidebar.expander("Select Specific Columns"):
        for group in selected_groups:
            st.write(f"Select specific columns from {group}:")
            selected_columns_group = st.multiselect(f"{group} Columns", options=column_groups[group], default=column_groups[group])
            selected_columns.extend(selected_columns_group)

    selected_columns = [col for col in selected_columns if col in df.columns]
    filtered_df = df[selected_columns]

    # Apply the common table styling
    apply_table_styling()

    # Convert the DataFrame to HTML, allowing the image tags to render
    st.write(f'<div class="dataframe">{filtered_df.to_html(escape=False, index=False)}</div>', unsafe_allow_html=True)

elif page_selection == "Tournament Scores Over Time":
    # Title for the app
    st.title("Tournament Scores Over Time")

    # Use the appropriate DataFrame
    filtered_df = all_heroes_df.copy()

    # Expander for Filters
    with st.expander("Filters and Sorting", expanded=False):
        # Arrange filters in columns
        col1, col2, col3 = st.columns(3)

        with col1:
            # Sidebar filter for stars (Moved to column layout)
            min_star, max_star = int(filtered_df['hero_stars'].min()), int(filtered_df['hero_stars'].max())
            selected_stars = st.slider('Filter by Hero Stars', min_value=min_star, max_value=max_star, value=(min_star, max_star))
            filtered_df = filtered_df[(filtered_df['hero_stars'] >= selected_stars[0]) & (filtered_df['hero_stars'] <= selected_stars[1])]

        with col2:
            # Price filter (Range slider for min and max price with smaller increments)
            min_price, max_price = st.slider(
                'Price Range',
                min_value=float(filtered_df['rarity4_lowest_price'].min()),
                max_value=float(filtered_df['rarity4_lowest_price'].max()),
                value=(float(filtered_df['rarity4_lowest_price'].min()), float(filtered_df['rarity4_lowest_price'].max())),
                step=0.001,
                format="%.3f"  # Display slider values with 3 decimal places
            )
            filtered_df = filtered_df[(filtered_df['rarity4_lowest_price'] >= min_price) & (filtered_df['rarity4_lowest_price'] <= max_price)]

        with col3:
            # Toggle for selecting which average to use for determining the top 5 heroes
            average_type = st.radio("Select average type for top 5", options=["Main_Tournaments_Ave", "Main_Last_4_Ave"])

    # Hero selection for comparison (in a separate row)
    selected_heroes = st.sidebar.multiselect('Select Heroes to Compare', options=filtered_df['hero_name'].unique())

    # Define the tournament columns in reverse chronological order
    tournament_columns = [
        'Main 11', 'Main 10', 'Main 9', 'Main 8', 'Main 7', 'Main 6 *Sat/Sun Only*',
        'Main 5', 'All Rarities | 22 days', 'Main 4', 'Main 3', 'Common Only ✳️ Capped 20 🌟',
        'Rare Only 💠', 'Main 2', 'Main 1', 'Flash Tournament'
    ]

    # Identify top 5 heroes based on the selected average type dynamically after filtering by stars and price
    if not selected_heroes:
        top_heroes = filtered_df.nlargest(5, average_type)['hero_name'].tolist()
    else:
        top_heroes = selected_heroes

    # Reshape the DataFrame from wide to long format
    long_df = filtered_df.melt(id_vars=['hero_name'], value_vars=tournament_columns,
                               var_name='Tournament', value_name='Points')

    # Create a Plotly figure
    fig = go.Figure()

    # Loop through each hero and create a trace for their data
    for hero in long_df['hero_name'].unique():
        hero_data = long_df[long_df['hero_name'] == hero]

        # Extract the custom data for the hero only once
        hero_customdata = filtered_df[filtered_df['hero_name'] == hero][['rarity1_lowest_price', 'rarity2_lowest_price', 'rarity3_lowest_price', 'rarity4_lowest_price']].iloc[0].values

        # Set opacity for top heroes
        opacity = 1.0 if hero in top_heroes else 0.2

        # Add trace for the hero
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

    # Update layout for better visualization with legend below the chart
    fig.update_layout(
        title="Tournament Scores Over Time",
        xaxis_title="Tournament",
        yaxis_title="Points",
        xaxis=dict(categoryorder="array", categoryarray=tournament_columns[::-1]),
        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
        showlegend=True,
        width=2000,  # Adjust the width as needed
        height=800  # Adjust the height as needed
    )

    # Display the plot using the correct function
    st.plotly_chart(fig, use_container_width=True)
