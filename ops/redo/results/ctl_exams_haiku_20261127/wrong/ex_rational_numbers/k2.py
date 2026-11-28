import math


class Rational:
    def __init__(self, numer, denom):
        if denom == 0:
            raise ValueError("denominator must not be zero")
        if denom < 0:
            numer, denom = -numer, -denom
        divisor = math.gcd(numer, denom) or 1
        self.numer = numer // divisor
        self.denom = denom // divisor

    def __eq__(self, other):
        return self.numer == other.numer and self.denom == other.denom

    def __repr__(self):
        return f'{self.numer}/{self.denom}'

    def __add__(self, other):
        return Rational(self.numer * other.denom + other.numer * self.denom,
                        self.denom * other.denom)

    def __sub__(self, other):
        return Rational(self.numer * other.denom - other.numer * self.denom,
                        self.denom * other.denom)

    def __mul__(self, other):
        return Rational(self.numer * other.numer, self.denom * other.denom)

    def __truediv__(self, other):
        if other.numer == 0:
            raise ZeroDivisionError("division by a zero rational")
        return Rational(self.numer * other.denom, self.denom * other.numer)

    def __abs__(self):
        return Rational(abs(self.numer), abs(self.denom))

    def __pow__(self, power):
        if isinstance(power, int):
            m = abs(power)
            numer, denom = self.numer ** m, self.denom ** m
            return Rational(numer, denom)
        return (self.numer / self.denom) ** power

    def __rpow__(self, base):
        return (base ** self.numer) ** (1 / self.denom)
