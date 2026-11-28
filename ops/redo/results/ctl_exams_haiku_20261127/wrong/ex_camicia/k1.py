from collections import deque

PAYMENT = {"J": 1, "Q": 2, "K": 3, "A": 4}


def _signature(deck):
    return tuple(card if card in PAYMENT else "#" for card in deck)


def _result(status, cards, tricks):
    return {"status": status, "cards": cards, "tricks": tricks}


def simulate_game(player_a, player_b):
    decks = [deque(player_a), deque(player_b)]
    pile = []
    cards = 0
    tricks = 0
    current = 0
    owed = 0
    payment_owner = None
    seen = set()

    while True:
        if not decks[current]:
            winner = 1 - current
            decks[winner].extend(pile)
            pile.clear()
            tricks += 1
            return _result("finished", cards, tricks)

        card = decks[current].popleft()
        pile.append(card)
        cards += 1

        if card in PAYMENT:
            owed = PAYMENT[card]
            payment_owner = current
            current = 1 - current
        elif owed > 0:
            owed -= 1
            if owed == 0:
                winner = payment_owner
                decks[winner].extend(pile)
                pile.clear()
                tricks += 1
                if not decks[1 - winner]:
                    return _result("finished", cards, tricks)
                current = winner
                key = (_signature(decks[0]), _signature(decks[1]), current)
                if key in seen:
                    return _result("loop", cards, tricks)
                seen.add(key)
        else:
            current = 1 - current
