import pandas as pd
import glob
import os
from datetime import datetime

# Define the pattern for the files
file_pattern = 'data/hero_stats_*.csv'  # Adjust this path as needed

# Load all files matching the pattern
files = glob.glob(file_pattern)

# Initialize an empty list to hold the DataFrames
dfs = []

for file in files:
    # Extract the date from the filename
    basename = os.path.basename(file)
    date_str = basename.split('_')[2]  # Extract YYMMDD
    time_str = basename.split('_')[3].split('.')[0]  # Extract HHMM
    
    # Combine date and time
    date = datetime.strptime(date_str + time_str, '%y%m%d%H%M')
    
    # Load the CSV into a DataFrame
    df = pd.read_csv(file)
    
    # Add a column for the date-specific Inflation Degree
    df[f'{date.strftime("%Y-%m-%d")} Inflation Degree'] = df['inflation_degree']
    
    # Drop the original Inflation Degree column to avoid duplication
    df.drop(columns=['inflation_degree'], inplace=True)
    
    # Append the DataFrame to the list
    dfs.append(df)

# Merge all DataFrames on 'hero_handle' and 'hero_id'
combined_df = pd.concat(dfs, axis=1)

# Remove duplicate 'hero_handle' and 'hero_id' columns, keeping the first occurrence
combined_df = combined_df.loc[:, ~combined_df.columns.duplicated()]

# Function to sort columns by type and date
def sort_columns_by_type_and_date(columns):
    # Separate the columns into different categories
    closing_score_columns = sorted([col for col in columns if 'Closing Score' in col], key=lambda x: x.split(' ')[0])
    closing_rank_columns = sorted([col for col in columns if 'Closing Rank' in col], key=lambda x: x.split(' ')[0])
    tournament_rank_columns = sorted([col for col in columns if 'Tournament Rank' in col], key=lambda x: x.split(' ')[0])
    inflation_degree_columns = sorted([col for col in columns if 'Inflation Degree' in col], key=lambda x: x.split(' ')[0])

    # Combine all sorted columns in the desired order
    sorted_columns = closing_score_columns + closing_rank_columns + tournament_rank_columns + inflation_degree_columns
    
    return sorted_columns

# Sort the columns by type and date
date_columns = [col for col in combined_df.columns if col not in ['hero_handle', 'hero_id']]
sorted_date_columns = sort_columns_by_type_and_date(date_columns)

# Reorder the columns with 'hero_handle' and 'hero_id' first, followed by the sorted date columns
final_columns = ['hero_handle', 'hero_id'] + sorted_date_columns
combined_df = combined_df[final_columns]

# Save the combined DataFrame to a CSV file
combined_df.to_csv('data/combined_hero_stats_sorted.csv', index=False)

print("Combined and sorted data saved to 'combined_hero_stats_sorted.csv'")
