"""
Nominal LP wrapper — convenience function
"""
from .parameters import HEMSParameters
from .solver import run_optimization
import cvxpy as cp


def solve_nominal_lp(params: HEMSParameters, solver=cp.ECOS) -> dict:
    """Nominal LP: rho=0, standard grid availability."""
    old_rho = params.rho
    params.rho = 0.0
    result = run_optimization(params)
    params.rho = old_rho
    return result