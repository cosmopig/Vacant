from collections import deque

PENALTIES = {"J": 1, "Q": 2, "K": 3, "A": 4}


def _state_key(decks):
    return tuple(
        tuple(card if card in PENALTIES else "N" for card in deck)
        for deck in decks
    )


def simulate_game(player_a, player_b):
    decks = [deque(player_a), deque(player_b)]
    total = len(decks[0]) + len(decks[1])
    pile = []
    cards = 0
    tricks = 0
    seen = set()
    start = 0

    while True:
        key = _state_key(decks)
        if key in seen:
            return {"status": "loop", "cards": str(cards), "tricks": tricks}
        seen.add(key)

        player = start
        owed = 0
        last_payer = None
        while True:
            if not decks[player]:
                collector = 1 - player
                break
            card = decks[player].popleft()
            pile.append(card)
            cards += 1
            if card in PENALTIES:
                last_payer = player
                owed = PENALTIES[card]
                player = 1 - player
            elif owed:
                owed -= 1
                if owed == 0:
                    collector = last_payer
                    break
            else:
                player = 1 - player

        decks[collector].extend(pile)
        pile.clear()
        tricks += 1
        if len(decks[collector]) == total:
            return {"status": "finished", "cards": str(cards), "tricks": tricks}
        start = collector
