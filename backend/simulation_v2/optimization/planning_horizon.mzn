% Pattern 4 — Planning horizon
%
% Given a SimulationConfig with a weekly target per product, distribute
% the work across `n_days` so that the MAX daily utilization is
% minimized (smoothest workload). MiniZinc plans the week; the SimPy
% engine then executes each day with the resulting daily quotas.
%
% Why minimize max-load instead of total wallclock? Smoothing the load
% spreads risk evenly: a high-load day is more likely to underrun, and
% a stuck-at-100% day has no headroom to absorb breakdowns. A smooth
% plan stays robust under variability — exactly the bridge to SimPy's
% stochastic execution layer.
%
% Inputs
%   n_days                   : planning horizon
%   n_products               : number of products to produce
%   weekly_demand            : pieces required across the horizon
%   minutes_per_piece_x100   : bottleneck minutes per piece × 100 (integer)
%   daily_minutes            : capacity in MINUTES of a single day
%
% Decision variables
%   daily_pieces[d, p]       : pieces of product p produced on day d
%   max_load_x100            : max daily minutes used × 100 / daily_minutes
%
% Output
%   single-line JSON: {daily_pieces: [[..]..], max_load_pct: int,
%                      daily_minutes_used: [..], total_pieces_per_product: [..]}
%
% Stdlib note: same as the other patterns — no `include "globals.mzn"`
% (Render's MZ 2.7 has the inverse_fn.mzn type error). Sums are simple
% enough that no global predicates are required.

% --- inputs -------------------------------------------------------------

int: n_days;
int: n_products;
array[1..n_products] of int: weekly_demand;
array[1..n_products] of int: minutes_per_piece_x100;
int: daily_minutes;

% --- bounds -------------------------------------------------------------
%
% Per-cell upper bound: a single day can't produce more than the day's
% minutes / per-piece time can bear. Use the cheapest product as the
% generous upper bound so the solver has slack.

int: max_pcs_per_day_per_product = max([
  daily_minutes * 100 div minutes_per_piece_x100[p] | p in 1..n_products
]) + 1;

int: max_pcs_per_product = max([weekly_demand[p] | p in 1..n_products]) + 1;
int: max_pcs_cell = min(max_pcs_per_day_per_product, max_pcs_per_product);

% --- decision variables -------------------------------------------------

array[1..n_days, 1..n_products] of var 0..max_pcs_cell: daily_pieces;
array[1..n_days] of var 0..(daily_minutes * 100): daily_minutes_used_x100;

% Express max load as integer (×100). Bound is the daily capacity itself.
var 0..(daily_minutes * 100): max_minutes_used_x100;

% --- constraints --------------------------------------------------------
%
% 1) Weekly demand fulfilled per product. Strict equality would over-
%    constrain when the residual doesn't divide evenly across days; ≥ is
%    safer and the objective will avoid overshooting.
% 2) Per-day minutes = sum over products of pieces × minutes/piece.
% 3) Per-day capacity ceiling: daily_minutes_used ≤ daily_minutes (in ×100 units).
% 4) max_minutes_used is the per-day max we minimize.

constraint forall (p in 1..n_products) (
  sum (d in 1..n_days) (daily_pieces[d, p]) >= weekly_demand[p]
);

constraint forall (d in 1..n_days) (
  daily_minutes_used_x100[d] =
    sum (p in 1..n_products) (daily_pieces[d, p] * minutes_per_piece_x100[p])
);

constraint forall (d in 1..n_days) (
  daily_minutes_used_x100[d] <= daily_minutes * 100
);

constraint forall (d in 1..n_days) (
  max_minutes_used_x100 >= daily_minutes_used_x100[d]
);

solve minimize max_minutes_used_x100;

% --- output: single-line JSON -------------------------------------------
%
% `daily_pieces` is N_DAYS × N_PRODUCTS row-major. Output as a flat list
% of length n_days * n_products; the Python service reshapes.

int: total_minutes_capacity = daily_minutes;
var int: max_load_pct = max_minutes_used_x100 div daily_minutes;

output [
  "{",
  "\"daily_pieces_flat\": [",
    concat([ if d = 1 /\ p = 1 then show(daily_pieces[d, p])
             else "," ++ show(daily_pieces[d, p]) endif
             | d in 1..n_days, p in 1..n_products ]),
  "],",
  "\"daily_minutes_used\": [",
    concat([ if d = 1 then show(daily_minutes_used_x100[d] div 100)
             else "," ++ show(daily_minutes_used_x100[d] div 100) endif
             | d in 1..n_days ]),
  "],",
  "\"max_load_pct\": ", show(max_load_pct), ",",
  "\"daily_minutes_capacity\": ", show(total_minutes_capacity),
  "}\n"
];
