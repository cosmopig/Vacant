"""A bowling game.

Visible-test API (``bowling_test.py``): ``BowlingGame`` with ``roll(pins)``
and ``score()``. Invalid rolls and scoring an incomplete game raise
``ValueError`` with a non-empty message (the test uses
``assertRaisesRegex(Exception, r".+")``).
"""


class BowlingGame:
    """Ten frames of ten-pin bowling.

    A strike earns the next two rolls as bonus; a spare earns the next roll.
    In the tenth frame a strike takes two bonus rolls, a spare one. The two
    bonus rolls after a strike obey the frame rule: if the first is not a
    strike, the pair may not exceed ten.
    """

    FRAMES = 10

    def __init__(self):
        self._rolls = []

    # ------------------------------------------------------------------ #
    # parsing / rules                                                    #
    # ------------------------------------------------------------------ #

    def _frames(self):
        """Split the rolls into ``(frames, bonuses)``.

        ``frames`` holds up to ``FRAMES`` frames, each a list of 1-2 rolls;
        ``bonuses`` are the rolls after the tenth frame (0-2). Raises
        ``ValueError`` when a two-roll frame exceeds ten pins.
        """
        frames, i, n = [], 0, len(self._rolls)
        while i < n and len(frames) < self.FRAMES:
            if self._rolls[i] == 10:
                frames.append([10])
                i += 1
            elif i + 1 < n:
                a, b = self._rolls[i], self._rolls[i + 1]
                if a + b > 10:
                    raise ValueError(
                        "two rolls in a frame cannot score more than 10 pins")
                frames.append([a, b])
                i += 2
            else:
                frames.append([self._rolls[i]])
                i += 1
        return frames, self._rolls[i:]

    @staticmethod
    def _bonus_pair_ok(bonuses):
        """The two bonus rolls after a tenth-frame strike are legal iff the
        first is a strike, or the pair does not exceed ten."""
        first, second = bonuses[0], bonuses[1]
        return first == 10 or first + second <= 10

    def roll(self, pins):
        if isinstance(pins, bool) or not isinstance(pins, int):
            raise ValueError("a roll must be an integer number of pins")
        if pins < 0 or pins > 10:
            raise ValueError(
                f"a roll of {pins} pins is outside the 0..10 range")
        frames, bonuses = self._frames()
        if len(frames) < self.FRAMES:
            if frames:  # an empty game takes its first roll of 0..10 freely
                last = frames[-1]
                if (len(last) == 1 and last[0] != 10
                        and last[0] + pins > 10):
                    raise ValueError(
                        "two rolls in a frame cannot score more than 10 pins")
        else:
            last = frames[-1]
            if len(last) == 1 and last[0] != 10:
                # the tenth frame still needs its second roll
                if last[0] + pins > 10:
                    raise ValueError(
                        "two rolls in a frame cannot score more than 10 pins")
            elif last == [10]:
                if len(bonuses) == 1 and bonuses[0] != 10 \
                        and bonuses[0] + pins > 10:
                    raise ValueError(
                        "the two bonus rolls after a strike in the last "
                        "frame cannot score more than 10 pins")
                elif len(bonuses) >= 2:
                    raise ValueError(
                        "cannot roll after the bonus rolls for a strike in "
                        "the last frame")
            elif len(last) == 2 and last[0] + last[1] == 10:
                if len(bonuses) >= 1:
                    raise ValueError(
                        "cannot roll after the bonus roll for a spare in "
                        "the last frame")
            else:
                raise ValueError("cannot roll after ten frames")
        self._rolls.append(pins)

    def score(self):
        frames, bonuses = self._frames()
        if not frames:
            raise ValueError("an unstarted game cannot be scored")
        if len(frames) < self.FRAMES:
            raise ValueError("an incomplete game cannot be scored")
        last = frames[-1]
        if last == [10]:
            if len(bonuses) != 2 or not self._bonus_pair_ok(bonuses):
                raise ValueError(
                    "a strike in the last frame needs two legal bonus rolls")
        elif len(last) == 2 and last[0] + last[1] == 10:
            if len(bonuses) != 1:
                raise ValueError(
                    "a spare in the last frame needs one bonus roll")
        elif len(last) == 2:
            if bonuses:
                raise ValueError("an open last frame takes no bonus rolls")
        else:
            raise ValueError("an incomplete game cannot be scored")

        total, pos = 0, 0
        for frame in frames[:-1]:
            if frame == [10]:
                total += 10
                total += self._rolls[pos + 1] + self._rolls[pos + 2]
                pos += 1
            else:
                total += sum(frame)
                if len(frame) == 2 and frame[0] + frame[1] == 10:
                    total += self._rolls[pos + 2]
                pos += len(frame)
        return total + sum(last) + sum(bonuses)
