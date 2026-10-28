class BowlingGame:
    def __init__(self):
        self.rolls = []

    def roll(self, pins):
        if pins < 0:
            raise ValueError("cannot score negative points")
        if pins > 10:
            raise ValueError("a roll cannot score more than 10 points")

        # Check if game is already finished before rolling
        if self._is_game_finished():
            raise IndexError("cannot roll if game already has ten frames")

        self.rolls.append(pins)
        self._validate_roll()

    def _is_game_finished(self):
        # A game is finished if we have completed 10 frames.
        count = 0
        roll_idx = 0
        for frame in range(10):
            if roll_idx >= len(self.rolls):
                break
            if self.rolls[roll_idx] == 10: # Strike
                count += 1
                roll_idx += 1
            else:
                count += 1
                roll_idx += 2
        return count == 10 and roll_idx == len(self.rolls)

    def _validate_roll(self):
        if not self.rolls:
            return

        # Find the start of the 10th frame rolls
        temp_roll_idx = 0
        for f in range(9):
            if temp_roll_idx >= len(self.rolls):
                break
            if self.rolls[temp_roll_idx] == 10:
                temp_roll_idx += 1
            else:
                temp_roll_idx += 2
        
        tenth_frame_rolls = self.rolls[temp_roll_idx:]

        # Rule: Two rolls in a frame cannot score more than 10 points (unless it's the 10th frame)
        current_roll_idx = 0
        for f in range(9):
            if current_roll_idx >= len(self.rolls):
                break
            if self.rolls[current_roll_idx] == 10:
                current_roll_idx += 1
            else:
                if current_roll_idx + 1 < len(self.rolls):
                    if self.rolls[current_roll_idx] + self.rolls[current_roll_idx+1] > 10:
                        raise ValueError("two rolls in a frame cannot score more than 10 points")
                    current_roll_idx += 2
                else:
                    # This part is reached if the game is incomplete but we are checking rules.
                    pass

        # Rules for the 10th frame
        if len(tenth_frame_rolls) > 0:
            first = tenth_frame_rolls[0]
            if first == 10:
                # Strike in 10th frame: can have up to 2 more rolls (total 3)
                if len(tenth_frame_rolls) > 3:
                    raise IndexError("cannot roll if game already has ten frames")
                if len(tenth_frame_rolls) == 3:
                    # Second and third bonus rolls cannot score more than 10 points
                    if tenth_frame_rolls[1] > 10: raise ValueError("bonus roll cannot score more than 10 points")
                    if tenth_frame_rolls[2] > 10: raise ValueError("bonus roll cannot score more than 10 points")
            else:
                # Not a strike in 10th frame
                if len(tenth_frame_rolls) == 2:
                    if tenth_frame_rolls[0] + tenth_frame_rolls[1] == 10:
                        # Spare, can have 1 more roll (total 3)
                        if len(tenth_frame_rolls) > 3:
                            raise IndexError("cannot roll if game already has ten frames")
                    else:
                        # Open frame, no bonus rolls allowed
                        if len(tenth_frame_rolls) > 2:
                            raise IndexError("cannot throw bonus with an open tenth frame")
                elif len(tenth_frame_rolls) == 3:
                    # If first was not strike and we have a third roll, it must be a spare
                    if tenth_frame_rolls[0] + tenth_frame_rolls[1] != 10:
                        raise IndexError("cannot throw bonus with an open tenth frame")
                    # And the second bonus roll cannot be a strike if the first one is not a strike?
                    # Wait, "the_second_bonus_rolls... cannot be a strike if the first one is not a strike"
                    if tenth_frame_rolls[2] == 10:
                        raise ValueError("the second bonus rolls after a strike in the last frame cannot be a strike if the first one is not a strike")
                elif len(tenth_frame_rolls) > 3:
                    raise IndexError("cannot roll if game already has ten frames")

    def score(self):
        if not self.rolls:
            raise IndexError("an unstarted game cannot be scored")
        
        # Check if the game is complete before scoring
        count = 0
        roll_idx = 0
        for frame in range(10):
            if roll_idx >= len(self.rolls):
                break
            if self.rolls[roll_idx] == 10: # Strike
                count += 1
                roll_idx += 1
            else:
                count += 1
                roll_idx += 2
        
        if count != 10 or roll_idx != len(self.rolls):
            raise IndexError("an incomplete game cannot be scored")

        total_score = 0
        roll_idx = 0
        for frame in range(10):
            if roll_idx >= len(self.rolls):
                break
            
            if self.rolls[roll_idx] == 10: # Strike
                bonus = 0
                if roll_idx + 1 < len(self.rolls):
                    bonus += self.rolls[roll_idx + 1]
                if roll_idx + 2 < len(self.rolls):
                    bonus += self.rolls[roll_idx + 2]
                total_score += (10 + bonus)
                roll_idx += 1
            else:
                if roll_idx + 1 < len(self.rolls):
                    score = self.rolls[roll_idx] + self.rolls[roll_idx + 1]
                    if score == 10: # Spare
                        bonus = self.rolls[roll_idx + 2] if roll_idx + 2 < len(self.rolls) else 0
                        total_score += (10 + bonus)
                    else:
                        total_score += score
                    roll_idx += 2
                else:
                    roll_idx += 1
        return total_score
