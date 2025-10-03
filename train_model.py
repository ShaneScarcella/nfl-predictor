import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
import joblib

# --- Helper Function for Profit Calculation ---
def calculate_profit(odds, bet_amount):
    """Calculates profit for a winning bet based on American odds."""
    if odds < 0:
        return (100 / abs(odds)) * bet_amount
    else:
        return (odds / 100) * bet_amount

# --- 1. Load and Prepare Data ---
file_path = 'data/games.csv'
df = pd.read_csv(file_path)

df = df[(df['game_type'] == 'REG') & (df['season'] >= 2006)]

# Keep only the columns we need for this simple model
columns_to_keep = ['result', 'spread_line', 'home_moneyline', 'away_moneyline']
df = df[columns_to_keep]
df = df.dropna()

# --- 2. Feature Engineering (Target: Outright Winner) ---
df['home_win'] = (df['result'] > 0).astype(int)

# --- 3. Prepare Data for Modeling ---
# Our only feature is the spread_line
X = df[['spread_line']]
y = df['home_win']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# --- 4. Train and Evaluate the Model ---
model = LogisticRegression()
model.fit(X_train, y_train)
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print("--- Simple Model (Best Accuracy) ---")
print("Feature: spread_line | Model: LogisticRegression")
print(f"Accuracy on test data: {accuracy:.4f}")

# --- 5. Moneyline Profitability Simulation ---
bet_amount = 100
total_profit = 0
total_bets = 0
wins = 0

test_df = df.loc[X_test.index]
test_df['prediction'] = y_pred

for index, row in test_df.iterrows():
    total_bets += 1
    actual_winner = row['home_win']
    predicted_winner = row['prediction']

    if predicted_winner == 1:
        if actual_winner == 1:
            wins += 1
            total_profit += calculate_profit(row['home_moneyline'], bet_amount)
        else:
            total_profit -= bet_amount
    else:
        if actual_winner == 0:
            wins += 1
            total_profit += calculate_profit(row['away_moneyline'], bet_amount)
        else:
            total_profit -= bet_amount

win_rate = (wins / total_bets) * 100
roi = (total_profit / (total_bets * bet_amount)) * 100

print("\n--- Moneyline Betting Simulation Results ---")
print(f"Total Bets Placed: {total_bets}")
print(f"Winning Bets: {wins} ({win_rate:.2f}%)")
print(f"Total Profit/Loss: ${total_profit:.2f}")
print(f"Return on Investment (ROI): {roi:.2f}%")

# --- 6. Save the Model ---
joblib.dump(model, 'model.pkl')
print("\nModel saved to model.pkl")