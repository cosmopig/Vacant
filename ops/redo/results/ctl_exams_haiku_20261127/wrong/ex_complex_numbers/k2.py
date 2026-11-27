import math


class ComplexNumber:
    def __init__(self, real, imaginary):
        self.real = real
        self.imaginary = imaginary

    @staticmethod
    def _coerce(other):
        if isinstance(other, ComplexNumber):
            return other
        if isinstance(other, (int, float)):
            return ComplexNumber(other, 0)
        return NotImplemented

    def __eq__(self, other):
        other = self._coerce(other)
        if other is NotImplemented:
            return NotImplemented
        return (math.isclose(self.real, other.real, abs_tol=1e-9)
                and math.isclose(self.imaginary, other.imaginary, abs_tol=1e-9))

    def __repr__(self):
        return f"ComplexNumber({self.real}, {self.imaginary})"

    def __add__(self, other):
        other = self._coerce(other)
        if other is NotImplemented:
            return NotImplemented
        return ComplexNumber(self.real + other.real,
                             self.imaginary + other.imaginary)

    def __mul__(self, other):
        other = self._coerce(other)
        if other is NotImplemented:
            return NotImplemented
        a, b = self.real, self.imaginary
        c, d = other.real, other.imaginary
        return ComplexNumber(a * c - b * d, b * c + a * d)

    def __sub__(self, other):
        other = self._coerce(other)
        if other is NotImplemented:
            return NotImplemented
        return ComplexNumber(self.real - other.real,
                             self.imaginary - other.imaginary)

    def __truediv__(self, other):
        other = self._coerce(other)
        if other is NotImplemented:
            return NotImplemented
        a, b = self.real, self.imaginary
        c, d = other.real, other.imaginary
        denom = c * c + d * d
        if denom == 0:
            raise ZeroDivisionError("complex division by zero")
        return ComplexNumber((a * c + b * d) / denom,
                             (b * c + a * d) / denom)

    def __abs__(self):
        return math.hypot(self.real, self.imaginary)

    def conjugate(self):
        return ComplexNumber(self.real, -self.imaginary)

    def exp(self):
        factor = math.exp(self.real)
        return ComplexNumber(factor * math.cos(self.imaginary),
                             factor * math.sin(self.imaginary))
