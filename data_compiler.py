import os
import re
import pandas as pd
from datetime import datetime
import numpy as np
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

# Clear the environment variables before loading the .env file
os.environ.clear()

# Retrieve DATA_FOLDER from environment variables
DATA_FOLDER = os.getenv("DATA_FOLDER")


TOURNAMENT_COLUMNS = [
    'Main 12', 'Main 11', 'Main 10', 'Main 9', 'Main 8', 'Main 7', 'Main 5', 'Main 4'
]
ALL_SCORES = [
    'hero_fantasy_score', 'Main 12','Main 11', 'Main 10', 'Main 9', 'Main 8', 'Main 7', 'Main 6 *Sat/Sun Only*', 
    'Main 5', 'All Rarities | 22 days', 'Main 4', 'Main 3', 'Common Only ✳️ Capped 20 🌟', 
    'Rare Only 💠', 'Main 2', 'Main 1', 'Flash Tournament', 'Average', 'Main_Tournaments_Ave', 'Main_Last_4_Ave'
]

# Functions

def get_latest_csv_files(folder_path):
    csv_files = {}
    pattern = re.compile(r'^(.*)_(\d{6}_\d{4})\.csv$')
    
    for file_name in os.listdir(folder_path):
        if file_name.endswith('.csv'):
            match = pattern.match(file_name)
            if match:
                prefix = match.group(1)
                timestamp_str = match.group(2)
                try:
                    timestamp = datetime.strptime(timestamp_str, '%y%m%d_%H%M')
                    if prefix not in csv_files or timestamp > csv_files[prefix][1]:
                        csv_files[prefix] = (file_name, timestamp)
                except Exception as e:
                    print(f"Error processing file {file_name}: {e}")
    return {prefix: os.path.join(folder_path, file_name) for prefix, (file_name, _) in csv_files.items()}

def import_latest_csv_files(folder_path):
    latest_files = get_latest_csv_files(folder_path)
    dataframes = {}
    for prefix, file_path in latest_files.items():
        print(f"Reading file: {file_path}")
        try:
            df = pd.read_csv(file_path)
            if df.empty:
                print(f"Warning: File {file_path} is empty. Skipping.")
                continue
            dataframes[prefix] = df
        except pd.errors.EmptyDataError:
            print(f"Warning: File {file_path} is empty or has no columns to parse. Skipping.")
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
    return dataframes


def calculate_tournament_statistics(df):
    if 'Name' in df.columns and 'Handle' in df.columns:
        # Convert relevant columns to numeric, ignoring 'Name' and 'Handle'
        numeric_df = df.drop(['Name', 'Handle'], axis=1).apply(pd.to_numeric, errors='coerce')

        # Calculate Mean Scores
        df['Average'] = numeric_df.mean(axis=1)
        df['Main_Tournaments_Ave'] = numeric_df[TOURNAMENT_COLUMNS].mean(axis=1)
        df['Main_Last_4_Ave'] = numeric_df[TOURNAMENT_COLUMNS[:4]].mean(axis=1)

        # Calculate Variance and Standard Deviation
        df['Variance'] = numeric_df.var(axis=1)
        df['Main_Tournaments_Variance'] = numeric_df[TOURNAMENT_COLUMNS].var(axis=1)
        df['Main_Last_4_Variance'] = numeric_df[TOURNAMENT_COLUMNS[:4]].var(axis=1)
        df['Standard_Deviation'] = numeric_df.std(axis=1)
        df['Main_Tournaments_Standard_Deviation'] = numeric_df[TOURNAMENT_COLUMNS].std(axis=1)
        df['Main_Last_4_Standard_Deviation'] = numeric_df[TOURNAMENT_COLUMNS[:4]].std(axis=1)

        # Calculate Z-scores (for each tournament score)
        z_scores = numeric_df.sub(df['Average'], axis=0).div(df['Standard_Deviation'], axis=0)
        z_score_columns = [f"Z_Score_{col}" for col in numeric_df.columns]
        z_scores.columns = z_score_columns

        # Add Z-scores to the original DataFrame
        df = pd.concat([df, z_scores], axis=1)

        # Handle NaN values that might result from division by zero
        df.fillna(0, inplace=True)

        # Calculate Moving Averages (e.g., 3-tournament moving average)
        df['Moving_Avg_3'] = numeric_df[TOURNAMENT_COLUMNS].rolling(window=3, axis=1).mean().iloc[:, -1]  # Last value in the moving window
        
    else:
        raise KeyError("Columns 'Name' and 'Handle' not found in the DataFrame")
    
    return df

def calculate_value(df):
    # Assuming you have a DataFrame 'df' with the necessary columns
    df['Price_to_Performance_Bronze'] = df['rarity4_lowest_price'] / df['Main_Last_4_Ave']
    df['Price_to_Performance_Silver'] = df['rarity3_lowest_price'] / df['Main_Last_4_Ave']

    # Adjusted ratio considering consistency
    df['Coefficient_of_Variation'] = df['Main_Last_4_Standard_Deviation'] / df['Main_Last_4_Ave']
    df['Adjusted_Price_to_Performance_Bronze'] = df['rarity4_lowest_price'] / (df['Main_Last_4_Ave'] * (1 - df['Coefficient_of_Variation']))
    df['Adjusted_Price_to_Performance_Silver'] = df['rarity3_lowest_price'] / (df['Main_Last_4_Ave'] * (1 - df['Coefficient_of_Variation']))

    # You could also compute market averages or percentiles
    market_avg_ratio_bronze = df['Price_to_Performance_Bronze'].mean()
    market_avg_ratio_silver = df['Price_to_Performance_Silver'].mean()
    df['Market_Relative_Price_to_Perf_Bronze'] = df['Price_to_Performance_Bronze'] / market_avg_ratio_bronze
    df['Market_Relative_Price_to_Perf_Silver'] = df['Price_to_Performance_Silver'] / market_avg_ratio_silver

    # Optional: Rank heroes based on adjusted price-to-performance
    df['Adj_Price_to_Performance_Rank_Bronze'] = df['Adjusted_Price_to_Performance_Bronze'].rank()
    df['Adj_Price_to_Performance_Rank_Silver'] = df['Adjusted_Price_to_Performance_Silver'].rank()

    return df


def reorder_basic_hero_stats(df):
    columns_order = ['current_rank', 'hero_name', 'hero_handle'] + \
        [col for col in df.columns if col not in ['current_rank', 'hero_name', 'hero_handle']]
    return df[columns_order]

def merge_dataframes(dataframes):
    # Merge operations
    merged_hero_stats = dataframes['basic_hero_stats'].merge(dataframes['hero_stats'], on='hero_handle', how='left')
    merged_hero_stats = merged_hero_stats.merge(dataframes['hero_card_supply'], on='hero_id', how='left')
    merged_hero_stats = merged_hero_stats.merge(dataframes['listings'], on=['hero_id', 'hero_handle'], how='left')
    merged_hero_stats = merged_hero_stats.merge(dataframes['last_trades'], on=['hero_id'], how='left')
    dataframes['tournament_scores'].drop(columns=['Name'], inplace=True) 
    merged_hero_stats = merged_hero_stats.merge(dataframes['tournament_scores'], left_on='hero_handle', right_on='Handle', how='left')
    merged_hero_stats.drop(columns=['Handle'], inplace=True)
    merged_hero_stats.drop_duplicates(subset=['hero_handle'], inplace=True)
    merged_hero_stats['hero_id'] = merged_hero_stats['hero_id'].astype(str)

    merged_hero_stats = calculate_value(merged_hero_stats)
    return merged_hero_stats

def save_final_dataframes(final_merged_df, portfolio_scores):
    final_merged_df.to_csv(f'{DATA_FOLDER}/allHeroData.csv', index=False)
    portfolio_scores.to_csv(f'{DATA_FOLDER}/portfolio.csv', index=False)

def process_portfolio_scores(portfolio_df, final_merged_df):
    merged_df = portfolio_df.merge(final_merged_df, on='hero_handle', how='left')
    portfolio_scores = merged_df.drop(['hero_name_y', 'hero_stars_y', 'hero_followers_count_y', 'hero_profile_image_url_y', 'token_id'], axis=1)
    portfolio_scores.columns = [col.replace('_x', '') for col in portfolio_scores.columns]
    
    columns_order = ['hero_name', 'hero_handle'] + [col for col in portfolio_scores.columns if col not in ['hero_name', 'hero_handle']]
    portfolio_scores = portfolio_scores[columns_order]
    
    portfolio_scores['lastSalePrice'] = portfolio_scores.apply(lambda row: row[f'rarity{row["rarity"]}lastSalePrice'], axis=1)
    portfolio_scores['lowestPrice'] = portfolio_scores.apply(lambda row: row[f'rarity{row["rarity"]}_lowest_price'], axis=1)
    portfolio_scores['rarityCount'] = portfolio_scores.apply(lambda row: row[f'rarity{row["rarity"]}Count'], axis=1)
    
    columns_to_drop = [
        'rarity1_lowest_price', 'rarity2_lowest_price', 'rarity3_lowest_price', 'rarity4_lowest_price',
        'rarity1lastSalePrice', 'rarity2lastSalePrice', 'rarity3lastSalePrice', 'rarity4lastSalePrice',
        'rarity1Count', 'rarity2Count', 'rarity3Count', 'rarity4Count',
        'rarity1_order_count', 'rarity2_order_count', 'rarity3_order_count', 'rarity4_order_count',
        'rarity1lastSaleTime', 'rarity2lastSaleTime', 'rarity3lastSaleTime', 'rarity4lastSaleTime'
    ]
    portfolio_scores = portfolio_scores.drop(columns=columns_to_drop)
    
    for col in ALL_SCORES:
        portfolio_scores[col] = pd.to_numeric(portfolio_scores[col], errors='coerce')
        portfolio_scores[col] = portfolio_scores.apply(lambda row: row[col] * 1.5 if row['hero_rarity_index'].endswith('3') else row[col], axis=1)
    
    return portfolio_scores

# Main Execution

def compile_data():
    dataframes = import_latest_csv_files(DATA_FOLDER)
    dataframes['tournament_scores'] = calculate_tournament_statistics(dataframes['tournament_scores'])
    dataframes['basic_hero_stats'] = reorder_basic_hero_stats(dataframes['basic_hero_stats'])
    final_merged_df = merge_dataframes(dataframes)
    portfolio_scores = process_portfolio_scores(dataframes['portfolio'], final_merged_df)
    save_final_dataframes(final_merged_df, portfolio_scores)

if __name__ == "__main__":
    compile_data()
