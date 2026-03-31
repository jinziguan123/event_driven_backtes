class DemoBuyHoldStrategy:
    name = 'demo_buy_hold'

    def on_bar(self, context, bars):
        broker = context['broker']
        if not bars:
            return None

        orders = []
        for symbol, bar in bars.items():
            position = broker.account.positions.get(symbol)
            if position is None or position.quantity == 0:
                quantity = 100
                orders.append({'symbol': symbol, 'type': 'BUY', 'quantity': quantity, 'price': bar.close})
                break
        return orders or None
