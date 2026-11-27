from camicia import simulate_game


def test_example_match_that_finishes():
    result = simulate_game(
        ["2", "A", "7", "8", "Q", "10"],
        ["3", "4", "5", "6", "K", "9", "J"],
    )
    # SRC: "If a player has all the cards in their possession after a trick, the game"
    assert result["status"] == "finished"
    # SRC: "total number of cards played throughout the game"
    assert result["cards"] == 13
    # SRC: "The moment when a player collects cards from the central pile is called a"
    assert result["tricks"] == 1


def test_example_match_that_loops():
    result = simulate_game(
        ["J", "2", "3"],
        ["4", "J", "5"],
    )
    # SRC: "as soon as the decks are identical to what they were earlier during the game,"
    assert result["status"] == "loop"
    # SRC: "total number of cards played throughout the game"
    assert result["cards"] == 8
    # SRC: "The moment when a player collects cards from the central pile is called a"
    assert result["tricks"] == 3


def test_number_cards_pass_turn_and_empty_player_loses_trick():
    result = simulate_game(["2"], ["3"])
    # SRC: "play simply passes to the other player."
    assert result["cards"] == 2
    # SRC: "If a player runs out of cards and is unable to play a card"
    assert result["tricks"] == 1
    # SRC: "If a player has all the cards in their possession after a trick, the game"
    assert result["status"] == "finished"


def test_number_cards_alternate_until_a_player_cannot_play():
    result = simulate_game(["2", "3"], ["4", "5"])
    # SRC: "play simply passes to the other player."
    assert result["cards"] == 4
    # SRC: "If a player runs out of cards and is unable to play a card"
    assert result["tricks"] == 1
    # SRC: "If a player has all the cards in their possession after a trick, the game"
    assert result["status"] == "finished"


def test_interrupting_payment_card_stops_penalty():
    result = simulate_game(["J"], ["J"])
    # SRC: "If the player paying a penalty reveals another payment card, that player stops paying the penalty."
    assert result["cards"] == 2
    # SRC: "The moment when a player collects cards from the central pile is called a"
    assert result["tricks"] == 1
    # SRC: "If a player has all the cards in their possession after a trick, the game"
    assert result["status"] == "finished"


def test_king_penalty_is_three_cards_and_unpaid_player_loses_trick():
    result = simulate_game(["K"], ["2", "3", "4", "5"])
    # SRC: "opponent must pay 3 cards"
    assert result["cards"] == 6
    # SRC: "The moment when a player collects cards from the central pile is called a"
    assert result["tricks"] == 2
    # SRC: "If a player has all the cards in their possession after a trick, the game"
    assert result["status"] == "finished"
