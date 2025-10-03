import pandas as pd

file_path = 'data/games.csv'

df = pd.read_csv(file_path)

print("Successfully loaded the data. Here are the first 5 rows:")
print(df.head())