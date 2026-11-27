import random


def roll_ability():
    dice = [random.randint(1, 6) for _ in range(4)]
    dice.sort()
    return sum(dice[1:])


class Character:
    def __init__(self):
        self.strength = roll_ability()
        self.dexterity = roll_ability()
        self.constitution = roll_ability()
        self.intelligence = roll_ability()
        self.wisdom = roll_ability()
        self.charisma = roll_ability()
        self.hitpoints = 10 + modifier(self.constitution)


def modifier(value):
    return int((value - 10) / 2)
