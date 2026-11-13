"""Request traffic generation: fixed traces and continuous arrivals."""

from .fixed_trace import generate_fixed_trace
from .poisson import generate_poisson_trace

__all__ = ["generate_fixed_trace", "generate_poisson_trace"]
