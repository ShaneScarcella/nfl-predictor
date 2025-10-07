import requests
import os

# This is the direct link to the raw CSV file on GitHub.
# We've updated it to the correct 'nfldata' repository.
DATA_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
# We want to save the file in our local 'data' directory.
LOCAL_FILE_PATH = os.path.join("data", "games.csv")

def update_game_data():
    """
    Downloads the latest NFL game data from the nflverse repository
    and saves it to the local 'data/games.csv' file.
    """
    print("Attempting to download the latest NFL game data...")
    print(f"From URL: {DATA_URL}")
    
    try:
        # Make a request to the URL. The timeout is a safeguard.
        response = requests.get(DATA_URL, timeout=15)
        
        # This will raise an error if the download failed (e.g., 404 Not Found).
        response.raise_for_status()
        
        # If the download was successful, we write the content to our local file.
        # 'wb' means 'write in binary mode', which is the standard way to save downloaded files.
        with open(LOCAL_FILE_PATH, 'wb') as f:
            f.write(response.content)
            
        print(f"Successfully downloaded and saved the latest data to '{LOCAL_FILE_PATH}'")
        print("You should now retrain the model to include the new data.")

    except requests.exceptions.RequestException as e:
        # If anything went wrong with the download, tell the user.
        print(f"\nError: Could not download the data file.")
        print("Please check your internet connection or try pasting the URL directly into your browser.")
        print(f"Details: {e}")

# This makes the script runnable from the command line by typing 'python update_data.py'
if __name__ == "__main__":
    update_game_data()

