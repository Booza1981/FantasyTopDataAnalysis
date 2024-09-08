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

    return all_hero_data

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
    merged_hero_stats = merged_hero_stats.merge(dataframes['last_trades'], on=['hero_id'], how='left')
    
    # Check if 'Name' exists in tournament_scores before dropping it
    if 'Name' in dataframes['tournament_scores'].columns:
        dataframes['tournament_scores'].drop(columns=['Name'], inplace=True)
    
    # Merge with the compiled tournament scores
    merged_hero_stats = merged_hero_stats.merge(dataframes['tournament_scores'], left_on='hero_handle', right_on='hero_handle', how='left')
    merged_hero_stats.drop_duplicates(subset=['hero_handle'], inplace=True)
    merged_hero_stats['hero_id'] = merged_hero_stats['hero_id'].astype(str)
    
    return merged_hero_stats

def save_final_dataframes(final_merged_df):
    """Saves the final merged dataframe to a CSV file."""
    final_merged_df.to_csv(f'{DATA_FOLDER}/allHeroData.csv', index=False)

# Main Execution

def compile_data():
    """Main function to compile the data."""
    dataframes = import_latest_csv_files(DATA_FOLDER)
    # Load tournament data from all CSVs
    
    dataframes['tournament_scores'] = import_all_tournament_csvs(os.path.join(DATA_FOLDER, "tournament_results"))

    # Calculate tournament statistics
    dataframes['tournament_scores'] = calculate_tournament_statistics(dataframes['tournament_scores'])

    # Load other hero data (assuming these are stored in separate files)
    

    # Merge all dataframes
    final_merged_df = merge_dataframes(dataframes)

    # Save the final merged data
    save_final_dataframes(final_merged_df)

if __name__ == "__main__":
    compile_data()
