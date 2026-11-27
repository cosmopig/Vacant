from camicia import simulate_game


def test_finished_game_from_requirements_example():
    result = simulate_game(
        ["2", "A", "7", "8", "Q", "10"],
        ["3", "4", "5", "6", "K", "9", "J"],
    )
    assert result["status"] == "finished"
    assert result["cards"] == 13
    assert result["tricks"] == 1


def test_loop_game_from_requirements_example():
    # Round 4 matches round 2 once number-card values are ignored.
    result = simulate_game(
        ["J", "2", "3"],
        ["4", "J", "5"],
    )
    assert result["status"] == "loop"
    assert result["cards"] == 8
    assert result["tricks"] == 3


def test_number_cards_only_player_runs_out_on_turn():
    # A plays 2, B plays 3, A plays 5, B has no card on its turn,
    # so A collects the pile and holds all three cards.
    result = simulate_game(["2", "5"], ["3"])
    assert result["status"] == "finished"
    assert result["cards"] == 3
    assert result["tricks"] == 1


def test_jack_penalty_paid_with_number_card_collects_pile():
    # A plays J, B must pay 1 and pays with 2. Penalty is complete and the
    # last payment card was A's, so A collects the pile and holds all cards.
    result = simulate_game(["J"], ["2"])
    assert result["status"] == "finished"
    assert result["cards"] == 2
    assert result["tricks"] == 1


def test_player_runs_out_while_paying_penalty_other_player_collects():
    # A plays K, B owes 3 and reveals J, so A owes 1 and has no cards left.
    # B, the other player, collects the pile and holds all cards.
    result = simulate_game(["K"], ["J", "2"])
    assert result["status"] == "finished"
    assert result["cards"] == 2
    assert result["tricks"] == 1


def test_interrupted_penalty_last_payment_card_owner_collects():
    # A plays K (B owes 3). B interrupts with J (A owes 1). A pays with 2,
    # which completes the penalty. B placed the last payment card (J),
    # so B collects the pile and holds all cards.
    result = simulate_game(["K", "2"], ["J", "3", "4", "5"])
    assert result["status"] == "finished"
    assert result["cards"] == 3
    assert result["tricks"] == 1


def test_king_penalty_is_three_cards():
    # A plays K, B pays 3, 4, 5 without interruption, and A collects.
    # Round 2: A plays 2, B plays 6, A plays K, and B cannot pay,
    # so A collects and holds all cards.
    result = simulate_game(["K", "2"], ["3", "4", "5", "6"])
    assert result["status"] == "finished"
    assert result["cards"] == 7
    assert result["tricks"] == 2


def test_ace_penalty_is_four_cards():
    # A plays A, B pays 3, 4, 5, 6 without interruption, and A collects.
    # Round 2: A plays 2, B plays 7, A plays A, and B cannot pay,
    # so A collects and holds all cards.
    result = simulate_game(["A", "2"], ["3", "4", "5", "6", "7"])
    assert result["status"] == "finished"
    assert result["cards"] == 8
    assert result["tricks"] == 2
