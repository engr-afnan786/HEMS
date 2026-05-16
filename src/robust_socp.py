"""
Robust SOCP wrapper
"""
from .parameters import HEMSParameters
from .solver import run_optimization


def solve_robust_socp(params: HEMSParameters) -> dict:
    """Robust SOCP: uses params.rho > 0."""
    return run_optimization(params)