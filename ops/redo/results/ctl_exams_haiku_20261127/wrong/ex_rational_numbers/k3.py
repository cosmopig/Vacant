from math import gcd


class Rational:
    def __init__(self, numer, denom):
        if denom == 0:
            raise ValueError("denominator must not be zero")
        if denom < 0:
            numer, denom = -numer, -denom
        g = gcd(numer, denom) or 1
        self.numer = numer // g
        self.denom = denom // g

    def __eq__(self, other):
        return self.numer == other.numer and self.denom == other.denom

    def __repr__(self):
        return f'{self.numer}/{self.denom}'

    @staticmethod
    def _coerce(value):
        if isinstance(value, Rational):
            return value
        if isinstance(value, int):
            return Rational(value, 1)
        return NotImplemented

    def __add__(self, other):
        other = self._coerce(other)
        if other is NotImplemented:
            return NotImplemented
        return Rational(self.numer * other.denom + other.numer * self.denom,
                        self.denom * other.denom)

    def __sub__(self, other):
        other = self._coerce(other)
        if other is NotImplemented:
            return NotImplemented
        return Rational(self.numer * other.denom - other.numer * self.denom,
                        self.denom * other.denom)

    def __mul__(self, other):
        other = self._coerce(other)
        if other is NotImplemented:
            return NotImplemented
        return Rational(self.numer * other.numer, self.denom * other.denom)

    def __truediv__(self, other):
        other = self._coerce(other)
        if other is NotImplemented:
            return NotImplemented
        if other.numer == 0:
            raise ZeroDivisionError("division by zero rational")
        return Rational(self.numer * other.denom, self.denom * other.numer)

    def __abs__(self):
        return Rational(abs(self.numer), abs(self.denom))

    def __pow__(self, power):
        if isinstance(power, int):
            if power >= 0:
                return Rational(self.numer ** power, self.denom ** power)
            m = -power
            obj = Rational.__new__(Rational)
            obj.numer = self.denom ** m
            obj.denom = self.numer ** m
            return obj
        if isinstance(power, float):
            return (self.numer ** power) / (self.denom ** power)
        return NotImplemented

    def __rpow__(self, base):
        if isinstance(base, (int, float)) and not isinstance(base, bool):
            return (base ** self.numer) ** (1.0 / self.denom)
        return NotImplemented
