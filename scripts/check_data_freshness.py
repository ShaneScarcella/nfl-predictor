import pandas as pd
import os

DATA_FILE_PATH = os.path.join('data', 'games.csv')

def check_latest_game_date():
    """
    Loads the local games.csv file, filters for games that have been played,
    and then finds and prints the date of the most recent completed game.
    """
    print(f"--- Checking freshness of '{DATA_FILE_PATH}' ---")
    
    try:
        # Load the data file.
        df = pd.read_csv(DATA_FILE_PATH)

        # Filter the DataFrame to include only rows where a home_score exists.
        played_games = df.dropna(subset=['home_score']).copy()

        if played_games.empty:
            print("No completed games with scores found in the file.")
            return

        # Convert the 'gameday' column to a proper date format.
        played_games['gameday'] = pd.to_datetime(played_games['gameday'])
        
        # Find the most recent date within the subset of played games.
        latest_date = played_games['gameday'].max()
        
        if pd.notna(latest_date):
            print(f"The latest COMPLETED game in your local file is from: {latest_date.strftime('%B %d, %Y')}")
        else:
            print("Could not determine the latest date among completed games.")

    except FileNotFoundError:
        print(f"Error: '{DATA_FILE_PATH}' not found.")
        print("Please run 'python scripts/update_data.py' first to download the data.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    check_latest_game_date()