import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
import joblib
import os

# Set up robust file paths that work regardless of where the script is run.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
DATA_FILE_PATH = os.path.join(PROJECT_ROOT, 'data/games.csv')
MODEL_DIR = os.path.join(PROJECT_ROOT, 'models')
MODEL_FILE_PATH = os.path.join(MODEL_DIR, 'model.pkl')

# Ensure the 'models' directory exists.
os.makedirs(MODEL_DIR, exist_ok=True)

# Load the dataset
df = pd.read_csv(DATA_FILE_PATH)

df = df[(df['game_type'] == 'REG') & (df['season'] >= 2006)]
df = df[['result', 'spread_line']].dropna()

# Feature Engineering
df['home_win'] = (df['result'] > 0).astype(int)

# Prepare data for modeling
X = df[['spread_line']]
y = df['home_win']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train the model
model = LogisticRegression()
model.fit(X_train, y_train)

# Evaluate and print accuracy
accuracy = model.score(X_test, y_test)
print(f"--- Model Training Complete ---")
print(f"Accuracy on test data: {accuracy:.4f}")

# Save the trained model
joblib.dump(model, MODEL_FILE_PATH)
print(f"Model saved to '{MODEL_FILE_PATH}'")