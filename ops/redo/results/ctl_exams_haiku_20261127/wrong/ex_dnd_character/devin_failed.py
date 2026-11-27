import random


class Character:
    def __init__(self):
        self.strength = self.ability()
        self.dexterity = self.ability()
        self.constitution = self.ability()
        self.intelligence = self.ability()
        self.wisdom = self.ability()
        self.charisma = self.ability()
        self.hit_points = 10 + modifier(self.constitution)

    @staticmethod
    def ability():
        return sum(sorted(random.choices(range(1, 7), k=4), reverse=True)[:3])


def modifier(value):
    return (value - 10) // 2
