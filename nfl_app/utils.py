def calculate_profit(odds, bet_amount):
    if odds < 0: 
        return (100 / abs(odds)) * bet_amount
    else: 
        return (odds / 100) * bet_amount