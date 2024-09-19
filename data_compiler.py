import os
import re
import pandas as pd
from datetime import datetime
import numpy as np
from get_data_script import DATA_FOLDER

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

def get_sorted_tournament_files(folder_path):
    """Sorts and retrieves all CSV files containing tournament data."""
    csv_files = []
    pattern = re.compile(r'_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.csv$')
    
    for file_name in os.listdir(folder_path):
        if file_name.endswith('.csv'):
            match = pattern.search(file_name)
            if match:
                start_date_str = match.group(1)
                end_date_str = match.group(2)
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                    csv_files.append((file_name, start_date, end_date))
                except Exception as e:
                    print(f"Error processing file {file_name}: {e}")
    
    # Sort by start date and return the sorted file list (most recent first)
    csv_files.sort(key=lambda x: x[1], reverse=True)
    return [os.path.join(folder_path, file[0]) for file in csv_files]

def import_all_tournament_csvs(folder_path):
    """Imports and merges all tournament CSVs into a single DataFrame."""
    tournament_files = get_sorted_tournament_files(folder_path)
    all_hero_data = pd.DataFrame()
    tournament_columns = []  # New list to keep track of tournament columns, used for calculating rarity scores laster

    for file_path in tournament_files:
        print(f"Reading tournament file: {file_path}")
        try:
            df = pd.read_csv(file_path)

            if df.empty:
                print(f"Warning: File {file_path} is empty. Skipping.")
                continue

            # Extract relevant columns (hero_handle and fantasy_score)
            if 'hero_handle' in df.columns and 'fantasy_score' in df.columns:
                file_name = os.path.basename(file_path).split('.')[0]
                parts = file_name.split('_')
                tournament_name = " ".join(parts[:-2])
                column_name = f"{tournament_name.replace('_', ' ')} Score"
                df = df[['hero_handle', 'fantasy_score']].rename(columns={'fantasy_score': column_name})
                
                tournament_columns.append(column_name)

                if all_hero_data.empty:
                    all_hero_data = df
                else:
                    all_hero_data = pd.merge(all_hero_data, df, on='hero_handle', how='outer')
                
            else:
                print(f"Warning: File {file_path} does not have the required columns. Skipping.")

        except pd.errors.EmptyDataError:
            print(f"Warning: File {file_path} is empty or has no columns to parse. Skipping.")
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")

    return all_hero_data, tournament_columns

def generate_all_scores_list(tournament_columns):
    """Generates the ALL_SCORES list based on the actual tournament columns and calculated statistics. This list can be used as the basis for adjustment for other rarities or custom calculations."""
    ALL_SCORES = tournament_columns.copy()
    
    # Add calculated statistics columns
    ALL_SCORES.extend([
        "Average",
        "Main_Tournaments_Ave",
        "Main_Last_4_Ave",
        "Variance",
        "Main_Tournaments_Variance",
        "Main_Last_4_Variance",
        "Standard_Deviation",
        "Main_Tournaments_Standard_Deviation",
        "Main_Last_4_Standard_Deviation",
        "Moving_Avg_3"
    ])
    
    # Add Z-score columns
    Z_SCORE_COLUMNS = [f"Z_Score_{col}" for col in tournament_columns]
    ALL_SCORES.extend(Z_SCORE_COLUMNS)
    
    return ALL_SCORES

def calculate_tournament_statistics(df):
    """Calculates tournament statistics like averages, variances, and Z-scores."""
    if 'hero_handle' in df.columns:
        numeric_df = df.drop(['hero_handle'], axis=1).apply(pd.to_numeric, errors='coerce')

        # Manually define the columns for now based on the imported data
        TOURNAMENT_COLUMNS = [col for col in df.columns if 'Main' in col]  # Main tournaments columns
        df['Average'] = numeric_df.mean(axis=1)
        df['Main_Tournaments_Ave'] = numeric_df[TOURNAMENT_COLUMNS].mean(axis=1)
        df['Main_Last_4_Ave'] = numeric_df[TOURNAMENT_COLUMNS[:4]].mean(axis=1)

        # Variance and standard deviation calculations
        df['Variance'] = numeric_df.var(axis=1)
        df['Main_Tournaments_Variance'] = numeric_df[TOURNAMENT_COLUMNS].var(axis=1)
        df['Main_Last_4_Variance'] = numeric_df[TOURNAMENT_COLUMNS[:4]].var(axis=1)
        df['Standard_Deviation'] = numeric_df.std(axis=1)
        df['Main_Tournaments_Standard_Deviation'] = numeric_df[TOURNAMENT_COLUMNS].std(axis=1)
        df['Main_Last_4_Standard_Deviation'] = numeric_df[TOURNAMENT_COLUMNS[:4]].std(axis=1)

        # Z-score calculations
        z_scores = numeric_df.sub(df['Average'], axis=0).div(df['Standard_Deviation'], axis=0)
        z_score_columns = [f"Z_Score_{col}" for col in numeric_df.columns]
        z_scores.columns = z_score_columns

        df = pd.concat([df, z_scores], axis=1)
        df.fillna(0, inplace=True)
        
        # Fix for the deprecation warning
        df['Moving_Avg_3'] = numeric_df[TOURNAMENT_COLUMNS].T.rolling(window=3).mean().T.iloc[:, -1]
        
    else:
        raise KeyError("Column 'hero_handle' not found in the DataFrame")
    
    return df


def merge_dataframes(dataframes):
    """Merges all dataframes including basic hero stats, tournament scores, and other hero-related data."""
    merged_hero_stats = dataframes['basic_hero_stats'].merge(dataframes['hero_stats'], on='hero_handle', how='left')
    merged_hero_stats = merged_hero_stats.merge(dataframes['hero_card_supply'], on='hero_id', how='left')
    merged_hero_stats = merged_hero_stats.merge(dataframes['listings'], on=['hero_id', 'hero_handle'], how='left')
    
    # Deduplicate hero_trades by taking the latest price per hero_id and rarity (adjust based on your needs)
    latest_trades_df = dataframes['hero_trades'].sort_values(by=['hero_id', 'rarity', 'timestamp'], ascending=False)
    latest_trades_df = latest_trades_df.drop_duplicates(subset=['hero_id', 'rarity'], keep='first')

    # Pivot the latest_trades_df so that each rarity has its own column
    latest_trades_pivot = latest_trades_df.pivot(index='hero_id', columns='rarity', values='price').reset_index()
    latest_trades_pivot.columns = ['hero_id', 'rarity4lastSalePrice', 'rarity3lastSalePrice', 'rarity2lastSalePrice', 'rarity1lastSalePrice']
    
    # Merge the latest trades with merged_hero_stats on 'hero_id'
    merged_hero_stats = merged_hero_stats.merge(latest_trades_pivot, on='hero_id', how='left')

    # Check if 'Name' exists in tournament_scores before dropping it
    if 'Name' in dataframes['tournament_scores'].columns:
        dataframes['tournament_scores'].drop(columns=['Name'], inplace=True)
    
    # Merge with the compiled tournament scores
    merged_hero_stats = merged_hero_stats.merge(dataframes['tournament_scores'], left_on='hero_handle', right_on='hero_handle', how='left')
    merged_hero_stats.drop_duplicates(subset=['hero_handle'], inplace=True)
    merged_hero_stats['hero_id'] = merged_hero_stats['hero_id'].astype(str)
    
    return merged_hero_stats


import os

def save_final_dataframes(final_merged_df, portfolio_scores):
    """Saves the final merged dataframe to a CSV file."""
    try:
        # Check if DATA_FOLDER is just a drive letter
        if DATA_FOLDER.endswith(':\\'):
            all_hero_path = f'{DATA_FOLDER}allHeroData.csv'
            portfolio_path = f'{DATA_FOLDER}portfolio.csv'
        else:
            all_hero_path = os.path.join(DATA_FOLDER, 'allHeroData.csv')
            portfolio_path = os.path.join(DATA_FOLDER, 'portfolio.csv')

        final_merged_df.to_csv(all_hero_path, index=False)
        portfolio_scores.to_csv(portfolio_path, index=False)
        print(f"Files successfully saved to {DATA_FOLDER}")
    except PermissionError as e:
        print(f"Permission error: {e}")
        print("Please ensure you have write permissions for the specified directory.")
        print(f"Attempted to write to: {DATA_FOLDER}")
    except Exception as e:
        print(f"An error occurred while saving the files: {e}")
        print(f"Attempted to write to: {DATA_FOLDER}")


def process_portfolio_scores(portfolio_df, final_merged_df, ALL_SCORES):
    merged_df = portfolio_df.merge(final_merged_df, on='hero_handle', how='left')
    portfolio_scores = merged_df.drop(['hero_name_y', 'hero_stars_y', 'hero_followers_count_y', 'hero_profile_image_url_y', 'token_id'], axis=1)
    portfolio_scores.columns = [col.replace('_x', '') for col in portfolio_scores.columns]
    
    columns_order = ['hero_name', 'hero_handle'] + [col for col in portfolio_scores.columns if col not in ['hero_name', 'hero_handle']]
    portfolio_scores = portfolio_scores[columns_order]
    
    portfolio_scores['lastSalePrice'] = portfolio_scores.apply(lambda row: row[f'rarity{row["rarity"]}lastSalePrice'], axis=1)
    portfolio_scores['lowestPrice'] = portfolio_scores.apply(lambda row: row[f'rarity{row["rarity"]}_lowest_price'], axis=1)
    portfolio_scores['rarityCount'] = portfolio_scores.apply(lambda row: row[f'rarity{row["rarity"]}Count'], axis=1)
    print(portfolio_scores.columns)
    columns_to_drop = [
        'rarity1_lowest_price', 'rarity2_lowest_price', 'rarity3_lowest_price', 'rarity4_lowest_price',
        'rarity1lastSalePrice', 'rarity2lastSalePrice', 'rarity3lastSalePrice', 'rarity4lastSalePrice',
        'rarity1Count', 'rarity2Count', 'rarity3Count', 'rarity4Count',
        'rarity1_order_count', 'rarity2_order_count', 'rarity3_order_count', 'rarity4_order_count'
    ]
    portfolio_scores = portfolio_scores.drop(columns=columns_to_drop)
    
    for col in ALL_SCORES:
        if col in portfolio_scores.columns:
            portfolio_scores[col] = pd.to_numeric(portfolio_scores[col], errors='coerce')
            if 'Variance' in col:
                portfolio_scores[col] = portfolio_scores.apply(lambda row: row[col] * 2.25 if row['hero_rarity_index'].endswith('3') else row[col], axis=1)
            elif 'Z_Score' in col:
                # Do not modify Z-scores
                pass
            else:
                # For raw scores, averages, and standard deviations
                portfolio_scores[col] = portfolio_scores.apply(lambda row: row[col] * 1.5 if row['hero_rarity_index'].endswith('3') else row[col], axis=1)

    return portfolio_scores


# Main Execution

def compile_data():
    """Main function to compile the data."""
    dataframes = import_latest_csv_files(DATA_FOLDER)
    # Load tournament data from all CSVs
    
    all_hero_data, tournament_columns = import_all_tournament_csvs(os.path.join(DATA_FOLDER, "tournament_results"))
    dataframes['tournament_scores'] = all_hero_data

    # Calculate tournament statistics
    dataframes['tournament_scores'] = calculate_tournament_statistics(dataframes['tournament_scores'])

    # Generate ALL_SCORES list
    ALL_SCORES = generate_all_scores_list(tournament_columns)
        
    # Merge all dataframes
    final_merged_df = merge_dataframes(dataframes)
    portfolio_scores = process_portfolio_scores(dataframes['portfolio'], final_merged_df, ALL_SCORES)
    # Save the final merged data
    save_final_dataframes(final_merged_df, portfolio_scores)

if __name__ == "__main__":
    compile_data()
