from collections import deque

PENALTIES = {"J": 1, "Q": 2, "K": 3, "A": 4}


def _state_key(hands):
    return tuple(
        tuple("N" if card not in PENALTIES else card for card in hand)
        for hand in hands
    )


def simulate_game(player_a, player_b):
    hands = [deque(player_a), deque(player_b)]
    total = len(hands[0]) + len(hands[1])
    pile = []
    cards = 0
    tricks = 0
    turn = 0
    owed = 0
    seen = {_state_key(hands)}

    def collect(collector):
        nonlocal tricks, owed, turn
        hands[collector].extend(pile)
        pile.clear()
        tricks += 1
        owed = 0
        turn = collector
        if len(hands[collector]) == total:
            return "finished"
        key = _state_key(hands)
        if key in seen:
            return "loop"
        seen.add(key)
        return None

    def result(status):
        return {"status": status, "cards": cards, "tricks": tricks}

    while True:
        status = None
        if not hands[turn]:
            status = collect(1 - turn)
        else:
            card = hands[turn].popleft()
            pile.append(card)
            cards += 1
            if owed:
                owed -= 1
                if card in PENALTIES:
                    owed = PENALTIES[card]
                    turn = 1 - turn
                elif owed == 0:
                    status = collect(turn)
            elif card in PENALTIES:
                owed = PENALTIES[card]
                turn = 1 - turn
            else:
                turn = 1 - turn
        if status is not None:
            return result(status)
