import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
import joblib
import os
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
DATA_FILE_PATH = os.path.join(PROJECT_ROOT, 'data/games.csv')
MODEL_DIR = os.path.join(PROJECT_ROOT, 'models')
MODEL_FILE_PATH = os.path.join(MODEL_DIR, 'model.pkl')
METRICS_FILE_PATH = os.path.join(PROJECT_ROOT, 'data/model_metrics.json')

os.makedirs(MODEL_DIR, exist_ok=True)

df = pd.read_csv(DATA_FILE_PATH)
df = df[(df['game_type'] == 'REG') & (df['season'] >= 2006)]

cols_to_keep = ['result', 'spread_line', 'home_moneyline', 'away_moneyline']
df = df[cols_to_keep].dropna()

df['home_win'] = (df['result'] > 0).astype(int)

X = df[['spread_line']]
y = df['home_win']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = LogisticRegression()
model.fit(X_train, y_train)

accuracy = model.score(X_test, y_test)

test_df = df.loc[X_test.index].copy()
test_df['prediction'] = model.predict(X_test)

def calculate_profit(odds, bet_amount):
    if odds < 0: 
        return (100 / abs(odds)) * bet_amount
    else: 
        return (odds / 100) * bet_amount

total_profit = 0
bet_amount = 100

for _, row in test_df.iterrows():
    if row['prediction'] == row['home_win']:
        if row['prediction'] == 1:
            total_profit += calculate_profit(row['home_moneyline'], bet_amount)
        else:
            total_profit += calculate_profit(row['away_moneyline'], bet_amount)
    else:
        total_profit -= bet_amount

roi = (total_profit / (len(test_df) * bet_amount)) * 100 if len(test_df) > 0 else 0

metrics = {
    'accuracy': f"{accuracy:.2%}",
    'total_games_tested': len(test_df),
    'simulated_roi': f"{roi:.2f}%"
}

with open(METRICS_FILE_PATH, 'w') as f:
    json.dump(metrics, f)

joblib.dump(model, MODEL_FILE_PATH)

print("--- Model Training Complete ---")
print(f"Accuracy on test data: {accuracy:.4f}")
print(f"Model saved to '{MODEL_FILE_PATH}'")
print(f"Metrics saved to '{METRICS_FILE_PATH}'")