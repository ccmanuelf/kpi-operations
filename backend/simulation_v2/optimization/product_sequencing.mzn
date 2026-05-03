% Pattern 3 — Product sequencing
%
% Given N products with known per-product production durations and a
% pairwise setup-time matrix, find the production order that minimizes
% the total makespan (line wallclock time).
%
% Inputs
%   n_products            : number of products
%   production_time_min   : minutes the line spends producing each product's
%                           demand quota at the chosen allocation (caller
%                           pre-computes from SimulationConfig)
%   setup_time_min        : N×N matrix of changeover times in minutes
%                           (`setup_time_min[i,j]` = switch from i to j)
%
% Decision variables
%   order[k]              : product index produced at sequence position k
%   start_time_min[k]     : line wallclock start of position k (minutes)
%
% Objective
%   makespan_min = start_time[N] + production_time_min[order[N]]
%
% Output
%   Single-line JSON with the order, per-position starts, makespan,
%   and total setup time.
%
% (No `include "globals.mzn"` — Render MZ 2.7 stdlib conflict applies.
% `alldifferent` is decomposed manually as forall i<j: order[i] != order[j].)

% --- inputs --------------------------------------------------------------

int: n_products;
array[1..n_products] of int: production_time_min;
array[1..n_products, 1..n_products] of int: setup_time_min;

% --- bounds for the time variables --------------------------------------
%
% The total wallclock can't exceed sum(production) + max-setup × N (every
% transition uses the max setup). This is loose but tight enough for the
% solver. We also can't be negative.

int: max_setup = max([setup_time_min[i,j] | i,j in 1..n_products where i != j]);
int: total_production = sum([production_time_min[i] | i in 1..n_products]);
int: time_horizon = total_production + max_setup * n_products + 1;

% --- decision variables --------------------------------------------------

array[1..n_products] of var 1..n_products: order;
array[1..n_products] of var 0..time_horizon: start_time;

% --- alldifferent decomposition (no globals include) ---------------------

constraint forall (i in 1..n_products, j in 1..n_products where i < j) (
  order[i] != order[j]
);

% --- schedule construction ----------------------------------------------
%
% Position 1 starts at 0; subsequent positions add the previous product's
% production time + the changeover to the new one.

constraint start_time[1] = 0;

constraint forall (k in 2..n_products) (
  start_time[k] =
    start_time[k-1]
    + production_time_min[order[k-1]]
    + setup_time_min[order[k-1], order[k]]
);

% --- objective: minimize makespan ----------------------------------------

var int: makespan_min =
  start_time[n_products] + production_time_min[order[n_products]];

% Total setup time is start_time[N] minus production from positions 1..N-1.
var int: total_setup_min =
  start_time[n_products]
  - sum([production_time_min[order[k]] | k in 1..n_products - 1]);

solve minimize makespan_min;

% --- output: single-line JSON --------------------------------------------

output [
  "{",
  "\"order\": [",
    concat([ if i = 1 then show(order[i])
             else "," ++ show(order[i]) endif
             | i in 1..n_products ]),
  "],",
  "\"start_time_min\": [",
    concat([ if i = 1 then show(start_time[i])
             else "," ++ show(start_time[i]) endif
             | i in 1..n_products ]),
  "],",
  "\"makespan_min\": ", show(makespan_min), ",",
  "\"total_setup_min\": ", show(total_setup_min),
  "}\n"
];
