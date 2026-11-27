import math
import random


class Character:
    def __init__(self):
        self.strength = self._roll_ability()
        self.dexterity = self._roll_ability()
        self.constitution = self._roll_ability()
        self.intelligence = self._roll_ability()
        self.wisdom = self._roll_ability()
        self.charisma = self._roll_ability()
        self.hitpoints = 10 + modifier(self.constitution)

    @staticmethod
    def _roll_ability():
        dice = sorted(random.randint(1, 6) for _ in range(4))
        return sum(dice[1:])


def modifier(value):
    return float(math.floor((value - 10) / 2))
