"""Acceptance tests for the Camicia card game simulation."""

from camicia import simulate_game


def _field(result, name):
    try:
        return result[name]
    except (TypeError, KeyError):
        return getattr(result, name)


def _summary(result):
    return (
        _field(result, "status"),
        _field(result, "cards"),
        _field(result, "tricks"),
    )


def test_result_exposes_status_cards_and_tricks():
    """REQ: "Determine the following information regarding the game: Status, Cards, Tricks" """
    result = simulate_game(["2"], ["3"])
    status = _field(result, "status")
    cards = _field(result, "cards")
    tricks = _field(result, "tricks")
    assert isinstance(status, str)
    assert isinstance(cards, int) and not isinstance(cards, bool)
    assert isinstance(tricks, int) and not isinstance(tricks, bool)


def test_status_is_finished_or_loop():
    """REQ: "Status: "finished" or "loop"" """
    ended = simulate_game(["2"], ["3"])
    looped = simulate_game(["J", "2", "3"], ["4", "J", "5"])
    assert _field(ended, "status") in ("finished", "loop")
    assert _field(looped, "status") in ("finished", "loop")


def test_example_game_that_ends():
    """REQ: "A small example of a match that ends." with status "finished", cards 13, tricks 1" """
    result = simulate_game(
        ["2", "A", "7", "8", "Q", "10"],
        ["3", "4", "5", "6", "K", "9", "J"],
    )
    assert _summary(result) == ("finished", 13, 1)


def test_example_game_that_loops():
    """REQ: "This is a small example of a match that loops." with status "loop", cards 8, tricks 3" """
    result = simulate_game(
        ["J", "2", "3"],
        ["4", "J", "5"],
    )
    assert _summary(result) == ("loop", 8, 3)


def test_minimal_number_cards_end_game():
    """REQ: "If a player runs out of cards and is unable to play a card (either while paying a penalty or when it is their turn), the other player collects the central pile." """
    result = simulate_game(["2"], ["3"])
    assert _summary(result) == ("finished", 2, 1)


def test_jack_penalty_is_one_card():
    """REQ: "J → opponent must pay 1 card" """
    result = simulate_game(["J"], ["2", "3"])
    assert _summary(result) == ("finished", 4, 2)


def test_queen_penalty_is_two_cards():
    """REQ: "Q → opponent must pay 2 cards" """
    result = simulate_game(["Q"], ["2", "3"])
    assert _summary(result) == ("finished", 3, 1)


def test_king_penalty_is_three_cards():
    """REQ: "K → opponent must pay 3 cards" """
    result = simulate_game(["K"], ["2", "3", "4"])
    assert _summary(result) == ("finished", 4, 1)


def test_ace_penalty_is_four_cards():
    """REQ: "A → opponent must pay 4 cards" """
    result = simulate_game(["A"], ["2", "3", "4", "5"])
    assert _summary(result) == ("finished", 5, 1)


def test_revealed_payment_card_interrupts_penalty():
    """REQ: "If the player paying a penalty reveals another payment card, that player stops paying the penalty. The other player must then pay a penalty based on the new payment card." """
    result = simulate_game(["J", "2"], ["Q", "3"])
    assert _summary(result) == ("finished", 3, 1)


def test_cards_count_every_play_including_replays():
    """REQ: "Cards: total number of cards played throughout the game" """
    result = simulate_game(["J", "2"], ["3", "4"])
    assert _summary(result) == ("finished", 5, 2)


def test_finished_game_has_at_least_one_trick():
    """REQ: "If a player has all the cards in their possession after a trick, the game ends." """
    for player_a, player_b in (
        (["2"], ["3"]),
        (["Q"], ["2", "3"]),
        (["A"], ["2", "3", "4", "5"]),
    ):
        result = simulate_game(player_a, player_b)
        assert _field(result, "status") == "finished"
        assert _field(result, "tricks") >= 1
        assert _field(result, "cards") >= 1


def test_simulation_is_deterministic():
    """REQ: "Using the input, simulate the game following the rules above." """
    first = _summary(simulate_game(["J", "2", "3"], ["4", "J", "5"]))
    second = _summary(simulate_game(["J", "2", "3"], ["4", "J", "5"]))
    assert first == second
