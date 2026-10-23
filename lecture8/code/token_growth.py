"""L8: how input tokens and cost grow with the number of loop steps.

F (FIXED, tokens sent on every call), h (PER_STEP, tokens each earlier step adds)
and the output per call (OUT) are measured in L8 Run 1 (outputs/agent_run1_usage.json,
from the API's usage fields); the prices are quoted from the Gemini pricing page
(gemini_prices.py).
PLAN_OUT is chosen for this example: no plan-and-execute run was recorded.

Run: python3 token_growth.py
"""
import json
from pathlib import Path

from gemini_prices import PRICE_IN, PRICE_OUT

USAGE = json.loads((Path(__file__).parent / ".." / "outputs" / "agent_run1_usage.json").read_text())
FIXED = USAGE["first_input"]                                                          # measured, call 1
PER_STEP = round((USAGE["last_input"] - USAGE["first_input"]) / (USAGE["calls"] - 1))  # measured mean growth
OUT = round(USAGE["billed_output_total"] / USAGE["calls"])                            # measured mean
PLAN_OUT = 40    # output tokens per step of a written plan, chosen for this example


def react(n):
    """n calls; call k re-sends FIXED plus the k - 1 earlier steps."""
    inputs = [FIXED + (k - 1) * PER_STEP for k in range(1, n + 1)]
    return sum(inputs), n * OUT, inputs[-1]


def plan_execute(n, replans=1):
    """One call writes an n-step plan; each replan is one more call.

    A replan sends the current state read from ROS, not the history,
    so each call sends FIXED tokens.
    """
    calls = 1 + replans
    return calls * FIXED, calls * n * PLAN_OUT


def cost(tokens_in, tokens_out):
    return (tokens_in * PRICE_IN + tokens_out * PRICE_OUT) / 1e6


if __name__ == "__main__":
    print("ReAct, one call per step")
    print(f"{'steps':>5} {'last call':>9} {'input':>7} {'output':>6}"
          f" {'cost $':>7}")
    for n in (5, 10, 20, 40):
        t_in, t_out, last = react(n)
        print(f"{n:>5} {last:>9} {t_in:>7} {t_out:>6}"
              f" {cost(t_in, t_out):>7.4f}")
    print("Plan-and-execute, one plan and one replan")
    print(f"{'steps':>5} {'calls':>9} {'input':>7} {'output':>6}"
          f" {'cost $':>7}")
    for n in (5, 10, 20, 40):
        t_in, t_out = plan_execute(n)
        print(f"{n:>5} {2:>9} {t_in:>7} {t_out:>6}"
              f" {cost(t_in, t_out):>7.4f}")
