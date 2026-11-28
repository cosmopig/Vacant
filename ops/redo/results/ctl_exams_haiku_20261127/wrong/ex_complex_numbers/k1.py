import math


class ComplexNumber:
    def __init__(self, real, imaginary):
        self.real = real
        self.imaginary = imaginary

    def __eq__(self, other):
        if not isinstance(other, ComplexNumber):
            return False
        return math.isclose(self.real, other.real) and math.isclose(
            self.imaginary, other.imaginary
        )

    def __add__(self, other):
        return ComplexNumber(self.real + other.real, self.imaginary + other.imaginary)

    def __mul__(self, other):
        a, b = self.real, self.imaginary
        c, d = other.real, other.imaginary
        return ComplexNumber(a * c - b * d, b * c + a * d)

    def __sub__(self, other):
        return ComplexNumber(self.real - other.real, self.imaginary - other.imaginary)

    def __truediv__(self, other):
        a, b = self.real, self.imaginary
        c, d = other.real, other.imaginary
        denominator = c * c + d * d
        return ComplexNumber(
            (a * c + b * d) / denominator,
            (b * c - a * d) / denominator,
        )

    def __abs__(self):
        return math.sqrt(self.real * self.real + self.imaginary * self.imaginary)

    def conjugate(self):
        return ComplexNumber(self.real, -self.imaginary)

    def exp(self):
        scale = math.exp(self.real)
        return ComplexNumber(
            scale * math.cos(self.imaginary),
            scale * math.sin(self.imaginary),
        )
