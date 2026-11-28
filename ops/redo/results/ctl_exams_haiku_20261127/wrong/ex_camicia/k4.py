from collections import deque

PENALTY = {"J": 1, "Q": 2, "K": 3, "A": 4}


def _shape(deck):
    return tuple("N" if card.isdigit() else card for card in deck)


def simulate_game(player_a, player_b):
    decks = [deque(player_a), deque(player_b)]
    total = len(player_a) + len(player_b)
    cards = 0
    tricks = 0
    leader = 0
    seen = set()

    while True:
        key = (_shape(decks[0]), _shape(decks[1]))
        if key in seen:
            return {"status": "loop", "cards": cards, "tricks": tricks}
        seen.add(key)

        pile = []
        turn = leader
        owed = 0
        payer = None
        last_owner = None
        collector = None

        while collector is None:
            p = payer if owed > 0 else turn
            if not decks[p]:
                collector = 1 - p
                break
            card = decks[p].popleft()
            pile.append(card)
            cards += 1
            if card in PENALTY:
                owed = PENALTY[card]
                payer = 1 - p
                last_owner = p
                turn = payer
            elif owed > 0:
                owed -= 1
                if owed == 0:
                    collector = last_owner
                    break
            else:
                turn = 1 - p

        decks[collector].extend(pile)
        tricks += 1
        leader = collector

        if len(decks[collector]) == total:
            return {"status": "finished", "cards": cards, "tricks": tricks}
