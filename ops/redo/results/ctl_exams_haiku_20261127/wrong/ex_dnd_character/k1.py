import random


def modifier(value):
    return int((value - 10) / 2)


class Character:
    def __init__(self):
        self.strength = self.roll_ability()
        self.dexterity = self.roll_ability()
        self.constitution = self.roll_ability()
        self.intelligence = self.roll_ability()
        self.wisdom = self.roll_ability()
        self.charisma = self.roll_ability()
        self.hitpoints = 10 + modifier(self.constitution)

    @staticmethod
    def roll_ability():
        rolls = sorted(random.randint(1, 6) for _ in range(4))
        return sum(rolls[1:])
