from config import MIN_PROFIT_USD, MAX_SLIPPAGE

def evaluate_spread(buy_price, sell_price, trade_usd=1.0):
    gross_profit = (sell_price - buy_price) * (trade_usd / buy_price)

    est_slippage = trade_usd * MAX_SLIPPAGE

    net_profit = gross_profit - est_slippage

    if net_profit >= MIN_PROFIT_USD:
        return True, round(net_profit, 4)

    return False, round(net_profit, 4)

