import math


def _to_complex(value):
    if isinstance(value, ComplexNumber):
        return value
    if isinstance(value, (int, float)):
        return ComplexNumber(value, 0)
    raise TypeError(f"unsupported operand type: {type(value).__name__}")


class ComplexNumber:
    def __init__(self, real, imaginary):
        self.real = real
        self.imaginary = imaginary

    def __eq__(self, other):
        if not isinstance(other, ComplexNumber):
            return NotImplemented
        return self.real == other.real and self.imaginary == other.imaginary

    def __repr__(self):
        return f"ComplexNumber({self.real!r}, {self.imaginary!r})"

    def __add__(self, other):
        other = _to_complex(other)
        return ComplexNumber(self.real + other.real, self.imaginary + other.imaginary)

    def __mul__(self, other):
        other = _to_complex(other)
        real = self.real * other.real - self.imaginary * other.imaginary
        imaginary = self.imaginary * other.real + self.real * other.imaginary
        return ComplexNumber(real, imaginary)

    def __sub__(self, other):
        other = _to_complex(other)
        return ComplexNumber(self.real - other.real, self.imaginary - other.imaginary)

    def __truediv__(self, other):
        other = _to_complex(other)
        denom = other.real ** 2 + other.imaginary ** 2
        if denom == 0:
            return ComplexNumber(float("nan"), float("nan"))
        real = (self.real * other.real + self.imaginary * other.imaginary) / denom
        imaginary = (self.imaginary * other.real - self.real * other.imaginary) / denom
        return ComplexNumber(real, imaginary)

    def __abs__(self):
        return math.hypot(self.real, self.imaginary)

    def conjugate(self):
        return ComplexNumber(self.real, -self.imaginary)

    def exp(self):
        magnitude = math.exp(self.real)
        return ComplexNumber(
            magnitude * math.cos(self.imaginary),
            magnitude * math.sin(self.imaginary),
        )
