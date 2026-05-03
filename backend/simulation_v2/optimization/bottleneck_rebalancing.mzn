% Pattern 2 — Bottleneck rebalancing
%
% Take an existing operator allocation (output of Block 7 from SimPy
% identifies the bottlenecks) and reshuffle operators to lift the
% bottleneck without (by default) growing the total head-count.
%
% Inputs
%   n_ops                  : number of operations
%   sam_min_x100           : SAM in minutes × 100 (integer encoding so
%                            we stay in pure integer arithmetic — see
%                            below for why)
%   grade_pct              : operator efficiency 0..100, per op
%   demand_pcs_per_day     : effective daily demand at this op (pcs/day)
%   current_operators      : current allocation per op
%   daily_planned_minutes  : minutes available per day
%   min_operators_per_op   : per-station floor (typically 1)
%   max_operators_per_op   : per-station ceiling
%   total_delta_max        : max total operators added (default 0 = strict swap)
%   total_delta_min        : max total operators removed (negative; default 0)
%
% Decision variables
%   delta[i]               : change in operators per op
%
% Why integer arithmetic (rather than var float)?
%   MZ 2.7 (the apt-shipped version on Render) can't determine bounds
%   on `floor(var float)` and rejects the model with "cannot determine
%   bounds". Encoding SAM as cents-style integer (×100) lets us compute
%   predicted pcs/day as a pure var int via integer division, which the
%   solver bounds exactly.
%
%   Float identity: pcs/day = operators * planned_min * grade / (sam_min * 100)
%   Integer form:  pcs/day = operators * planned_min * grade / sam_min_x100
%   (since sam_min_x100 = sam_min * 100, the two `× 100`s cancel)
%
% Objective
%   Maximize the minimum slack (predicted - demand) across stations —
%   the integer-friendly form of "lift the bottleneck."
%
% Output
%   Single-line JSON: { "delta":[...], "operators_after":[...],
%                       "predicted_pcs_per_day_per_op":[...],
%                       "slack_pcs":[...], "min_slack":N, "total_delta":N }
%
% (No `include "globals.mzn"` — Render MZ 2.7 chokes on `inverse_fn.mzn`.)

% --- inputs --------------------------------------------------------------

int: n_ops;

array[1..n_ops] of int: sam_min_x100;
array[1..n_ops] of int: grade_pct;
array[1..n_ops] of int: demand_pcs_per_day;
array[1..n_ops] of int: current_operators;

int: daily_planned_minutes;
int: min_operators_per_op;
int: max_operators_per_op;
int: total_delta_max;
int: total_delta_min;

% --- decision variable ---------------------------------------------------

array[1..n_ops] of var int: delta;

constraint forall (i in 1..n_ops) (
  delta[i] >= min_operators_per_op - current_operators[i]
  /\
  delta[i] <= max_operators_per_op - current_operators[i]
);

% --- total-delta budget --------------------------------------------------

var int: total_delta = sum(delta);

constraint total_delta <= total_delta_max;
constraint total_delta >= total_delta_min;

% --- predicted throughput per op (pcs/day, integer) ----------------------

array[1..n_ops] of var int: predicted_pcs_per_day =
  [ ((current_operators[i] + delta[i]) * daily_planned_minutes * grade_pct[i])
      div sam_min_x100[i]
    | i in 1..n_ops ];

% --- slack (predicted - demand) ------------------------------------------

array[1..n_ops] of var int: slack_pcs =
  [ predicted_pcs_per_day[i] - demand_pcs_per_day[i] | i in 1..n_ops ];

% --- objective: maximize min slack ---------------------------------------

var int: min_slack;
constraint forall (i in 1..n_ops) (slack_pcs[i] >= min_slack);
solve maximize min_slack;

% --- output: single-line JSON --------------------------------------------

output [
  "{",
  "\"delta\": [",
    concat([ if i = 1 then show(delta[i])
             else "," ++ show(delta[i]) endif
             | i in 1..n_ops ]),
  "],",
  "\"operators_after\": [",
    concat([ if i = 1 then show(current_operators[i] + delta[i])
             else "," ++ show(current_operators[i] + delta[i]) endif
             | i in 1..n_ops ]),
  "],",
  "\"predicted_pcs_per_day_per_op\": [",
    concat([ if i = 1 then show(predicted_pcs_per_day[i])
             else "," ++ show(predicted_pcs_per_day[i]) endif
             | i in 1..n_ops ]),
  "],",
  "\"slack_pcs\": [",
    concat([ if i = 1 then show(slack_pcs[i])
             else "," ++ show(slack_pcs[i]) endif
             | i in 1..n_ops ]),
  "],",
  "\"min_slack\": ", show(min_slack), ",",
  "\"total_delta\": ", show(total_delta),
  "}\n"
];
