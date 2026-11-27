import math


class Rational:
    def __init__(self, numer, denom):
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
        other = _to_rational(other)
        return Rational(
            self.numer * other.denom + other.numer * self.denom,
            self.denom * other.denom,
        )

    def __sub__(self, other):
        other = _to_rational(other)
        return Rational(
            self.numer * other.denom - other.numer * self.denom,
            self.denom * other.denom,
        )

    def __mul__(self, other):
        other = _to_rational(other)
        return Rational(self.numer * other.numer, self.denom * other.denom)

    def __truediv__(self, other):
        other = _to_rational(other)
        if other.numer == 0:
            raise ZeroDivisionError("division by zero rational number")
        return Rational(self.numer * other.denom, self.denom * other.numer)

    def __abs__(self):
        return Rational(abs(self.numer), self.denom)

    def __pow__(self, power):
        if isinstance(power, int):
            if power >= 0:
                return Rational(self.numer ** power, self.denom ** power)
            m = -power
            return Rational(self.denom ** m, self.numer ** m)
        if isinstance(power, float):
            return (self.numer ** power) / (self.denom ** power)
        return NotImplemented

    def __rpow__(self, base):
        if not isinstance(base, (int, float)):
            return NotImplemented
        p = base ** self.numer
        if self.denom == 1:
            return p
        return p ** (1 / self.denom)


def _to_rational(value):
    if isinstance(value, Rational):
        return value
    if isinstance(value, int):
        return Rational(value, 1)
    return NotImplemented
