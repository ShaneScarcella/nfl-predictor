import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib

# --- Helper Functions ---

def calculate_profit(odds, bet_amount):
    """Calculates profit for a winning bet based on American odds."""
    if odds < 0:
        return (100 / abs(odds)) * bet_amount
    else:
        return (odds / 100) * bet_amount

def calculate_implied_probability(odds):
    """Converts American odds to implied probability."""
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    else:
        return 100 / (odds + 100)

# --- 1. Load and Prepare Data ---
file_path = 'data/games.csv'
df = pd.read_csv(file_path)
df = df[(df['game_type'] == 'REG') & (df['season'] >= 2006)]
columns_to_keep = [
    'result', 'spread_line', 'home_moneyline', 'away_moneyline',
    'total_line', 'home_rest', 'away_rest', 'div_game'
]
df = df[columns_to_keep]
df = df.dropna()

# --- 2. Feature Engineering ---
df['home_win'] = (df['result'] > 0).astype(int)

# --- 3. Prepare Data for Modeling ---
features = ['spread_line', 'total_line', 'home_rest', 'away_rest', 'div_game']
X = df[features]
y = df['home_win']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# --- 4. Train the Model ---
model = RandomForestClassifier(n_estimators=100, min_samples_leaf=10, random_state=42)
model.fit(X_train, y_train)

# --- 5. Value Betting Simulation ---

# Get prediction probabilities for the test set
# The output is an array like [[P(lose), P(win)], [P(lose), P(win)], ...]
probabilities = model.predict_proba(X_test)

bet_amount = 100
total_profit = 0
total_bets = 0
wins = 0
# --- MODIFIED: Define our "edge" threshold ---
# We will only bet if our model's confidence is at least 5% higher than the implied odds.
CONFIDENCE_THRESHOLD = 0.05

test_df = df.loc[X_test.index]
test_df['model_prob_home_win'] = probabilities[:, 1] # Probability of home team winning

for index, row in test_df.iterrows():
    prob_home_win = row['model_prob_home_win']
    prob_away_win = 1 - prob_home_win

    implied_prob_home = calculate_implied_probability(row['home_moneyline'])
    implied_prob_away = calculate_implied_probability(row['away_moneyline'])

    # --- Betting Logic: Look for an edge ---

    # Case 1: Model sees value in the home team
    if prob_home_win > implied_prob_home + CONFIDENCE_THRESHOLD:
        total_bets += 1
        if row['home_win'] == 1:
            wins += 1
            total_profit += calculate_profit(row['home_moneyline'], bet_amount)
        else:
            total_profit -= bet_amount

    # Case 2: Model sees value in the away team
    elif prob_away_win > implied_prob_away + CONFIDENCE_THRESHOLD:
        total_bets += 1
        if row['home_win'] == 0:
            wins += 1
            total_profit += calculate_profit(row['away_moneyline'], bet_amount)
        else:
            total_profit -= bet_amount

win_rate = (wins / total_bets) * 100 if total_bets > 0 else 0
roi = (total_profit / (total_bets * bet_amount)) * 100 if total_bets > 0 else 0

print("--- Value Betting Simulation Results (Edge = 5%) ---")
print(f"Total Bets Placed: {total_bets} (out of {len(test_df)} games)")
if total_bets > 0:
    print(f"Winning Bets: {wins} ({win_rate:.2f}%)")
    print(f"Total Profit/Loss: ${total_profit:.2f}")
    print(f"Return on Investment (ROI): {roi:.2f}%")
else:
    print("No value bets found with the current confidence threshold.")

if total_profit > 0:
    print("\nSUCCESS! This value-betting strategy was profitable!")
else:
    print("\nThis strategy was not profitable. Beating the market is extremely difficult.")

# --- 6. Save the Model ---
joblib.dump(model, 'model.pkl')
print("\nModel saved to model.pkl")

